from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from home_snapshot import HomeSnapshotService
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class TruthfulHomeSnapshotService(HomeSnapshotService):
    """Home Snapshot that never turns missing state coverage into factual zeros."""

    async def answer(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        coverage_errors: list[str] = []

        devices, diagnostics, hub_status = await self._load_sources(
            force=False,
            coverage_errors=coverage_errors,
        )
        snapshot = self._build_snapshot(devices, diagnostics, hub_status)

        recovery_attempted = False
        if devices and snapshot.get("states_read", 0) == 0:
            recovery_attempted = True
            recovery_errors: list[str] = []
            recovered_devices, recovered_diagnostics, recovered_hub = await self._load_sources(
                force=True,
                coverage_errors=recovery_errors,
            )
            recovered_snapshot = self._build_snapshot(
                recovered_devices,
                recovered_diagnostics,
                recovered_hub,
            )
            if recovered_snapshot.get("states_read", 0) > 0:
                devices = recovered_devices
                diagnostics = recovered_diagnostics
                hub_status = recovered_hub
                snapshot = recovered_snapshot
                coverage_errors = recovery_errors
            else:
                coverage_errors.extend(
                    error for error in recovery_errors if error not in coverage_errors
                )
                coverage_errors.append(
                    "device states: Hubitat returned device records without readable attributes"
                )

        states_available = snapshot.get("states_read", 0) > 0
        deterministic = (
            self._deterministic_summary(snapshot)
            if states_available
            else (
                "I could not verify current motion, light or switch states because the "
                "Hubitat device response contained no readable state records. No zero "
                "counts should be treated as real until the state scan recovers."
            )
        )

        ai_message: str | None = None
        ai_error: str | None = None
        model: str | None = None
        synthesis_started = time.perf_counter()
        if self.ai_enabled and states_available:
            try:
                ai_message, model = await asyncio.wait_for(
                    self._natural_summary(snapshot, deterministic),
                    timeout=self.ai_timeout_seconds + 1.0,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                ai_error = str(exc) or exc.__class__.__name__
        synthesis_ms = round((time.perf_counter() - synthesis_started) * 1000)

        message = ai_message or deterministic
        display = display_payload(
            "home-snapshot",
            "Home right now",
            subtitle=self._truthful_subtitle(
                snapshot,
                coverage_errors,
                states_available=states_available,
            ),
            metrics=self._truthful_metrics(snapshot, states_available=states_available),
            items=self._display_items(snapshot) if states_available else [],
            note=self._truthful_coverage_note(
                snapshot,
                coverage_errors,
                states_available=states_available,
                recovery_attempted=recovery_attempted,
            ),
        )
        display["summary"] = message

        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": bool(devices) and states_available,
            "route": (
                "ollama+snapshot"
                if ai_message
                else "mcp-snapshot"
                if states_available
                else "mcp-snapshot-state-unavailable"
            ),
            "intent": "home-snapshot",
            "message": message,
            "model": model,
            "display": display,
            "snapshot": snapshot,
            "coverage_complete": states_available and not coverage_errors,
            "coverage_errors": coverage_errors,
            "state_recovery_attempted": recovery_attempted,
            "synthesis_error": ai_error,
            "phase_ms": {
                "snapshot_and_hub": max(0, elapsed - synthesis_ms),
                "synthesis": synthesis_ms,
            },
            "elapsed_ms": elapsed,
            "technical": safe_debug(
                {
                    "snapshot": snapshot,
                    "coverage_errors": coverage_errors,
                    "state_recovery_attempted": recovery_attempted,
                    "ollama_synthesis_error": ai_error,
                    "model": model,
                }
            ),
        }

    async def _load_sources(
        self,
        *,
        force: bool,
        coverage_errors: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        devices_task = asyncio.create_task(
            self.device_index.enriched_devices(force=force)
        )
        diagnostics_task = asyncio.create_task(
            self.device_index.diagnostics(force=force)
        )
        hub_task = asyncio.create_task(self._hub_status())

        try:
            devices = list(await devices_task)
        except Exception as exc:
            devices = []
            coverage_errors.append(f"devices: {exc}")

        try:
            diagnostics = await diagnostics_task
        except Exception as exc:
            diagnostics = {}
            coverage_errors.append(f"index: {exc}")

        try:
            hub_status = await hub_task
            if hub_status.get("error"):
                coverage_errors.append(f"hub: {hub_status['error']}")
        except Exception as exc:
            hub_status = {"items": [], "error": str(exc)}
            coverage_errors.append(f"hub: {exc}")

        return devices, diagnostics, hub_status

    @staticmethod
    def _truthful_metrics(
        snapshot: dict[str, Any],
        *,
        states_available: bool,
    ) -> list[dict[str, Any]]:
        if not states_available:
            return [
                {"label": "Motion active", "value": "—", "icon": "🏃"},
                {"label": "Lights on", "value": "—", "icon": "💡"},
                {"label": "Other devices on", "value": "—", "icon": "🔌"},
                {"label": "Needs attention", "value": "—", "icon": "⚠️"},
            ]
        return [
            {
                "label": "Motion active",
                "value": str(len(snapshot["motion_active"])),
                "icon": "🏃",
            },
            {
                "label": "Lights on",
                "value": str(len(snapshot["lights_on"])),
                "icon": "💡",
            },
            {
                "label": "Other devices on",
                "value": str(len(snapshot["devices_on"])),
                "icon": "🔌",
            },
            {
                "label": "Needs attention",
                "value": str(len(snapshot["attention"])),
                "icon": "⚠️",
            },
        ]

    @staticmethod
    def _truthful_subtitle(
        snapshot: dict[str, Any],
        errors: list[str],
        *,
        states_available: bool,
    ) -> str:
        age = snapshot.get("index_age_seconds")
        freshness = (
            "Updated just now"
            if age is None or float(age) < 5
            else f"Updated {float(age):.0f}s ago"
        )
        if not states_available:
            coverage = "state scan unavailable"
        else:
            coverage = "scan incomplete" if errors else "live Hubitat MCP"
        return (
            f"{freshness} · {coverage} · "
            f"{snapshot['selected_devices']} selected devices checked"
        )

    @staticmethod
    def _truthful_coverage_note(
        snapshot: dict[str, Any],
        errors: list[str],
        *,
        states_available: bool,
        recovery_attempted: bool,
    ) -> str:
        if not states_available:
            note = (
                f"Hubitat returned {snapshot['selected_devices']} selected device records but "
                "none contained readable live attributes. HomeBrain did not convert missing "
                "states into zero motion or zero lights."
            )
            if recovery_attempted:
                note += " One forced state refresh was attempted."
        else:
            note = (
                f"Live states were available for {snapshot['states_read']} of "
                f"{snapshot['selected_devices']} selected devices. "
                f"{len(snapshot['background_on'])} always-on/background device"
                f"{'' if len(snapshot['background_on']) == 1 else 's'} were omitted "
                "from the main device-on list."
            )
        if errors:
            note += " Incomplete sources: " + "; ".join(errors) + "."
        return note


def install_truthful_home_snapshot(
    application: Any,
    device_index: Any,
    *,
    ai_enabled: bool = True,
    ai_timeout_seconds: float = 12.0,
    max_items_per_group: int = 8,
) -> TruthfulHomeSnapshotService:
    original_ask: AskHandler = application.ask
    service = TruthfulHomeSnapshotService(
        application,
        device_index,
        ai_enabled=ai_enabled,
        ai_timeout_seconds=ai_timeout_seconds,
        max_items_per_group=max_items_per_group,
    )

    async def ask_with_home_snapshot(request: Any) -> dict[str, Any]:
        if service.matches(str(request.query or "")):
            answer = await service.answer(str(request.query or ""))
            answer.setdefault("version", application.VERSION)
            return answer
        return await original_ask(request)

    application.ask = ask_with_home_snapshot
    application.home_snapshot = service
    return service


__all__ = ["TruthfulHomeSnapshotService", "install_truthful_home_snapshot"]
