"""0.18.47: Internet access semantics must not contradict live advertised commands.

Device 6923 (Internet room) reports on/off AND blockInternet, allowInternet,
addTime and resetUsage. The role of the latter commands is not yet proven.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from tool_registry import device_resolver_tool  # noqa: E402


def test_resolver_grounds_internet_guidance_in_actual_capabilities():
    tool = device_resolver_tool()
    body = tool.description
    assert "Internet room" in body
    assert "switch=off (access blocked)" in body
    assert "switch=on (access allowed)" in body
    assert "blockInternet" in body
    assert "allowInternet" in body
    assert "addTime" in body
    assert "resetUsage" in body
    assert "Some Internet-room drivers ALSO advertise" in body
    assert "parameters, side effects, usage accounting and persistence" in body
    assert "Read-only diagnostic requests must NEVER call control commands" in body


def test_resolver_command_requirement_does_not_deny_advertised_methods():
    schema = device_resolver_tool().input_schema["properties"]["required_command"]
    description = schema["description"]
    assert "blockInternet" in description
    assert "observed on that exact device" in description
    assert "never presume" in description
    assert "matching excludes devices that do not advertise" in description


def test_resolver_does_not_claim_optional_commands_always_exist():
    text = device_resolver_tool().description
    assert "Do not assume all Internet controls have" in text
    assert "Internet blocking is a semantic intent" in text
    assert "The returned device ID, room and actual advertised commands are evidence" in text
