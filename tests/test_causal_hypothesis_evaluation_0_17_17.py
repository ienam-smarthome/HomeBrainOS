"""Regression contract for evidence-scoped OFF hypothesis evaluation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))
from causal_hypothesis_evaluation import evaluate_off_hypotheses


def _graph(excerpts=None, correlations=None, command=None):
    return {
        "scope": "single-observed-event",
        "transitionEvidence": {"off": {
            "observed": True, "directCommand": command,
            "state": {"producer": {"label": "Matter Bridge", "type": "device"}},
            "sensorCorrelations": correlations if correlations is not None else [
                {"sensor": "Room FP300", "value": "inactive", "signedDeltaMs": -69.0},
                {"sensor": "Soft Sensor", "value": "inactive", "signedDeltaMs": 949.0},
            ],
            "notifiedListenerContext": {"configuration": {
                "checked": excerpts is not None,
                "excerpts": excerpts or [],
            }},
            "externalAutomationIdentityVerified": False,
        }},
    }


def test_five_second_inactivity_timer_cannot_start_69ms_before_off():
    result = evaluate_off_hypotheses(_graph([
        "turn lights off after 5 seconds of no active motion; backup off check after 2 minutes"
    ]))
    assert result["status"] == "producer-unresolved"
    assert result["reporterIsNotInitiatingActor"] is True
    assert result["configuredInactivityDelaysMs"] == [5000.0]
    comparison = result["sensorTimerComparisons"]
    assert comparison[0]["elapsedBeforeOffMs"] == 69.0
    assert comparison[0]["assessment"] == "too-soon-for-new-timer"
    assert comparison[0]["newTimerFromThisEdgeCanExplainOff"] is False
    assert comparison[1]["assessment"] == "edge-after-off"
    assert result["historicalConfigVerified"] is False
    assert result["hypotheses"][0]["status"] == "not-proven"


def test_timing_compatible_does_not_prove_automation_executed():
    result = evaluate_off_hypotheses(_graph(
        ["inactive off after 5 seconds"],
        [{"sensor": "Room motion", "value": "inactive", "signedDeltaMs": -6000.0}],
    ))
    assert result["sensorTimerComparisons"][0]["assessment"] == "timing-compatible-not-execution-proof"
    assert result["hypotheses"][0]["status"] == "not-proven"


def test_no_config_never_invents_a_timer_or_excludes_actors():
    result = evaluate_off_hypotheses(_graph())
    assert result["configuredInactivityDelaysMs"] == []
    assert result["sensorTimerComparisons"] == []
    assert {h["status"] for h in result["hypotheses"]} == {"not-proven", "possible-unverified"}


def test_verified_direct_command_does_not_prove_upstream_trigger():
    result = evaluate_off_hypotheses(_graph(
        ["no active motion after 5 seconds"], command={"producer": {"id": "42", "type": "app"}}
    ))
    assert result["status"] == "direct-producer-recorded"
    assert result["hypotheses"][0]["status"] == "direct-command-recorded"
    assert result["historicalConfigVerified"] is False


def test_ambiguous_boundary_fails_closed():
    result = evaluate_off_hypotheses({"scope": "ambiguous-or-unobserved-event"})
    assert result == {"status": "not-applicable", "hypotheses": []}


def test_delays_are_unit_aware_and_skip_non_inactivity_descriptions():
    result = evaluate_off_hypotheses(_graph([
        "When inactive, switch off after 250 milliseconds",
        "when motion inactive, delay 2 minutes",
        "set brightness after 4 seconds",
    ]))
    assert result["configuredInactivityDelaysMs"] == [250.0, 120000.0]
