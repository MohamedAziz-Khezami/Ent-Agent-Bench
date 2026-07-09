from __future__ import annotations

import random

import pytest

from src.db.scenarios.crm_scenario.tasks import template_interpreter as ti


def _rng(seed=1):
    return random.Random(seed)


# ── expressions ──────────────────────────────────────────────────────────

def test_expr_arithmetic_and_names():
    assert ti.eval_expr("threshold * 1.3", {"threshold": 50000}) == 65000.0
    assert ti.eval_expr("1 + n_actions", {"n_actions": 2}) == 3


def test_expr_comparison():
    assert ti.eval_expr("branch == 'high'", {"branch": "high"}) is True
    assert ti.eval_expr("branch == 'high'", {"branch": "low"}) is False


def test_expr_item_attribute_access():
    assert ti.eval_expr("item.due_date", {"item": {"due_date": "2026-05-20"}}) == "2026-05-20"


def test_expr_date_offset_function():
    assert ti.eval_expr("date_offset(item.due_date, 3)",
                         {"item": {"due_date": "2026-05-20"}}) == "2026-05-23"


def test_expr_rejects_disallowed_nodes():
    with pytest.raises(ValueError):
        ti.eval_expr("__import__('os')", {})
    with pytest.raises(ValueError):
        ti.eval_expr("unknown_name", {})


# ── placeholders ─────────────────────────────────────────────────────────

def test_fill_single_placeholder_is_typed():
    assert ti.fill("{value}", {"value": 71400.0}) == 71400.0   # float, not "71400.0"


def test_fill_format_spec():
    assert ti.fill("over ${threshold:,}", {"threshold": 50000}) == "over $50,000"


def test_fill_ref_passthrough():
    assert ti.fill("@the_deal", {"the_deal": 99}) == "@the_deal"   # builder's job, not fill's


# ── draw specs ───────────────────────────────────────────────────────────

def test_choice_and_randint_deterministic():
    assert ti.resolve_spec({"choice": [1, 2, 3]}, _rng(), {}) == ti.resolve_spec({"choice": [1, 2, 3]}, _rng(), {})
    v = ti.resolve_spec({"randint": [60, 95]}, _rng(), {})
    assert 60 <= v <= 95


def test_draw_pool():
    name = ti.resolve_spec({"draw": "person_name"}, _rng(), {})
    first, last = name.split(" ")
    from src.db.scenarios.crm_scenario import pools
    assert first in pools.FIRST and last in pools.LAST


def test_value_between_with_expressions_stays_on_grid():
    v = ti.resolve_spec({"value_between": ["threshold * 1.3", 120000]}, _rng(), {"threshold": 50000})
    assert v >= 65000 and v % 500 == 0


def test_if_spec_branches():
    spec = {"if": [{"when": "branch == 'high'", "then": 1}, {"when": "branch == 'low'", "then": 2}]}
    assert ti.resolve_spec(spec, _rng(), {"branch": "high"}) == 1
    assert ti.resolve_spec(spec, _rng(), {"branch": "low"}) == 2


def test_sim_date_offset():
    from src.db.scenarios.crm_scenario.crm_db import sim_date
    assert ti.resolve_spec({"sim_date_offset": 3}, _rng(), {}) == sim_date(3)
    v = ti.resolve_spec({"sim_date_offset": {"randint": [-20, -8]}}, _rng(), {})
    assert v < sim_date(-7)


def test_sample_from_menu():
    menus = {"deal_actions": [{"phrase": "a"}, {"phrase": "b"}, {"phrase": "c"}]}
    chosen = ti.resolve_spec({"sample": "deal_actions", "k": "{n_actions}"},
                              _rng(), {"n_actions": 2}, menus)
    assert len(chosen) == 2


# ── params ordering ──────────────────────────────────────────────────────

def test_draw_params_later_entries_see_earlier():
    template = {"params": {
        "branch": {"choice": ["high"]},
        "threshold": {"choice": [50000]},
        "value": {"if": [{"when": "branch == 'high'",
                            "then": {"value_between": ["threshold * 1.3", 120000]}}]},
    }}
    params = ti.draw_params(template, _rng())
    assert params["value"] >= 65000


def test_template_args_visible_to_params():
    template = {"params": {"k": {"expr": "n_actions + 1"}}}
    assert ti.draw_params(template, _rng(), {"n_actions": 2})["k"] == 3


# ── kernel expansion ─────────────────────────────────────────────────────

def test_kernel_repeat_groups_and_per_item_draws():
    template = {"kernel": [
        {"ref": "the_deals", "table": "deals", "repeat": "{n}",
         "row": {"stage": "prospecting", "value": {"value_between": [5000, 120000]}}},
    ]}
    rows = ti.expand_kernel(template, {"n": 3}, _rng())
    assert len(rows) == 3
    assert [r["index"] for r in rows] == [0, 1, 2]
    assert len({r["cols"]["value"] for r in rows}) > 1  # drawn per item, not shared


def test_kernel_refs_pass_through():
    template = {"kernel": [
        {"ref": "the_lead", "table": "leads", "row": {"contact_id": "@the_contact"}},
    ]}
    rows = ti.expand_kernel(template, {}, _rng())
    assert rows[0]["cols"]["contact_id"] == "@the_contact"


def test_distractors_included_only_when_asked():
    template = {"kernel": [{"ref": "a", "table": "deals", "row": {}}],
                "distractors": [{"ref": "d", "table": "deals", "row": {"stage": "won"}}]}
    assert len(ti.expand_kernel(template, {}, _rng())) == 1
    assert len(ti.expand_kernel(template, {}, _rng(), include_distractors=True)) == 2


# ── effects expansion ────────────────────────────────────────────────────

def _resolver(ids: dict, rows: dict | None = None):
    def resolve(ref, field=None):
        if field == "__rows__":
            return rows[ref]
        if field:
            return rows[ref][field]
        return ids[ref]
    return resolve


def test_effects_if_branching():
    template = {"effects": {"if": [
        {"when": "branch == 'high'",
         "then": {"changed": [{"table": "deals", "id": "@the_deal",
                                 "fields": {"stage": "negotiation"}}]}},
        {"when": "branch == 'low'",
         "then": {"added": [{"table": "activities",
                               "row": {"deal_id": "@the_deal", "type": "note", "subject": "{note}"}}]}},
    ]}}
    high = ti.expand_effects(template, {"branch": "high", "note": "x"}, _resolver({"the_deal": 17}))
    assert high["expected_changed"] == {"deals": [{"id": 17, "fields": {"stage": "negotiation"}}]}
    assert high["expected_added"] == {}
    low = ti.expand_effects(template, {"branch": "low", "note": "needs review"}, _resolver({"the_deal": 17}))
    assert low["expected_added"] == {"activities": [{"deal_id": 17, "type": "note", "subject": "needs review"}]}
    assert low["exact_added_count"] == {"activities": 1}


def test_effects_for_each_with_item_expr():
    template = {"effects": [
        {"for_each": "lows",
         "changed": [{"table": "followups", "id": "@item",
                        "fields": {"due_date": {"expr": "date_offset(item.due_date, 3)"}}}]},
    ]}
    rows = {"lows": [{"id": 8, "due_date": "2026-05-28"}, {"id": 15, "due_date": "2026-06-01"}]}
    fx = ti.expand_effects(template, {}, _resolver({}, rows))
    assert fx["expected_changed"]["followups"] == [
        {"id": 8, "fields": {"due_date": "2026-05-31"}},
        {"id": 15, "fields": {"due_date": "2026-06-04"}},
    ]


def test_effects_from_chosen_actions():
    chosen = [
        {"phrase": "log a {atype} about '{subject}' on it", "kind": "added", "table": "activities",
         "row": {"deal_id": "@anchor", "type": "{atype}", "subject": "{subject}"}},
        {"phrase": "move it to the {new_stage} stage", "kind": "changed", "table": "deals",
         "row": {"id": "@anchor", "fields": {"stage": "{new_stage}"}}},
    ]
    template = {"effects": {"from_chosen_actions": {"anchor": "@the_deal"}}}
    params = {"chosen": chosen, "atype": "call", "subject": "pricing", "new_stage": "closing"}
    fx = ti.expand_effects(template, params, _resolver({"the_deal": 30}))
    assert fx["expected_added"] == {"activities": [{"deal_id": 30, "type": "call", "subject": "pricing"}]}
    assert fx["expected_changed"] == {"deals": [{"id": 30, "fields": {"stage": "closing"}}]}


# ── answer / query helpers ───────────────────────────────────────────────

def test_build_answer_ref_and_param():
    template = {"answer": {"deal_id": "@the_deal", "n_updated": "{n}"}}
    out = ti.build_answer(template, {"n": 3}, _resolver({"the_deal": 17}))
    assert out == {"deal_id": 17, "n_updated": 3}


def test_chosen_phrases_joined():
    params = {"chosen": [{"phrase": "log a {atype}"}, {"phrase": "move it"}], "atype": "call"}
    assert ti.chosen_phrases_joined(params) == "log a call, then move it"


def test_guards_filled():
    template = {"guards": [{"table": "deals", "where": {"stage": "{stage}"}}]}
    assert ti.expand_guards(template, {"stage": "proposal"}) == [
        {"table": "deals", "where": {"stage": "proposal"}}]


def test_n_functions_expr():
    assert ti.n_functions({"n_functions": "1 + n_deals"}, {"n_deals": 3}) == 4
    assert ti.n_functions({"n_functions": 2}, {}) == 2
