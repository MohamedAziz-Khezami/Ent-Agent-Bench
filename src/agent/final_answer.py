# final_answer.py — detects and parses a model's FINAL_ANSWER turn.
# Surface-agnostic: the same convention (a "FINAL_ANSWER" marker followed by a
# JSON object) is used whether the episode ran Python, JS, or JSON/MCP mode —
# this module only looks at the model's raw text output for one turn.
#
# A malformed FINAL_ANSWER is a legitimate model failure to record (the
# verifier will fail the task for it), never a harness crash — every function
# here returns a structured result instead of raising.
from __future__ import annotations

import json
import re

FINAL_ANSWER_MARKER = "FINAL_ANSWER"

# Matches a fenced code block, optionally tagged with a language
# (```json ... ``` or plain ``` ... ```).
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def is_final_answer(text: str) -> bool:
    """Quick check the agent loop uses to decide whether this turn should be
    executed as code (or dispatched as a tool call) or treated as the
    episode's last turn."""
    return FINAL_ANSWER_MARKER in text


def parse_final_answer(text: str) -> dict:
    """Parse a FINAL_ANSWER turn.

    Returns {"fields": dict, "raw": str, "parse_error": str | None}.
    `fields` is {} whenever parse_error is set.
    """
    if FINAL_ANSWER_MARKER not in text:
        return {"fields": {}, "raw": text, "parse_error": "no FINAL_ANSWER marker found"}

    after_marker = text.split(FINAL_ANSWER_MARKER, 1)[1]

    fence_match = _FENCE_RE.search(after_marker)
    blob = fence_match.group(1).strip() if fence_match else after_marker.strip()

    if not blob:
        return {"fields": {}, "raw": text, "parse_error": "FINAL_ANSWER marker found but no content followed"}

    try:
        fields = json.loads(blob)
    except json.JSONDecodeError as e:
        return {"fields": {}, "raw": text, "parse_error": f"invalid JSON after FINAL_ANSWER: {e}"}

    if not isinstance(fields, dict):
        return {"fields": {}, "raw": text, "parse_error": f"FINAL_ANSWER JSON must be an object, got "f"{type(fields).__name__}"}

    return {"fields": fields, "raw": text, "parse_error": None}
