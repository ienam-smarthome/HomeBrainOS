from __future__ import annotations

import asyncio
import time
from typing import Any

from control_agent import AskHandler, HomeBrainControlAgent
from device_intelligence_index import _attributes, _device_id
from mcp_client import MCPToolResult


_LEVEL_READ_STRATEGIES: tuple[tuple[str | None, bool, str], ...] = (
    ("SwitchLevel", False, "summary-currentStates:SwitchLevel"),
    (None, False, "all-summary-currentStates"),
    ("Switch Level", False, "summary-currentStates:Switch Level"),
    ("SwitchLevel", True, "detailed-attributes:SwitchLevel"),
    (None, True, "all-detailed-attributes"),
)
_LEVEL_QUICK_RETRY_STRATEGIES = _LEVEL_READ_STRATEGIES[:2]
_CANONICAL_PARAMETER_KEY = "parameters"
_COMPATIBILITY_PARAMETER_KEYS = (
    "params",
    "arguments",
    "args",
    "commandParams",
    "commandArguments",
)
_DEVICE_ID_KEYS = ("deviceId", "id", "device_id")


def _level_number(value: Any) -> float | None:
    if isinstance(value, dict):
        for key in ("currentValue", "value", "currentState", "level", "finalValue"):
            if key in value:
                parsed = _level_number(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return None


def _parameter_value(schema: dict[str, Any], level: int, *, canonical: bool) -> Any:
    """Build the ordered command arguments advertised by the MCP tool schema.

    The MCP Rule Server's canonical ``hub_call_device_command`` contract is an
    array of strings under ``parameters``. Compatibility keys are retained only
    for older/custom servers that genuinely omit the canonical field.
    """

    if canonical:
        return [str(level)]
    declared_type = str(schema.get("type") or "").strip().lower()
    if declared_type == "array" or not declared_type:
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        item_type = str(item_schema.get("type") or "").strip().lower()
        return [str(level)] if item_type == "string" else [level]
    if declared_type == "string":
        return str(level)
    if declared_type in {"integer", "number"}:
        return level
    return [level]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _response_state_level(data: dict[str, Any]) -> float | None:
    state = data.get("state")
    if not isinstance(state, dict):
        return None
    return _level_number(state.get("level"))


class FastVerifiedControlAgent(HomeBrainControlAgent):
    """Control Agent with canonical setLevel payload and authoritative verification."""

    def __init__(
        self,
        *args: Any,
        level_verification_timeout_seconds: float = 3.0,
        level_verification_poll_seconds: float = 0.25,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.level_verification_timeout_seconds = max(
            0.8,
            min(7.0, float(level_verification_timeout_seconds)),
        )
        self.level_verification_poll_seconds = max(
            0.1,
            min(0.75, float(level_verification_poll_seconds)),
        )

    async def _set_level(self, node: Any, value: float) -> dict[str, Any]:
        requested = max(0, min(100, round(float(value))))
        client = self.fallback.client
        try:
            tool = await client.get_tool("hub_call_device_command")
        except Exception as exc:
            return self._command_error(
                node.label,
                requested,
                f"Could not read the MCP command schema: {str(exc).strip() or type(exc).__name__}",
            )

        input_schema = getattr(tool, "input_schema", {}) if tool is not None else {}
        properties = (
            input_schema.get("properties", {})
            if isinstance(input_schema, dict)
            else {}
        )
        properties = properties if isinstance(properties, dict) else {}

        arguments: dict[str, Any] = {}
        device_key = next(
            (key for key in _DEVICE_ID_KEYS if not properties or key in properties),
            None,
        )
        if device_key is None:
            return self._command_error(
                node.label,
                requested,
                "The MCP command schema does not expose a device ID field.",
            )
        arguments[device_key] = node.id
        arguments["command"] = "setLevel"

        # The official MCP Rule Server contract is `parameters: ["30"]`.
        # Never prefer a compatibility alias when the canonical field exists.
        if not properties or _CANONICAL_PARAMETER_KEY in properties:
            parameter_key = _CANONICAL_PARAMETER_KEY
        else:
            parameter_key = next(
                (key for key in _COMPATIBILITY_PARAMETER_KEYS if key in properties),
                None,
            )
        if parameter_key is None:
            return self._command_error(
                node.label,
                requested,
                (
                    "The MCP command schema does not expose the canonical parameters field "
                    "or a recognised compatibility field for setLevel."
                ),
            )
        parameter_schema = properties.get(parameter_key)
        parameter_schema = parameter_schema if isinstance(parameter_schema, dict) else {}
        arguments[parameter_key] = _parameter_value(
            parameter_schema,
            requested,
            canonical=parameter_key == _CANONICAL_PARAMETER_KEY,
        )

        wait_for_supported = not properties or "waitFor" in properties
        wait_for_request: dict[str, Any] | None = None
        if wait_for_supported:
            wait_for_request = {
                "attribute": "level",
                "expectedValue": str(requested),
                "comparator": "eq",
                "timeoutMs": max(
                    800,
                    min(7000, round(self.level_verification_timeout_seconds * 1000)),
                ),
                "pollIntervalMs": max(
                    100,
                    min(750, round(self.level_verification_poll_seconds * 1000)),
                ),
            }
            arguments["waitFor"] = wait_for_request

        safe_arguments = {
            "deviceIdField": device_key,
            "deviceId": str(node.id),
            "command": "setLevel",
            "parameterField": parameter_key,
            "parameterValue": arguments[parameter_key],
            "waitFor": wait_for_request,
        }

        try:
            command_result = await client.call_tool("hub_call_device_command", arguments)
        except Exception as exc:
            return self._command_error(
                node.label,
                requested,
                f"The MCP command call failed: {str(exc).strip() or type(exc).__name__}",
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
            )
        if command_result.is_error:
            return self._command_error(
                node.label,
                requested,
                command_result.text or f"Failed to set {node.label} to {requested}%.",
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
            )

        response = _mapping(command_result.data)
        server_wait = _mapping(response.get("waitFor"))
        wait_converged = server_wait.get("converged") is True
        wait_final = _level_number(server_wait.get("finalValue"))
        response_level = _response_state_level(response)
        observed = wait_final if wait_final is not None else response_level

        if wait_converged and observed is not None and abs(observed - requested) <= 1.0:
            return self._confirmed_response(
                node.label,
                requested,
                observed,
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
                source="hub_call_device_command.waitFor",
                server_wait=server_wait,
                attempts=[],
            )

        invalidate = getattr(client, "invalidate", None)
        if callable(invalidate):
            try:
                await invalidate("devices")
            except Exception:
                pass

        # A current MCP server with waitFor has already spent the requested timeout
        # polling. Perform one independent fresh read for honesty, but do not wait for
        # another full timeout. Older servers without waitFor use the local polling path.
        if wait_for_supported and server_wait:
            independent, source, attempts = await self._read_level_once(node.id)
            if independent is not None:
                observed = independent
            if observed is not None and abs(observed - requested) <= 1.0:
                return self._confirmed_response(
                    node.label,
                    requested,
                    observed,
                    parameter_key=parameter_key,
                    command_arguments=safe_arguments,
                    source=source or "fresh-independent-read",
                    server_wait=server_wait,
                    attempts=attempts,
                )
            return self._unverified_response(
                node.label,
                requested,
                observed,
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
                server_wait=server_wait,
                attempts=attempts,
            )

        # Compatibility path for an older/custom MCP server that does not advertise
        # or return waitFor. Verification remains fresh and bounded.
        initial_delay = min(
            0.2,
            max(
                0.05,
                float(
                    getattr(
                        self.fallback,
                        "control_verification_initial_delay_seconds",
                        0.15,
                    )
                ),
            ),
        )
        await asyncio.sleep(initial_delay)
        verified, source, attempts = await self._poll_live_level(node.id, requested)
        if verified is not None and abs(verified - requested) <= 1.0:
            return self._confirmed_response(
                node.label,
                requested,
                verified,
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
                source=source or "fresh-live-read",
                server_wait=server_wait,
                attempts=attempts,
            )
        return self._unverified_response(
            node.label,
            requested,
            verified if verified is not None else observed,
            parameter_key=parameter_key,
            command_arguments=safe_arguments,
            server_wait=server_wait,
            attempts=attempts,
        )

    async def _read_level_once(
        self,
        device_id: str,
    ) -> tuple[float | None, str | None, list[dict[str, Any]]]:
        attempts: list[dict[str, Any]] = []
        for capability, detailed, source in _LEVEL_READ_STRATEGIES:
            try:
                reading, present = await self._read_live_level(
                    device_id,
                    capability=capability,
                    detailed=detailed,
                )
                attempts.append(
                    {
                        "source": source,
                        "device_present": present,
                        "level": reading,
                        "success": True,
                    }
                )
            except Exception as exc:
                attempts.append(
                    {
                        "source": source,
                        "success": False,
                        "error": str(exc).strip() or type(exc).__name__,
                    }
                )
                continue
            if reading is not None:
                return reading, source, attempts
        return None, None, attempts

    async def _poll_live_level(
        self,
        device_id: str,
        requested: int,
    ) -> tuple[float | None, str | None, list[dict[str, Any]]]:
        deadline = time.monotonic() + self.level_verification_timeout_seconds
        preferred: tuple[str | None, bool, str] | None = None
        observed: float | None = None
        observed_source: str | None = None
        attempts: list[dict[str, Any]] = []
        no_value_passes = 0

        while time.monotonic() < deadline:
            if preferred is not None:
                strategies = (preferred,)
            elif no_value_passes:
                strategies = _LEVEL_QUICK_RETRY_STRATEGIES
            else:
                strategies = _LEVEL_READ_STRATEGIES

            numeric_seen = False
            for capability, detailed, source in strategies:
                try:
                    reading, present = await self._read_live_level(
                        device_id,
                        capability=capability,
                        detailed=detailed,
                    )
                    attempts.append(
                        {
                            "source": source,
                            "device_present": present,
                            "level": reading,
                            "success": True,
                        }
                    )
                except Exception as exc:
                    attempts.append(
                        {
                            "source": source,
                            "success": False,
                            "error": str(exc).strip() or type(exc).__name__,
                        }
                    )
                    continue
                if reading is None:
                    continue
                numeric_seen = True
                observed = reading
                observed_source = source
                preferred = (capability, detailed, source)
                if abs(reading - requested) <= 1.0:
                    return reading, source, attempts

            if numeric_seen:
                await asyncio.sleep(self.level_verification_poll_seconds)
                continue
            no_value_passes += 1
            if no_value_passes >= 2:
                break
            await asyncio.sleep(min(0.2, self.level_verification_poll_seconds))

        return observed, observed_source, attempts

    @staticmethod
    def _confirmed_response(
        label: str,
        requested: int,
        observed: float,
        *,
        parameter_key: str,
        command_arguments: dict[str, Any],
        source: str,
        server_wait: dict[str, Any],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "success": True,
            "intent": "control-agent-level-confirmed",
            "message": f"{label} is confirmed at {observed:g}%.",
            "tools_used": [
                {
                    "name": "hub_call_device_command",
                    "success": True,
                    "command": "setLevel",
                    "parameter_field": parameter_key,
                    "verification_source": source,
                    "observed_level": observed,
                }
            ],
            "level_verification": {
                "requested": requested,
                "observed": observed,
                "source": source,
                "command_arguments": command_arguments,
                "server_wait_for": server_wait,
                "fresh_read_attempts": attempts,
            },
        }

    @staticmethod
    def _unverified_response(
        label: str,
        requested: int,
        observed: float | None,
        *,
        parameter_key: str,
        command_arguments: dict[str, Any],
        server_wait: dict[str, Any],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reason = (
            f"; last reading was {observed:g}%."
            if observed is not None
            else "; no numeric level was returned by the command or fresh device reads."
        )
        return {
            "success": False,
            "intent": "control-agent-level-unverified",
            "message": (
                f"{label} received setLevel {requested}%, but the final level could not be verified"
                + reason
            ),
            "tools_used": [
                {
                    "name": "hub_call_device_command",
                    "success": True,
                    "command": "setLevel",
                    "parameter_field": parameter_key,
                    "server_wait_converged": server_wait.get("converged"),
                    "server_wait_final_value": server_wait.get("finalValue"),
                }
            ],
            "level_verification": {
                "requested": requested,
                "observed": observed,
                "source": "hub_call_device_command.waitFor"
                if server_wait
                else "fresh-live-read",
                "command_arguments": command_arguments,
                "server_wait_for": server_wait,
                "fresh_read_attempts": attempts,
            },
        }

    @staticmethod
    def _command_error(
        label: str,
        requested: int,
        message: str,
        *,
        parameter_key: str | None = None,
        command_arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool: dict[str, Any] = {
            "name": "hub_call_device_command",
            "success": False,
            "command": "setLevel",
        }
        if parameter_key:
            tool["parameter_field"] = parameter_key
        return {
            "success": False,
            "intent": "control-agent-level-error",
            "message": message or f"Failed to set {label} to {requested}%.",
            "tools_used": [tool],
            "level_verification": {
                "requested": requested,
                "command_arguments": command_arguments or {},
                "error": message,
            },
        }

    async def _read_live_level(
        self,
        device_id: str,
        *,
        capability: str | None,
        detailed: bool,
    ) -> tuple[float | None, bool]:
        fresh: MCPToolResult | None = await self.fallback._direct_fresh_devices(
            capability,
            detailed=detailed,
        )
        if fresh is not None:
            rows = self.fallback._device_rows(fresh.data)
        elif capability:
            try:
                rows = await self.device_index.capability_devices(
                    capability,
                    detailed=detailed,
                    force=True,
                )
            except TypeError:
                rows = await self.device_index.capability_devices(capability, force=True)
        else:
            rows = await self.device_index.summary_devices(force=True)

        match = next(
            (item for item in rows if str(_device_id(item)) == str(device_id)),
            None,
        )
        if match is None:
            return None, False
        attrs = _attributes(match)
        raw = attrs.get("level", match.get("level"))
        return _level_number(raw), True


def install_control_agent(
    application: Any,
    device_index: Any,
    fallback: Any,
    **kwargs: Any,
) -> FastVerifiedControlAgent:
    original_ask: AskHandler = application.ask
    agent = FastVerifiedControlAgent(application, device_index, fallback, **kwargs)

    async def ask_with_control_agent(request: Any) -> dict[str, Any]:
        if not application.option_bool("control_agent_enabled", True):
            return await original_ask(request)
        return await agent.answer(request, original_ask)

    application.ask = ask_with_control_agent
    return agent


__all__ = ["FastVerifiedControlAgent", "install_control_agent"]
