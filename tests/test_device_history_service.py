from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from deterministic_tool_presenter import present_tool_result  # noqa: E402
from device_history_service import (  # noqa: E402
    DEVICE_GATEWAY,
    DEVICE_HISTORY_TOOL,
    EVENT_OPERATION,
    LOCATION_EVENTS_TOOL,
    DeviceHistoryService,
)
from mcp_client import MCPToolResult  # noqa: E402
from tool_registry import (  # noqa: E402
    EVIDENCE_KINDS,
    ToolEffect,
    classify_tool_effect,
    device_history_tool,
)


class HistoryMCP:
    def __init__(self, *, resolve: bool = True) -> None:
        self.resolve = resolve
        self.calls: list[tuple[str, dict]] = []

    async def get_cached_devices(self):
        if not self.resolve:
            return []
        return [{
            "id": "42",
            "label": "Livingroom Light 1",
            "capabilities": ["Switch"],
            "commands": ["on", "off"],
        }]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            devices = []
            if self.resolve:
                devices = [{
                    "id": "42",
                    "label": "Livingroom Light 1",
                    "capabilities": ["Switch"],
                    "commands": ["on", "off"],
                }]
            return MCPToolResult(name, arguments, {}, "ok", {"devices": devices})
        if operation == EVENT_OPERATION:
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "source": "device",
                    "deviceId": "42",
                    "device": "Livingroom Light 1",
                    "events": [
                        {
                            "name": "switch",
                            "value": "off",
                            "date": "2026-08-01T12:30:00.000+0100",
                            "description": "Livingroom Light 1 was turned off",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-08-01T11:00:00.000+0100",
                            "descriptionText": "Livingroom Light 1 was turned on",
                            "isStateChange": True,
                        },
                    ],
                    "count": 2,
                },
            )
        raise AssertionError(f"unexpected operation: {operation}")


@pytest.mark.asyncio
async def test_reads_bounded_authoritative_history_after_targeted_resolution():
    mcp = HistoryMCP()
    receipts = []
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: receipts.append((args, kwargs)),
    )

    result = await service.history({
        "name": "living room light 1",
        "hours_back": 999,
        "attribute": "switch",
        "limit": 500,
    })

    assert result.is_error is False
    assert result.data["label"] == "Livingroom Light 1"
    assert result.data["hoursBack"] == 168
    assert result.data["count"] == 2
    assert result.data["causationAvailable"] is False
    # `attribute` is deliberately NOT forwarded to the upstream call -- see
    # test_attribute_filter_is_applied_locally_not_forwarded_upstream for
    # why (a live-confirmed upstream filter bug for at least one attribute
    # name). The full unfiltered window is fetched instead and filtered by
    # attribute name on this side.
    assert mcp.calls[-1] == (
        DEVICE_GATEWAY,
        {
            "tool": EVENT_OPERATION,
            "args": {
                "deviceId": "42",
                "hoursBack": 168,
                "limit": 50,
            },
        },
    )
    assert receipts[-1][1]["evidence_kind"] == (
        "authoritative_device_event_history"
    )
    assert receipts[-1][1]["success"] is True


@pytest.mark.asyncio
async def test_attribute_scoped_query_widens_default_window_to_seven_days():
    """Live-observed bug (2026-08-13): "When did the front door last open?"
    and its "and when did it close before that?" follow-up both answered
    "No contact events were reported for Front Door in the last 24 hours" --
    even though real contact events existed, just further back than one
    day. The model correctly scoped the query to attribute="contact" with a
    small limit per the tool's own guidance for a "last X" point question,
    but never passed hours_back, so it silently inherited the generic
    24-hour default meant for open-ended "what happened" reviews. A "last
    <state>" question has no natural window -- it wants the most recent
    matching event whenever it occurred -- so when attribute is set and
    hours_back is left unset, the host must widen the search to the full
    seven-day bound instead of truncating to one day.
    """

    mcp = HistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({
        "name": "living room light 1",
        "attribute": "switch",
        "limit": 3,
    })

    assert result.is_error is False
    assert result.data["hoursBack"] == 168
    # `attribute` is no longer forwarded upstream (see
    # test_attribute_filter_is_applied_locally_not_forwarded_upstream) and
    # the fetch always uses the max bound when scoped to one attribute, so
    # the caller's small `limit` is applied client-side after filtering,
    # not sent to the upstream call.
    assert mcp.calls[-1] == (
        DEVICE_GATEWAY,
        {
            "tool": EVENT_OPERATION,
            "args": {
                "deviceId": "42",
                "hoursBack": 168,
                "limit": 50,
            },
        },
    )
    assert result.data["count"] == 2


@pytest.mark.asyncio
async def test_unscoped_query_keeps_the_original_twenty_four_hour_default():
    """Companion to the attribute-scoped-widening fix above: a query with
    no attribute filter (a broad 'what happened' review, not a 'last X'
    point question) must keep the original 24-hour default -- only the
    attribute-scoped case changes.
    """

    mcp = HistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "living room light 1"})

    assert result.is_error is False
    assert result.data["hoursBack"] == 24


@pytest.mark.asyncio
async def test_explicit_hours_back_still_overrides_attribute_default():
    """An explicit hours_back must still win even when attribute is set --
    the widened 168 is only a default for when the model leaves it unset."""

    mcp = HistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({
        "name": "living room light 1",
        "attribute": "switch",
        "hours_back": 6,
    })

    assert result.is_error is False
    assert result.data["hoursBack"] == 6


class BrokenAttributeFilterHistoryMCP(HistoryMCP):
    """Reproduces a live-confirmed upstream bug (2026-08-13): calling
    hub_list_device_events with attribute="contact" for the real Front
    Door device silently returned zero events -- despite real contact
    events existing in the exact same window, confirmed by re-running the
    identical call with no attribute filter at all. attribute="motion" on
    that same device filtered correctly, so this is not a device- or
    account-wide outage, just a specific, silent, per-attribute filter
    failure with no error and no is_error flag -- indistinguishable from
    "no events occurred" unless the caller stops trusting the filter.
    """

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            return await super().call_tool(name, arguments)
        if operation == EVENT_OPERATION:
            args = arguments.get("args") or {}
            if args.get("attribute") == "contact":
                # The exact live failure: an attribute filter the upstream
                # server silently can't honour comes back as a clean empty
                # list, not an error.
                return MCPToolResult(
                    name, arguments, {}, "ok",
                    {"events": [], "count": 0},
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "motion",
                            "value": "active",
                            "date": "2026-08-13T22:17:53.559+0100",
                            "isStateChange": True,
                        },
                        {
                            "name": "contact",
                            "value": "closed",
                            "date": "2026-08-13T22:17:53.470+0100",
                            "description": "Front Door contact is closed (raw:true)",
                            "isStateChange": True,
                        },
                        {
                            "name": "contact",
                            "value": "open",
                            "date": "2026-08-13T22:17:46.015+0100",
                            "description": "Front Door contact is open (raw:false)",
                            "isStateChange": True,
                        },
                    ],
                    "count": 3,
                },
            )
        raise AssertionError(f"unexpected operation: {operation}")


@pytest.mark.asyncio
async def test_attribute_filter_is_applied_locally_not_forwarded_upstream():
    """Direct regression test for the live-confirmed upstream attribute-
    filter bug: 'When did the front door last open?' still answered 'No
    contact events...' even after the seven-day window widening fix,
    because the upstream hub_list_device_events attribute="contact" filter
    itself silently drops real events. The fix must never forward
    `attribute` to the upstream call -- it must fetch the unfiltered window
    and filter by attribute name on this side, so a broken upstream filter
    for any attribute can no longer produce a false "no events" answer.
    """

    mcp = BrokenAttributeFilterHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({
        "name": "living room light 1",
        "attribute": "contact",
        "limit": 1,
    })

    assert result.is_error is False
    assert result.data["count"] == 1
    assert result.data["events"][0]["name"] == "contact"
    assert result.data["events"][0]["value"] == "closed"
    # The upstream call itself must never carry the attribute filter that
    # was proven unreliable.
    assert "attribute" not in mcp.calls[-1][1]["args"]


@pytest.mark.asyncio
async def test_client_side_attribute_filter_still_respects_requested_limit():
    """The client-side filtering fallback must still cap results to the
    caller's requested `limit` after filtering, not the wider fetch bound
    used to work around the unreliable upstream filter."""

    mcp = BrokenAttributeFilterHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({
        "name": "living room light 1",
        "attribute": "contact",
        "limit": 1,
    })

    assert result.data["count"] == 1
    assert len(result.data["events"]) == 1


@pytest.mark.asyncio
async def test_short_name_resolves_prefixed_hyphenated_device_before_history():
    class PrefixedHistoryMCP(HistoryMCP):
        def __init__(self):
            super().__init__()
            self.devices = [{
                "id": "6916",
                "label": "Block Tab-S9-FE",
                "capabilities": ["Switch"],
                "commands": ["blockInternet", "allowInternet"],
            }]

        async def get_cached_devices(self):
            return self.devices

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            operation = arguments.get("tool")
            if operation == "hub_list_devices":
                assert arguments.get("args") == {}
                return MCPToolResult(
                    name, arguments, {}, "ok", {"devices": self.devices}
                )
            if operation == EVENT_OPERATION:
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "ok",
                    {
                        "events": [{
                            "name": "switch",
                            "value": "off",
                            "date": "2026-08-01T14:55:00.000+0100",
                            "isStateChange": True,
                        }]
                    },
                )
            raise AssertionError(f"unexpected operation: {operation}")

    mcp = PrefixedHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "tab s9"})

    assert result.is_error is False
    assert result.data["deviceId"] == "6916"
    assert result.data["label"] == "Block Tab-S9-FE"
    inventory_calls = [
        (name, arguments)
        for name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
    ]
    assert inventory_calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert mcp.calls[-1][1]["args"]["deviceId"] == "6916"


@pytest.mark.asyncio
async def test_unresolved_device_never_reads_event_history():
    mcp = HistoryMCP(resolve=False)
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "missing lamp"})

    assert result.is_error is True
    assert result.data["success"] is False
    assert all(
        arguments.get("tool") != EVENT_OPERATION
        for _, arguments in mcp.calls
    )


class StringFalseHistoryMCP(HistoryMCP):
    """Reproduces a live-plausible partial-failure shape: the event-history
    read reports `"success": "false"` (string, not JSON boolean) instead of
    an explicit is_error transport failure. Both history() and
    location_events() used to check this with a strict `is False` identity
    comparison, which never matches a string -- so this was silently
    treated as a successful, empty-events read instead of a failure.
    """

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            return await super().call_tool(name, arguments)
        if operation == EVENT_OPERATION:
            return MCPToolResult(
                name, arguments, {}, "device unreachable",
                {"success": "false", "error": "device unreachable"},
            )
        raise AssertionError(f"unexpected operation: {operation}")


@pytest.mark.asyncio
async def test_history_treats_a_string_false_success_flag_as_failure():
    mcp = StringFalseHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "living room light 1"})

    assert result.is_error is True
    assert result.data["success"] is False


@pytest.mark.asyncio
async def test_location_events_treats_a_string_false_success_flag_as_failure():
    mcp = StringFalseHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.location_events({})

    assert result.is_error is True
    assert result.data["success"] is False


class LocationEventsMCP:
    """Fake MCP reproducing the confirmed-live location-events response
    shape: hub_list_device_events called with both deviceId and appId
    omitted returns "source": "location" and mode-change rows.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == EVENT_OPERATION:
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "source": "location",
                    "events": [
                        {
                            "name": "mode",
                            "value": "Afternoon",
                            "description": "Hub C8 Pro is now in Afternoon mode",
                            "date": "2026-08-10T12:00:02.375+0100",
                            "type": "LOCATION_MODE_CHANGE",
                            "isStateChange": True,
                        },
                        {
                            "name": "sunriseSunsetUpdated",
                            "value": "",
                            "date": "2026-08-10T12:00:02.228+0100",
                            "type": "API",
                            "isStateChange": True,
                        },
                    ],
                    "count": 2,
                },
            )
        raise AssertionError(f"unexpected operation: {operation}")


@pytest.mark.asyncio
async def test_location_events_omits_device_and_app_id():
    """The upstream contract for location events is a hub_list_device_events
    call with BOTH deviceId and appId omitted -- this must never resolve or
    attach any device target, unlike history().
    """

    mcp = LocationEventsMCP()
    receipts = []
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: receipts.append((args, kwargs)),
    )

    result = await service.location_events({"hours_back": 48, "limit": 20})

    assert result.is_error is False
    assert result.data["success"] is True
    assert result.data["hoursBack"] == 48
    assert result.data["count"] == 2
    assert mcp.calls[-1] == (
        DEVICE_GATEWAY,
        {"tool": EVENT_OPERATION, "args": {"hoursBack": 48, "limit": 20}},
    )
    assert "deviceId" not in mcp.calls[-1][1]["args"]
    assert "appId" not in mcp.calls[-1][1]["args"]
    assert receipts[-1][1]["evidence_kind"] == "authoritative_location_event_history"
    assert receipts[-1][1]["success"] is True


@pytest.mark.asyncio
async def test_location_events_bounds_hours_back_and_limit():
    mcp = LocationEventsMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.location_events({"hours_back": 9999, "limit": 9999})

    assert result.data["hoursBack"] == 168
    assert mcp.calls[-1][1]["args"]["limit"] == 50


def test_location_events_tool_name_is_distinct_from_device_history_tool():
    assert LOCATION_EVENTS_TOOL == "homebrain_location_events"
    assert LOCATION_EVENTS_TOOL != DEVICE_HISTORY_TOOL


def test_history_tool_is_a_bounded_read_only_local_schema():
    tool = device_history_tool()

    assert tool.name == DEVICE_HISTORY_TOOL
    assert tool.input_schema["required"] == ["name"]
    assert tool.input_schema["properties"]["hours_back"]["maximum"] == 168
    assert tool.input_schema["properties"]["limit"]["maximum"] == 50
    assert classify_tool_effect(tool, {"name": "lamp"}) is ToolEffect.READ
    assert EVIDENCE_KINDS[DEVICE_HISTORY_TOOL] == (
        "deterministic_device_event_history"
    )


def test_history_presenter_reports_transitions_without_inventing_cause():
    message = present_tool_result(
        DEVICE_HISTORY_TOOL,
        {
            "success": True,
            "label": "Livingroom Light 1",
            "hoursBack": 24,
            "count": 1,
            "events": [{
                "name": "switch",
                "value": "off",
                "date": "2026-08-01T12:30:00.000+0100",
                "description": "Livingroom Light 1 was turned off",
            }],
        },
    )

    assert "Recent history for **Livingroom Light 1**" in message
    assert "**switch: off**" in message
    assert "do not by themselves identify what caused them" in message


def test_history_presenter_renders_natural_local_time_not_raw_iso():
    """Live-observed gap: the general device-history answer rendered the
    raw Hubitat ISO timestamp verbatim ("2026-08-10T15:04:12.318+0100")
    instead of a human-readable local time, unlike every other
    history-style presenter in this codebase (contact_history_queries.py,
    location_event_queries.py), which already go through
    natural_datetime.format_natural_datetime.
    """

    message = present_tool_result(
        DEVICE_HISTORY_TOOL,
        {
            "success": True,
            "label": "Front Door",
            "hoursBack": 24,
            "count": 1,
            "events": [{
                "name": "contact",
                "value": "closed",
                "date": "2026-08-10T15:04:12.318+0100",
                "description": "Front Door contact is closed (raw:true)",
            }],
        },
    )

    assert "2026-08-10T15:04:12.318+0100" not in message
    assert "3:04 pm on Monday 10 August 2026" in message


def test_empty_history_is_explicit_about_window_and_attribute():
    message = present_tool_result(
        DEVICE_HISTORY_TOOL,
        {
            "success": True,
            "label": "Hallway Motion",
            "hoursBack": 6,
            "attribute": "motion",
            "events": [],
        },
    )

    assert message == (
        "No motion events were reported for **Hallway Motion** in the last "
        "6 hours."
    )
