"""Cross-domain status-vs-causal completion gate, frozen first-answer regression.

A model-proposed hypothesis packet is not a historical command obligation.
The output is never scored as factually verified by this test: that still
requires independent typed device-attribute evidence.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import build_observed_agent_outcome
from shared_investigation_completion import apply_shared_investigation_completion
from investigation_intelligence import plan_investigation
from investigation_policy import is_causal_investigation


def _read():
    return {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "authoritative_device_event_history",
        "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "1234", "limit": 3, "hoursBack": 24},
        },
        "details": {
            "historySourceIntegrityVerified": False,
            "observedEventsTruncated": False,
            "observedEvents": [
                {"name": "lastSeen", "value": "2026-11-02 11:02:38",
                 "date": "2026-11-02T11:02:38+00:00"},
                {"name": "dataAgeSeconds", "value": "0",
                 "date": "2026-11-02T11:02:38+00:00"},
            ],
        },
    }


def _observation(coverage):
    native = AgentOutcome(
        message="The device reports off and 0 W. Previous activity is unknown.",
        request_class="live-read",
        evidence=[_read()],
        choices=[],
        investigation_coverage=coverage,
    )
    return build_observed_agent_outcome(
        native, {"outcome": "success", "counters": {}, "timings_ms": {}},
    )


STATUS = (
    "Is Workshop Plug running right now? Verify its latest switch and power "
    "readings and their timestamps, and explain what those reports can and "
    "cannot prove about the physical cycle. Read-only; do not change anything."
)


def test_current_status_with_model_hypotheses_does_not_inherit_command_history():
    assert not is_causal_investigation(STATUS)
    assert plan_investigation(STATUS) is None
    prior = {
        "hypothesisComparisons": [{
            "candidate": "The plug may have been on recently",
            "source_kind": "device_history",
            "discriminator_verified": False,
        }],
        "hypothesisComparisonStatus": "model-proposed-source-checks-not-causal-verdicts",
    }
    original = _observation(prior)
    assessed = apply_shared_investigation_completion(original, STATUS)
    assert assessed is original
    assert assessed.investigation_coverage == prior
    assert assessed.metrics["outcome"] == "success"
    assert "shared_completion_partial" not in assessed.metrics["counters"]
    assert assessed.message == original.message


def test_other_noncausal_factual_status_with_prior_source_packet_is_not_causal():
    request = ("Compare the current reported temperatures and humidity "
               "for these two sensors; explain which readings were checked.")
    assert plan_investigation(request) is None
    assert not is_causal_investigation(request)
    original = _observation({"sourceChecksComplete": False, "domain": "status"})
    assessed = apply_shared_investigation_completion(original, request)
    assert assessed is original
    assert assessed.investigation_coverage["sourceChecksComplete"] is False



def test_host_specialist_telemetry_domain_is_preserved_without_keyword_route():
    request = "Compare competing explanations for the endpoint's behaviour."
    assert plan_investigation(request) is None
    assert not is_causal_investigation(request)
    original = _observation({
        "domain": "device_telemetry", "evidenceComplete": False,
        "hypothesisComparisonStatus": "model-proposed-source-checks-not-causal-verdicts",
        "hypothesisComparisons": [{
            "candidate": "Endpoint telemetry has not been independently verified",
            "source_kind": "device_logs",
            "required_origin": "upstream",
            "origin_state": "upstream-origin-not-independently-verified",
            "source_state": "source-class-checked-verdict-unverified",
            "hypothesis_verdict": "unverified",
        }],
    })
    assessed = apply_shared_investigation_completion(original, request)
    assert assessed is not original
    assert assessed.investigation_coverage["domain"] == "device_telemetry"
    assert assessed.metrics["outcome"] == "unresolved"
    assert "device_logs" in assessed.investigation_coverage[
        "sourceCoverage"
    ]["missingSourceKinds"]

def test_real_why_request_still_requires_command_provenance():
    request = "Why did Workshop Plug turn off?"
    original = _observation(None)
    assessed = apply_shared_investigation_completion(original, request)
    assert assessed is not original
    assert assessed.investigation_coverage["domain"] == "causal_provenance"
    assert "command_history" in assessed.investigation_coverage[
        "sourceCoverage"
    ]["missingSourceKinds"]
    assert assessed.metrics["outcome"] == "unresolved"


def test_existing_telemetry_diagnosis_still_keeps_domain_incompleteness():
    request = (
        "Investigate device 1234 offline connection; explain the last "
        "telemetry activity and recent device logs."
    )
    assert plan_investigation(request) is not None
    original = _observation(None)
    assessed = apply_shared_investigation_completion(original, request)
    assert assessed is not original
    assert assessed.investigation_coverage["domain"] == "device_telemetry"
    assert assessed.metrics["outcome"] == "unresolved"
