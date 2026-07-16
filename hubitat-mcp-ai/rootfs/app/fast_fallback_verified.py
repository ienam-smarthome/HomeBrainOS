from __future__ import annotations

import asyncio
import json
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import FastFallbackRouter as LiveFastFallbackRouter
from fast_fallback_live import live_attributes
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, first_mapping
from system_presenter_v2 import present_hub_info_v2


class FastFallbackRouter(LiveFastFallbackRouter):
    """Live MCP fallback with verified controls and explicit update reporting."""

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

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        candidates_result = await self._live_devices("Switch")
        candidates = self._device_rows(candidates_result.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if not match:
            if alternatives:
                return self._response(
                    "I could not find an exact device match. Closest matches: "
                    + ", ".join(alternatives[:5])
                    + ".",
                    "fallback-ambiguous-device",
                    False,
                    candidates_result,
                )
            return self._response(
                f'I could not find a device named "{requested_name}".',
                "fallback-device-not-found",
                False,
                candidates_result,
            )

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
                    {"label": "Verified state", "value": initial_state.title(), "icon": "✅"},
                ],
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
        for delay in (0.35, 0.75, 1.1):
            await asyncio.sleep(delay)
            verification_result = await self._live_devices("Switch")
            current = next(
                (
                    item
                    for item in self._device_rows(verification_result.data)
                    if str(_device_id(item)) == str(device_id)
                    or _normalise(_label(item)) == _normalise(label)
                ),
                None,
            )
            if current:
                verified_state = _normalise(live_attributes(current).get("switch")) or "unknown"
            if verified_state == desired_state:
                break

        confirmed = verified_state == desired_state
        if confirmed:
            message = f"{label} turned {desired_state} and was confirmed {verified_state}."
            subtitle = f"Confirmed {verified_state}"
            tone = "success"
            intent = "fallback-device-control-confirmed"
        elif verified_state in {"on", "off"}:
            message = (
                f"The {desired_state} command was sent to {label}, but verification still "
                f"reports {verified_state}. The action was not confirmed."
            )
            subtitle = f"Not confirmed · still {verified_state}"
            tone = "warning"
            intent = "fallback-device-control-not-confirmed"
        else:
            message = (
                f"The {desired_state} command was sent to {label}, but Hubitat did not return "
                "a readable switch state, so the action could not be verified."
            )
            subtitle = "State could not be verified"
            tone = "warning"
            intent = "fallback-device-control-unverified"

        display = display_payload(
            "device-control",
            label,
            subtitle=subtitle,
            metrics=[
                {"label": "Before", "value": initial_state.title(), "icon": "↩️"},
                {"label": "Requested", "value": desired_state.title(), "icon": "🎯"},
                {
                    "label": "Verified",
                    "value": verified_state.title(),
                    "icon": "✅" if confirmed else "⚠️",
                },
            ],
            items=[
                {
                    "icon": "✅" if confirmed else "⚠️",
                    "title": "Command verification",
                    "subtitle": message,
                    "value": "Confirmed" if confirmed else "Not confirmed",
                    "tone": tone,
                }
            ],
            note="Control results are read back from Hubitat currentStates after the command.",
        )
        response = self._response(
            message,
            intent,
            confirmed,
            verification_result or command_result,
        )
        response["command_sent"] = True
        response["confirmed"] = confirmed
        response["requested_state"] = desired_state
        response["initial_state"] = initial_state
        response["verified_state"] = verified_state
        response["technical"] = json.dumps(
            {
                "device_id": device_id,
                "label": label,
                "command_arguments": command_args,
                "command_result": command_result.data,
                "verified_state": verified_state,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        response["display"] = display
        return response
