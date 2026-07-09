# loop.py — the actual per-episode orchestration: builds the prompt, drives
# the model turn by turn, runs its code or tool calls, detects FINAL_ANSWER,
# and grades the result. Everything below it (Episode, EpisodeMeter,
# verify(), the model clients, prompts.py) was already independently built
# and tested — this is the piece that assembles them into one real episode.
#
# KNOWN GAP: AnthropicClient normalizes *responses* into ModelResponse, but
# the multi-turn message-building below (assistant tool_calls, role="tool"
# results) is the OpenAI wire format. Anthropic's Messages API uses a
# genuinely different shape for tool use (tool_use/tool_result content
# blocks) that AnthropicClient does not yet translate on the way in. This
# hasn't been fixed because it can't be tested here (no Anthropic API key in
# this environment) — flagged rather than silently assumed to work.
from __future__ import annotations

import json
import re
import time
import uuid

import requests

from src.agent import prompts
from src.agent.final_answer import is_final_answer, parse_final_answer
from src.agent.trajectory import Trajectory
from src.db import db as db_mod
from src.db.scenarios.crm_scenario import crm_db
from src.docker_runner.episode import Episode
from src.llm_clients.client import make_client
from src.meter.meter import EpisodeMeter
from src.verifier.verify import verify

#TODO: Move them to env and config file

TRAJECTORY_DIR = "results/trajectories"
# Uniform across every surface on purpose (not n_functions + slack): json_mcp
# needs ~1 turn per required tool call (no batching), code-mode can batch
# many calls into one execute() turn — a per-task budget derived from
# n_functions would silently give code-mode far more slack than json_mcp on
# the same task. A fixed budget keeps the comparison fair; if json_mcp runs
# out of room on a hard multi-action task, that's a real, comparable finding
# (hit_turn_budget), not a harness artifact.
TURN_BUDGET = 20
_EMPTY_VERIFY_CHECKS = {"answer": False, "expected_added": False, "exact_added_count": False,
                        "expected_changed": False, "exact_changed_count": False, "forbidden": False}


def _to_raw_tool_call(tc: dict) -> dict:
    """ModelResponse.tool_calls has `arguments` as a parsed dict (convenient
    for callers); sending a tool call back as conversation history requires
    the raw OpenAI wire format, where arguments is a JSON *string*."""
    return {"id": tc["id"], "type": "function",
            "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}}


def _model_visible(exec_result: dict) -> dict:
    """Strip meter-internal bookkeeping (tool_calls count) before showing an
    exec() result back to the model — it doesn't need to see that."""
    return {"ok": exec_result["ok"], "stdout": exec_result.get("stdout", ""),
            "value": exec_result["value"], "error": exec_result["error"]}


def _extract_code_fence(text: str, lang: str) -> str | None:
    match = re.search(rf"```{re.escape(lang)}\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None


def _call_crm_tool_directly(tool_server_url: str, name: str, args: dict):
    """json_mcp mode has no executor container — tool calls go straight to
    the tool-server's HTTP API. Returns (exec_result_shaped_dict, latency,
    value) — exec_result is shaped like an episode.exec() response so
    EpisodeMeter.record_exec_result() can be reused unchanged."""
    t0 = time.monotonic()
    try:
        resp = requests.post(f"{tool_server_url}/{name}", json=args, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as e:
        latency = time.monotonic() - t0
        return ({"ok": False, "tool_calls": 1,
                 "error": {"code": None, "name": type(e).__name__}}, latency, None)
    latency = time.monotonic() - t0
    if not result["ok"]:
        err = result["error"]
        return ({"ok": False, "tool_calls": 1,
                 "error": {"code": err["code"], "name": None}}, latency, None)
    return ({"ok": True, "tool_calls": 1, "error": None}, latency, result["result"])


def _infra_error_result(message: str) -> dict:
    return {"passed": False, "reasons": [f"infra error: {message}"], "checks": dict(_EMPTY_VERIFY_CHECKS)}


def _model_api_error_result(message: str) -> dict:
    return {"passed": False, "reasons": [f"model API error: {message}"], "checks": dict(_EMPTY_VERIFY_CHECKS)}


def _episode_error_result(message: str) -> dict:
    return {"passed": False, "reasons": [f"episode error: {message}"], "checks": dict(_EMPTY_VERIFY_CHECKS)}


def run_episode(model_config, surface: str, interaction_mode: str, task: dict, ready_timeout_s: float = 15.0) -> dict:
    world_seed = task["world_seed"]
    episode_id = uuid.uuid4().hex[:8]
    meter = EpisodeMeter(episode_id, model_config.name, surface, interaction_mode, task["task_id"], task["difficulty"], world_seed, task["n_functions"])
    traj = Trajectory(episode_id, model_config.name, surface, interaction_mode, task["task_id"], task["query"])
    client = make_client(model_config)
    turn_budget = TURN_BUDGET

    try:
        # world_db is the frozen world artifact attached by load_tasks();
        # Episode copies it, so the corpus file itself is never mutated
        episode = Episode(world_db=task["world_db"], surface=surface, ready_timeout_s=ready_timeout_s)
    except Exception as e:  # noqa: BLE001 — episode setup failing is an infra problem, not the model's fault
        meter.mark_infra_error()
        infra_result = _infra_error_result(str(e))
        traj.finish(None, infra_result)
        traj.save(TRAJECTORY_DIR)
        return meter.finalize(infra_result)

    try:
        baseline = db_mod.snapshot(episode.db_path)
        messages = prompts.build_initial_messages(surface, interaction_mode, task)
        tools_param = prompts.build_tools_param(surface, interaction_mode, task)
        answer_fields = None

        for _turn in range(turn_budget):
            traj.new_turn()
            t0 = time.monotonic()
            try:
                resp = client.complete(messages, tools=tools_param)  # Model call
            except Exception as e:  # noqa: BLE001 — providers raise many different
                # exception types for this (context-length exceeded, rate limits,
                # malformed requests, outages...); catching broadly and recording
                # a distinct outcome beats letting one bad call crash the entire
                # batch run (main.py has no try/except around run_episode()).
                meter.mark_model_api_error(str(e))
                error_result = _model_api_error_result(str(e))
                traj.finish(None, error_result)
                traj.save(TRAJECTORY_DIR)
                return meter.finalize(error_result)
            turn_latency = time.monotonic() - t0
            meter.record_model_turn(turn_latency, resp.input_tokens, resp.output_tokens)
            traj.record_model_turn(turn_latency, resp.input_tokens, resp.output_tokens, resp.content, resp.tool_calls)

            if interaction_mode == "text_block":
                messages.append({"role": "assistant", "content": resp.content}) # Messages get appended and saved so the model can reason over past turns
                if is_final_answer(resp.content):
                    parsed = parse_final_answer(resp.content)
                    if parsed["parse_error"]: #parse the final response error
                        meter.record_parse_error()
                    answer_fields = parsed["fields"]
                    break
                code = _extract_code_fence(resp.content, surface)
                if code is None:
                    # same alternation risk as the structured branch above:
                    # looping straight back to complete() with no new turn in
                    # between would eventually hand the server two trailing
                    # assistant messages if the model keeps just talking.
                    messages.append({"role": "user",
                                      "content": f"Write a ```{surface}``` code block to make progress, "
                                                  "or write FINAL_ANSWER if you already have the answer."})
                    continue
                t0 = time.monotonic()
                exec_result = episode.exec(code, surface)
                exec_latency = time.monotonic() - t0
                meter.record_exec_result(exec_result, exec_latency)
                traj.record_exec_result(code, surface, exec_latency, exec_result)
                messages.append({"role": "user",
                                  "content": f"Execution result: {json.dumps(_model_visible(exec_result))}"})
                continue

            # structured: tool_call (code-mode) or json_mcp
            if not resp.tool_calls:
                # A bare assistant reply with no tool call and nothing appended
                # after it would leave two assistant messages back-to-back the
                # next time this loop calls complete() with the same history —
                # most OpenAI-compatible servers (llama.cpp included) reject
                # that as invalid (no assistant/assistant repeats allowed).
                # Nudge with a user turn so alternation stays valid and the
                # model has a concrete next step instead of drifting.
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user",
                                  "content": "Call a tool to make progress, or call final_answer "
                                              "if you already have the answer."})
                continue

            messages.append({"role": "assistant", "content": resp.content or "",
                              "tool_calls": [_to_raw_tool_call(tc) for tc in resp.tool_calls]})

            finished = False
            for tc in resp.tool_calls:
                if tc["name"] == "final_answer":
                    answer_fields = tc["arguments"]
                    finished = True
                    continue

                if surface == "json_mcp":
                    exec_result, latency, value = _call_crm_tool_directly(episode.tool_server_url(), tc["name"], tc["arguments"])
                    meter.record_exec_result(exec_result, latency)
                    traj.record_tool_call_result(tc["name"], tc["arguments"], latency,
                                                  exec_result["ok"], value, exec_result["error"])
                    content = json.dumps({"ok": exec_result["ok"], "value": value,
                                           "error": exec_result["error"]})
                else:  # execute(code, lang)
                    t0 = time.monotonic()
                    exec_result = episode.exec(tc["arguments"]["code"],
                                                tc["arguments"].get("lang", surface))
                    exec_latency = time.monotonic() - t0
                    meter.record_exec_result(exec_result, exec_latency)
                    traj.record_exec_result(tc["arguments"]["code"], tc["arguments"].get("lang", surface), exec_latency, exec_result)
                    content = json.dumps(_model_visible(exec_result))

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": content})

            if finished:
                break
        else:
            meter.mark_hit_turn_budget()

        if answer_fields is None:
            answer_fields = {}

        diff = db_mod.state_diff(baseline, episode.db_path, crm_db.TABLES)
        verify_result = verify(task, diff, answer_fields)
        traj.finish(answer_fields, verify_result)
        traj.save(TRAJECTORY_DIR)
        return meter.finalize(verify_result)
    except Exception as e:  # noqa: BLE001 — last-resort net: an executor container
        # hanging, a tool-server network blip, a bug in verify()/state_diff — none
        # of these are the specific "model call failed" case above, but they must
        # not crash the batch run in main.py either. Only the earlier, more
        # specific handlers (model_api_error) get a chance first; whatever falls
        # through to here is genuinely unanticipated.
        meter.mark_episode_error(str(e))
        error_result = _episode_error_result(str(e))
        traj.finish(None, error_result)
        traj.save(TRAJECTORY_DIR)
        return meter.finalize(error_result)
    finally:
        episode.teardown()
