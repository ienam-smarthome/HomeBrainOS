"""v0.18.169 verified, targeted read: direct source + HTTP, never a write."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.targeted_status import (
    current_status_attributes, read_verified_target_status)
from investigation_v2.test_service import resolve_verified_device_subjects
from mcp_client import MCPTool, MCPToolResult


QUESTION = ("Read the current switch state and brightness level of "
            "Livingroom Light 2 directly from Hubitat. Do not change anything.")
# The real Hubitat inventory also contains two generic driver names
# 'switch'. The user means the ATTRIBUTE, not either socket.
TARGET = [
    {"id": "7828", "label": "Livingroom Light 2",
     "name": "Generic Dimmer", "roomName": "Living Room"},
    {"id": "7786", "label": "LivCAM socket", "name": "switch"},
    {"id": "7787", "label": "FP2 Livingroom socket", "name": "switch"},
]


def read_gateway(readonly=True, with_mode=True, expose=True):
    fields = {"deviceId": {"type": "string"}}
    required = ["deviceId"]
    if with_mode:
        fields["mode"] = {"type": "string", "enum": ["status"]}
        required.append("mode")
    return MCPTool("hub_read_devices", "read device", {
        "type": "object", "properties": {
            "tool": {"type": "string",
                     "enum": ["hub_get_device"] if expose else ["hub_list_device_events"]},
            "args": {"type": "object", "properties": fields,
                     "required": required, "additionalProperties": False},
        }, "required": ["tool", "args"], "additionalProperties": False,
    }, annotations={"readOnlyHint": readonly, "mutates": not readonly})


class FakeMCP:
    def __init__(self, *, device_id="7828", level=30, read_only=True,
                 expose=True, with_mode=True):
        self.device_id = device_id
        self.level = level
        self.calls = []
        self.gateway = read_gateway(read_only, with_mode, expose)

    async def list_tools(self):
        return [self.gateway]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        attributes = [{"name": "switch", "value": "on"}]
        if self.level is not None:
            attributes.append({"name": "level", "value": self.level})
        return MCPToolResult(name, arguments, raw={}, text="UNTRUSTED",
            data={"device": {"id": self.device_id, "attributes": attributes}},
            is_error=False)


def test_only_exact_verified_current_question_uses_targeted_path():
    assert current_status_attributes(QUESTION, ["Livingroom Light 2"]) == ("switch", "level")
    for q in (
        "Why did Livingroom Light 2 turn on and set brightness to 30?",
        "Set Livingroom Light 2 brightness to 30%.",
        "When was Livingroom Light 2 last set to 30%?",
        "Read the current switch state and brightness level of another device.",
    ):
        assert current_status_attributes(q, ["Livingroom Light 2"]) == ()
    assert current_status_attributes(QUESTION, ["Livingroom Light 2", "Hallway Light 1"]) == ()


@pytest.mark.asyncio
async def test_scoped_targeted_status_schema_and_no_untrusted_text():
    fake = FakeMCP()
    snapshot = await read_verified_target_status(fake, "7828")
    assert snapshot is not None
    row, provenance = snapshot
    assert row["attributes"] == {"switch": "on", "level": 30}
    assert provenance["scope"] == "single_verified_id"
    assert provenance["source_operation"] == "hub_get_device"
    assert len(fake.calls) == 1
    assert fake.calls[0][1] == {
        "tool": "hub_get_device", "args": {"deviceId": "7828", "mode": "status"}
    }
    assert "UNTRUSTED" not in json.dumps(snapshot)


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [
    {"device_id": "7829"}, {"read_only": False}, {"expose": False},
])
async def test_wrong_identity_and_write_capable_manifest_fail_closed(kwargs):
    fake = FakeMCP(**kwargs)
    assert await read_verified_target_status(fake, "7828") is None
    if kwargs.get("read_only") is False or kwargs.get("expose") is False:
        assert not fake.calls


@pytest.mark.asyncio
async def test_absent_brightness_is_not_inferred_from_previous_setlevel():
    fake = FakeMCP(level=None)
    result = await read_verified_target_status(fake, "7828")
    assert result is not None
    assert result[0]["attributes"] == {"switch": "on"}


def test_coordinated_attribute_phrase_anchors_one_full_named_device():
    ids, resolved, method = resolve_verified_device_subjects(QUESTION, TARGET)
    assert ids == ("7828",)
    assert resolved == [{"id": "7828", "label": "Livingroom Light 2"}]
    assert method == "question"
    assert current_status_attributes(QUESTION, [resolved[0]["label"]]) == (
        "switch", "level")
    with pytest.raises(ValueError, match="Ambiguous device name"):
        resolve_verified_device_subjects(
            "Check the switch and Livingroom Light 2.", TARGET)


@pytest.mark.asyncio
async def test_source_failure_reports_a_bounded_reason_without_source_data():
    diagnostics = {}
    fake = FakeMCP(device_id="7829")
    assert await read_verified_target_status(
        fake, "7828", diagnostics=diagnostics) is None
    assert diagnostics == {"outcome": "source_id_missing_or_mismatched",
                           "gateway_read_attempted": True}
    assert "UNTRUSTED" not in json.dumps(diagnostics)
    diagnostics.clear()
    fake = FakeMCP(expose=False)
    assert await read_verified_target_status(
        fake, "7828", diagnostics=diagnostics) is None
    assert diagnostics == {"outcome": "live_read_operation_unavailable"}
    assert not fake.calls

