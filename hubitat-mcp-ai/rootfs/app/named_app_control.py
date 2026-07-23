from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from presenter import display_payload, first_value, normalise_text, safe_debug, walk


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_LIST_RE = re.compile(
    r"^\s*(?:please\s+)?(?:list|show)(?:\s+all)?\s+(?:(?P<state>disabled|enabled|active)\s+)?(?:hubitat\s+)?apps?(?:lications)?\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_WRITE_RE = re.compile(
    r"^\s*(?P<confirm>confirm\s+)?(?P<action>enable|disable)\s+(?:hubitat\s+)?(?:app(?:lication)?\s+)?(?P<target>.+?)\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalise_text(value).lower()).strip()


def _deep_value(value: Any, *names: str) -> Any:
    wanted = {name.lower() for name in names}
    for item in walk(value):
        if not isinstance(item, dict):
            continue
        for key, nested in item.items():
            if str(key).lower() in wanted and nested not in (None, ""):
                return nested
    return None


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "1", "disabled", "inactive"}:
        return True
    if text in {"false", "no", "0", "enabled", "active"}:
        return False
    return None


def _target_variants(value: str) -> tuple[str, ...]:
    raw = re.sub(r"\s+", " ", value.strip(" .!?"))
    candidates = [raw]
    for prefix in ("the ", "app ", "application ", "the app ", "the application "):
        if raw.lower().startswith(prefix):
            candidates.append(raw[len(prefix) :].strip())
    for candidate in list(candidates):
        for suffix in (" app", " application"):
            if candidate.lower().endswith(suffix):
                candidates.append(candidate[: -len(suffix)].strip())
    ordered: list[str] = []
    for candidate in candidates:
        normalised = _normalise(candidate)
        if normalised and normalised not in ordered:
            ordered.append(normalised)
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class AppWriteIntent:
    action: str
    requested_name: str
    variants: tuple[str, ...]
    confirmed: bool


def parse_app_write_intent(query: str) -> AppWriteIntent | None:
    match = _WRITE_RE.match(str(query or ""))
    if not match:
        return None
    requested = match.group("target").strip(" .!?")
    variants = _target_variants(requested)
    if not variants:
        return None
    return AppWriteIntent(
        action=match.group("action").lower(),
        requested_name=requested,
        variants=variants,
        confirmed=bool(match.group("confirm")),
    )


class NamedAppController:
    """Guarded deterministic Hubitat app inventory and enable/disable controller."""

    def __init__(self, application: Any) -> None:
        self.application = application
        self.mcp = application.mcp

    async def handle_list(self, state: str | None) -> dict[str, Any]:
        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_apps", {})
        if listed.is_error:
            return self._error("I could not read the Hubitat app inventory.", listed, started)
        apps = self._app_rows(listed.data)
        wanted = (state or "").lower()
        if wanted == "disabled":
            apps = [app for app in apps if app["disabled"] is True]
            title = "Disabled Hubitat apps"
        elif wanted in {"enabled", "active"}:
            apps = [app for app in apps if app["disabled"] is False]
            title = "Enabled Hubitat apps"
        else:
            title = "Hubitat apps"
        disabled_count = sum(app["disabled"] is True for app in apps)
        enabled_count = sum(app["disabled"] is False for app in apps)
        unknown_count = sum(app["disabled"] is None for app in apps)
        message = f"{len(apps)} apps returned: {enabled_count} enabled, {disabled_count} disabled"
        if unknown_count:
            message += f", {unknown_count} status unknown"
        message += "."
        return {
            "success": True,
            "route": "mcp-app-inventory",
            "intent": "hubitat-app-inventory",
            "message": message,
            "answered_by": "Hubitat MCP deterministic app controller",
            "display": display_payload(
                "apps",
                title,
                subtitle=message,
                metrics=[
                    {"label": "Total", "value": str(len(apps)), "icon": "📦"},
                    {"label": "Enabled", "value": str(enabled_count), "icon": "▶️"},
                    {"label": "Disabled", "value": str(disabled_count), "icon": "⏸️"},
                    {"label": "Unknown", "value": str(unknown_count), "icon": "❓"},
                ],
                items=[
                    {
                        "icon": "🧩",
                        "title": app["name"],
                        "value": "Disabled" if app["disabled"] is True else "Enabled" if app["disabled"] is False else "Status unknown",
                        "subtitle": f"App ID {app['id']}" + (f" · {app['type']}" if app.get("type") else ""),
                        "tone": "warning" if app["disabled"] is True else "success" if app["disabled"] is False else "neutral",
                    }
                    for app in apps
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"apps": apps, "mcp": listed.data}),
        }

    async def handle_write(self, intent: AppWriteIntent) -> dict[str, Any] | None:
        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_apps", {})
        if listed.is_error:
            return self._error("I could not read the Hubitat app inventory, so no app command was sent.", listed, started)
        apps = self._app_rows(listed.data)
        matches = self._exact_matches(apps, intent)
        if len(matches) != 1:
            candidates = matches or self._possible_matches(apps, intent)
            if not candidates:
                return self._clarification(intent, [], listed, started)
            return self._clarification(intent, candidates, listed, started)
        app = matches[0]
        requested_disabled = intent.action == "disable"
        if not intent.confirmed:
            return self._confirmation(intent, app, listed, started)
        current = app["disabled"]
        if current is requested_disabled:
            state = "disabled" if requested_disabled else "enabled"
            return self._already_state(app, state, listed, started)
        available = await self._available_tool_names()
        if "hub_set_app_disabled" not in available:
            return self._error(
                "The connected MCP server does not advertise `hub_set_app_disabled`. No app command was sent.",
                listed,
                started,
                app=app,
            )
        arguments = {"appId": app["id"], "disabled": requested_disabled}
        result = await self.mcp.call_tool("hub_set_app_disabled", arguments)
        failed = result.is_error or _deep_value(result.data, "success") is False
        if failed:
            detail = result.text or str(_deep_value(result.data, "error") or "Hubitat rejected the command")
            return self._error(f"No verified app change can be reported for **{app['name']}**: {detail}", result, started, app=app)
        reported = _bool_value(_deep_value(result.data, "disabled"))
        command_verified = reported is requested_disabled
        readback_verified = False
        readback = await self.mcp.call_tool("hub_list_apps", {})
        if not readback.is_error:
            refreshed = next((row for row in self._app_rows(readback.data) if str(row["id"]) == str(app["id"])), None)
            readback_verified = bool(refreshed and refreshed["disabled"] is requested_disabled)
        verified = command_verified or readback_verified
        state = "disabled" if requested_disabled else "enabled"
        if verified:
            message = f"App {state} for **{app['name']}**. Hubitat confirmed `disabled: {str(requested_disabled).lower()}`."
            title = f"App {state}"
        else:
            message = f"The {intent.action} command was accepted for **{app['name']}**, but the new disabled state was not confirmed."
            title = f"App {intent.action} requested"
        return {
            "success": True,
            "route": "mcp-app-control",
            "intent": f"hubitat-app-{intent.action}-{'verified' if verified else 'accepted'}",
            "message": message,
            "answered_by": "Hubitat MCP deterministic app controller",
            "display": display_payload(
                "app-control",
                title,
                subtitle="Verified by Hubitat" if verified else "Command accepted; state confirmation unavailable",
                metrics=[
                    {"label": "Action", "value": intent.action.title(), "icon": "🎯"},
                    {"label": "App ID", "value": str(app["id"]), "icon": "🧩"},
                ],
                items=[{"icon": "🧩", "title": app["name"], "value": state.title(), "subtitle": f"App ID {app['id']}"}],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "requested_action": intent.action,
                    "resolved_app": app,
                    "tool": "hub_set_app_disabled",
                    "arguments": arguments,
                    "mcp": result.data,
                    "command_verified": command_verified,
                    "inventory_readback_verified": readback_verified,
                    "post_state_verified": verified,
                }
            ),
        }

    async def _available_tool_names(self) -> set[str]:
        tools = await self.mcp.list_tools()
        names = {str(tool.name) for tool in tools}
        gateway_map = getattr(self.mcp, "gateway_map", None)
        if callable(gateway_map):
            names.update((await gateway_map()).keys())
        return names

    @staticmethod
    def _app_rows(value: Any) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for item in walk(value):
            if not isinstance(item, dict):
                continue
            app_id = first_value(item, "id", "appId", "applicationId")
            name = first_value(item, "label", "name", "appName", "applicationName")
            if app_id in (None, "") or not name:
                continue
            disabled = _bool_value(first_value(item, "disabled", "isDisabled"))
            if disabled is None:
                disabled = _bool_value(first_value(item, "status", "state"))
            rows[str(app_id)] = {
                "id": app_id,
                "name": normalise_text(name),
                "normalised": _normalise(name),
                "disabled": disabled,
                "type": normalise_text(first_value(item, "type", "appType") or ""),
            }
        return sorted(rows.values(), key=lambda row: (row["name"].lower(), str(row["id"])))

    @staticmethod
    def _requested_id(intent: AppWriteIntent) -> str | None:
        match = re.fullmatch(r"(?:app\s+)?(?:id\s+)?#?(\d+)", _normalise(intent.requested_name))
        return match.group(1) if match else None

    @classmethod
    def _exact_matches(cls, apps: list[dict[str, Any]], intent: AppWriteIntent) -> list[dict[str, Any]]:
        requested_id = cls._requested_id(intent)
        if requested_id is not None:
            return [app for app in apps if str(app["id"]) == requested_id]
        variants = set(intent.variants)
        return [app for app in apps if app["normalised"] in variants]

    @staticmethod
    def _possible_matches(apps: list[dict[str, Any]], intent: AppWriteIntent) -> list[dict[str, Any]]:
        return [
            app for app in apps
            if any(variant in app["normalised"] or app["normalised"] in variant for variant in intent.variants)
        ][:6]

    def _confirmation(self, intent: AppWriteIntent, app: dict[str, Any], listed: Any, started: float) -> dict[str, Any]:
        action = intent.action
        display = display_payload(
            "app-control",
            f"Confirm app {action}",
            subtitle="No command has been sent",
            items=[{"icon": "🧩", "title": app["name"], "value": f"App ID {app['id']}", "subtitle": f"Currently {'disabled' if app['disabled'] is True else 'enabled' if app['disabled'] is False else 'status unknown'}"}],
        )
        display["actions"] = [
            {"label": f"Confirm {action}", "query": f"confirm {action} app id {app['id']}", "tone": "danger" if action == "disable" else "primary"},
            {"label": "Cancel", "cancel": True, "tone": "secondary"},
        ]
        return {
            "success": False,
            "route": "mcp-app-confirmation",
            "intent": "hubitat-app-confirmation",
            "message": f"Confirm {action} for **{app['name']}**. No command has been sent.",
            "display": display,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested_action": action, "resolved_app": app, "mcp": listed.data}),
        }

    def _clarification(self, intent: AppWriteIntent, candidates: list[dict[str, Any]], listed: Any, started: float) -> dict[str, Any]:
        if candidates:
            message = "I did not find one exact app match, so no command was sent. Select an app or cancel."
        else:
            message = f"I could not find a Hubitat app named **{intent.requested_name}**. No command was sent."
        display = display_payload(
            "apps",
            "Select app",
            subtitle="No command has been sent",
            items=[{"icon": "🧩", "title": app["name"], "value": str(app["id"]), "subtitle": "Select this app or cancel"} for app in candidates],
        )
        if candidates:
            display["actions"] = [
                {"label": f"{intent.action.title()} {app['name']}", "query": f"{intent.action} app id {app['id']}", "tone": "primary"}
                for app in candidates
            ] + [{"label": "Cancel", "cancel": True, "tone": "secondary"}]
        return {
            "success": False,
            "route": "mcp-app-clarification",
            "intent": "hubitat-app-clarification",
            "message": message,
            "display": display,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested": intent.requested_name, "candidates": candidates, "mcp": listed.data}),
        }

    def _already_state(self, app: dict[str, Any], state: str, listed: Any, started: float) -> dict[str, Any]:
        return {
            "success": True,
            "route": "mcp-app-control",
            "intent": f"hubitat-app-already-{state}",
            "message": f"**{app['name']}** is already {state}. No command was needed.",
            "answered_by": "Hubitat MCP deterministic app controller",
            "display": display_payload("app-control", f"App already {state}", subtitle="No change was needed"),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"resolved_app": app, "mcp": listed.data}),
        }

    @staticmethod
    def _error(message: str, result: Any, started: float, *, app: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-app-control-error",
            "intent": "hubitat-app-control-error",
            "message": message,
            "display": display_payload("error", "App command unavailable", subtitle="No verified app change is reported"),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"app": app, "mcp": getattr(result, "data", None), "error": getattr(result, "text", "")}),
        }


def install_named_app_controller(application: Any) -> NamedAppController:
    controller = NamedAppController(application)
    original_ask: AskHandler = application.ask

    async def ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        list_match = _LIST_RE.match(query)
        if list_match:
            return await controller.handle_list(list_match.group("state"))
        intent = parse_app_write_intent(query)
        if intent:
            return await controller.handle_write(intent)
        return await original_ask(request)

    application.ask = ask
    return controller


__all__ = ["AppWriteIntent", "NamedAppController", "install_named_app_controller", "parse_app_write_intent"]
