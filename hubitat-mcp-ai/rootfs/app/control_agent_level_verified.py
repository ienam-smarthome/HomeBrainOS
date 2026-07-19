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
_COMMAND_PARAMETER_KEYS = (
    "params",
    "arguments",
    "args",
    "parameters",
    "commandParams",
    "commandArguments",
)
_DEVICE_ID_KEYS = ("deviceId", "id", "device_id")


def _level_number(value: Any) -> float | None:
    if isinstance(value, dict):
        for key in ("currentValue", "value", "currentState", "level"):
            if key in value:
                parsed = _level_number(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return None


def _command_parameter_value(schema: dict[str, Any], level: int) -> Any:
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


class FastVerifiedControlAgent(HomeBrainControlAgent):
    """Control Agent with schema-aware setLevel and fast live level verification."""

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

        parameter_key = next(
            (key for key in _COMMAND_PARAMETER_KEYS if key in properties),
            None,
        )
        if parameter_key is None and not properties:
            parameter_key = "params"
        if parameter_key is None:
            return self._command_error(
                node.label,
                requested,
                (
                    "The MCP command schema does not expose a parameter field for setLevel. "
                    "Refresh the MCP tool catalogue and try again."
                ),
            )
        parameter_schema = properties.get(parameter_key)
        parameter_schema = parameter_schema if isinstance(parameter_schema, dict) else {}
        arguments[parameter_key] = _command_parameter_value(parameter_schema, requested)

        try:
            command_result = await client.call_tool("hub_call_device_command", arguments)
        except Exception as exc:
            return self._command_error(
                node.label,
                requested,
                f"The MCP command call failed: {str(exc).strip() or type(exc).__name__}",
                parameter_key=parameter_key,
            )
        if command_result.is_error:
            return self._command_error(
                node.label,
                requested,
                command_result.text or f"Failed to set {node.label} to {requested}%.",
                parameter_key=parameter_key,
            )

        invalidate = getattr(client, "invalidate", None)
        if callable(invalidate):
            try:
                await invalidate("devices")
            except Exception:
                pass

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

        deadline = time.monotonic() + self.level_verification_timeout_seconds
        preferred: tuple[str | None, bool, str] | None = None
        observed: float | None = None
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
                        node.id,
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
                preferred = (capability, detailed, source)
                if abs(reading - requested) <= 1.0:
                    return {
                        "success": True,
                        "intent": "control-agent-level-confirmed",
                        "message": f"{node.label} is confirmed at {reading:g}%.",
                        "tools_used": [
                            {
                                "name": "hub_call_device_command",
                                "success": True,
                                "command": "setLevel",
                                "parameter_field": parameter_key,
                            },
                            {
                                "name": "hub_list_devices",
                                "success": True,
                                "capability": capability,
                                "detailed": detailed,
                                "evidence_source": source,
                                "observed_level": reading,
                            },
                        ],
                        "level_verification": {
                            "requested": requested,
                            "observed": reading,
                            "source": source,
                            "attempts": attempts,
                        },
                    }

            if numeric_seen:
                await asyncio.sleep(self.level_verification_poll_seconds)
                continue

            # If every compatible source omitted level entirely, use one short retry
            # of the two cheapest live shapes. Waiting for the full control timeout
            # cannot make an unsupported field appear and only makes an exact command
            # feel slow.
            no_value_passes += 1
            if no_value_passes >= 2:
                break
            await asyncio.sleep(min(0.2, self.level_verification_poll_seconds))

        reason = (
            f"; last reading was {observed:g}%."
            if observed is not None
            else "; the MCP device responses exposed no numeric level field."
        )
        return {
            "success": False,
            "intent": "control-agent-level-unverified",
            "message": (
                f"{node.label} accepted setLevel {requested}%, but the final level could not be verified"
                + reason
            ),
            "tools_used": [
                {
                    "name": "hub_call_device_command",
                    "success": True,
                    "command": "setLevel",
                    "parameter_field": parameter_key,
                },
                {
                    "name": "hub_list_devices",
                    "success": False,
                    "evidence_sources": [item[2] for item in _LEVEL_READ_STRATEGIES],
                },
            ],
            "level_verification": {
                "requested": requested,
                "observed": observed,
                "attempts": attempts,
            },
        }

    @staticmethod
    def _command_error(
        label: str,
        requested: int,
        message: str,
        *,
        parameter_key: str | None = None,
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
