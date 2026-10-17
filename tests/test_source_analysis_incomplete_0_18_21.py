"""Full source retrieval and a useful answer can still omit required methods."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "hubitat-mcp-ai" / "rootfs" / "app"))

from source_analysis_completion import source_method_claim_gap
from shared_investigation_completion import apply_shared_investigation_completion


REQUEST = (
    "Investigate actual Groovy driver source code 3686, retrieve the full "
    "source and trace mqttStatus, lastSeen, dataAgeSeconds, watchdog methods "
    "and command acknowledgements. Correlate logs, read-only."
)
ADMITTED_GAP = (
    "The driver source was retrieved. The methods that actually set "
    "mqttStatus, lastSeen, dataAgeSeconds, perform the watchdog reconnection, "
    "and handle message acknowledgements — connect(), publishCmd(), "
    "publishPower(), initializeHealthState(), deviceHealthCheck(), "
    "healthCheckIntervalSeconds(), and the MQTT message handlers — are "
    "not present in the visible excerpt. Their exact implementation "
    "cannot be traced from the evidence shown."
)


def _source_receipt():
    return {
        "tool":"hub_read_apps_code", "sub_tool":"hub_get_source",
        "arguments":{"tool":"hub_get_source",
                     "args":{"type":"driver","id":"3686"}},
        "success": True, "mutates": False, "effect":"read",
        "details":{"sourceRetrieved":True, "sourceCodeId":"3686",
                   "offset":0, "chunkLength":20531, "totalLength":20531},
    }


def _result(message):
    return SimpleNamespace(
        request_class="live-read", route="unified-mcp-agent",
        message=message, evidence=[_source_receipt()],
        metrics={"outcome":"success","counters":{}},
        investigation_coverage=None,
    )


def test_model_admits_required_method_bodies_were_not_shown():
    assert source_method_claim_gap(ADMITTED_GAP)
    resolved = apply_shared_investigation_completion(
        _result(ADMITTED_GAP), REQUEST,
    )
    assert resolved.investigation_coverage["fullImplementationVerified"] is True
    assert resolved.investigation_coverage["objectiveSatisfied"] is False
    assert resolved.investigation_coverage["analysisAnswerVerified"] is True
    assert resolved.investigation_coverage["analysisStatus"] == (
        "model-admitted-relevant-methods-not-reviewed"
    )
    assert resolved.investigation_coverage["methodBodyCoverage"]["status"] == (
        "model-admitted-unreviewed-methods"
    )
    assert resolved.metrics["outcome"] == "unresolved"
    assert resolved.message == ADMITTED_GAP


def test_verified_method_body_explanation_without_admitted_gap_is_not_blocked():
    answer = ("The code's parse method updates device state; the broker's "
              "upstream packet source still remains unverified.")
    assert not source_method_claim_gap(answer)
    result = apply_shared_investigation_completion(_result(answer), REQUEST)
    assert result.investigation_coverage["objectiveSatisfied"] is True
    assert result.metrics["outcome"] == "success"


def test_generic_no_code_claims_not_misclassified_as_method_gaps():
    assert not source_method_claim_gap(
        "The driver has no evidence of a physical command acknowledgement."
    )
    assert not source_method_claim_gap(
        "Not all relevant devices appeared in the bounded history."
    )
