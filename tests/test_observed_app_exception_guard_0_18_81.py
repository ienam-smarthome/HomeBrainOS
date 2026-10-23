"""Regression: the live 0.18.80 answer denied exceptions present in its own logs."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observed_app_exception_guard import (
    guard_observed_app_exception_denials, observed_exception_app_ids,
)
from api_response_builder import build_agent_response


def receipt(app_id: int, *, success: bool = True, level: str = "ERROR", member: str = "Member A"):
    return {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": success, "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_get_logs", "args": {"since": "24h"}},
        "details": {"logs": [{
            "date": "2026-10-23 22:34:01",
            "level": level,
            "message": (
                f"dev|1000|{member}|com.hubitat.app.exception.LimitExceededException: "
                f"App {app_id} generates excessive hub load on line 420 "
                "(method updateMember)"
            ),
        }]},
    }


def observed():
    return [
        receipt(4061, member="Member A"),
        receipt(4061, member="Member B"),
        receipt(3977, member="Display"),
    ]


def test_real_failure_shape_repairs_scoped_negative_and_exclusive_causation():
    text = (
        "Causation for the exceptions is only proven for Device Status Notifier.\n\n"
        "| App Name | App ID | pctBusy |\n"
        "| --- | --- | --- |\n"
        "| Device Status Notifier | 3977 | 10% |\n"
        "| 00 Life360 Connect | 4061 | 7% |\n"
        "| Octopus Energy | 3933 | 5% |\n\n"
        "### Analysis: Correlation vs. Causation\n"
        "* **Proven Causation:** There is direct evidence that App 3977 caused the load.\n"
        "* **Correlation:** Life360 and Octopus Energy are also listed. "
        "However, the provided logs contain no LimitExceededException entries for these two apps.\n"
    )
    fixed, changed = guard_observed_app_exception_denials(text, observed())
    assert changed
    assert "### Analysis: Correlation vs. Causation" in fixed
    assert "no LimitExceededException entries" not in fixed
    assert "only proven" not in fixed
    assert "Proven Causation" not in fixed
    assert "App 3977, App 4061" in fixed
    assert "not a shared root cause" in fixed
    assert "Octopus Energy are also listed" in fixed


def test_specific_true_negative_for_other_app_remains_untouched():
    text = "The available sample has no LimitExceededException entries for App 3933."
    assert guard_observed_app_exception_denials(text, observed()) == (text, False)


def test_true_negative_scoped_to_unobserved_app_is_preserved():
    text = "A scoped App 3933 log read returned no LimitExceededException entries."
    assert guard_observed_app_exception_denials(text, observed()) == (text, False)


def test_exclusive_load_attribution_is_corrected_if_two_apps_have_errors():
    text = "The logs only attribute excessive hub load to App 3977."
    fixed, changed = guard_observed_app_exception_denials(text, observed())
    assert changed
    assert "App 4061" in fixed
    assert "only attribute" not in fixed


def test_explicit_false_negative_with_numeric_app_id_corrected():
    text = "There are no LimitExceededException entries for App 4061."
    fixed, changed = guard_observed_app_exception_denials(text, observed())
    assert changed and "App 4061" in fixed and "There are no" not in fixed


def test_positive_receipts_must_be_successful_structured_error_logs():
    for evidence in (
        [receipt(4061, success=False)],
        [receipt(4061, level="INFO")],
        [{"sub_tool": "hub_get_logs", "success": True,
          "summary": "LimitExceededException: App 4061 generates excessive hub load"}],
        [{"sub_tool": "hub_get_performance_stats", "success": True,
          "details": {"logs": receipt(4061)["details"]["logs"]}}],
    ):
        assert observed_exception_app_ids(evidence) == ()
        text = "There are no LimitExceededException entries for App 4061."
        assert guard_observed_app_exception_denials(text, evidence) == (text, False)


def test_positive_evidence_deduplicates_multiple_members():
    assert observed_exception_app_ids(observed()) == ("3977", "4061")


def test_explicit_uncertainty_about_proven_causation_is_preserved():
    text = "A shared root cause is not proven; causation is unverified."
    assert guard_observed_app_exception_denials(text, observed()) == (text, False)


def test_correct_answer_is_not_modified():
    text = (
        "App 4061 generated an explicit LimitExceededException in recent logs. "
        "Whether it and App 3977 share a root cause is unverified."
    )
    assert guard_observed_app_exception_denials(text, observed()) == (text, False)


def test_final_api_serialization_sets_transparent_repair_receipt():
    outcome = SimpleNamespace(
        message="The logs contain no LimitExceededException entries for App 4061.",
        route="unified-mcp-agent", request_class="live-read",
        evidence=observed(), metrics={"counters": {"model_rounds": 1}},
    )
    answer = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=100, version="0.18.81"
    )
    assert "App 4061" in answer["message"]
    assert "contain no" not in answer["message"]
    assert answer["evidence_validation"]["observed_app_exception_denial_corrected"] is True
    assert all(item.get("mutates") is False for item in answer["evidence"])


def test_app_exceptions_do_not_claim_earlier_logs_are_complete():
    text = "There were no LimitExceededException entries for App 4061."
    fixed, _ = guard_observed_app_exception_denials(text, observed())
    assert "Current-turn" in fixed
    assert "sampled" in fixed
    assert "24-hour coverage" not in fixed
