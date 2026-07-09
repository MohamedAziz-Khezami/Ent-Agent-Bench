# verify.py — scenario-agnostic grading of one finished episode against its
# frozen task. Needs only a task dict (from tasks/frozen/*.json), a db diff
# (db.state_diff() output), and the model's parsed final-answer fields —
# no model, no Docker, no live episode required, so this is fully unit
# testable against hand-crafted fixtures.
from __future__ import annotations


def _coerce_eq(expected, actual) -> bool:
    """Type-tolerant equality: answer_fields come from parsed model text
    (often strings), ground_truth is often a real int."""
    if expected == actual:
        return True
    try:
        return int(expected) == int(actual)
    except (TypeError, ValueError):
        return str(expected).strip().lower() == str(actual).strip().lower()


def _check_answer(task: dict, answer_fields: dict, reasons: list[str]) -> bool:
    ok = True
    for key in task["answer_keys"]:
        expected = task["ground_truth"][key]
        actual = answer_fields.get(key)
        if actual is None:
            reasons.append(f"answer key '{key}' missing from final answer")
            ok = False
        elif not _coerce_eq(expected, actual):
            reasons.append(f"answer key '{key}' expected {expected!r}, got {actual!r}")
            ok = False
    return ok


def _check_expected_added(task: dict, diff: dict, reasons: list[str]) -> bool:
    ok = True
    for table, expected_rows in task["expected_added"].items():
        actual_added = diff.get(table, {}).get("added", [])
        for expected_row in expected_rows:
            match = any(
                all(row.get(k) == v for k, v in expected_row.items())
                for row in actual_added
            )
            if not match:
                reasons.append(f"expected added row {expected_row!r} not found in {table}")
                ok = False
    return ok


def _check_exact_added_count(task: dict, diff: dict, reasons: list[str]) -> bool:
    ok = True
    for table, expected_count in task["exact_added_count"].items():
        actual_count = len(diff.get(table, {}).get("added", []))
        if actual_count != expected_count:
            reasons.append(
                f"{table}: expected exactly {expected_count} added row(s), got {actual_count}")
            ok = False
    return ok


def _check_expected_changed(task: dict, diff: dict, reasons: list[str]) -> bool:
    ok = True
    for table, expected_specs in task["expected_changed"].items():
        actual_changed = dict(diff.get(table, {}).get("changed", []))
        for spec in expected_specs:
            delta = actual_changed.get(spec["id"])
            if delta is None:
                reasons.append(f"{table}: expected row id={spec['id']} to change, but it didn't")
                ok = False
                continue
            for col, expected_value in spec["fields"].items():
                if col not in delta or delta[col][1] != expected_value:
                    reasons.append(
                        f"{table} id={spec['id']}: expected '{col}' to become "
                        f"{expected_value!r}, got {delta.get(col, (None, None))[1]!r}")
                    ok = False
    return ok


def _check_exact_changed_count(task: dict, diff: dict, reasons: list[str]) -> bool:
    """Cardinality check for changes, mirroring exact_added_count for adds.
    The frozen task JSON has no explicit 'exact_changed_count' field, so this
    infers the expected count from len(expected_changed[table]), catching
    incidental changes to rows the task never asked to touch, which the
    'forbidden' list can't express (it would also block the required change)."""
    ok = True
    for table, expected_specs in task["expected_changed"].items():
        expected_count = len(expected_specs)
        actual_count = len(diff.get(table, {}).get("changed", []))
        if actual_count != expected_count:
            reasons.append(
                f"{table}: expected exactly {expected_count} changed row(s), got {actual_count}")
            ok = False
    return ok


def _check_forbidden(task: dict, diff: dict, reasons: list[str]) -> bool:
    ok = True
    for table, kinds in task["forbidden"].items():
        table_diff = diff.get(table, {})
        for kind in kinds:
            if table_diff.get(kind):
                reasons.append(f"forbidden '{kind}' occurred on {table}")
                ok = False
    return ok


def verify(task: dict, diff: dict, answer_fields: dict) -> dict:
    """Grade one finished episode. `diff` is db.state_diff() output; `answer_fields`
    is agent.final_answer.parse_final_answer(text)["fields"]. `checks` names each
    of the six checks so callers (e.g. the meter's fulfillment_score) can read a
    per-check breakdown instead of only the all-or-nothing `passed` bool."""
    reasons: list[str] = []
    checks = {
        "answer": _check_answer(task, answer_fields, reasons),
        "expected_added": _check_expected_added(task, diff, reasons),
        "exact_added_count": _check_exact_added_count(task, diff, reasons),
        "expected_changed": _check_expected_changed(task, diff, reasons),
        "exact_changed_count": _check_exact_changed_count(task, diff, reasons),
        "forbidden": _check_forbidden(task, diff, reasons),
    }
    return {"passed": all(checks.values()), "reasons": reasons, "checks": checks}
