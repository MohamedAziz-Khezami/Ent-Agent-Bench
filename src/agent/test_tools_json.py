# test_tools_json.py — tools.json is hand-maintained (kept in sync with
# tool_server/models.py by hand, same philosophy as ts_executor/tools.d.ts),
# so nothing enforces it stays correct except tests like these.
from __future__ import annotations

import json
import re
from pathlib import Path

from src.tool_server import models as M

TOOLS_JSON = Path(__file__).parent / "tools.json"
SERVER_PY = Path(__file__).parent.parent / "tool_server" / "server.py"

_MODEL_BY_TOOL_NAME = {
    "find_contacts": M.FindContactsArgs, "get_contact": M.GetByIdArgs,
    "find_leads": M.FindLeadsArgs, "get_lead": M.GetByIdArgs, "get_deal": M.GetByIdArgs,
    "find_deals": M.FindDealsArgs, "get_activities": M.GetActivitiesArgs,
    "get_followups": M.GetFollowupsArgs, "create_contact": M.CreateContactArgs,
    "update_contact": M.UpdateContactArgs, "create_lead": M.CreateLeadArgs,
    "update_lead": M.UpdateLeadArgs, "create_deal": M.CreateDealArgs,
    "update_deal": M.UpdateDealArgs, "log_activity": M.LogActivityArgs,
    "schedule_followup": M.ScheduleFollowupArgs,
}


def _load():
    return json.loads(TOOLS_JSON.read_text())


def test_tool_names_match_real_routes():
    real_names = set(re.findall(r'operation_id="(\w+)"', SERVER_PY.read_text()))
    json_names = {t["function"]["name"] for t in _load()["crm_tools"]}
    assert json_names == real_names


def test_required_and_optional_fields_match_pydantic_models():
    tools_by_name = {t["function"]["name"]: t["function"]["parameters"] for t in _load()["crm_tools"]}
    for name, pydantic_model in _MODEL_BY_TOOL_NAME.items():
        schema = pydantic_model.model_json_schema()
        assert set(schema.get("required", [])) == set(tools_by_name[name]["required"]), name
        assert set(schema["properties"].keys()) == set(tools_by_name[name]["properties"].keys()), name


def test_execute_tool_present():
    data = _load()
    assert data["execute"]["function"]["name"] == "execute"
    props = data["execute"]["function"]["parameters"]["properties"]
    assert set(props["lang"]["enum"]) == {"python", "js", "ts"}
