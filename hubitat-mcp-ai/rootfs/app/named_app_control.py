from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from presenter import display_payload, first_value, normalise_text, safe_debug, walk


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_LIST_RE = re.compile(
    r"^\s*(?:please\s+)?(?:list|show)\s+(?:(?P<state>disabled|enabled|active|inactive)\s+)?(?:hubitat\s+)?apps?(?:lications?)?\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_CONTROL_RE = re.compile(
    r"^\s*(?:please\s+)?(?P<confirm>confirm\s+)?(?P<action>enable|disable)\s+(?:(?:the\s+)?(?:hubitat\s+)?app(?:lication)?\s+)?(?P<target>.+?)\s*[.!?]*\s*$",
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
    if text in {"true", "yes", "1", "on", "enabled", "active"}:
        return True
    if text in {"false", "no", "0", "off", "disabled", "inactive"}:
        return False
    return None


def _disabled_state(item: dict[str, Any]) -> bool | None:
    disabled = _bool_value(first_value(item, "disabled", "isDisabled"))
    if disabled is not None:
        return disabled
    enabled = _bool_value(first_value(item, "enabled", "isEnabled", "active"))
    if enabled is not None:
        return not enabled
    status = str(first_value(item, "status", "state") or "").strip().lower()
    if status in {"disabled", "inactive", "off"}:
        return True
    if status in {"enabled", "active", "on"}:
        return False
    return None


def _target_variants(value: str) -> tuple[str, ...]:
    raw = re.sub(r"\s+", " ", str(value or "").strip(" .!?"))
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
class NamedAppIntent:
    action: str
    requested_name: str
    variants: tuple[str, ...]
    confirmed: bool = False


def parse_named_app_intent(query: str) -> NamedAppIntent | None:
    match = _CONTROL_RE.match(str(query or ""))
    if not match:
        return None
    target = match.group("target").strip(" .!?")
    variants = _target_variants(target)
    if not variants:
        return None
    # Do not steal ordinary device commands. Natural app writes must explicitly say
    # app/application, while exact clickable confirmations use "app id <n>".
    explicit_app = bool(
        re.search(r"(?:^|\s)app(?:lication)?(?:\s|$)", str(query or ""), re.IGNORECASE)
        or re.fullmatch(r"(?:app\s+)?(?:id\s+)?#?\d+", _normalise(target), re.IGNORECASE)
    )
    if not explicit_app:
        return None
    return NamedAppIntent(
        action=match.group("action").lower(),
        requested_name=target,
        variants=variants,
        confirmed=bool(match.group("confirm")),
    )


class NamedAppController:
    """Guarded deterministic Hubitat app inventory and enable/disable control."""

    def __init__(self, application: Any) -> None:
        self.application = application
        self.mcp = application.mcp

    async def list_apps(self, state_filter: str | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_apps", {})
        if listed.is_error:
            return self._error("I could not read the Hubitat app inventory.", listed, started)
        apps = self._app_rows(listed.data)
        requested_state = str(state_filter or "").lower()
        if requested_state in {"disabled", "inactive"}:
            apps = [app for app in apps if app["disabled"] is True]
            title = "Disabled Hubitat apps"
        elif requested_state in {"enabled", "active"}:
            apps = [app for app in apps if app["disabled"] is False]
            title = "Enabled Hubitat apps"
        else:
            title = "Hubitat apps"

        enabled_count = sum(app["disabled"] is False for app in apps)
        disabled_count = sum(app["disabled"] is True for app in apps)
        unknown_count = sum(app["disabled"] is None for app in apps)
        message = f"{len(apps)} Hubitat apps returned: {enabled_count} enabled, {disabled_count} disabled"
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
                        "value": "Disabled" if app["disabled"] is True else "Enabled" if app["disabled"] is False else "Unknown",
                        "subtitle": f"App ID {app['id']}" + (f" · {app['type']}" if app.get("type") else ""),
                        "tone": "warning" if app["disabled"] is True else "success" if app["disabled"] is False else "neutral",
                    }
                    for app in apps
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"filter": requested_state or None, "apps": apps, "mcp": listed.data}),
        }

    async def control(self, intent: NamedAppIntent) -> dict[str, Any] | None:
        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_apps", {})
        if listed.is_error:
            return self._error("I could not read the Hubitat app inventory, so no app command was sent.", listed, started)

        apps = self._app_rows(listed.data)
        matches = self._exact_matches(apps, intent)
        if len(matches) != 1:
            candidates = matches or self._possible_matches(apps, intent)
            return self._clarification(intent, candidates, listed, started)

        app = matches[0]
        requested_disabled = intent.action == "disable"
        if app["disabled"] is requested_disabled:
            state = "disabled" if requested_disabled else "enabled"
            return {
                "success": True,
                "route": "mcp-app-control-noop",
                "intent": f"hubitat-app-already-{state}",
                "message": f"**{app['name']}** is already {state}. No command was sent.",
                "answered_by": "Hubitat MCP deterministic app controller",
                "display": display_payload(
                    "app-control",
                    f"App already {state}",
                    subtitle="No change was needed",
                    metrics=[
                        {"label": "State", "value": state.title(), "icon": "🧩"},
                        {"label": "App ID", "value": str(app["id"]), "icon": "#️⃣"},
                    ],
                ),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "technical": safe_debug({"requested_action": intent.action, "resolved_app": app, "write_sent": False}),
            }

        if not intent.confirmed:
            return self._confirmation(intent, app, listed, started)

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
            return self._error(
                f"No verified app change can be reported for **{app['name']}**: {detail}",
                result,
                started,
                app=app,
            )

        reported_disabled = _bool_value(_deep_value(result.data, "disabled", "isDisabled"))
        response_verified = reported_disabled is requested_disabled
        readback_verified = False
        readback_app: dict[str, Any] | None = None
        try:
            refreshed = await self.mcp.call_tool("hub_list_apps", {})
            if not refreshed.is_error:
                refreshed_rows = self._app_rows(refreshed.data)
                readback_app = next((row for row in refreshed_rows if str(row["id"]) == str(app["id"])), None)
                readback_verified = bool(readback_app and readback_app["disabled"] is requested_disabled)
        except Exception:
            refreshed = None

        verified = response_verified or readback_verified
        state = "disabled" if requested_disabled else "enabled"
        if verified:
            source = "hub_set_app_disabled response and app inventory read-back" if response_verified and readback_verified else "hub_set_app_disabled response" if response_verified else "app inventory read-back"
            message = f"App {state} for **{app['name']}**. Hubitat confirmed `disabled: {str(requested_disabled).lower()}`."
            title = f"App {state}"
            note = f"Confirmed by {source}."
        else:
            message = f"The {intent.action} command was accepted for **{app['name']}**, but the new disabled state was not returned or independently read back."
            title = f"App {intent.action} requested"
            note = "The write completed without verifiable state confirmation."

        return {
            "success": True,
            "route": "mcp-app-control",
            "intent": f"hubitat-app-{intent.action}-{'verified' if verified else 'accepted'}",
            "message": message,
            "answered_by": "Hubitat MCP deterministic app controller",
            "display": display_payload(
                "app-control",
                title,
                subtitle=note,
                metrics=[
                    {"label": "Action", "value": intent.action.title(), "icon": "🎯"},
                    {"label": "App ID", "value": str(app["id"]), "icon": "🧩"},
                    {"label": "Verified", "value": "Yes" if verified else "No", "icon": "✅" if verified else "⚠️"},
                ],
                items=[
                    {
                        "icon": "🧩",
                        "title": app["name"],
                        "value": state.title() if verified else "Command accepted",
                        "subtitle": note,
                        "tone": "success" if verified else "warning",
                    }
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "requested_action": intent.action,
                    "resolved_app": app,
                    "tool": "hub_set_app_disabled",
                    "arguments": arguments,
                    "mcp": result.data,
                    "command_verified": response_verified,
                    "inventory_readback_verified": readback_verified,
                    "post_state_verified": verified,
                    "readback_app": readback_app,
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
            key = str(app_id)
            rows[key] = {
                "id": app_id,
                "name": normalise_text(name),
                "normalised": _normalise(name),
                "disabled": _disabled_state(item),
                "type": normalise_text(first_value(item, "type", "appType", "namespace") or ""),
            }
        return sorted(rows.values(), key=lambda row: (row["name"].lower(), str(row["id"])))

    @staticmethod
    def _requested_id(intent: NamedAppIntent) -> str | None:
        match = re.fullmatch(r"(?:app\s+)?(?:id\s+)?#?(\d+)", _normalise(intent.requested_name))
        return match.group(1) if match else None

    @classmethod
    def _exact_matches(cls, apps: list[dict[str, Any]], intent: NamedAppIntent) -> list[dict[str, Any]]:
        requested_id = cls._requested_id(intent)
        if requested_id is not None:
            return [app for app in apps if str(app["id"]) == requested_id]
        variants = set(intent.variants)
        return [app for app in apps if app["normalised"] in variants]

    @staticmethod
    def _possible_matches(apps: list[dict[str, Any]], intent: NamedAppIntent) -> list[dict[str, Any]]:
        return [
            app
            for app in apps
            if any(variant in app["normalised"] or app["normalised"] in variant for variant in intent.variants)
        ][:5]

    def _confirmation(self, intent: NamedAppIntent, app: dict[str, Any], listed: Any, started: float) -> dict[str, Any]:
        display = display_payload(
            "app-control",
            f"Confirm app {intent.action}",
            subtitle="No command has been sent",
            items=[
                {
                    "icon": "🧩",
                    "title": app["name"],
                    "value": f"App ID {app['id']}",
                    "subtitle": f"Currently {'disabled' if app['disabled'] is True else 'enabled' if app['disabled'] is False else 'status unknown'}",
                }
            ],
        )
        display["actions"] = [
            {
                "label": f"Confirm {intent.action}",
                "query": f"confirm {intent.action} app id {app['id']}",
                "tone": "danger" if intent.action == "disable" else "primary",
            },
            {"label": "Cancel", "cancel": True, "tone": "secondary"},
        ]
        return {
            "success": False,
            "route": "mcp-app-confirmation",
            "intent": "hubitat-app-confirmation",
            "message": f"Confirm {intent.action} for **{app['name']}**. No command has been sent.",
            "display": display,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested_action": intent.action, "resolved_app": app, "confirmation_required": True, "mcp": listed.data}),
        }

    def _clarification(self, intent: NamedAppIntent, candidates: list[dict[str, Any]], listed: Any, started: float) -> dict[str, Any]:
        if candidates:
            message = "I did not find one exact app match, so no command was sent. Possible apps:\n" + "\n".join(
                f"- {app['name']} (App ID {app['id']})" for app in candidates
            )
        else:
            message = f"I could not find a Hubitat app named **{intent.requested_name}**. No command was sent."
        display = display_payload(
            "apps",
            "Select app",
            subtitle="No command has been sent",
            items=[
                {
                    "icon": "🧩",
                    "title": app["name"],
                    "value": str(app["id"]),
                    "subtitle": "Select this app or cancel",
                }
                for app in candidates
            ],
        )
        if candidates:
            display["actions"] = [
                {
                    "label": f"{intent.action.title()} {app['name']}",
                    "query": f"{intent.action} app id {app['id']}",
                    "tone": "danger" if intent.action == "disable" else "primary",
                }
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

    def _error(self, message: str, result: Any, started: float, *, app: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-app-control-error",
            "intent": "hubitat-app-control-error",
            "message": message,
            "display": display_payload(
                "error",
                "App command not completed",
                subtitle="No verified app change can be reported",
                items=[{"icon": "🧩", "title": app["name"], "value": str(app["id"])}] if app else [],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"app": app, "mcp": getattr(result, "data", None), "text": getattr(result, "text", None)}),
        }


def install_named_app_controller(application: Any) -> NamedAppController:
    controller = NamedAppController(application)
    original_ask: AskHandler = application.ask

    async def ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        list_match = _LIST_RE.match(query)
        if list_match:
            return await controller.list_apps(list_match.group("state"))
        intent = parse_named_app_intent(query)
        if intent is None:
            return await original_ask(request)
        answer = await controller.control(intent)
        return answer if answer is not None else await original_ask(request)

    application.ask = ask
    return controller


__all__ = [
    "NamedAppController",
    "NamedAppIntent",
    "install_named_app_controller",
    "parse_named_app_intent",
]
