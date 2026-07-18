from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from device_intelligence_index import (
    _attributes,
    _label,
    _looks_like_light,
    _normalise,
    _room_name,
)
from presenter import display_payload, first_mapping, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HOME_QUERY = re.compile(
    r"^(?:what(?:'s| is)|show|tell me)\s+(?:me\s+)?(?:what(?:'s| is)\s+)?(?:currently\s+)?happening(?:\s+(?:at|in|around)\s+(?:the\s+)?home)?[?.!]*$|^home\s+(?:status|summary|snapshot)[?.!]*$",
    re.IGNORECASE,
)

_BACKGROUND_SWITCH_TERMS = (
    "camera",
    " cam ",
    "router",
    "mesh",
    "freezer",
    "fridge",
    "nest mini",
    "streamer",
    "bridge",
    "hubitat",
    "mcp server",
)

_DANGER_HEALTH = {"offline", "unavailable", "dead", "failed", "not present"}
_CLEAR_ALARM_STATES = {"clear", "dry", "tested", "inactive", "off", "false", "0", "none"}


def _value(raw: Any) -> Any:
    if isinstance(raw, dict):
        for key in ("value", "currentValue", "currentState"):
            if raw.get(key) not in (None, ""):
                return raw[key]
    return raw


def _number(raw: Any) -> float | None:
    raw = _value(raw)
    try:
        match = re.search(r"-?\d+(?:\.\d+)?", str(raw or ""))
        return float(match.group(0)) if match else None
    except Exception:
        return None


def _state(raw: Any) -> str:
    return _normalise(_value(raw))


def _join_names(values: list[str], *, limit: int = 6) -> str:
    names = [str(item).strip() for item in values if str(item).strip()]
    if not names:
        return ""
    shown = names[:limit]
    extra = len(names) - len(shown)
    if len(shown) == 1:
        text = shown[0]
    elif len(shown) == 2:
        text = f"{shown[0]} and {shown[1]}"
    else:
        text = ", ".join(shown[:-1]) + f", and {shown[-1]}"
    return f"{text} plus {extra} more" if extra > 0 else text


class HomeSnapshotService:
    """Build one compact live home snapshot, then optionally phrase it with Ollama.

    The model never plans or selects MCP tools for this route. It receives a bounded,
    authoritative snapshot and is allowed one short synthesis call. The structured
    display is returned regardless of whether Ollama is available.
    """

    def __init__(
        self,
        application: Any,
        device_index: Any,
        *,
        ai_enabled: bool = True,
        ai_timeout_seconds: float = 12.0,
        max_items_per_group: int = 8,
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.ai_enabled = bool(ai_enabled)
        self.ai_timeout_seconds = max(2.0, min(30.0, float(ai_timeout_seconds)))
        self.max_items_per_group = max(3, min(20, int(max_items_per_group)))

    @staticmethod
    def matches(query: str) -> bool:
        return bool(_HOME_QUERY.match(str(query or "").strip()))

    async def answer(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        devices_task = asyncio.create_task(self.device_index.enriched_devices())
        diagnostics_task = asyncio.create_task(self.device_index.diagnostics())
        hub_task = asyncio.create_task(self._hub_status())

        coverage_errors: list[str] = []
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

        snapshot = self._build_snapshot(devices, diagnostics, hub_status)
        deterministic = self._deterministic_summary(snapshot)

        ai_message = None
        ai_error = None
        model = None
        synthesis_started = time.perf_counter()
        if self.ai_enabled and devices:
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
            subtitle=self._subtitle(snapshot, coverage_errors),
            metrics=[
                {"label": "Motion active", "value": str(len(snapshot["motion_active"])), "icon": "🏃"},
                {"label": "Lights on", "value": str(len(snapshot["lights_on"])), "icon": "💡"},
                {"label": "Other devices on", "value": str(len(snapshot["devices_on"])), "icon": "🔌"},
                {"label": "Needs attention", "value": str(len(snapshot["attention"])), "icon": "⚠️"},
            ],
            items=self._display_items(snapshot),
            note=self._coverage_note(snapshot, coverage_errors),
        )
        display["summary"] = message

        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": bool(devices),
            "route": "ollama+snapshot" if ai_message else "mcp-snapshot",
            "intent": "home-snapshot",
            "message": message,
            "model": model,
            "display": display,
            "snapshot": snapshot,
            "coverage_complete": not coverage_errors,
            "coverage_errors": coverage_errors,
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
                    "ollama_synthesis_error": ai_error,
                    "model": model,
                }
            ),
        }

    async def _hub_status(self) -> dict[str, Any]:
        try:
            result = await self.application.mcp.call_tool(
                "hub_get_info",
                {"includeHealthAlerts": True},
            )
            if result.is_error:
                return {"items": [], "error": result.text or "hub_get_info failed"}
            data = first_mapping(result.data)
            items: list[dict[str, Any]] = []
            if data.get("safeMode") is True:
                items.append(
                    {
                        "icon": "🛡️",
                        "title": "Hub safe mode",
                        "value": "On",
                        "subtitle": "Hubitat is running in safe mode",
                        "tone": "danger",
                        "priority": 0,
                    }
                )
            for field, title, icon in (
                ("memoryWarning", "Hub memory", "💾"),
                ("temperatureWarning", "Hub temperature", "🌡️"),
                ("databaseWarning", "Hub database", "🗄️"),
            ):
                if data.get(field):
                    items.append(
                        {
                            "icon": icon,
                            "title": title,
                            "value": "Warning",
                            "subtitle": str(data[field]),
                            "tone": "danger",
                            "priority": 1,
                        }
                    )
            health_alerts = data.get("healthAlerts")
            active = health_alerts.get("active") if isinstance(health_alerts, dict) else []
            if isinstance(active, list):
                for alert in active:
                    items.append(
                        {
                            "icon": "⚠️",
                            "title": "Hub health alert",
                            "value": str(alert),
                            "subtitle": "Hubitat platform alert",
                            "tone": "danger",
                            "priority": 1,
                        }
                    )
            return {"items": items, "data": data}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    def _build_snapshot(
        self,
        devices: list[dict[str, Any]],
        diagnostics: dict[str, Any],
        hub_status: dict[str, Any],
    ) -> dict[str, Any]:
        lights_on: list[dict[str, Any]] = []
        devices_on: list[dict[str, Any]] = []
        background_on: list[dict[str, Any]] = []
        motion_active: list[dict[str, Any]] = []
        open_contacts: list[dict[str, Any]] = []
        heating: list[dict[str, Any]] = []
        attention: list[dict[str, Any]] = list(hub_status.get("items") or [])
        states_read = 0

        seen_attention: set[tuple[str, str]] = set()

        def row(
            item: dict[str, Any],
            *,
            icon: str,
            value: str,
            subtitle: str | None = None,
            tone: str | None = None,
            priority: float = 50,
        ) -> dict[str, Any]:
            label = _label(item) or "Unnamed Hubitat device"
            room = _room_name(item)
            return {
                "icon": icon,
                "title": label,
                "value": value,
                "subtitle": subtitle or room or "No room assigned",
                "tone": tone,
                "priority": priority,
                "room": room,
            }

        def add_attention(item: dict[str, Any]) -> None:
            key = (_normalise(item.get("title")), _normalise(item.get("value")))
            if key not in seen_attention:
                seen_attention.add(key)
                attention.append(item)

        for item in devices:
            if item.get("disabled") is True:
                continue
            attrs = _attributes(item)
            if attrs:
                states_read += 1
            label = _label(item)
            label_norm = f" {_normalise(label)} "
            groups = set(self.device_index._groups(item))

            switch = _state(attrs.get("switch"))
            if switch == "on":
                if "light" in groups or _looks_like_light(item):
                    lights_on.append(row(item, icon="💡", value="On", tone="success"))
                else:
                    current = row(item, icon="🔌", value="On", tone="success")
                    if any(term.strip() in label_norm for term in _BACKGROUND_SWITCH_TERMS):
                        background_on.append(current)
                    else:
                        devices_on.append(current)

            if _state(attrs.get("motion")) == "active":
                motion_active.append(row(item, icon="🏃", value="Active", tone="success"))

            if _state(attrs.get("contact")) == "open":
                open_contacts.append(row(item, icon="🚪", value="Open", tone="warning"))

            operating = _state(attrs.get("thermostatOperatingState"))
            if operating in {"heating", "heat", "pending heat"}:
                setpoint = _number(attrs.get("heatingSetpoint"))
                value = f"Heating to {setpoint:g}°C" if setpoint is not None else "Heating"
                heating.append(row(item, icon="🔥", value=value, tone="success"))

            battery = _number(attrs.get("battery"))
            if battery is not None and battery <= 20:
                add_attention(
                    row(
                        item,
                        icon="🪫",
                        value=f"{battery:g}%",
                        subtitle="Replace soon" if battery <= 15 else "Low battery",
                        tone="danger" if battery <= 15 else "warning",
                        priority=battery + 5,
                    )
                )

            health = _state(attrs.get("healthStatus") or attrs.get("status"))
            if health in _DANGER_HEALTH:
                add_attention(
                    row(
                        item,
                        icon="📡",
                        value="Offline",
                        subtitle="Device is not responding",
                        tone="danger",
                        priority=2,
                    )
                )

            for attribute, title, icon in (
                ("smoke", "Smoke detected", "🚨"),
                ("carbonMonoxide", "Carbon monoxide", "☠️"),
                ("water", "Water detected", "💦"),
                ("alarm", "Alarm active", "🚨"),
            ):
                state = _state(attrs.get(attribute))
                if state and state not in _CLEAR_ALARM_STATES:
                    add_attention(
                        row(
                            item,
                            icon=icon,
                            value=title,
                            subtitle=f"Live {attribute} state: {state}",
                            tone="danger",
                            priority=-5,
                        )
                    )

        for item in attention:
            seen_attention.add((_normalise(item.get("title")), _normalise(item.get("value"))))
        attention.sort(key=lambda item: (float(item.get("priority", 50)), _normalise(item.get("title"))))
        key = lambda item: (_normalise(item.get("room")), _normalise(item.get("title")))
        for values in (lights_on, devices_on, background_on, motion_active, open_contacts, heating):
            values.sort(key=key)

        return {
            "selected_devices": len(devices),
            "states_read": states_read,
            "index_age_seconds": diagnostics.get("last_refresh_age_seconds"),
            "rooms": list(diagnostics.get("rooms") or []),
            "lights_on": lights_on,
            "devices_on": devices_on,
            "background_on": background_on,
            "motion_active": motion_active,
            "open_contacts": open_contacts,
            "heating": heating,
            "attention": attention,
        }

    def _display_items(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        groups = (
            ("Needs attention", snapshot["attention"]),
            ("Activity", snapshot["motion_active"]),
            ("Open contacts", snapshot["open_contacts"]),
            ("Lights on", snapshot["lights_on"]),
            ("Other devices on", snapshot["devices_on"]),
            ("Heating", snapshot["heating"]),
        )
        for group, values in groups:
            for item in values[: self.max_items_per_group]:
                output.append(
                    {
                        key: value
                        for key, value in {**item, "group": group}.items()
                        if key not in {"priority", "room"} and value is not None
                    }
                )
            remaining = len(values) - self.max_items_per_group
            if remaining > 0:
                output.append(
                    {
                        "group": group,
                        "icon": "➕",
                        "title": f"{remaining} more",
                        "value": "",
                        "subtitle": "Open Technical details for the complete snapshot",
                    }
                )
        return output

    def _deterministic_summary(self, snapshot: dict[str, Any]) -> str:
        sentences: list[str] = []
        urgent = snapshot["attention"]
        if urgent:
            details = [f"{item['title']} {item['value']}" for item in urgent[:4]]
            sentences.append(f"Attention is needed for {_join_names(details, limit=4)}.")

        motion = snapshot["motion_active"]
        if motion:
            rooms = sorted({item.get("room") for item in motion if item.get("room")}, key=str.lower)
            room_text = f" in {_join_names(rooms)}" if rooms else ""
            names = [item["title"] for item in motion]
            sentences.append(
                f"{len(motion)} motion sensor{'' if len(motion) == 1 else 's'} are active{room_text}: {_join_names(names)}."
            )

        on_items = snapshot["lights_on"] + snapshot["devices_on"]
        if on_items:
            names = [item["title"] for item in on_items]
            sentences.append(
                f"{len(snapshot['lights_on'])} light{'' if len(snapshot['lights_on']) == 1 else 's'} and "
                f"{len(snapshot['devices_on'])} other device{'' if len(snapshot['devices_on']) == 1 else 's'} are on: {_join_names(names)}."
            )

        if snapshot["open_contacts"]:
            sentences.append(
                f"Open contacts: {_join_names([item['title'] for item in snapshot['open_contacts']])}."
            )
        if not sentences:
            return "Nothing urgent or unusually active was found in the selected live Hubitat devices."
        return " ".join(sentences[:3])

    async def _natural_summary(
        self,
        snapshot: dict[str, Any],
        deterministic: str,
    ) -> tuple[str, str]:
        ollama = self.application.ollama
        health = await ollama.health()
        if not health.get("online"):
            raise RuntimeError(health.get("error") or "Ollama is offline")
        installed = list(health.get("models") or [])
        resolver = getattr(ollama, "_resolve_routine_model", None)
        model = resolver(installed) if callable(resolver) else str(getattr(ollama, "model", ""))
        evidence = {
            "attention": [
                {"device": item["title"], "value": item["value"], "detail": item.get("subtitle")}
                for item in snapshot["attention"][:6]
            ],
            "motion_active": [
                {"device": item["title"], "room": item.get("room")}
                for item in snapshot["motion_active"][:8]
            ],
            "lights_on": [item["title"] for item in snapshot["lights_on"][:8]],
            "other_devices_on": [item["title"] for item in snapshot["devices_on"][:8]],
            "open_contacts": [item["title"] for item in snapshot["open_contacts"][:6]],
            "heating": [item["title"] for item in snapshot["heating"][:6]],
            "coverage": {
                "selected_devices": snapshot["selected_devices"],
                "states_read": snapshot["states_read"],
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are HomeBrain, a concise natural smart-home assistant. Use only the supplied "
                    "verified snapshot. Write two or three short sentences. Put urgent safety or battery "
                    "issues first. Use exact device names when naming devices. Mention active rooms where "
                    "useful. Do not invent causes, do not call tools, do not offer follow-up options, and "
                    "do not say everything is fine when coverage is incomplete."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Summarise what is happening at home now.\n"
                    f"Verified snapshot: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}\n"
                    f"Deterministic wording to improve, not contradict: {deterministic}"
                ),
            },
        ]
        body = await ollama._chat(
            model=model,
            messages=messages,
            tools=None,
            timeout_seconds=self.ai_timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=100,
            temperature=0.1,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty home summary")
        return content, model

    @staticmethod
    def _subtitle(snapshot: dict[str, Any], errors: list[str]) -> str:
        age = snapshot.get("index_age_seconds")
        freshness = "Updated just now" if age is None or float(age) < 5 else f"Updated {float(age):.0f}s ago"
        coverage = "scan incomplete" if errors else "live Hubitat MCP"
        return f"{freshness} · {coverage} · {snapshot['selected_devices']} selected devices checked"

    @staticmethod
    def _coverage_note(snapshot: dict[str, Any], errors: list[str]) -> str:
        note = (
            f"Live states were available for {snapshot['states_read']} of {snapshot['selected_devices']} selected devices. "
            f"{len(snapshot['background_on'])} always-on/background device{'' if len(snapshot['background_on']) == 1 else 's'} "
            "were omitted from the main device-on list."
        )
        if errors:
            note += " Incomplete sources: " + "; ".join(errors) + "."
        return note


def install_home_snapshot(
    application: Any,
    device_index: Any,
    *,
    ai_enabled: bool = True,
    ai_timeout_seconds: float = 12.0,
    max_items_per_group: int = 8,
) -> HomeSnapshotService:
    original_ask: AskHandler = application.ask
    service = HomeSnapshotService(
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


__all__ = ["HomeSnapshotService", "install_home_snapshot"]
