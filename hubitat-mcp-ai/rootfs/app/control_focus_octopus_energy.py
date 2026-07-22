from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any, Awaitable, Callable

import request_tracing
from fallback_router import _attributes, _device_id, _label, _normalise
from presenter import display_payload, safe_debug
from routing_policy import RouteDecision


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_PREFIXES = ("octopus live meter display", "octopus meter")
_PERIOD_ORDER = ("power", "today", "yesterday", "week", "month", "rates", "previous rate", "standing charge")
_PERIOD_ALIASES = {
    "today": ("today", "today's", "current day"),
    "yesterday": ("yesterday", "previous day"),
    "week": ("week", "weekly", "this week"),
    "month": ("month", "monthly", "this month"),
    "power": ("power", "live power", "current power", "right now", "currently", "now"),
    "rates": ("rates", "rates compact", "tariff", "price"),
    "previous rate": ("previous rate", "last rate"),
    "standing charge": ("standing charge",),
}
_ENERGY_TERMS = (
    "power consumption",
    "energy consumption",
    "electricity consumption",
    "power usage",
    "energy usage",
    "electricity usage",
    "total power",
    "total energy",
    "whole house power",
    "whole house energy",
    "overall power",
    "overall energy",
)
_META_KEYS = {
    "id",
    "deviceid",
    "device_id",
    "name",
    "label",
    "displayname",
    "room",
    "disabled",
    "lastactivity",
    "capabilities",
    "commands",
    "type",
    "devicetype",
    "category",
}
_VALUE_KEYS = (
    "currentvalue",
    "value",
    "state",
    "status",
    "displayvalue",
    "display",
    "text",
    "reading",
    "sensor",
    "power",
    "energy",
    "cost",
    "html",
)
_UNIT_KEYS = ("unit", "unitofmeasurement", "unit_of_measurement")


def _query(value: str) -> str:
    return re.sub(r"\s+", " ", _normalise(value).replace("-", " ")).strip(" .!?")


def requested_octopus_period(query: str) -> str | None:
    q = _query(query)
    padded = f" {q} "
    for period, aliases in _PERIOD_ALIASES.items():
        if any(f" {alias} " in padded or q.endswith(f" {alias}") for alias in aliases):
            return period
    return None


def is_octopus_display_query(query: str) -> bool:
    q = _query(query)
    if "octopus" not in q:
        return False
    if re.fullmatch(r"find octopus(?: (?:meters?|sensors?|devices?))?", q):
        return True
    return any(term in q for term in ("live meter", "meter display", "energy display", "octopus meter"))


def is_whole_house_period_query(query: str) -> bool:
    q = _query(query)
    period = requested_octopus_period(q)
    if period not in {"today", "yesterday", "week", "month"}:
        return False
    if re.fullmatch(
        r"(?:(?:show|show me|display|get|check|give me|tell me) )?"
        r"(?:energy|electricity) (?:today|yesterday|(?:this )?week|(?:this )?month)",
        q,
    ) or re.fullmatch(
        r"(?:(?:show|show me|display|get|check|give me|tell me) )?"
        r"(?:today|yesterday|(?:this )?week|(?:this )?month) (?:energy|electricity)",
        q,
    ):
        return True
    return any(term in q for term in _ENERGY_TERMS)


def is_whole_house_power_query(query: str) -> bool:
    q = _query(query)
    patterns = (
        r"how much (?:power|electricity) (?:are we|is the house|is my home) using(?: (?:right )?now)?",
        r"what(?:'s| is) (?:our|the(?: whole house)?|my|current|whole house) (?:power|electricity) (?:usage|use|consumption)(?: (?:right )?now)?",
        r"(?:show|give|tell) me (?:the )?(?:current|live|whole house) (?:power|electricity)(?: usage| consumption)?",
        r"(?:current|live|whole house|overall|total) (?:power|electricity) (?:usage|use|consumption)",
    )
    return any(re.fullmatch(pattern, q) for pattern in patterns)


def is_octopus_energy_query(query: str) -> bool:
    return (
        is_octopus_display_query(query)
        or is_whole_house_period_query(query)
        or is_whole_house_power_query(query)
    )


def _is_octopus_meter_row(item: dict[str, Any]) -> bool:
    return _normalise(_label(item)).startswith(_PREFIXES)


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            rows.append(item)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return rows


def _device_rows(value: Any) -> list[dict[str, Any]]:
    rows = [item for item in _walk_dicts(value) if _device_id(item) is not None and _label(item)]
    deduped: dict[str, dict[str, Any]] = {}
    for item in rows:
        deduped[str(_device_id(item))] = item
    return list(deduped.values())


def _state_map(item: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for container_key in ("attributes", "state", "states", "currentStates"):
        container = item.get(container_key)
        if isinstance(container, dict):
            merged.update(container)
            continue
        if not isinstance(container, list):
            continue
        for entry in container:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("attribute") or entry.get("key")
            if name not in (None, ""):
                merged[str(name)] = entry
    return merged


def _merge_rows(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for group in groups:
        for raw in group:
            if not isinstance(raw, dict):
                continue
            key = str(_device_id(raw) or "").strip() or _normalise(_label(raw))
            if not key:
                continue
            if key not in merged:
                merged[key] = {}
                order.append(key)
            existing_states = _state_map(merged[key])
            incoming_states = _state_map(raw)
            merged[key].update(raw)
            if existing_states or incoming_states:
                merged[key]["currentStates"] = {**existing_states, **incoming_states}
    return [merged[key] for key in order]


def _clean_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        return ""
    text = html.unescape(str(value)).replace("\u00a0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if _normalise(text) in {"unknown", "unavailable", "none", "null", "available"}:
        return ""
    return text


def _unwrap_state(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        unit = ""
        for key in _UNIT_KEYS:
            if value.get(key) not in (None, ""):
                unit = _clean_text(value.get(key))
                break
        for key in _VALUE_KEYS:
            if value.get(key) not in (None, ""):
                return _clean_text(value.get(key)), unit
        return "", unit
    return _clean_text(value), ""


def _period_from_label(label: str) -> str:
    q = _normalise(label)
    if q.endswith(" previous rate"):
        return "previous rate"
    if q.endswith(" standing charge"):
        return "standing charge"
    if q.endswith(" rates compact") or q.endswith(" rates"):
        return "rates"
    for period in ("power", "today", "yesterday", "week", "month"):
        if q.endswith(f" {period}"):
            return period
    return "other"


def _candidate_values(item: dict[str, Any]) -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    states = _state_map(item)
    for key, raw in states.items():
        value, unit = _unwrap_state(raw)
        if value:
            candidates.append((_normalise(key), value, unit))
    for key, raw in item.items():
        normal_key = _normalise(key).replace(" ", "")
        if normal_key in _META_KEYS or key in {"attributes", "state", "states", "currentStates"}:
            continue
        value, unit = _unwrap_state(raw)
        if value:
            candidates.append((_normalise(key), value, unit))
    return candidates


def _display_value(item: dict[str, Any]) -> str:
    label = _label(item)
    period = _period_from_label(label)
    candidates = _candidate_values(item)
    if not candidates:
        return "No live value"

    preferred = [period.replace(" ", ""), period, *_VALUE_KEYS]

    def score(candidate: tuple[str, str, str]) -> tuple[int, int]:
        key, value, _unit = candidate
        compact = key.replace(" ", "")
        points = 0
        for index, wanted in enumerate(preferred):
            wanted_compact = str(wanted).replace(" ", "")
            if compact == wanted_compact:
                points = max(points, 100 - index)
            elif wanted_compact and wanted_compact in compact:
                points = max(points, 70 - index)
        if any(term in compact for term in ("battery", "lastactivity", "health", "rtt")):
            points -= 80
        if any(symbol in value for symbol in ("£", "W", "kWh", "p/kWh", "%")):
            points += 10
        return points, -len(value)

    key, value, unit = max(candidates, key=score)
    if unit and _normalise(unit) not in _normalise(value):
        value = f"{value} {unit}".strip()
    return value


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    period = _period_from_label(_label(item))
    try:
        return _PERIOD_ORDER.index(period), _label(item).lower()
    except ValueError:
        return len(_PERIOD_ORDER), _label(item).lower()


class OctopusLiveMeterSummary:
    def __init__(self, application: Any) -> None:
        self.application = application

    async def answer(self, query: str) -> dict[str, Any]:
        rows, tools, errors = await self._read_family()
        rows = sorted(rows, key=_sort_key)
        requested = requested_octopus_period(query)
        if is_whole_house_period_query(query) and requested is None:
            requested = "today"

        if requested:
            selected = next((row for row in rows if _period_from_label(_label(row)) == requested), None)
            if selected is not None:
                value = _display_value(selected)
                title = requested.title() if requested != "power" else "Live power"
                message = f"Octopus whole-house {title.lower()}: {value}."
                items = [self._item(selected)]
                success = value != "No live value"
            else:
                labels = ", ".join(_label(row) for row in rows) or "none"
                message = f"The Octopus {requested} display was not returned. Available displays: {labels}."
                items = [self._item(row) for row in rows]
                success = False
            intent = "octopus-period-energy"
            heading = f"Octopus {requested.title()}"
        else:
            readable = [row for row in rows if _display_value(row) != "No live value"]
            lines = [f"- {self._short_label(row)}: {_display_value(row)}" for row in readable]
            if lines:
                message = "Octopus whole-house meter displays:\n" + "\n".join(lines)
                success = True
            elif rows:
                message = "The Octopus display devices were found, but no live display values were returned."
                success = False
            else:
                message = "No selected Octopus Live Meter Display devices were found."
                success = False
            items = [self._item(row) for row in rows]
            intent = "octopus-live-meter-family"
            heading = "Octopus whole-house meter"

        display = display_payload(
            "octopus-live-meter-summary",
            heading,
            subtitle=f"{len(rows)} grouped Octopus display sensor{'s' if len(rows) != 1 else ''}",
            metrics=[
                {"label": "Displays found", "value": str(len(rows)), "icon": "⚡"},
                {"label": "Live values", "value": str(sum(_display_value(row) != 'No live value' for row in rows)), "icon": "📡"},
                {"label": "Scope", "value": "Whole house", "icon": "🏠"},
            ],
            items=items,
            note=(
                "These Octopus display sensors are treated as overall whole-house readings. "
                "They are not added to individual device totals."
            ),
        )
        display["summary"] = message
        return {
            "success": success,
            "route": "mcp-octopus-summary",
            "intent": intent,
            "message": message,
            "display": display,
            "model": None,
            "answered_by": "Deterministic Octopus whole-house display reader",
            "selected_tools": tools,
            "octopus_displays": [
                {
                    "id": str(_device_id(row) or ""),
                    "label": _label(row),
                    "period": _period_from_label(_label(row)),
                    "value": _display_value(row),
                    "room": str(row.get("room") or ""),
                }
                for row in rows
            ],
            "technical": safe_debug(
                {
                    "query": query,
                    "requested_period": requested,
                    "display_count": len(rows),
                    "evidence_errors": errors,
                    "rows": rows,
                }
            ),
        }

    async def _read_family(self) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        client = self.application.mcp
        groups: list[list[dict[str, Any]]] = []
        tools: list[str] = []
        errors: list[str] = []
        invalidate = getattr(client, "invalidate", None)
        if callable(invalidate):
            try:
                await invalidate("devices")
            except Exception as exc:
                errors.append(f"cache invalidation: {str(exc).strip() or type(exc).__name__}")

        fields = [
            "id",
            "name",
            "label",
            "room",
            "currentStates",
            "attributes",
            "capabilities",
            "commands",
            "disabled",
            "lastActivity",
        ]
        for detailed in (False, True):
            desired = {
                "detailed": detailed,
                "format": "detailed" if detailed else "summary",
                "labelFilter": "Octopus Live Meter Display",
                "fields": fields,
            }
            try:
                args = await client.supported_arguments("hub_list_devices", desired)
                result = await client.call_tool("hub_list_devices", args)
                tools.append("hub_list_devices")
                if result.is_error:
                    errors.append(result.text or f"hub_list_devices detailed={detailed} failed")
                    continue
                filtered = [row for row in _device_rows(result.data) if _is_octopus_meter_row(row)]
                if filtered:
                    groups.append(filtered)
            except Exception as exc:
                errors.append(f"hub_list_devices detailed={detailed}: {str(exc).strip() or type(exc).__name__}")

        rows = _merge_rows(groups)
        if not rows:
            try:
                desired = {"detailed": False, "format": "summary", "fields": fields}
                args = await client.supported_arguments("hub_list_devices", desired)
                result = await client.call_tool("hub_list_devices", args)
                tools.append("hub_list_devices")
                if not result.is_error:
                    rows = [row for row in _device_rows(result.data) if _is_octopus_meter_row(row)]
            except Exception as exc:
                errors.append(f"all-device Octopus fallback: {str(exc).strip() or type(exc).__name__}")

        index = getattr(self.application, "device_index", None)
        enriched_devices = getattr(index, "enriched_devices", None)
        if callable(enriched_devices):
            try:
                indexed = list(await enriched_devices(force=True))
                indexed = [row for row in indexed if _is_octopus_meter_row(row)]
                if indexed:
                    rows = _merge_rows([rows, indexed])
                    tools.append("homebrain_device_index")
            except Exception as exc:
                errors.append(
                    f"complete device index: {str(exc).strip() or type(exc).__name__}"
                )

        enriched = await self._read_by_ids(rows, tools, errors)
        if enriched:
            rows = _merge_rows([rows, enriched])
        return rows, list(dict.fromkeys(tools)), errors

    async def _read_by_ids(
        self,
        rows: list[dict[str, Any]],
        tools: list[str],
        errors: list[str],
    ) -> list[dict[str, Any]]:
        client = self.application.mcp
        ids = [str(_device_id(row)) for row in rows if _device_id(row) is not None]
        if not ids:
            return []

        # In gateway mode ``hub_read_devices`` is a category gateway, not a bulk
        # detail operation. Request the real hidden operation by name and let the
        # shared MCP broker translate it through that gateway when necessary.
        async def get_one(device_id: str) -> Any:
            return await client.call_tool("hub_get_device", {"deviceId": device_id})

        detail_responses = await asyncio.gather(
            *(get_one(device_id) for device_id in ids),
            return_exceptions=True,
        )
        detail_rows: list[dict[str, Any]] = []
        for response in detail_responses:
            tools.append("hub_get_device")
            if isinstance(response, Exception):
                errors.append(
                    f"hub_get_device: {str(response).strip() or type(response).__name__}"
                )
            elif response.is_error:
                errors.append(response.text or "hub_get_device failed")
            else:
                detail_rows.extend(_device_rows(response.data))
        if detail_rows:
            return detail_rows

        # Compatibility fallback for older servers that expose a true bulk/single
        # ``hub_read_devices`` operation instead of ``hub_get_device``.
        try:
            tool = await client.get_tool("hub_read_devices")
        except Exception:
            tool = None
        if tool is None or not rows:
            return []
        properties = (tool.input_schema or {}).get("properties") or {}

        plural_key = next((key for key in ("deviceIds", "device_ids", "ids") if key in properties), None)
        singular_key = next((key for key in ("deviceId", "device_id", "id") if key in properties), None)
        results: list[Any] = []
        if plural_key:
            args: dict[str, Any] = {plural_key: ids}
            if "detailed" in properties:
                args["detailed"] = True
            try:
                result = await client.call_tool("hub_read_devices", args)
                tools.append("hub_read_devices")
                if result.is_error:
                    errors.append(result.text or "hub_read_devices failed")
                else:
                    results.append(result.data)
            except Exception as exc:
                errors.append(f"hub_read_devices: {str(exc).strip() or type(exc).__name__}")
        elif singular_key:
            async def read_one(device_id: str) -> Any:
                args: dict[str, Any] = {singular_key: device_id}
                if "detailed" in properties:
                    args["detailed"] = True
                return await client.call_tool("hub_read_devices", args)

            responses = await asyncio.gather(*(read_one(device_id) for device_id in ids), return_exceptions=True)
            for response in responses:
                tools.append("hub_read_devices")
                if isinstance(response, Exception):
                    errors.append(f"hub_read_devices: {str(response).strip() or type(response).__name__}")
                elif response.is_error:
                    errors.append(response.text or "hub_read_devices failed")
                else:
                    results.append(response.data)
        return [row for data in results for row in _device_rows(data)]

    @staticmethod
    def _short_label(row: dict[str, Any]) -> str:
        label = _label(row)
        prefix = "Octopus Live Meter Display "
        return label[len(prefix):] if label.startswith(prefix) else label

    def _item(self, row: dict[str, Any]) -> dict[str, Any]:
        period = _period_from_label(_label(row))
        return {
            "icon": "⚡" if period == "power" else "🔋",
            "title": self._short_label(row),
            "value": _display_value(row),
            "subtitle": str(row.get("room") or "Whole-house Octopus meter"),
            "tone": "warning" if period == "power" else None,
        }


def install_control_focus_octopus_energy(application: Any) -> OctopusLiveMeterSummary:
    original_ask: AskHandler = application.ask
    original_classifier = request_tracing.classify_query
    service = OctopusLiveMeterSummary(application)

    def classify_with_octopus(query: str) -> RouteDecision:
        if is_octopus_energy_query(query):
            return RouteDecision(
                "mcp-fast",
                "Control Focus grouped Octopus whole-house display read; period queries select the matching verified display sensor",
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_octopus

    async def ask_with_octopus(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_octopus_energy_query(query):
            return await original_ask(request)
        answer = dict(await service.answer(query))
        answer.setdefault("version", application.VERSION)
        return answer

    application.ask = ask_with_octopus
    application.octopus_live_meter_summary = service
    return service


__all__ = [
    "OctopusLiveMeterSummary",
    "install_control_focus_octopus_energy",
    "is_octopus_display_query",
    "is_octopus_energy_query",
    "is_whole_house_period_query",
    "requested_octopus_period",
]
