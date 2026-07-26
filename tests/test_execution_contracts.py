from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from assistant_contracts import RouteClass, VerificationOutcome
from execution_contract_bridge import (
    annotate_execution_contract,
    classify_legacy_route,
    infer_verification_outcome,
)


def test_legacy_routes_map_to_three_authoritative_lanes():
    assert classify_legacy_route("mcp-rule-control") is RouteClass.FAST_CONTROL
    assert classify_legacy_route("mcp-fast") is RouteClass.FAST_READ
    assert classify_legacy_route("ollama+mcp") is RouteClass.AGENT


def test_verified_control_response_is_annotated_without_replacing_legacy_route():
    response = annotate_execution_contract(
        {
            "success": True,
            "route": "mcp-rule-control",
            "intent": "automation-rule-pause-verified",
            "message": "Rule paused.",
            "technical": {"post_state_verified": True},
        }
    )
    assert response["route"] == "mcp-rule-control"
    assert response["execution_lane"] == "fast-control"
    assert response["verification_state"] == "completed"


def test_unsupported_write_is_marked_uncertain_because_no_command_was_sent():
    response = {
        "success": False,
        "route": "mcp-rule-control-unsupported",
        "intent": "automation-rule-disabled-write-unsupported",
        "message": "No command was sent.",
        "technical": {"command_sent": False},
    }
    assert infer_verification_outcome(response) is VerificationOutcome.UNCERTAIN


def test_accepted_control_is_marked_sent_not_completed():
    response = {
        "success": True,
        "route": "mcp-app-control",
        "intent": "app-disable-accepted",
        "message": "Command accepted without read-back.",
    }
    assert infer_verification_outcome(response) is VerificationOutcome.SENT
