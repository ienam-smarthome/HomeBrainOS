"""Transport-success does not imply investigation proof.

The API's evidence coverage is additive and does not alter ordinary
read/control response fields or expose private log text.
"""
from __future__ import annotations

from types import SimpleNamespace

from api_response_builder import build_agent_response


def _outcome(coverage=None):
    return SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="No historical execution evidence was recovered.",
        choices=[], confirmation_required=False, confirmation_count=0,
        automation_items=[], evidence=[], metrics={
            "outcome": "success", "counters": {}, "timings_ms": {},
        },
        investigation_coverage=coverage,
    )


def test_incomplete_investigation_has_distinct_coverage_and_transport_success():
    source = {
        "domain": "manual_motion_lockout",
        "status": "not-established", "evidenceComplete": False,
        "requirements": [
            {"key": "target_off", "state": "not-checked",
             "source": "targeted device switch-event history"},
        ],
    }
    result = build_agent_response(
        _outcome(source), model="gemma4:31b-cloud", elapsed_ms=2814,
        version="0.17.35",
    )
    assert result["success"] is True
    assert result["investigation_coverage"]["status"] == "not-established"
    assert result["investigation_coverage"]["evidenceComplete"] is False
    source["requirements"][0]["state"] = "observed"
    assert result["investigation_coverage"]["requirements"][0]["state"] == "not-checked"


def test_existing_api_contract_for_ordinary_requests_remains_unchanged():
    result = build_agent_response(
        _outcome(), model="gemma4:31b-cloud", elapsed_ms=12,
        version="0.17.35",
    )
    assert result["success"] is True
    assert "investigation_coverage" not in result
    assert result["route"] == "unified-mcp-agent"
