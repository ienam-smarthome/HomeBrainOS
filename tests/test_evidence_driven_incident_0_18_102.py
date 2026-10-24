"""0.18.102: AI-led discriminating evidence instead of repeated symptom reports.

The checkpoint uses already observed target identity and read-only receipt
progress. The model chooses tools and scope; no keyword-to-tool routing and
no live writes are exercised by these tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from ai_investigation_routing import (
    ReadRouteDecision, set_request_interpretation,
    reset_request_interpretation,
)
from device_incident_depth import (
    evidence_progress_checkpoint, CONNECTIVITY_EVIDENCE_PLAN,
)
from mcp_agent_orchestrator import _explicit_mutation_request

Q = "Explain why the status indicators disagree for the named device."


def evidence(tool, args, success=True, *, mutates=False):
    return {
        "tool": "hub_read_devices", "sub_tool": tool,
        "arguments": {"tool": tool, "args": args},
        "success": success, "mutates": mutates,
        "effect": "write" if mutates else "read",
    }


def test_incident_after_driver_read_requires_code_interpretation_and_targeted_sources():
    token = set_request_interpretation(
        Q, ReadRouteDecision("model_led", "model_choice", objective="device_connectivity"),
    )
    try:
        observed = [
            evidence("hub_list_device_events", {"deviceId": "7103", "hoursBack": 24}),
            evidence("hub_get_source", {"id": "3686", "type": "driver"}),
            evidence("hub_get_logs", {"since": "30m", "limit": 100}),
            evidence("hub_list_apps", {"nameFilter": "MQTT Manager"}),
        ]
        followup = evidence_progress_checkpoint(Q, observed)
        assert followup is not None
        assert "Device 7103" in followup
        assert "3686" in followup
        assert "METHOD BODIES" in followup
        assert "dependent-app" in followup
        assert "Unfiltered hub/app logs" in followup
        assert "single most useful" in followup
        assert "Never send commands" in followup
    finally:
        reset_request_interpretation(token)


def test_progress_based_not_keywords_or_specific_device_name():
    request = "Why is the unit behaving strangely?"
    token = set_request_interpretation(
        request, ReadRouteDecision("model_led", "model_choice", objective="device_connectivity"),
    )
    try:
        for device_id in ("7103", "4801"):
            question = evidence_progress_checkpoint(
                request,
                [evidence("hub_list_device_events", {"deviceId": device_id}),
                 evidence("hub_get_logs", {"deviceId": device_id})],
            )
            assert question is not None
            assert "Device " + device_id in question
    finally:
        reset_request_interpretation(token)


def test_missing_target_competing_targets_or_unrelated_only_cannot_trigger():
    token = set_request_interpretation(
        Q, ReadRouteDecision("model_led", "model_choice", objective="device_connectivity"),
    )
    try:
        generic = [evidence("hub_get_logs", {"since": "30m"}),
                   evidence("hub_list_apps", {})]
        assert evidence_progress_checkpoint(Q, generic) is None
        assert evidence_progress_checkpoint(
            Q, [evidence("hub_list_device_events", {"deviceId": "7103"}), *generic]
        ) is None
        assert evidence_progress_checkpoint(
            Q, [evidence("hub_list_device_events", {"deviceId": "7103"}),
                evidence("hub_list_device_events", {"deviceId": "7104"}),
                evidence("hub_get_source", {"type": "driver", "id": "3686"})],
        ) is None
    finally:
        reset_request_interpretation(token)


def test_failed_reads_and_state_changes_never_create_progress():
    token = set_request_interpretation(
        Q, ReadRouteDecision("model_led", "model_choice", objective="device_connectivity"),
    )
    try:
        observed = [
            evidence("hub_list_device_events", {"deviceId": "7103"}),
            evidence("hub_get_source", {"type": "driver", "id": "3686"}, False),
            evidence("hub_list_device_dependents", {"deviceId": "7103"}, mutates=True),
            evidence("hub_get_logs", {"deviceId": "7103"}, False),
        ]
        assert evidence_progress_checkpoint(Q, observed) is None
    finally:
        reset_request_interpretation(token)


def test_direct_control_and_different_ai_objective_stay_out():
    assert _explicit_mutation_request("Turn on TV")
    for target in ("historical_command", "source_code", "general_investigation"):
        token = set_request_interpretation(
            Q, ReadRouteDecision("model_led", "model_choice", objective=target),
        )
        try:
            assert evidence_progress_checkpoint(
                Q, [evidence("hub_list_device_events", {"deviceId": "7103"}),
                    evidence("hub_get_source", {"type": "driver", "id": "3686"})],
            ) is None
        finally:
            reset_request_interpretation(token)


def test_model_can_choose_tools_and_method_projection_without_driver_word_trigger():
    source = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "incident_evidence_checkpoint_used = False" in source
    assert "target_checkpoint = evidence_progress_checkpoint(" in source
    assert "round_index + 1 < active_round_budget" in source
    assert "catalog.expose_read_gateways(" in source
    assert "source_investigation\n                        or (connectivity_incident and adaptive_investigation)" in source
    assert 'and "driver" in user_prompt.casefold()' not in source
    assert "same-integration control group" in CONNECTIVITY_EVIDENCE_PLAN
