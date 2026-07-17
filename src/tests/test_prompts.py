# test_prompts.py — covers prompts.py's system-prompt/tools-param
# construction, previously untested.
from __future__ import annotations

from src.agent.prompts import build_system_prompt, build_tools_param

_TASK = {"answer_keys": ["deal_id", "stage"], "query": "irrelevant for these tests"}


def test_tool_call_prompt_disambiguates_final_answer_from_tools():
    for surface in ("python", "js", "ts"):
        prompt = build_system_prompt(surface, "tool_call", _TASK)
        assert "final_answer" in prompt
        assert "not a method on `tools`" in prompt
        assert "must never be written inside your executed code" in prompt


def test_json_mcp_prompt_unchanged_shape():
    prompt = build_system_prompt("json_mcp", "tool_call", _TASK)
    assert "call final_answer" in prompt
    assert "not a method on `tools`" not in prompt


def test_text_block_prompt_uses_marker_convention():
    prompt = build_system_prompt("python", "text_block", _TASK)
    assert "FINAL_ANSWER" in prompt
    assert "not a method on `tools`" not in prompt


def test_final_answer_is_separate_tool_entry():
    tools = build_tools_param("python", "tool_call", _TASK)
    names = [t["function"]["name"] for t in tools]
    assert "execute" in names
    assert "final_answer" in names
    assert names.count("final_answer") == 1
