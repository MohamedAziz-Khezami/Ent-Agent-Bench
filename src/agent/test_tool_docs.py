# test_tool_docs.py — tools_python.pyi, tools_js.js, and
# executors/ts_executor/tools.d.ts are each hand-maintained separately (no
# shared source, no conversion script), so nothing enforces they list the
# same 17 tools except tests like these.
from __future__ import annotations

import re
from pathlib import Path

AGENT_DIR = Path(__file__).parent
SERVER_PY = AGENT_DIR.parent / "tool_server" / "server.py"
TOOLS_DTS = AGENT_DIR.parent / "executors" / "ts_executor" / "tools.d.ts"

REAL_TOOL_NAMES = set(re.findall(r'operation_id="(\w+)"', SERVER_PY.read_text()))


def test_python_doc_lists_all_17_tools():
    src = (AGENT_DIR / "tools_python.pyi").read_text()
    names = set(re.findall(r"^tools\.(\w+)\(", src, re.MULTILINE))
    assert names == REAL_TOOL_NAMES


def test_js_doc_lists_all_17_tools():
    src = (AGENT_DIR / "tools_js.js").read_text()
    names = set(re.findall(r"^tools\.(\w+)\(", src, re.MULTILINE))
    assert names == REAL_TOOL_NAMES


def test_ts_doc_lists_all_17_tools():
    src = TOOLS_DTS.read_text()
    names = set(re.findall(r"^  (\w+)\(", src, re.MULTILINE))
    assert names == REAL_TOOL_NAMES
