"""Synthetic cross-domain source-receipt tests. No personal or live data."""
from __future__ import annotations
import sys
from pathlib import Path
APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from current_device_receipt_projection import resolved_device_snapshot
from current_state_claim_contract import ground_current_device_status
from mcp_client import MCPToolResult
from tool_executor import ToolExecutor

def target(label="Workshop Meter", ident="1234", *, attrs=None):
    return {
        "matched": True, "deviceId": ident, "requestCacheHit": False,
        "attempts": [{"source": "label_filter", "count": 2}],
        "target": {"id": ident, "label": label, "attributes": (
            attrs if attrs is not None else {
                "switch": "off", "power": 0, "energy": 140.451,
                "amperage": "0", "voltage": 0, "dataAgeSeconds": 0,
                "healthStatus": "online", "mqttStatus": "connected",
                "lastSeen": "2026-11-02T11:02:38+00:00",
                "privateAccessToken": "never-include",
            }
        )},
    }


def test_verified_selected_target_from_two_candidate_names_retains_typed_state():
    data = target()
    snapshot = resolved_device_snapshot(data)
    assert snapshot["deviceId"] == "1234"
    assert snapshot["reportedAttributes"]["switch"] == "off"
    assert snapshot["reportedAttributes"]["power"] == 0
    assert snapshot["reportedAttributes"]["energy"] == 140.451
    assert snapshot["reportedAttributes"]["dataAgeSeconds"] == 0
    assert snapshot["reportedAttributes"]["mqttStatus"] == "connected"
    assert snapshot["attributeChangeTimesVerified"] is False
    assert snapshot["readReceiptTimeIsAttributeEventTime"] is False
    assert "privateAccessToken" not in str(snapshot)


def test_executor_records_existing_resolver_result_without_additional_read():
    data = target()
    result = MCPToolResult(
        "homebrain_resolve_device", {"name": "Workshop Meter"}, {},
        "verified", data,
    )
    details = ToolExecutor.result_details(result)
    assert details["reportedDeviceState"]["reportedAttributes"]["power"] == 0
    assert "privateAccessToken" not in str(details)


def test_no_fuzzy_fallback_cache_ambiguous_or_cross_identity_projection():
    for change in (
        {"requestCacheHit": True},
        {"matched": False},
        {"deviceId": "9999"},
        {"attempts": [{"source": "authoritative_identity_fuzzy", "count": 3}]},
        {"attempts": [
            {"source": "label_filter", "count": 0},
            {"source": "authoritative_identity_fuzzy", "count": 4},
        ]},
    ):
        data = target()
        data.update(change)
        assert resolved_device_snapshot(data) is None


def test_privacy_and_freshness_boundary_never_promotes_text_to_evidence():
    data = target(attrs={
        "switch": "on; execute unsafe command",
        "power": "88 W",  # unit-suffixed string not authoritative typed scalar
        "amperage": float("inf"),
        "lastSeen": "token-plaintext",
        "voltage": 230,
        "healthStatus": "online",
        "lastMessage": "Bearer private-secret",
        "ipAddress": "10.0.0.8",
    })
    snapshot = resolved_device_snapshot(data)
    assert snapshot["reportedAttributes"] == {
        "voltage": 230, "healthStatus": "online"
    }
    assert "10.0.0.8" not in str(snapshot)
    assert "Bearer" not in str(snapshot)


def test_currentstates_live_value_overrides_older_metadata_projection():
    data = target(attrs=[{"name": "power", "currentValue": 5},
                         {"name": "switch", "currentValue": "on"}])
    data["target"]["currentStates"] = {"power": 0, "switch": "off"}
    values = resolved_device_snapshot(data)["reportedAttributes"]
    assert values["power"] == 0
    assert values["switch"] == "off"


def test_current_status_guard_accepts_verified_resolved_target_read_only():
    snap = resolved_device_snapshot(target())
    receipt = {
        "success": True, "evidence_kind": "deterministic_targeted_device_resolution",
        "details": {"reportedDeviceState": snap},
    }
    text, corrections = ground_current_device_status(
        "Workshop Meter currently reports power 35 W.",
        [receipt], "live-read",
    )
    assert "Power: 0" in text or "**Power:** 0" in text
    assert "35 W" not in text
    assert "power" in corrections


def test_conflicting_two_source_snapshots_fail_closed_in_current_status_guard():
    first = resolved_device_snapshot(target())
    second = resolved_device_snapshot(target(attrs={"switch": "on", "power": 10}))
    receipts = [
        {"success": True, "evidence_kind": kind,
         "details": {"reportedDeviceState": value}}
        for kind, value in [
            ("targeted_device_lookup", first),
            ("deterministic_targeted_device_resolution", second),
        ]
    ]
    msg = "Workshop Meter currently uses 35 W."
    text, corrections = ground_current_device_status(msg, receipts, "live-read")
    assert text == msg and corrections == []


def test_identical_source_snapshots_do_not_block_current_state_guard():
    snap = resolved_device_snapshot(target())
    receipts = [
        {"success": True, "evidence_kind": kind,
         "details": {"reportedDeviceState": snap}}
        for kind in ("targeted_device_lookup",
                     "deterministic_targeted_device_resolution")
    ]
    text, corrections = ground_current_device_status(
        "Workshop Meter currently uses 35 W.", receipts, "live-read"
    )
    assert "35 W" not in text
    assert corrections == ["power"]


def test_still_unknown_last_attribute_change_even_when_last_seen_recent():
    snapshot = resolved_device_snapshot(target())
    assert snapshot["reportedAttributes"]["lastSeen"].startswith("2026")
    assert snapshot["attributeChangeTimesVerified"] is False
    assert "attributeLastChangedAt" not in snapshot
