from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import FastFallbackRouter as LiveFastFallbackRouter
from fast_fallback_live import live_attributes
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, first_mapping
from system_presenter_v2 import present_hub_info_v2


class FastFallbackRouter(LiveFastFallbackRouter):
    """Live MCP fallback with verified controls and explicit update reporting."""

    def __init__(
        self,
        *args: Any,
        control_verification_timeout_seconds: float = 7.0,
        control_verification_initial_delay_seconds: float = 0.2,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.control_verification_timeout_seconds = max(
            2.0,
            min(20.0, float(control_verification_timeout_seconds)),
        )
        self.control_verification_initial_delay_seconds = max(
            0.05,
            min(2.0, float(control_verification_initial_delay_seconds)),
        )

    async def _hub_info(self) -> dict[str, Any]:
        arguments = {
            "includeAppUpdate": True,
            "includeHealthAlerts": True,
        }
        result = await self.client.call_tool("hub_get_info", arguments)
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        # The MCP app-version check is asynchronous on its first call. Give it one
        # short follow-up read when the server explicitly says a check is in progress.
        data = first_mapping(result.data)
        app_update = data.get("appUpdate") if isinstance(data, dict) else None
        latest = (
            str(app_update.get("latestVersion") or "")
            if isinstance(app_update, dict)
            else ""
        )
        if "check in progress" in latest.lower():
            await asyncio.sleep(1.0)
            follow_up = await self.client.call_tool("hub_get_info", arguments)
            if not follow_up.is_error:
                result = follow_up

        message, display = present_hub_info_v2(result.data)
        return self._decorate(
            self._response(message, "fallback-hub-info", True, result),
            display,
            result,
        )

    async def _fresh_live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        """Force a new Hubitat read instead of reusing a pre-command cache entry.

        Verification used to re-read through the 12-second device cache. If the
        first poll happened before a slow device published its new state, every
        later poll returned that same cached old value. Invalidating before each
        poll makes every attempt an authoritative upstream read.
        """
        invalidate = getattr(self.client, "invalidate", None)
        if callable(invalidate):
            await invalidate("devices")
        return await self._live_devices(capability_filter)

    @staticmethod
    def _find_control_device(
        result: MCPToolResult,
        *,
        device_id: Any,
        label: str,
    ) -> dict[str, Any] | None:
        rows = FastFallbackRouter._device_rows(result.data)
        return next(
            (
                item
                for item in rows
                if str(_device_id(item)) == str(device_id)
                or _normalise(_label(item)) == _normalise(label)
            ),
            None,
        )

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        # A control decision must not use a cached state. This prevents a recently
        # changed device being incorrectly reported as "already on/off".
        candidates_result = await self._fresh_live_devices("Switch")
        candidates = self._device_rows(candidates_result.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if not match:
            response: dict[str, Any]
            if alternatives:
                response = self._response(
                    "I could not find an exact device match. Closest matches: "
                    + ", ".join(alternatives[:5])
                    + ".",
                    "fallback-ambiguous-device",
                    False,
                    candidates_result,
                )
                response["alternatives"] = alternatives[:5]
            else:
                response = self._response(
                    f'I could not find a device named "{requested_name}".',
                    "fallback-device-not-found",
                    False,
                    candidates_result,
                )
                response["alternatives"] = []
            response["requested_name"] = requested_name
            response["requested_state"] = _normalise(action)
            return response

        device_id = _device_id(match)
        label = _label(match) or requested_name
        if device_id is None:
            return self._response(
                f'I found "{label}", but the MCP result did not include its device ID.',
                "fallback-device-id-missing",
                False,
            )

        initial_state = _normalise(live_attributes(match).get("switch")) or "unknown"
        desired_state = _normalise(action)
        if initial_state == desired_state:
            display = display_payload(
                "device-control",
                label,
                subtitle=f"Already {desired_state}",
                metrics=[
                    {"label": "Requested", "value": desired_state.title(), "icon": "🎯"},
                    {"label": "Fresh state", "value": initial_state.title(), "icon": "✅"},
                ],
                note="The current state was refreshed from Hubitat before deciding no command was needed.",
            )
            return self._decorate(
                self._response(
                    f"{label} is already {desired_state}.",
                    "fallback-device-already-set",
                    True,
                    candidates_result,
                ),
                display,
                candidates_result,
            )

        direct_tool = await self.client.get_tool("hub_call_device_command")
        properties = (
            (direct_tool.input_schema or {}).get("properties", {})
            if direct_tool
            else {}
        )
        command_args: dict[str, Any] = {}
        for key in ("deviceId", "id", "device_id"):
            if not properties or key in properties:
                command_args[key] = device_id
                break
        command_args["command"] = desired_state
        if not properties or "params" in properties:
            command_args["params"] = []

        command_result = await self._execute_catalog_tool(
            "hub_call_device_command",
            "hub_manage_devices",
            command_args,
        )
        if command_result.is_error:
            return self._response(
                command_result.text or f'Failed to turn {desired_state} "{label}".',
                "fallback-control-error",
                False,
                command_result,
            )

        verified_state = "unknown"
        verification_result: MCPToolResult | None = None
        attempts: list[dict[str, Any]] = []
        verification_started = time.perf_counter()
        deadline = verification_started + self.control_verification_timeout_seconds
        delays = (
            self.control_verification_initial_delay_seconds,
            0.45,
            0.8,
            1.25,
            1.75,
            2.25,
        )

        for delay in delays:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            await asyncio.sleep(min(delay, remaining))
            if time.perf_counter() > deadline:
                break
            poll_started = time.perf_counter()
            verification_result = await self._fresh_live_devices("Switch")
            current = self._find_control_device(
                verification_result,
                device_id=device_id,
                label=label,
            )
            if current:
                verified_state = _normalise(live_attributes(current).get("switch")) or "unknown"
            attempts.append(
                {
                    "elapsed_seconds": round(time.perf_counter() - verification_started, 2),
                    "state": verified_state,
                    "read_ms": round((time.perf_counter() - poll_started) * 1000),
                }
            )
            if verified_state == desired_state:
                break

        verification_seconds = round(time.perf_counter() - verification_started, 2)
        confirmed = verified_state == desired_state
        if confirmed:
            message = f"{label} turned {desired_state} and was confirmed {verified_state}."
            subtitle = f"Confirmed {verified_state} in {verification_seconds:g}s"
            tone = "success"
            intent = "fallback-device-control-confirmed"
            success = True
        elif verified_state in {"on", "off"}:
            message = (
                f"The {desired_state} command was accepted for {label}, but its Hubitat switch "
                f"state was still {verified_state} after {verification_seconds:g} seconds. "
                "The device may be reporting its new state late; check it again."
            )
            subtitle = f"State update pending · last read {verified_state}"
            tone = "warning"
            intent = "fallback-device-control-pending"
            success = False
        else:
            message = (
                f"The {desired_state} command was accepted for {label}, but Hubitat did not return "
                f"a readable switch state within {verification_seconds:g} seconds. Check the device state again."
            )
            subtitle = "State update pending"
            tone = "warning"
            intent = "fallback-device-control-unverified"
            success = False

        display = display_payload(
            "device-control",
            label,
            subtitle=subtitle,
            metrics=[
                {"label": "Before", "value": initial_state.title(), "icon": "↩️"},
                {"label": "Requested", "value": desired_state.title(), "icon": "🎯"},
                {
                    "label": "Latest read",
                    "value": verified_state.title(),
                    "icon": "✅" if confirmed else "⏳",
                },
                {"label": "Verification", "value": f"{verification_seconds:g}s", "icon": "⏱️"},
            ],
            items=[
                {
                    "icon": "✅" if confirmed else "⏳",
                    "title": "Command verification",
                    "subtitle": message,
                    "value": "Confirmed" if confirmed else "Pending",
                    "tone": tone,
                }
            ],
            note=(
                "Every verification attempt bypasses the device-state cache and reads fresh Hubitat currentStates. "
                "Most devices confirm on the first or second read; slower drivers are allowed a longer window."
            ),
        )
        response = self._response(
            message,
            intent,
            success,
            verification_result or command_result,
        )
        response["command_sent"] = True
        response["command_accepted"] = True
        response["confirmed"] = confirmed
        response["requested_state"] = desired_state
        response["initial_state"] = initial_state
        response["verified_state"] = verified_state
        response["verification_seconds"] = verification_seconds
        response["verification_attempts"] = attempts
        response["technical"] = json.dumps(
            {
                "device_id": device_id,
                "label": label,
                "command_arguments": command_args,
                "command_result": command_result.data,
                "initial_state": initial_state,
                "verified_state": verified_state,
                "verification_seconds": verification_seconds,
                "verification_attempts": attempts,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        response["display"] = display
        return response
