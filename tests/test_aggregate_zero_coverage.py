"""Read-only aggregate completeness and zero-claim publication contract.

Synthetic device records only. No Hubitat, HA, router or model calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai/rootfs/app"
sys.path.insert(0, str(APP))

from aggregate_zero_claim_guard import guard_aggregate_zero_claims  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from device_state_summary import switch_state_coverage  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402


def fake_device(ident, label, room, caps, **states):
    return {
        "id": str(ident), "label": label, "room": room,
        "capabilities": caps, "attributes": states,
    }


def fleet(*, known_all=False):
    return [
        fake_device("11", "Lounge Light", "Lounge", ["Switch", "SwitchLevel"],
                    switch="off", level=72),
        fake_device("12", "Bedroom Lamp", "Bedroom", ["Switch"], switch="off"),
        fake_device("13", "Dining Bulb", "Dining", ["ColorControl", "Switch"],
                    **({"switch": "off"} if known_all else {})),
        # Illuminance sensor label is not proof this device is a light
        # fixture or has a controllable switch state.
        fake_device("14", "Aqara Light Sensor", "Lounge",
                    ["IlluminanceMeasurement"], illuminance=9),
        fake_device("15", "Kitchen Plug", "Kitchen", ["Outlet", "Switch"],
                    switch="on"),
        fake_device("16", "Hallway Switch", "Hallway", ["Switch"]),
    ]


class FakeMCP:
    def __init__(self, devices):
        self.devices = devices
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return MCPToolResult(name, args, {}, "ok", {"devices": self.devices})

    async def get_cached_devices(self):
        return self.devices


def receipt(result):
    fields = ToolExecutor.result_details(result)
    assert fields and "aggregateState" in fields
    return {
        "tool": result.name,
        "success": True,
        "effect": "read",
        "mutates": False,
        "supports_live_claim": True,
        "details": fields,
    }


def test_state_coverage_distinguishes_absent_switch_from_off_and_retained_level():
    observed = switch_state_coverage(fleet(), device_kind="light")
    assert observed == {
        "candidate_count": 3, "on_count": 0,
        "off_count": 2, "unknown_state_count": 1,
    }
    assert switch_state_coverage(
        fleet(known_all=True), device_kind="light"
    )["unknown_state_count"] == 0
    assert switch_state_coverage(
        fleet(), device_kind="non_light_switch"
    ) == {
        "candidate_count": 2, "on_count": 1,
        "off_count": 0, "unknown_state_count": 1,
    }


def test_room_scoped_counts_exclude_unrelated_unknown_states():
    selected = switch_state_coverage(
        fleet(), device_kind="light", rooms=("Lounge",)
    )
    assert selected == {
        "candidate_count": 1, "on_count": 0,
        "off_count": 1, "unknown_state_count": 0,
    }


@pytest.mark.asyncio
async def test_active_light_tool_exposes_structural_receipt_not_private_device_list():
    mcp = FakeMCP(fleet())
    service = DeviceQueryService(mcp, lambda *a, **kw: None)
    result = await service.active_lights({}, user_question="Which lights are currently on?")
    assert not result.is_error
    assert result.data["count"] == 0
    assert result.data["total_scanned"] == 6
    assert result.data["scope"] == "whole-home"
    assert result.data["complete"] is True
    assert result.data["state_coverage_complete"] is False
    assert result.data["state_coverage"]["unknown_state_count"] == 1
    details = ToolExecutor.result_details(result)
    aggregate = details["aggregateState"]
    assert aggregate["category"] == "lights"
    assert aggregate["onCount"] == 0
    assert aggregate["candidateCount"] == 3
    assert aggregate["unknownStateCount"] == 1
    assert "unknown_switch=1" in ToolExecutor.result_summary(result)
    assert "Lounge Light" not in str(details)
    assert "Kitchen Plug" not in str(details)


@pytest.mark.asyncio
async def test_known_off_fixture_allows_zero_claim_and_excludes_retained_level():
    service = DeviceQueryService(FakeMCP(fleet(known_all=True)), lambda *a, **kw: None)
    result = await service.active_lights({}, user_question="Which lights are currently on?")
    assert result.data["lights"] == []
    assert result.data["state_coverage_complete"] is True
    response, issues = guard_aggregate_zero_claims(
        "No lights are currently on.", [receipt(result)]
    )
    assert response == "No lights are currently on."
    assert issues == []


@pytest.mark.asyncio
async def test_unknown_light_switch_does_not_prove_all_lights_off():
    service = DeviceQueryService(FakeMCP(fleet()), lambda *a, **kw: None)
    result = await service.active_lights({}, user_question="Which lights are currently on?")
    response, issues = guard_aggregate_zero_claims(
        "No lights are currently on.", [receipt(result)]
    )
    assert "1 candidate(s) lacked a usable ON/OFF state" in response
    assert "complete zero-active conclusion is unverified" in response
    assert issues == ["aggregate_state_coverage_gap"]


@pytest.mark.asyncio
async def test_positive_on_light_prevents_false_model_zero_claim():
    values = fleet(known_all=True)
    values[0]["attributes"]["switch"] = "on"
    service = DeviceQueryService(FakeMCP(values), lambda *a, **kw: None)
    result = await service.active_lights({}, user_question="Which lights are currently on?")
    assert result.data["count"] == 1
    response, issues = guard_aggregate_zero_claims(
        "No lights are currently on.", [receipt(result)]
    )
    assert "reports 1 recognised light devices ON" in response
    assert "zero-active claim is not supported" in response
    assert issues == ["aggregate_zero_contradicted"]


@pytest.mark.asyncio
async def test_non_light_switches_use_same_coverage_contract():
    service = DeviceQueryService(FakeMCP(fleet()), lambda *a, **kw: None)
    result = await service.active_switches(
        {}, user_question="Which switches are currently on?"
    )
    assert result.data["count"] == 1
    assert result.data["state_coverage"]["unknown_state_count"] == 1
    assert ToolExecutor.result_details(result)["aggregateState"]["category"] == (
        "non_light_switches"
    )
    text, issues = guard_aggregate_zero_claims(
        "No switches are currently on.", [receipt(result)]
    )
    assert "non-light switches ON" in text
    assert issues == ["aggregate_zero_contradicted"]


@pytest.mark.asyncio
async def test_room_filtered_light_read_and_unrelated_unknown_elsewhere():
    service = DeviceQueryService(FakeMCP(fleet()), lambda *a, **kw: None)
    result = await service.active_lights(
        {"room": "Lounge"}, user_question="Which Lounge lights are currently on?"
    )
    assert result.data["scopeVerified"] is True
    assert result.data["scope"] == "room"
    assert result.data["state_coverage_complete"] is True
    assert result.data["state_coverage"]["candidate_count"] == 1
    result_text, issues = guard_aggregate_zero_claims(
        "No lights are currently on in the Lounge.", [receipt(result)]
    )
    assert result_text == "No lights are currently on in the Lounge."
    assert issues == []


def test_zero_candidates_cannot_prove_every_light_physically_off():
    data = {
        "aggregateState": {
            "category": "lights", "onCount": 0, "candidateCount": 0,
            "unknownStateCount": 0, "totalScanned": 7,
            "scope": "whole-home", "scopeVerified": True,
            "inventoryComplete": True, "stateCoverageComplete": True,
        },
    }
    r = {
        "tool": "homebrain_active_lights", "success": True,
        "supports_live_claim": True, "effect": "read", "mutates": False,
        "details": data,
    }
    output, issues = guard_aggregate_zero_claims("All lights are off.", [r])
    assert "No recognised light devices were recognised" in output
    assert issues == ["aggregate_no_eligible_candidates"]


def test_missing_failed_or_conflicting_aggregate_proof_does_not_invent_counts():
    exact = "No lights are currently on."
    r = {
        "tool": "homebrain_active_lights", "success": True,
        "supports_live_claim": True, "effect": "read", "mutates": False,
        "details": {"aggregateState": {
            "category": "lights", "onCount": 0, "candidateCount": 2,
            "unknownStateCount": 0, "totalScanned": 10,
            "scope": "whole-home", "scopeVerified": True,
            "inventoryComplete": True, "stateCoverageComplete": True,
        }},
    }
    for evidence in ([], [{**r, "success": False}], [{**r, "mutates": True}],
                     [r, r], [{**r, "details": {}}], [{**r, "supports_live_claim": False}]):
        output, issues = guard_aggregate_zero_claims(exact, evidence)
        assert output == exact
        assert issues == []


def test_other_status_claims_are_untouched_by_aggregate_zero_guard():
    source = {
        "tool": "homebrain_active_lights", "success": True,
        "supports_live_claim": True, "effect": "read", "mutates": False,
        "details": {"aggregateState": {
            "category": "lights", "onCount": 0, "candidateCount": 2,
            "unknownStateCount": 1, "totalScanned": 10,
            "scope": "whole-home", "scopeVerified": True,
            "inventoryComplete": True, "stateCoverageComplete": False,
        }},
    }
    for answer in (
        "Two lighting switches report as OFF.",
        "Hallway Light 1 is on at 50%.",
        "No devices are reported offline.",
    ):
        assert guard_aggregate_zero_claims(answer, [source]) == (answer, [])
