from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_level_verified import FastVerifiedControlAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def result(data: Any, *, name: str = "hub_list_devices", error: bool = False, text: str = ""):
    return MCPToolResult(
        name=name,
        arguments={},
        raw={"isError": error},
        text=text,
        data=data,
        is_error=error,
    )


def device(level: float | None = 80.0) -> dict[str, Any]:
    states: dict[str, Any] = {"switch": "on"}
    if level is not None:
        states["level"] = level
    return {
        "id": "7057",
        "label": "Bedroom 1 Light",
        "name": "Bedroom 1 Light",
        "room": "Bedroom 1",
        "disabled": False,
        "currentStates": states,
    }


class FakeApplication:
    ollama = SimpleNamespace()

    @staticmethod
    def option_bool(name: str, default: bool = False) -> bool:
        if name == "ollama_enabled":
            return False
        return default


class FakeIndex:
    def __init__(self, fallback: "FakeFallback") -> None:
        self.fallback = fallback

    async def summary_devices(self, force: bool = False):
        return [device(self.fallback.level if self.fallback.inventory_has_level else None)]

    async def capability_devices(self, capability: str, force: bool = False, detailed: bool = False):
        if capability == "Switch":
            return [device(self.fallback.level)]
        return []


class FakeCommandClient:
    def __init__(
        self,
        fallback: "FakeFallback",
        *,
        wait_for_supported: bool,
        command_applies: bool,
    ) -> None:
        self.fallback = fallback
        self.wait_for_supported = wait_for_supported
        self.command_applies = command_applies

    async def get_tool(self, name: str):
        assert name == "hub_call_device_command"
        properties: dict[str, Any] = {
            "deviceId": {"type": "string"},
            "command": {"type": "string"},
            # This mirrors the MCP Rule Server's authoritative schema.
            "parameters": {
                "type": "array",
                "items": {"type": "string"},
            },
        }
        if self.wait_for_supported:
            properties["waitFor"] = {"type": "object"}
        return SimpleNamespace(
            input_schema={
                "type": "object",
                "properties": properties,
                "required": ["deviceId", "command"],
            }
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        assert name == "hub_call_device_command"
        self.fallback.commands.append(dict(arguments))

        canonical = arguments.get("parameters")
        requested = float(canonical[0]) if isinstance(canonical, list) and canonical else None
        if self.command_applies and requested is not None:
            self.fallback.level = requested

        data: dict[str, Any] = {
            "success": True,
            "device": "Bedroom 1 Light",
            "command": "setLevel",
            "parameters": canonical,
            "state": {"level": {"value": self.fallback.level}},
        }
        if self.wait_for_supported:
            expected = str((arguments.get("waitFor") or {}).get("expectedValue") or "")
            converged = requested is not None and str(int(self.fallback.level)) == expected
            data["waitFor"] = {
                "attribute": "level",
                "expected": expected,
                "converged": converged,
                "finalValue": str(int(self.fallback.level)),
                "elapsedMs": 180 if converged else 3000,
                **({} if converged else {"timedOut": True, "transitioning": False}),
            }
        return result(data, name=name)

    async def invalidate(self, category: str):
        self.fallback.invalidations.append(category)
        return 1


class FakeFallback:
    def __init__(
        self,
        *,
        verification_mode: str,
        wait_for_supported: bool = True,
        command_applies: bool = True,
        inventory_has_level: bool = True,
    ) -> None:
        self.verification_mode = verification_mode
        self.inventory_has_level = inventory_has_level
        self.level = 80.0
        self.commands: list[dict[str, Any]] = []
        self.invalidations: list[str] = []
        self.reads: list[tuple[str | None, bool]] = []
        self.control_verification_initial_delay_seconds = 0.01
        self.client = FakeCommandClient(
            self,
            wait_for_supported=wait_for_supported,
            command_applies=command_applies,
        )

    async def _direct_fresh_devices(self, capability: str | None = None, detailed: bool = False):
        self.reads.append((capability, detailed))
        if capability == "Switch":
            return result({"devices": [device(self.level)]})

        if self.verification_mode == "switchlevel":
            rows = [device(self.level)] if capability == "SwitchLevel" and not detailed else []
        elif self.verification_mode == "summary":
            rows = [device(self.level)] if capability is None and not detailed else []
        else:
            rows = [device(None)] if capability is None and not detailed else []
        return result({"devices": rows})

    @staticmethod
    def _device_rows(value: Any):
        if isinstance(value, dict):
            value = value.get("devices") or []
        return [item for item in value if isinstance(item, dict)]

    async def _control_device(self, label: str, action: str):
        raise AssertionError("The level test must not use the on/off controller")


def make_agent(
    tmp_path: Path,
    *,
    verification_mode: str = "switchlevel",
    wait_for_supported: bool = True,
    command_applies: bool = True,
    inventory_has_level: bool = True,
):
    fallback = FakeFallback(
        verification_mode=verification_mode,
        wait_for_supported=wait_for_supported,
        command_applies=command_applies,
        inventory_has_level=inventory_has_level,
    )
    index = FakeIndex(fallback)
    agent = FastVerifiedControlAgent(
        FakeApplication(),
        index,
        fallback,
        alias_path=str(tmp_path / "aliases.json"),
        level_verification_timeout_seconds=3,
        level_verification_poll_seconds=0.1,
    )
    return agent, fallback


def request(query: str):
    return SimpleNamespace(query=query, session_id="level-test", history=[])


async def unused(_request: Any):
    raise AssertionError("Exact level controls must not reach the AI or legacy planner")


def test_exact_level_uses_canonical_string_parameters_and_server_wait_for(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    answer = asyncio.run(
        agent.answer(request("set Bedroom 1 Light to 30%"), unused)
    )

    assert answer["success"] is True
    assert answer["answered_by"] == "Deterministic Control Agent + verified Hubitat MCP"
    assert len(fallback.commands) == 1
    command = fallback.commands[0]
    assert command["deviceId"] == "7057"
    assert command["command"] == "setLevel"
    assert command["parameters"] == ["30"]
    assert "params" not in command
    assert command["waitFor"] == {
        "attribute": "level",
        "expectedValue": "30",
        "comparator": "eq",
        "timeoutMs": 3000,
        "pollIntervalMs": 100,
    }
    # One selected-device preflight read; successful server-side waitFor needs no
    # separate post-command catalogue read.
    assert fallback.reads == [("Switch", False)]
    assert "30%" in answer["message"]
    assert answer["tools_used"][0]["parameter_field"] == "parameters"
    assert answer["tools_used"][0]["verification_source"] == "hub_call_device_command.waitFor"


def test_server_wait_for_timeout_reports_stable_old_level_without_resending(tmp_path: Path):
    agent, fallback = make_agent(tmp_path, command_applies=False)

    answer = asyncio.run(
        agent.answer(request("set Bedroom 1 Light to 30%"), unused)
    )

    assert answer["success"] is False
    assert len(fallback.commands) == 1
    assert fallback.commands[0]["parameters"] == ["30"]
    assert "last reading was 80%" in answer["message"]
    # After the MCP server's own three-second wait, only one independent fresh
    # strategy chain is allowed; the command is never blindly repeated.
    assert fallback.reads[:2] == [("Switch", False), ("SwitchLevel", False)]


def test_older_server_without_wait_for_uses_bounded_local_verification(tmp_path: Path):
    agent, fallback = make_agent(
        tmp_path,
        wait_for_supported=False,
        verification_mode="summary",
    )

    answer = asyncio.run(
        agent.answer(request("set Bedroom 1 Light to 45%"), unused)
    )

    assert answer["success"] is True
    assert fallback.commands == [
        {"deviceId": "7057", "command": "setLevel", "parameters": ["45"]}
    ]
    assert fallback.reads[:3] == [
        ("Switch", False),
        ("SwitchLevel", False),
        (None, False),
    ]
    assert "45%" in answer["message"]


def test_missing_level_field_returns_quickly_on_server_without_wait_for(tmp_path: Path):
    agent, fallback = make_agent(
        tmp_path,
        wait_for_supported=False,
        verification_mode="missing",
        inventory_has_level=False,
    )

    started = time.monotonic()
    answer = asyncio.run(
        agent.answer(request("set Bedroom 1 Light to 55%"), unused)
    )
    elapsed = time.monotonic() - started

    assert answer["success"] is False
    assert answer["intent"] == "control-agent-unresolved"
    assert "does not support set_level" in answer["message"]
    assert fallback.commands == []
    assert elapsed < 1.2
    assert len(fallback.reads) <= 8


def test_release_wires_capability_aware_level_agent_without_ai_for_exact_commands():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "from control_agent_level_verified import install_control_agent" in entrypoint
    assert "control_level_verification_timeout_seconds" in entrypoint
    assert "control_level_verification_timeout_seconds: 3" in config
