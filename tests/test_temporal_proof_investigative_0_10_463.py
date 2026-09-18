from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from history_temporal_analysis import history_temporal_evidence_details  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402


@dataclass
class FakeOutcome:
    message: str
    evidence: list[dict[str, Any]]
    request_class: str = "live-read"
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    automation_items: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "outcome": "success",
            "counters": {"model_rounds": 2},
            "timings_ms": {},
        }
    )


def _history_receipt(
    label: str = "Bedroom 3 Light",
    *,
    attribute: str = "switch",
    intervals: int = 5,
    active_state: str = "on",
    inactive_state: str = "off",
) -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": label,
            "attribute": attribute,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "activeState": active_state,
                "inactiveState": inactive_state,
                "intervalCount": intervals,
                "totalActiveDuration": "1h 44m" if intervals else "0s",
                "totalActiveSeconds": 6237 if intervals else 0,
                "longestActiveDuration": "1h 27m" if intervals else "0s",
                "longestActiveSeconds": 5234 if intervals else 0,
                "coverage": "partial",
                "totalIsLowerBound": False,
                "durationReliability": "unverified-event-stream",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "windowed": True,
                "windowLabel": "last night",
                "boundaryStateKnown": False,
            },
        },
    }


def test_temporal_evidence_details_include_bounded_interval_proof() -> None:
    result = {
        "label": "Bedroom 3 Light",
        "attribute": "switch",
        "hoursBack": 24,
        "temporalAnalysis": {
            "activeState": "on",
            "inactiveState": "off",
            "intervalCount": 2,
            "intervals": [
                {
                    "start": "2026-09-18T00:02:53+01:00",
                    "end": "2026-09-18T01:30:07+01:00",
                    "startNatural": "12:02 am",
                    "endNatural": "1:30 am",
                    "durationSeconds": 5234,
                    "duration": "1h 27m",
                    "clippedAtWindowStart": False,
                    "clippedAtWindowEnd": False,
                },
                {
                    "start": "2026-09-18T01:32:51+01:00",
                    "end": "2026-09-18T01:45:02+01:00",
                    "durationSeconds": 731,
                    "duration": "12m",
                },
            ],
            "totalActiveSeconds": 5965,
            "totalActiveDuration": "1h 39m",
            "coverage": "partial",
            "sourceIntegrityVerified": False,
            "durationReliability": "unverified-event-stream",
        },
    }

    details = history_temporal_evidence_details(result)
    assert details is not None
    temporal = details["temporalAnalysis"]
    assert temporal["observedIntervals"][0]["durationSeconds"] == 5234
    assert temporal["observedIntervals"][1]["start"].startswith("2026-09-18T01:32:51")
    assert temporal["observedIntervalsTruncated"] is False


def test_interval_cardinality_guard_corrects_exhaustive_two_period_claim() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "Bedroom 3 Light was on during two separate periods last night. "
                "The Late Night mode change is only a correlation."
            ),
            evidence=[_history_receipt()],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert "5 observed bounded on intervals" in response["message"]
    assert "two separate periods" not in response["message"]
    assert response["message"].endswith(
        "The Late Night mode change is only a correlation."
    )
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_interval_cardinality_guard_allows_nonexhaustive_longest_subset() -> None:
    message = (
        "The two longest periods were 00:02-01:30 and 01:32-01:45. "
        "There were five observed intervals in total."
    )
    response = build_agent_response(
        FakeOutcome(message=message, evidence=[_history_receipt()]),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )
    assert response["message"] == message


def test_interval_cardinality_guard_does_not_rewrite_unrelated_times_count() -> None:
    message = (
        "Late Night mode changed two times during the investigation. "
        "Bedroom 3 Light had five observed intervals in total."
    )
    response = build_agent_response(
        FakeOutcome(message=message, evidence=[_history_receipt()]),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert response["message"] == message
    assert response["evidence"][0]["details"].get("finalAnswerCorrectionApplied") is not True


def test_unverified_zero_motion_data_claim_is_rewritten_without_erasing_subject_history() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "Bedroom 3 Light has several recorded intervals. "
                "There is no recorded motion data for the Bedroom 3 sensors."
            ),
            evidence=[
                _history_receipt(),
                _history_receipt(
                    "Bedroom 3 Soft Sensor",
                    attribute="motion",
                    intervals=0,
                    active_state="active",
                    inactive_state="inactive",
                ),
            ],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert response["message"].startswith(
        "Bedroom 3 Light has several recorded intervals."
    )
    assert "No bounded active interval was established for Bedroom 3 Soft Sensor" in response["message"]
    assert "does not prove it stayed inactive" in response["message"]
    assert "no recorded motion data" not in response["message"].casefold()


def _tool(name: str, description: str, schema: dict[str, Any] | None = None) -> MCPTool:
    return MCPTool(name, description, schema or {"type": "object"})


def test_gateway_operation_guard_rejects_operation_not_listed_by_gateway() -> None:
    diagnostics = _tool(
        "hub_read_diagnostics",
        "Read diagnostics via hub_get_logs, hub_get_jobs, hub_get_performance_stats.",
    )
    catalog = ToolDiscoveryCatalog([diagnostics])

    error = catalog.gateway_operation_error(
        "hub_read_diagnostics",
        {"tool": "hub_list_apps", "args": {"scope": "instances"}},
    )

    assert error is not None
    assert "hub_list_apps" in error
    assert "not listed" in error


def test_gateway_operation_guard_uses_live_discovery_mapping() -> None:
    diagnostics = _tool(
        "hub_read_diagnostics",
        "Read diagnostics via hub_get_logs, hub_get_jobs.",
    )
    apps = _tool(
        "hub_read_apps_code",
        "Read installed apps via hub_list_apps, hub_get_app_config.",
    )
    search = _tool("hub_search_tools", "search")
    catalog = ToolDiscoveryCatalog([search, diagnostics, apps])
    catalog.expand(
        MCPToolResult(
            "hub_search_tools",
            {},
            {},
            "",
            {
                "results": [
                    {"tool": "hub_list_apps", "gateway": "hub_read_apps_code"}
                ]
            },
        )
    )

    error = catalog.gateway_operation_error(
        "hub_read_diagnostics",
        {"tool": "hub_list_apps"},
    )
    assert error is not None
    assert "hub_read_apps_code" in error



class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeAI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return _FakeResponse(next(self.responses))

    async def aclose(self):
        return None


class _InvestigativeMCP:
    def __init__(self):
        self.devices = [
            {
                "id": "1",
                "name": "Bedroom 3 Light",
                "label": "Bedroom 3 Light",
                "room": "Bedroom 3",
                "capabilities": ["Switch", "Light"],
                "attributes": {"switch": "off"},
                "commands": ["on", "off"],
            },
            {
                "id": "2",
                "name": "Bedroom 3 Sensor T1",
                "label": "Bedroom 3 Sensor T1",
                "room": "Bedroom 3",
                "capabilities": ["IlluminanceMeasurement", "TemperatureMeasurement"],
                "attributes": {"illuminance": 124, "temperature": 22.0},
                "commands": [],
            },
        ]
        self.calls = []

    async def list_tools(self):
        return []

    async def get_cached_devices(self):
        return list(self.devices)

    def peek_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if name == "hub_read_devices" and operation == "hub_list_devices":
            needle = str((arguments.get("args") or {}).get("labelFilter") or "").casefold()
            matches = [
                device for device in self.devices
                if needle in str(device["label"]).casefold()
            ]
            return MCPToolResult(name, arguments, {}, "ok", {"devices": matches})
        if name == "hub_read_devices" and operation == "hub_list_device_events":
            device_id = str((arguments.get("args") or {}).get("deviceId") or "")
            if device_id == "1":
                events = [
                    {
                        "name": "switch",
                        "value": "off",
                        "date": "2026-09-18T01:45:02+01:00",
                        "isStateChange": True,
                    },
                    {
                        "name": "switch",
                        "value": "on",
                        "date": "2026-09-18T01:32:51+01:00",
                        "isStateChange": True,
                    },
                ]
            else:
                events = [
                    {
                        "name": "illuminance",
                        "value": "124",
                        "date": "2026-09-18T01:33:00+01:00",
                        "isStateChange": True,
                    }
                ]
            return MCPToolResult(name, arguments, {}, "ok", {"events": events})
        raise AssertionError((name, arguments))


def _fc(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"function": {"name": name, "arguments": arguments}}


def test_placeholder_for_async_import():
    # Keeps imports local to this release test and avoids changing older fixtures.
    from homebrain_agent import UnifiedMCPAgent  # noqa: F401


import pytest


@pytest.mark.asyncio
async def test_investigative_related_history_requires_explicit_attribute_before_execution() -> None:
    from homebrain_agent import UnifiedMCPAgent

    mcp = _InvestigativeMCP()
    ai = _FakeAI(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        _fc(
                            "homebrain_device_history",
                            {
                                "name": "Bedroom 3 Light",
                                "attribute": "switch",
                                "hours_back": 24,
                            },
                        )
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        _fc(
                            "homebrain_device_history",
                            {
                                "name": "Bedroom 3 Sensor T1",
                                "hours_back": 24,
                            },
                        )
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        _fc(
                            "homebrain_device_history",
                            {
                                "name": "Bedroom 3 Sensor T1",
                                "attribute": "illuminance",
                                "hours_back": 24,
                            },
                        )
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "The light history is established; illuminance was checked "
                        "separately, but it does not establish the cause."
                    ),
                }
            },
        ]
    )
    agent = UnifiedMCPAgent(mcp, "key", "gemma4:31b", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Why was Bedroom 3 Light on last night?"
    )

    assert outcome.metrics["counters"]["investigative_attribute_required"] == 1
    sensor_event_calls = [
        arguments
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
        and arguments.get("tool") == "hub_list_device_events"
        and str((arguments.get("args") or {}).get("deviceId")) == "2"
    ]
    assert len(sensor_event_calls) == 1
    retry_prompt = "\n".join(
        str(message.get("content") or "")
        for message in ai.requests[2][1]["json"]["messages"]
    )
    assert "requires an explicit attribute" in retry_prompt
    assert "attribute=..." in retry_prompt
