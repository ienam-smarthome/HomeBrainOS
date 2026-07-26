from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from execution_contract_bridge import annotate_execution_contract
from execution_contracts import (
    ExecutionRequest,
    ExecutionResult,
    RouteKind,
    VerificationState,
    classify_legacy_route,
    infer_verification_state,
)


def test_execution_request_normalises_query():
    request = ExecutionRequest(query="  Status of fridge freezer rule?  ")
    assert request.query == "Status of fridge freezer rule?"


def test_execution_result_serialises_typed_contract():
    result = ExecutionResult(
        success=True,
        route=RouteKind.FAST_READ,
        intent="automation-rule-status",
        message="Rule is paused.",
        verification=VerificationState.NOT_APPLICABLE,
    )
    assert result.to_response() == {
        "success": True,
        "route": "fast-read",
        "intent": "automation-rule-status",
        "message": "Rule is paused.",
        "verification": "not-applicable",
    }


def test_legacy_routes_map_to_three_authoritative_lanes():
    assert classify_legacy_route("mcp-rule-control") is RouteKind.FAST_CONTROL
    assert classify_legacy_route("mcp-fast") is RouteKind.FAST_READ
    assert classify_legacy_route("ollama+mcp") is RouteKind.AGENT


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
    assert response["verification_state"] == "verified"


def test_unsupported_write_is_not_marked_failed_execution():
    response = {
        "success": False,
        "route": "mcp-rule-control-unsupported",
        "intent": "automation-rule-disabled-write-unsupported",
        "message": "No command was sent.",
        "technical": {"command_sent": False},
    }
    assert infer_verification_state(response) is VerificationState.NOT_ATTEMPTED
