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
        return {"capability": capability, "detailed": detailed, "force": force}

    async def summary_result(self, *, force: bool = False):
        self.calls.append(("summary", force))
        return {"summary": True, "force": force}


def make_router(index: FakeIndex) -> FastFallbackRouter:
    router = object.__new__(FastFallbackRouter)
    router.device_index = index
    router.control_verification_timeout_seconds = 7.0
    router.control_verification_initial_delay_seconds = 0.2
    return router


def test_exact_index_alias_executes_without_fuzzy_confirmation(monkeypatch):
    observed: dict[str, Any] = {}

    async def parent_control(self, requested_name: str, action: str):
        live = await self._live_devices("Switch")
        observed.update(
            {
                "requested_name": requested_name,
                "action": action,
                "fresh": live["force"],
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
    assert asyncio.run(router._live_devices("Switch"))["force"] is False


def test_ambiguous_index_name_is_not_silently_rewritten(monkeypatch):
    observed: dict[str, Any] = {}

    async def parent_control(self, requested_name: str, action: str):
        observed["requested_name"] = requested_name
        observed["fresh"] = (await self._live_devices("Switch"))["force"]
        return {"success": False, "confirmation_required": True}

    monkeypatch.setattr(CapabilityDeviceRouter, "_control_device", parent_control)
    router = make_router(FakeIndex(None))

    answer = asyncio.run(router._control_device("dehumidifier", "off"))

    assert observed == {"requested_name": "dehumidifier", "fresh": True}
    assert "device_index_exact_match" not in answer
    assert asyncio.run(router._live_devices("Switch"))["force"] is False


def test_all_index_read_paths_bypass_cache_during_control(monkeypatch):
    observed: dict[str, Any] = {}

    async def parent_control(self, requested_name: str, action: str):
        observed["live"] = await self._live_devices("Switch")
        observed["summary"] = await self._summary_devices()
        observed["detailed"] = await self._capability_devices(
            "Thermostat",
            detailed=True,
        )
        return {"success": True}

    monkeypatch.setattr(CapabilityDeviceRouter, "_control_device", parent_control)
    index = FakeIndex(None)
    router = make_router(index)

    asyncio.run(router._control_device("Test switch", "off"))

    assert observed["live"]["force"] is True
    assert observed["summary"]["force"] is True
    assert observed["detailed"]["force"] is True
    assert index.calls == [
        ("Switch", True),
        ("summary", True),
        ("Thermostat", True),
    ]


def test_concurrent_controls_keep_fresh_reads_isolated(monkeypatch):
    first_started = asyncio.Event()
    second_finished = asyncio.Event()
    observed: dict[str, bool] = {}

    async def parent_control(self, requested_name: str, action: str):
        if requested_name == "First switch":
            first_started.set()
            await second_finished.wait()
            observed["first_after_second"] = (
                await self._live_devices("Switch")
            )["force"]
        else:
            await first_started.wait()
            observed["second"] = (await self._live_devices("Switch"))["force"]
            second_finished.set()
        return {"success": True}

    monkeypatch.setattr(CapabilityDeviceRouter, "_control_device", parent_control)
    router = make_router(FakeIndex(None))

    async def run_controls():
        await asyncio.gather(
            router._control_device("First switch", "off"),
            router._control_device("Second switch", "off"),
        )
        observed["outside"] = (await router._live_devices("Switch"))["force"]

    asyncio.run(run_controls())

    assert observed == {
        "second": True,
        "first_after_second": True,
        "outside": False,
    }
