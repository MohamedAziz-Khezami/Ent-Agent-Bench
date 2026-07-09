from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db.scenarios.crm_scenario.tasks import template_interpreter as ti
from src.db.scenarios.crm_scenario.tasks import world_builder as wb


def _logical_dump(path: Path) -> dict:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        out = {}
        for table in ("reps", "contacts", "leads", "deals", "activities", "followups"):
            out[table] = sorted(tuple(dict(r).items())
                                 for r in conn.execute(f"SELECT * FROM {table}"))
        return out
    finally:
        conn.close()


def test_build_is_deterministic(tmp_path):
    template = ti.load_template("decide_by_deal_value", "expert")
    t1 = wb.build_task(7001, template, tmp_path / "a.sqlite")
    t2 = wb.build_task(7001, template, tmp_path / "b.sqlite")
    assert t1 == t2
    assert _logical_dump(tmp_path / "a.sqlite") == _logical_dump(tmp_path / "b.sqlite")


def test_different_seeds_differ(tmp_path):
    template = ti.load_template("decide_by_deal_value", "expert")
    t1 = wb.build_task(7001, template, tmp_path / "a.sqlite")
    t2 = wb.build_task(7002, template, tmp_path / "b.sqlite")
    assert t1 != t2


def test_kernel_ids_interleaved_not_clustered_at_max(tmp_path):
    """Across many seeds, the anchor deal's id should land all over the
    1..N range — the classic naive-injection fingerprint is ids at the top."""
    template = ti.load_template("act_on_a_deal", "easy")
    positions = []
    for seed in range(8000, 8030):
        task = wb.build_task(seed, template, tmp_path / f"{seed}.sqlite")
        conn = sqlite3.connect(tmp_path / f"{seed}.sqlite")
        n = conn.execute("SELECT MAX(id) FROM deals").fetchone()[0]
        conn.close()
        positions.append(task["ground_truth"]["deal_id"] / n)
    assert min(positions) < 0.35, f"anchor never lands in the low id range: {positions}"
    assert max(positions) > 0.65, f"anchor never lands in the high id range: {positions}"
    assert sum(1 for p in positions if p > 0.95) < len(positions) / 3


def test_answer_set_closed_for_bulk(tmp_path):
    """Reference partitioning: no background deal may match the bulk group
    predicate — the world must contain EXACTLY n_updated matching deals."""
    template = ti.load_template("update_every_matching_deal", "expert")
    for seed in range(8100, 8110):
        task = wb.build_task(seed, template, tmp_path / f"{seed}.sqlite")
        rep_name = task["query"].split("owned by ")[1].split(" to the")[0]
        conn = sqlite3.connect(tmp_path / f"{seed}.sqlite")
        n = conn.execute(
            "SELECT COUNT(*) FROM deals d JOIN reps r ON d.rep_id=r.id "
            "WHERE r.name=? AND d.stage='prospecting'", (rep_name,)).fetchone()[0]
        conn.close()
        assert n == task["ground_truth"]["n_updated"], f"seed {seed}: contaminated group"


def test_anchor_description_unique_with_distractors(tmp_path):
    """Identity exclusion + closed-stage distractors: the entity description
    must match exactly 1 row even with 2 lookalikes at the same company
    (the hard-tier copy carries those distractors)."""
    template = ti.load_template("act_on_a_deal", "hard")
    for seed in range(8200, 8210):
        task = wb.build_task(seed, template, tmp_path / f"{seed}.sqlite")
        conn = sqlite3.connect(tmp_path / f"{seed}.sqlite")
        conn.row_factory = sqlite3.Row
        anchor = conn.execute(
            "SELECT d.stage, c.company FROM deals d JOIN leads l ON d.lead_id=l.id "
            "JOIN contacts c ON l.contact_id=c.id WHERE d.id=?",
            (task["ground_truth"]["deal_id"],)).fetchone()
        rows = conn.execute(
            "SELECT d.id FROM deals d JOIN leads l ON d.lead_id=l.id "
            "JOIN contacts c ON l.contact_id=c.id WHERE c.company=? AND d.stage=?",
            (anchor["company"], anchor["stage"])).fetchall()
        same_company = conn.execute(
            "SELECT COUNT(*) FROM deals d JOIN leads l ON d.lead_id=l.id "
            "JOIN contacts c ON l.contact_id=c.id WHERE c.company=?",
            (anchor["company"],)).fetchone()[0]
        conn.close()
        assert len(rows) == 1 and rows[0][0] == task["ground_truth"]["deal_id"]
        assert same_company >= 3, "hard tier should plant 2 distractor deals at the company"


def test_conditional_branch_matches_world(tmp_path):
    template = ti.load_template("decide_by_deal_value", "expert")
    for seed in range(8300, 8315):
        task = wb.build_task(seed, template, tmp_path / f"{seed}.sqlite")
        raw = task["query"].split("over $")[1].split(" ")[0].rstrip(",.")
        threshold = float(raw.replace(",", ""))
        conn = sqlite3.connect(tmp_path / f"{seed}.sqlite")
        value = conn.execute("SELECT value FROM deals WHERE id=?",
                              (task["ground_truth"]["deal_id"],)).fetchone()[0]
        conn.close()
        went_high = bool(task["expected_changed"])
        assert (value > threshold) == went_high
        # constructed margin: never a near-tie
        assert abs(value - threshold) >= 0.2 * threshold


def test_no_op_impossible_for_changed_effects(tmp_path):
    """Every expected_changed field must actually differ from the world's
    current value (the old generator rejected worlds for this; now it must
    hold by construction)."""
    for name, tier in [("act_on_a_deal", "easy"), ("act_on_a_lead", "medium"),
                        ("triage_each_followup", "expert")]:
        template = ti.load_template(name, tier)
        for seed in range(8400, 8410):
            task = wb.build_task(seed, template, tmp_path / f"{name}{seed}.sqlite")
            conn = sqlite3.connect(tmp_path / f"{name}{seed}.sqlite")
            conn.row_factory = sqlite3.Row
            for table, specs in task["expected_changed"].items():
                for spec in specs:
                    current = dict(conn.execute(
                        f"SELECT * FROM {table} WHERE id=?", (spec["id"],)).fetchone())
                    for col, target in spec["fields"].items():
                        assert current[col] != target, \
                            f"{name} seed {seed}: no-op change {table}.{col}={target}"
            conn.close()
