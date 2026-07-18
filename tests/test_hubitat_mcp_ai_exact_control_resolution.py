from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_index import (  # noqa: E402
    CapabilityDeviceRouter,
    FastFallbackRouter,
)


class FakeIndex:
    def __init__(self, exact: dict[str, Any] | None) -> None:
        self.exact = exact
        self.calls: list[tuple[str, bool]] = []

    async def exact_device(self, requested_name: str):
        return self.exact, [] if self.exact else ["Dehumidifier 2"]

    async def capability_result(self, capability: str, *, detailed: bool, force: bool = False):
        self.calls.append((capability, force))
        return {"capability": capability, "force": force}

    async def summary_result(self, *, force: bool = False):
        self.calls.append(("summary", force))
        return {"summary": True, "force": force}


def make_router(index: FakeIndex) -> FastFallbackRouter:
    router = object.__new__(FastFallbackRouter)
    router.device_index = index
    router._force_fresh_control_reads = False
    router.control_verification_timeout_seconds = 7.0
    router.control_verification_initial_delay_seconds = 0.2
    return router


def test_exact_index_alias_executes_without_fuzzy_confirmation(monkeypatch):
    observed: dict[str, Any] = {}

    async def parent_control(self, requested_name: str, action: str):
        observed.update(
            {
                "requested_name": requested_name,
                "action": action,
                "fresh": self._force_fresh_control_reads,
            }
        )
        return {"success": True, "intent": "fallback-device-control-confirmed"}

    monkeypatch.setattr(CapabilityDeviceRouter, "_control_device", parent_control)
    router = make_router(FakeIndex({"id": "22", "label": "Dehumidifier 2"}))

    answer = asyncio.run(router._control_device("dehumidifier two", "off"))

    assert observed == {
        "requested_name": "Dehumidifier 2",
        "action": "off",
        "fresh": True,
    }
    assert answer["device_index_exact_match"] is True
    assert answer["requested_name"] == "dehumidifier two"
    assert answer["resolved_device_name"] == "Dehumidifier 2"
    assert router._force_fresh_control_reads is False


def test_ambiguous_index_name_is_not_silently_rewritten(monkeypatch):
    observed: dict[str, Any] = {}

    async def parent_control(self, requested_name: str, action: str):
        observed["requested_name"] = requested_name
        return {"success": False, "confirmation_required": True}

    monkeypatch.setattr(CapabilityDeviceRouter, "_control_device", parent_control)
    router = make_router(FakeIndex(None))

    answer = asyncio.run(router._control_device("dehumidifier", "off"))

    assert observed["requested_name"] == "dehumidifier"
    assert "device_index_exact_match" not in answer
    assert router._force_fresh_control_reads is False


def test_all_control_reads_bypass_the_device_index_cache():
    index = FakeIndex(None)
    router = make_router(index)
    router._force_fresh_control_reads = True

    result = asyncio.run(router._live_devices("Switch"))

    assert result == {"capability": "Switch", "force": True}
    assert index.calls == [("Switch", True)]
