"""Q2 frozen synthetic source-role regressions; no Hubitat/HA or provider calls.

This checks evidence admission, not semantic quality of model first answers.
Native MCP rows and deterministic wrappers are two presentations of scoped
source receipts. Neither proves physical delivery or a historical trigger.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from causal_initiator_provenance_guard import (
    build_state_report_provenance,
    guard_unverified_initiator_claims,
    render_state_report_provenance,
)

DATE = "2026-10-01T18:28:49.542+00:00"


def native(*rows, device_id="9911", success=True, effect="read", **overrides):
    item = {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "success": success,
        "supports_live_claim": True,
        "evidence_kind": "authoritative_command_event_history",
        "mutates": False,
        "effect": effect,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": device_id, "hoursBack": 24}},
        "details": {"label": "Example actuator", "events": list(rows)},
    }
    item.update(overrides)
    return item


def state(*, producer=None, listeners=None):
    return {
        "name": "switch", "value": "off", "date": DATE,
        "type": "physical", "isStateChange": True,
        "producedBy": producer or {
            "id": "7001", "type": "device", "label": "Example bridge",
        },
        "triggered": listeners if listeners is not None else [
            {"id": "4200", "type": "app", "label": "Example rules"},
        ],
    }


def command(producer=None):
    return {
        "name": "command-off", "value": None, "date": DATE,
        "type": "command", "isStateChange": False,
        "producedBy": producer or {
            "id": "3100", "type": "app", "label": "Example app",
        },
    }


def test_native_mcp_event_shape_preserves_all_three_source_roles():
    report = build_state_report_provenance([native(command(), state())])
    assert report["state_report_count"] == 1
    assert report["direct_command_count"] == 1
    assert report["direct_command_app_ids"] == ["3100"]
    assert report["direct_command_target_ids"] == ["9911"]
    assert report["reporting_devices"] == ["Example bridge"]
    assert report["downstream_listener_app_ids"] == ["4200"]
    assert set((e["from"], e["to"], e["role"])
               for e in report["source_role_edges"]) == {
        ("app:3100", "device:9911", "issued-command"),
        ("device:7001", "device:9911", "reported-state"),
        ("device:9911", "app:4200", "notified-listener"),
    }
    assert report["upstream_initiator_established"] is False
    assert report["source_history_completeness_verified"] is False
    assert report["physical_event_does_not_prove_manual_operation"] is True


def test_native_state_without_corresponding_command_does_not_prove_external_cause():
    evidence = [native(state())]
    context = render_state_report_provenance(evidence)
    assert context is not None
    assert "source_history_completeness_verified" in context
    msg = "The actuator was initiated by an external source outside of Hubitat."
    corrected, changed = guard_unverified_initiator_claims(
        msg, evidence, "Investigate why the actuator turned OFF.",
        graph={"scope": "multiple-observed-events"},
    )
    assert changed
    assert "initiated by an external source" not in corrected
    assert "does not identify an initiating controller" in corrected
    assert "remains possible" in corrected


def test_native_command_actor_without_state_report_is_not_external_origin_proof():
    record = build_state_report_provenance([native(command())])
    assert record["state_report_count"] == 0
    assert record["direct_command_count"] == 1
    assert record["direct_command_app_ids"] == ["3100"]
    assert record["upstream_initiator_established"] is False


def test_wrong_role_untyped_id_or_conflicting_ids_never_admitted_as_actor():
    malformed = native(
        command({"id": "3000", "type": "device"}),
        command({"id": "3000"}),  # Bare ID cannot be attributed to an app.
        command({"appId": "3100", "id": "3101", "type": "app"}),
        state(producer={"deviceId": "7001", "id": "7002",
                        "type": "device", "label": "Conflicting bridge"},
              listeners=[{"id": "4200"}, {"id": "4201", "type": "device"},
                         {"appId": "4202", "id": "4203", "type": "app"}]),
    )
    result = build_state_report_provenance([malformed])
    assert result["direct_command_count"] == 0
    assert result["direct_command_app_ids"] == []
    assert result["reporting_devices"] == []
    assert result["downstream_listener_app_ids"] == []
    assert result["state_report_count"] == 1


def test_source_scope_is_strict_no_unverified_or_unrelated_mcp_event_rows():
    signed = native(state())
    variants = [
        native(state(), success=False),
        native(state(), effect="write"),
        native(state(), mutates=True),
        native(state(), supports_live_claim=False),
        native(state(), device_id=""),
        native(state(), device_id="not-a-number"),
        native(state(), evidence_kind="unverified_model_claim"),
        {**signed, "sub_tool": "hub_list_apps"},
        {**signed, "details": {"events": "not an event list"}},
    ]
    for row in variants:
        result = build_state_report_provenance([row])
        assert result["state_report_count"] == 0, row


def test_anonymised_cross_domain_records_stay_observations_not_causes():
    for label in ("Example ventilation fan", "Example heating relay",
                  "Example smart outlet"):
        event = state()
        evidence = [native(event, details={"events": [event], "label": label})]
        report = build_state_report_provenance(evidence)
        assert report["state_report_count"] == 1
        assert report["direct_command_count"] == 0
        assert report["upstream_initiator_established"] is False
