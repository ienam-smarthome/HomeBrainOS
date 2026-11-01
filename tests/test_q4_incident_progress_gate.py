"""Regression for redundant connectivity-incident retry fan-out.

All source rows are synthetic and non-private. This tests the typed source
progress gate used after a model has already received one evidence-checkpoint
opportunity. It does NOT claim any reduction in actual provider latency.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from device_incident_depth import substantive_incident_progress_since


def row(op, args, details=None, *, success=True, mutates=False):
    return {
        "tool": "hub_read_devices",
        "sub_tool": op, "success": success, "mutates": mutates,
        "effect": "write" if mutates else "read",
        "arguments": {"tool": op, "args": args},
        "details": details or {},
    }


def baseline():
    return [
        row("hub_list_devices", {"labelFilter": "Anonymised Socket"}),
        row("hub_list_device_events", {"deviceId": "9911", "hoursBack": 24}),
        row("hub_get_logs", {"deviceId": "9911", "since": "24h"}),
    ]


def test_empty_or_repeated_source_retries_do_not_stack_model_rounds():
    base = baseline()
    assert not substantive_incident_progress_since(base, len(base))
    repeated = base + [
        row("hub_list_device_events", {"deviceId": "9911", "hoursBack": 24}),
        row("hub_get_logs", {"deviceId": "9911", "since": "24h"}),
        row("hub_list_devices", {}),
        row("hub_list_devices", {"labelFilter": "Tasmota"}),
    ]
    assert not substantive_incident_progress_since(repeated, len(base))


def test_unlinked_source_attempt_or_configuration_read_not_inferred_to_target():
    base = baseline()
    for other in [
        row("hub_get_source", {"type": "driver", "id": "5555"},
            {"sourceRetrieved": True, "sourceCodeId": "5555"}),
        row("hub_get_device", {"deviceId": "9911", "mode": "configuration"},
            {"driverSource": "unknown"}),
        row("hub_get_app_config", {"appId": "3950"}, {"name": "Power saving"}),
        row("hub_list_device_dependents", {"deviceId": "9911"}, {"dependents": []}),
        row("hub_get_device_health", {}, {"pingResults": [{"host": "other"}]}),
        row("hub_get_source", {"type": "driver", "id": "7777"},
            {"sourceRetrieved": True, "sourceCodeId": "7777"}, success=False),
        row("hub_get_app_config", {"appId": "3950"},
            {"verifiedControlsDeviceId": "9911"}, mutates=True),
    ]:
        assert not substantive_incident_progress_since(base + [other], len(base)), other


def test_exact_device_driver_source_and_dependency_leads_allow_followup():
    base = baseline()
    mapping = row("hub_get_device", {"deviceId": "9911"},
                  {"verifiedInstalledDriverCodeId": "5555"})
    assert substantive_incident_progress_since(base + [mapping], len(base))
    # An unrelated code read is NOT source-linked; a verified code mapping is.
    associated = base + [mapping, row(
        "hub_get_source", {"type": "driver", "id": "5555"},
        {"sourceRetrieved": True, "sourceCodeId": "5555"}
    )]
    assert substantive_incident_progress_since(associated, len(base) + 1)
    for lead in [
        row("hub_list_device_dependents", {"deviceId": "9911"},
            {"verifiedDeviceTargetLinks": True}),
        row("hub_list_device_dependents", {"deviceId": "9911"},
            {"dependents": [{"appId": "3950"}]}),
        row("hub_get_app_config", {"appId": "3950"},
            {"verifiedControlsDeviceId": "9911"}),
        row("hub_get_device_health", {},
            {"verifiedForDeviceId": "9911", "pingResults": [{"ok": False}]}),
        row("custom_read", {},
            {"verifiedForDeviceId": "9911", "independentObservationVerified": True}),
    ]:
        assert substantive_incident_progress_since(base + [lead], len(base)), lead


def test_other_devices_and_unreliable_baselines_fail_closed():
    base = baseline()
    assert not substantive_incident_progress_since(base, -1)
    assert not substantive_incident_progress_since(base, len(base) + 1)
    assert not substantive_incident_progress_since(base, 1.5)
    foreign = row("hub_list_device_dependents", {"deviceId": "1111"},
                  {"dependents": [{"appId": "3950"}]})
    assert not substantive_incident_progress_since(base + [foreign], len(base))
    mixed = base + [row("hub_list_device_events", {"deviceId": "1111"})]
    mixed += [row("hub_get_device", {"deviceId": "9911"},
                  {"verifiedInstalledDriverCodeId": "5555"})]
    assert not substantive_incident_progress_since(mixed, len(base))


def test_orchestrator_second_retry_conditional_requires_typed_progress():
    source = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "incident_checkpoint_receipt_count = len(" in source
    assert "substantive_incident_progress_since(" in source
    assert "incident_checkpoint_receipt_count is None" in source
    assert "device_incident_followup_used = False" in source
    assert '"device_incident_depth_retry"' in source
