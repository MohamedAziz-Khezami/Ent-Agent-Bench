# trajectory.py — full step-by-step replay log for one episode, complementing
# EpisodeMeter's aggregate numbers with the actual conversation: every model
# turn (content, tool calls, tokens, latency) and every tool/exec result, in
# order. Same usage pattern as EpisodeMeter — instantiate per episode, call
# record_*() as things happen, save() once at the end.
from __future__ import annotations

import json
from pathlib import Path


class Trajectory:
    def __init__(self, episode_id: str, model: str, surface: str, interaction_mode: str,
                 task_id: str, task_query: str):
        self.episode_id = episode_id
        self.model = model
        self.surface = surface
        self.interaction_mode = interaction_mode
        self.task_id = task_id
        self.task_query = task_query
        self.steps: list[dict] = []
        self._turn = 0
        self.final_answer_fields: dict | None = None
        self.verify_result: dict | None = None

    def new_turn(self) -> None:
        self._turn += 1

    def record_model_turn(self, latency_seconds: float, input_tokens: int, output_tokens: int,
                           content: str, tool_calls: list[dict]) -> None:
        self.steps.append({
            "turn": self._turn, "type": "model_response",
            "latency_seconds": latency_seconds,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "content": content, "tool_calls": tool_calls,
        })

    def record_exec_result(self, code: str, lang: str, latency_seconds: float, exec_result: dict) -> None:
        self.steps.append({
            "turn": self._turn, "type": "exec_result",
            "code": code, "lang": lang, "latency_seconds": latency_seconds,
            "ok": exec_result["ok"], "stdout": exec_result.get("stdout"),
            "value": exec_result.get("value"), "error": exec_result.get("error"),
        })

    def record_tool_call_result(self, name: str, arguments: dict, latency_seconds: float,
                                 ok: bool, value, error) -> None:
        self.steps.append({
            "turn": self._turn, "type": "tool_result",
            "name": name, "arguments": arguments, "latency_seconds": latency_seconds,
            "ok": ok, "value": value, "error": error,
        })

    def finish(self, final_answer_fields: dict, verify_result: dict) -> None:
        self.final_answer_fields = final_answer_fields
        self.verify_result = verify_result

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id, "model": self.model, "surface": self.surface,
            "interaction_mode": self.interaction_mode, "task_id": self.task_id,
            "task_query": self.task_query, "steps": self.steps,
            "final_answer_fields": self.final_answer_fields, "verify_result": self.verify_result,
        }

    def save(self, directory: str | Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.episode_id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return path
