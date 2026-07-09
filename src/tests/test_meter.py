from __future__ import annotations

from src.meter.meter import EpisodeMeter, _categorize_error


def _new_meter(**overrides):
    defaults = dict(episode_id="ep_1", model="gemma4", surface="python",
                     interaction_mode="tool_call", task_id="task_007",
                     difficulty="easy", world_seed=1007, n_functions_expected=2)
    defaults.update(overrides)
    return EpisodeMeter(**defaults)


def _passed_verify_result(checks=None):
    checks = checks if checks is not None else {"answer": True, "expected_added": True,
                                                 "exact_added_count": True, "expected_changed": True,
                                                 "exact_changed_count": True, "forbidden": True}
    return {"passed": all(checks.values()), "reasons": [], "checks": checks}


def test_categorize_error_ts_codes():
    assert _categorize_error({"code": "ts_syntax_error", "name": None}) == "syntax"
    assert _categorize_error({"code": "ts_type_error", "name": None}) == "type"


def test_categorize_error_domain_codes():
    assert _categorize_error({"code": "not_found", "name": "RuntimeError"}) == "tool"
    assert _categorize_error({"code": "duplicate_key", "name": "RuntimeError"}) == "tool"
    assert _categorize_error({"code": "malformed_filter", "name": "Error"}) == "tool"


def test_categorize_error_native_syntax_error():
    assert _categorize_error({"code": None, "name": "SyntaxError"}) == "syntax"


def test_categorize_error_transport_error():
    assert _categorize_error({"code": None, "name": "HTTPError"}) == "tool"


def test_categorize_error_falls_back_to_runtime():
    assert _categorize_error({"code": None, "name": "TypeError"}) == "runtime"
    assert _categorize_error({"code": None, "name": None}) == "runtime"


def test_model_turns_and_tokens_accumulate():
    m = _new_meter()
    m.record_model_turn(1.5, 100, 20)
    m.record_model_turn(2.5, 200, 40)
    row = m.finalize(_passed_verify_result())
    assert row["model_turns"] == 2
    assert row["model_latency_seconds"] == 4.0
    assert row["input_tokens"] == 300
    assert row["output_tokens"] == 60
    assert row["total_tokens"] == 360


def test_tool_calls_and_execution_latency_accumulate():
    m = _new_meter()
    m.record_exec_result({"ok": True, "error": None, "tool_calls": 2}, 0.4)
    m.record_exec_result({"ok": True, "error": None, "tool_calls": 1}, 0.2)
    row = m.finalize(_passed_verify_result())
    assert row["tool_calls_made"] == 3
    assert abs(row["execution_latency_seconds"] - 0.6) < 1e-9


def test_error_counters_categorized_correctly():
    m = _new_meter()
    m.record_exec_result({"ok": False, "tool_calls": 0,
                           "error": {"code": "ts_syntax_error", "name": None}}, 0.1)
    m.record_exec_result({"ok": False, "tool_calls": 1,
                           "error": {"code": "not_found", "name": "RuntimeError"}}, 0.1)
    m.record_exec_result({"ok": False, "tool_calls": 0,
                           "error": {"code": None, "name": "TypeError"}}, 0.1)
    row = m.finalize(_passed_verify_result())
    assert row["syntax_error_count"] == 1
    assert row["tool_error_count"] == 1
    assert row["runtime_error_count"] == 1
    assert row["type_error_count"] == 0


def test_parse_error_counted_separately():
    m = _new_meter()
    m.record_parse_error()
    m.record_parse_error()
    row = m.finalize(_passed_verify_result())
    assert row["parse_error_count"] == 2


def test_fulfillment_score_partial():
    checks = {"answer": True, "expected_added": True, "exact_added_count": False,
              "expected_changed": True, "exact_changed_count": True, "forbidden": True}
    m = _new_meter()
    row = m.finalize(_passed_verify_result(checks))
    assert row["fulfillment_score"] == 5 / 6
    assert row["passed"] == 0  # not all checks passed


def test_recovered_true_when_error_then_passed():
    m = _new_meter()
    m.record_exec_result({"ok": False, "tool_calls": 0,
                           "error": {"code": "not_found", "name": "RuntimeError"}}, 0.1)
    row = m.finalize(_passed_verify_result())  # all checks pass -> episode ultimately passed
    assert row["recovered"] == 1


def test_recovered_zero_when_no_error_at_all():
    m = _new_meter()
    row = m.finalize(_passed_verify_result())
    assert row["recovered"] == 0  # nothing to recover from


def test_recovered_zero_when_error_and_still_failed():
    checks = {"answer": False, "expected_added": True, "exact_added_count": True,
              "expected_changed": True, "exact_changed_count": True, "forbidden": True}
    m = _new_meter()
    m.record_exec_result({"ok": False, "tool_calls": 0,
                           "error": {"code": "not_found", "name": "RuntimeError"}}, 0.1)
    row = m.finalize(_passed_verify_result(checks))
    assert row["recovered"] == 0


def test_answer_correct_and_db_correct_split():
    checks = {"answer": False, "expected_added": True, "exact_added_count": True,
              "expected_changed": True, "exact_changed_count": True, "forbidden": True}
    m = _new_meter()
    row = m.finalize(_passed_verify_result(checks))
    assert row["answer_correct"] == 0
    assert row["db_correct"] == 1  # every non-answer check passed


def test_hit_turn_budget_and_infra_error_flags():
    m = _new_meter()
    m.mark_hit_turn_budget()
    m.mark_infra_error()
    row = m.finalize(_passed_verify_result())
    assert row["hit_turn_budget"] == 1
    assert row["infra_error"] == 1


def test_verifier_reasons_joined():
    result = {"passed": False, "reasons": ["reason one", "reason two"],
              "checks": {"answer": False, "expected_added": True, "exact_added_count": True,
                         "expected_changed": True, "exact_changed_count": True, "forbidden": True}}
    m = _new_meter()
    row = m.finalize(result)
    assert row["verifier_reasons"] == "reason one; reason two"


def test_identifying_fields_pass_through():
    m = _new_meter(model="claude-sonnet-5", surface="ts", interaction_mode="text_block",
                    task_id="task_042", difficulty="hard", world_seed=1042,
                    n_functions_expected=4)
    row = m.finalize(_passed_verify_result())
    assert row["model"] == "claude-sonnet-5"
    assert row["surface"] == "ts"
    assert row["interaction_mode"] == "text_block"
    assert row["task_id"] == "task_042"
    assert row["difficulty"] == "hard"
    assert row["world_seed"] == 1042
    assert row["n_functions_expected"] == 4
