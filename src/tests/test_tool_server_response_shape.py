# test_tool_server_response_shape.py — asserts on the tool-server's actual
# HTTP response envelope (success, DomainError, and Pydantic-validation
# paths), which no other test in this suite covers.
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.db.scenarios.crm_scenario.tasks import template_interpreter as ti
from src.db.scenarios.crm_scenario.tasks import world_builder as wb
from src.tool_server import server


@pytest.fixture
def client(tmp_path):
    template = ti.load_template("decide_by_deal_value", "expert")
    wb.build_task(9001, template, tmp_path / "world.sqlite")
    server.app.state.db_path = str(tmp_path / "world.sqlite")
    with TestClient(server.app) as c:
        yield c


def test_success_path_shape(client):
    resp = client.post("/list_reps", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None
    assert isinstance(body["data"], list)


def test_domain_error_path_shape(client):
    resp = client.post("/get_contact", json={"id": 999999})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "not_found"
    assert body["error"]["technical_message"]


def test_validation_error_path_shape(client):
    resp = client.post("/find_deals", json={"name": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert "name" in body["error"]["technical_message"]


def test_duplicate_key_meta(client):
    reps = client.post("/list_reps", json={}).json()["data"]
    rep_id = reps[0]["id"]
    email = "dup-test@example.com"
    first = client.post("/create_contact",
                         json={"name": "First", "email": email, "rep_id": rep_id})
    assert first.json()["success"] is True
    existing_id = first.json()["data"]["id"]

    dup = client.post("/create_contact",
                       json={"name": "Second", "email": email, "rep_id": rep_id})
    body = dup.json()
    assert body["success"] is False
    assert body["error"]["code"] == "duplicate_key"
    assert body["meta"] == {"existing_id": existing_id}
