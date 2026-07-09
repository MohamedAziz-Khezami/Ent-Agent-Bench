from __future__ import annotations

import json
from pathlib import Path

from src.verifier.verify import verify

FROZEN = Path(__file__).parent.parent / "db/scenarios/crm_scenario/tasks/frozen"
# task_000: "mark it as done" on followup id=1 (a "changed" task)
TASK_CHANGED = json.loads((FROZEN / "easy/task_000.json").read_text())
# task_003: "schedule a follow-up for 2026-06-11" on deal id=2 (an "added" task)
TASK_ADDED = json.loads((FROZEN / "easy/task_003.json").read_text())

_GOOD_CHANGED_DIFF = {"followups": {"added": [], "removed": [],
                                     "changed": [(1, {"status": ("open", "done")})]}}


def test_changed_task_correct_diff_passes():
    result = verify(TASK_CHANGED, _GOOD_CHANGED_DIFF, {"followup_id": 1})
    assert result["passed"], result["reasons"]


def test_changed_task_wrong_answer_fails():
    result = verify(TASK_CHANGED, _GOOD_CHANGED_DIFF, {"followup_id": 999})
    assert not result["passed"]
    assert any("followup_id" in r for r in result["reasons"])


def test_answer_as_string_still_passes():
    # model text almost always parses to strings; ground_truth is an int
    result = verify(TASK_CHANGED, _GOOD_CHANGED_DIFF, {"followup_id": "1"})
    assert result["passed"], result["reasons"]


def test_missing_expected_change_fails():
    result = verify(TASK_CHANGED, {}, {"followup_id": 1})
    assert not result["passed"]
    assert any("expected row id=1 to change" in r for r in result["reasons"])


def test_forbidden_violation_fails():
    # model also (wrongly) changed a deal's stage — forbidden for this task
    diff = {"followups": _GOOD_CHANGED_DIFF["followups"],
            "deals": {"added": [], "removed": [],
                      "changed": [(4, {"stage": ("proposal", "negotiation")})]}}
    result = verify(TASK_CHANGED, diff, {"followup_id": 1})
    assert not result["passed"]
    assert any("forbidden 'changed' occurred on deals" in r for r in result["reasons"])


def test_side_effect_on_unrelated_table_caught():
    # the generator emits a COMPLETE forbidden contract — every table this
    # task never asked about (e.g. activities) is forbidden too
    assert "activities" in TASK_CHANGED["forbidden"]
    diff = {"followups": _GOOD_CHANGED_DIFF["followups"],
            "activities": {"added": [{"id": 5, "type": "note", "subject": "unrequested"}],
                            "removed": [], "changed": []}}
    result = verify(TASK_CHANGED, diff, {"followup_id": 1})
    assert not result["passed"]
    assert any("forbidden 'added' occurred on activities" in r for r in result["reasons"])


def test_incidental_extra_change_caught_by_cardinality():
    # the required change happened, but an unrelated second followup also
    # changed — 'forbidden' can't catch this ('changed' can't be forbidden
    # on the task's own table); only exact_changed_count cardinality does.
    diff = {"followups": {"added": [], "removed": [],
                           "changed": [(1, {"status": ("open", "done")}),
                                        (12, {"status": ("open", "done")})]}}
    result = verify(TASK_CHANGED, diff, {"followup_id": 1})
    assert not result["passed"]
    assert any("expected exactly 1 changed row" in r for r in result["reasons"])


def test_added_task_correct_diff_passes():
    diff = {"followups": {"added": [{"id": 91, "deal_id": 2, "due_date": "2026-06-11",
                                      "note": "confirm terms", "status": "open"}],
                           "removed": [], "changed": []}}
    result = verify(TASK_ADDED, diff, {"deal_id": 2})
    assert result["passed"], result["reasons"]


def test_added_task_duplicate_add_caught_by_exact_count():
    # model scheduled the followup twice
    diff = {"followups": {"added": [
                {"id": 91, "deal_id": 2, "due_date": "2026-06-11"},
                {"id": 92, "deal_id": 2, "due_date": "2026-06-11"},
            ], "removed": [], "changed": []}}
    result = verify(TASK_ADDED, diff, {"deal_id": 2})
    assert not result["passed"]
    assert any("expected exactly 1 added row" in r for r in result["reasons"])


def test_added_task_missing_add_fails():
    result = verify(TASK_ADDED, {}, {"deal_id": 2})
    assert not result["passed"]
    assert any("expected added row" in r for r in result["reasons"])
