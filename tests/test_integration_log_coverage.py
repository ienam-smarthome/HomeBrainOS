from __future__ import annotations

from automation_diagnostic_policy import is_integration_runtime_diagnostic
from synthesis_validator import guard_bounded_log_absence_claim, validate_synthesis


def _log_evidence(*, count: int = 100, limit: int = 100, successful: bool = True):
    return [{
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": successful,
        "arguments": {
            "tool": "hub_get_logs",
            "args": {"limit": limit, "since": "24h", "patterns": ["Octopus"]},
        },
        "details": {"logCount": count, "logs": [{} for _ in range(min(count, 4))]},
    }]


def test_integration_failures_use_investigative_reasoning():
    assert is_integration_runtime_diagnostic(
        "Investigate whether my Octopus Energy integration has experienced recent polling failures."
    )
    assert is_integration_runtime_diagnostic("Why is my telemetry polling failing?")
    assert not is_integration_runtime_diagnostic("Show me the current energy reading")


def test_saturated_octopus_logs_cannot_support_no_failure_claim():
    answer = (
        "Based on the logs from the last 24 hours, there is "
        "**no evidence of polling failures** for the integration.\n\n"
        "**Conclusion:** The integration is currently healthy and polling normally."
    )
    corrected, changed = guard_bounded_log_absence_claim(
        answer, _log_evidence()
    )
    assert changed
    assert "100-row log request for 24h reached its limit" in corrected
    assert "cannot rule out earlier failures" in corrected
    assert "integration has recent successful telemetry" in corrected
    assert "currently healthy and polling normally" not in corrected
    corrected2, issues = validate_synthesis(answer, _log_evidence())
    assert "bounded_log_absence_claim" in issues
    assert corrected2.startswith("**Log coverage limitation:**")


def test_unsaturated_and_failure_log_reads_do_not_create_false_guards():
    text = "There is no evidence of polling failures."
    for evidence in (_log_evidence(count=40), _log_evidence(successful=False), []):
        assert guard_bounded_log_absence_claim(text, evidence) == (text, False)


def test_qualified_bounded_log_claim_is_not_needlessly_rewritten():
    text = (
        "In the 100 returned rows, recent Octopus telemetry looks operational. "
        "Earlier failures remain unverified."
    )
    assert guard_bounded_log_absence_claim(text, _log_evidence()) == (text, False)
