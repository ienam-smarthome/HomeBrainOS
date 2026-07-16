from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from mcp_client import HubitatMCPClient, MCPError, MCPToolResult


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _walk(value) if isinstance(item, dict)]


def _label(item: dict[str, Any]) -> str:
    return str(
        item.get("label")
        or item.get("displayName")
        or item.get("name")
        or item.get("deviceLabel")
        or ""
    ).strip()


def _device_id(item: dict[str, Any]) -> Any:
    return item.get("id") or item.get("deviceId") or item.get("device_id")


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    attrs = item.get("attributes") or item.get("state") or {}
    if isinstance(attrs, dict):
        return attrs
    if isinstance(attrs, list):
        result = {}
        for attr in attrs:
            if not isinstance(attr, dict):
                continue
            name = attr.get("name") or attr.get("attribute")
            if name:
                result[str(name)] = attr.get("currentValue", attr.get("value"))
        return result
    return {}


class HomeBrainFallbackRouter:
    """Deterministic MCP fallback used when Ollama is unavailable."""

    def __init__(self, client: HubitatMCPClient) -> None:
        self.client = client

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if not q:
            return self._response("Please enter a question.", "fallback-empty", False)

        try:
            if any(term in q for term in ("hub health", "hub status", "cpu", "free memory")):
                return await self._hub_info()

            if ("battery" in q or "batteries" in q) and any(
                term in q for term in ("low", "which", "replace", "status")
            ):
                return await self._low_batteries()

            command = self._parse_switch_command(q)
            if command:
                action, requested_name = command
                return await self._control_device(requested_name, action)

            if any(term in q for term in ("lights on", "which lights", "what lights")):
                return await self._list_on_devices(kind="light")

            if any(term in q for term in ("switches on", "which switches")):
                return await self._list_on_devices(kind="switch")

            if any(term in q for term in ("list rooms", "what rooms", "rooms")):
                return await self._simple_tool(
                    ["hub_list_rooms", "hub_read_rooms"],
                    "Room information",
                )

            if any(term in q for term in ("weather", "rain", "temperature outside")):
                return await self._find_weather()

            if any(term in q for term in ("what's happening", "whats happening", "home status")):
                return await self._home_status()

            return self._response(
                "Ollama is unavailable. The local fallback currently handles device on/off, "
                "lights or switches on, low batteries, weather, rooms, and hub health.",
                "fallback-unsupported",
                False,
            )
        except Exception as exc:
            return self._response(
                f"The local MCP fallback could not complete that request: {exc}",
                "fallback-error",
                False,
            )

    async def _hub_info(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")
        return self._response(
            self._humanise_result(result, "Hub information is available."),
            "fallback-hub-info",
            True,
            result,
        )

    async def _low_batteries(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        rows = []
        for item in self._device_rows(result.data):
            attrs = _attributes(item)
            battery = item.get("battery", attrs.get("battery"))
            try:
                number = float(str(battery).replace("%", "").strip())
            except Exception:
                continue
            if number <= 20:
                rows.append((_label(item) or f"Device {_device_id(item)}", number))
        rows.sort(key=lambda row: (row[1], row[0].lower()))
        if not rows:
            message = "No devices at or below 20% were found in the MCP device data."
        else:
            message = "Low battery devices:\n" + "\n".join(
                f"- {name}: {value:g}%" for name, value in rows
            )
        return self._response(message, "fallback-low-batteries", True, result)

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        candidates_result = await self._list_devices(
            detailed=False,
            label_filter=requested_name,
        )
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
        if device_id is None:
            return self._response(
                f'I found "{_label(match)}", but the MCP result did not include its device ID.',
                "fallback-device-id-missing",
                False,
            )

        tool = await self.client.get_tool("hub_call_device_command")
        properties = (
            (tool.input_schema or {}).get("properties", {})
            if tool
            else {}
        )
        args: dict[str, Any] = {}
        for key in ("deviceId", "id", "device_id"):
            if not properties or key in properties:
                args[key] = device_id
                break
        args["command"] = action
        if not properties or "params" in properties:
            args["params"] = []

        result = await self.client.call_tool("hub_call_device_command", args)
        if result.is_error:
            return self._response(
                result.text or f'Failed to turn {action} "{_label(match)}".',
                "fallback-control-error",
                False,
                result,
            )
        return self._response(
            f'{_label(match)} was sent the {action} command.',
            "fallback-device-control",
            True,
            result,
        )

    async def _list_on_devices(self, kind: str) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        names = []
        for item in self._device_rows(result.data):
            text = _normalise(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("category", "type", "deviceType", "label", "name")
                )
            )
            if kind == "light" and "light" not in text and "bulb" not in text:
                continue
            attrs = _attributes(item)
            state = _normalise(item.get("switch", attrs.get("switch")))
            if state == "on":
                names.append(_label(item) or str(_device_id(item)))
        if names:
            message = f"{len(names)} {kind}{'' if len(names) == 1 else 's'} on: " + ", ".join(names) + "."
        else:
            message = f"No {kind}s are currently reporting as on."
        return self._response(message, f"fallback-{kind}s-on", True, result)

    async def _find_weather(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True, label_filter="weather")
        rows = self._device_rows(result.data)
        weather = next(
            (
                item
                for item in rows
                if "weather" in _normalise(_label(item) + " " + str(item.get("type") or ""))
            ),
            None,
        )
        if not weather:
            return self._response(
                "I could not find a weather device through the MCP server.",
                "fallback-weather-missing",
                False,
                result,
            )
        attrs = _attributes(weather)
        preferred = [
            "weatherSummary",
            "weatherSummaryLine",
            "condition",
            "temperature",
            "humidity",
            "precipitation",
        ]
        parts = []
        for key in preferred:
            value = weather.get(key, attrs.get(key))
            if value not in (None, ""):
                parts.append(f"{key}: {value}")
        message = "\n".join(parts) if parts else self._humanise_result(result, "Weather data was returned.")
        return self._response(message, "fallback-weather", True, result)

    async def _home_status(self) -> dict[str, Any]:
        lights = await self._list_on_devices("light")
        batteries = await self._low_batteries()
        return self._response(
            lights["message"] + "\n" + batteries["message"],
            "fallback-home-status",
            True,
        )

    async def _simple_tool(
        self,
        names: list[str],
        fallback_label: str,
    ) -> dict[str, Any]:
        tools = {tool.name for tool in await self.client.list_tools()}
        for name in names:
            if name not in tools:
                continue
            result = await self.client.call_tool(name, {})
            return self._response(
                self._humanise_result(result, f"{fallback_label} was returned."),
                f"fallback-{name}",
                not result.is_error,
                result,
            )
        return self._response(
            f"The MCP server did not expose a direct tool for {fallback_label.lower()}.",
            "fallback-tool-missing",
            False,
        )

    async def _list_devices(
        self,
        detailed: bool,
        label_filter: str | None = None,
    ) -> MCPToolResult:
        desired: dict[str, Any] = {"detailed": detailed}
        if label_filter:
            desired["labelFilter"] = label_filter
        args = await self.client.supported_arguments("hub_list_devices", desired)
        return await self.client.call_tool("hub_list_devices", args)

    @staticmethod
    def _device_rows(value: Any) -> list[dict[str, Any]]:
        rows = []
        for item in _dicts(value):
            if _device_id(item) is not None and _label(item):
                rows.append(item)
        deduped = {}
        for item in rows:
            deduped[str(_device_id(item))] = item
        return list(deduped.values())

    @staticmethod
    def _match_device(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[str]]:
        target = _normalise(requested_name)
        exact = [item for item in candidates if _normalise(_label(item)) == target]
        if len(exact) == 1:
            return exact[0], []

        scored = sorted(
            (
                (
                    SequenceMatcher(None, target, _normalise(_label(item))).ratio(),
                    item,
                )
                for item in candidates
                if _label(item)
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        alternatives = [_label(item) for score, item in scored if score >= 0.35]
        return None, alternatives

    @staticmethod
    def _parse_switch_command(q: str) -> tuple[str, str] | None:
        match = re.match(
            r"^(?:please\s+)?(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+?)[.!?]*$",
            q,
        )
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    @staticmethod
    def _humanise_result(result: MCPToolResult, fallback: str) -> str:
        if result.text:
            return result.text
        if result.data is not None:
            return json.dumps(result.data, ensure_ascii=False, indent=2)
        return fallback

    @staticmethod
    def _response(
        message: str,
        intent: str,
        success: bool,
        tool_result: MCPToolResult | None = None,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "route": "fallback",
            "intent": intent,
            "message": message,
            "tool": tool_result.name if tool_result else None,
        }
