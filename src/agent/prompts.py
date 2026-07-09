# prompts.py — builds the system prompt and `tools=` parameter for one
# episode, branching on (surface, interaction_mode). Pure functions, no
# model/Docker dependency, so fully testable on their own.
from __future__ import annotations

import json
from pathlib import Path

from src.db.scenarios.crm_scenario.crm_db import SIM_TODAY

_TOOLS_JSON = json.loads((Path(__file__).parent / "tools.json").read_text())

# Each code-mode surface gets its OWN hand-written tool reference, in that
# language's own native style (real Python kwargs signatures, real JSDoc,
# real TS types) — not one shared document. Reusing a single TS-shaped
# document across all three previously misled a real model (gemma4) into
# writing tools.find_deals(args={...}) for Python, which
# tool_server/models.py's extra="forbid" would reject outright.
_TOOLS_DOC_BY_SURFACE = {
    "python": (Path(__file__).parent / "tools_python.pyi").read_text(),
    "js": (Path(__file__).parent / "tools_js.js").read_text(),
    "ts": (Path(__file__).parent.parent / "executors" / "ts_executor" / "tools.d.ts").read_text(),
}


def build_final_answer_tool(task: dict) -> dict:
    """final_answer's schema depends on the task's own answer_keys, so unlike
    the 17 CRM tools + execute (fixed, hand-written in tools.json), this is
    built fresh per task."""
    properties = {key: {"type": "string"} for key in task["answer_keys"]}
    return {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": "Submit your final answer for this task.",
            "parameters": {"type": "object", "properties": properties,
                            "required": task["answer_keys"]},
        },
    }


def build_tools_param(surface: str, interaction_mode: str, task: dict) -> list[dict] | None:
    """Returns the `tools=` argument for client.complete(), or None for
    text_block mode (which uses no structured tools at all)."""
    if interaction_mode == "text_block":
        return None
    final_answer = build_final_answer_tool(task)
    if surface == "json_mcp":
        return _TOOLS_JSON["crm_tools"] + [final_answer]
    return [_TOOLS_JSON["execute"], final_answer]


def build_system_prompt(surface: str, interaction_mode: str, task: dict) -> str:
    answer_keys = ", ".join(task["answer_keys"])

    today_line = f"Today's date is {SIM_TODAY}."

    if surface == "json_mcp":
        return (
            "You are solving a CRM task. "
            f"{today_line} "
            "Use the provided tools to look up and "
            "modify data as needed. When you have the answer, call final_answer "
            f"with these fields: {answer_keys}."
        )

    tools_doc = _TOOLS_DOC_BY_SURFACE[surface]

    if interaction_mode == "tool_call":
        return (
            f"You solve CRM tasks by writing {surface} code. {today_line} "
            f"Call the `execute` "
            f"tool with your code and lang='{surface}' to run it — always use "
            f"lang='{surface}', never any other value. Inside your code, a `tools` "
            "object is available with one method per CRM tool. Its available "
            f"methods:\n\n{tools_doc}\n\n"
            "When you have the answer, call final_answer with these fields: "
            f"{answer_keys}."
        )

    # text_block
    return (
        f"You solve CRM tasks by writing {surface} code in a fenced "
        f"```{surface} block. {today_line} Inside your code, a `tools` object is available "
        f"with one method per CRM tool. Its available methods:\n\n{tools_doc}\n\n"
        "When you have solved the task, write the marker FINAL_ANSWER followed "
        "by a ```json code block containing an object with these exact keys: "
        f"{answer_keys}."
    )


def build_initial_messages(surface: str, interaction_mode: str, task: dict) -> list[dict]:
    return [
        {"role": "system", "content": build_system_prompt(surface, interaction_mode, task)},
        {"role": "user", "content": task["query"]},
    ]
