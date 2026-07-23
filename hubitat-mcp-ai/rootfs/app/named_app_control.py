from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from presenter import display_payload, first_value, normalise_text, safe_debug, walk


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_LIST_RE = re.compile(
    r"^\s*(?:please\s+)?(?:list|show)\s+(?:(?P<state>disabled|enabled|active)\s+)?(?:hubitat\s+)?(?:apps|applications)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_WRITE_RE = re.compile(
    r"^\s*(?P<confirm>confirm\s+)?(?P<action>enable|disable)\s+(?P<target>.+?)\s*[.!?]*\s*$",
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
class AppIntent:
    kind: str
    action: str | None = None
    requested_name: str = ""
    variants: tuple[str, ...] = ()
    confirmed: bool = False
    state_filter: str | None = None


def parse_app_intent(query: str) -> AppIntent | None:
    text = str(query or "")
    list_match = _LIST_RE.match(text)
    if list_match:
        return AppIntent(kind="list", state_filter=(list_match.group("state") or "").lower() or None)

    write_match = _WRITE_RE.match(text)
    if not write_match:
        return None
    target = write_match.group("target").strip(" .!?")
    explicit_app = bool(
        re.search(r"(?:^|\s)(?:app|application)(?:\s|$)", target, re.IGNORECASE)
        or re.fullmatch(r"(?:app\s+)?(?:id\s+)?#?\d+", target, re.IGNORECASE)
    )
    # Do not steal ordinary device commands such as "disable bedroom light".
    if not explicit_app:
        return None
    return AppIntent(
        kind="write",
        action=write_match.group("action").lower(),
        requested_name=target,
        variants=_target_variants(target),
        confirmed=bool(write_match.group("confirm")),
    )


class NamedAppController:
    """Guarded deterministic Hubitat app inventory and enable/disable control."""

    def __init__(self, application: Any) -> None:
        self.application = application
        self.mcp = application.mcp

    async def handle(self, intent: AppIntent) -> dict[str, Any] | None:
        started = time.perf_counter()
        listed = await self.mcp.call_tool("hub_list_apps", {})
        if listed.is_error:
            return self._error("I could not read the Hubitat app inventory. No app command was sent.", listed, started)

        apps = self._app_rows(listed.data)
        if intent.kind == "list":
            return self._inventory(intent, apps, listed, started)

        matches = self._exact_matches(apps, intent)
        if len(matches) != 1:
            candidates = matches or self._possible_matches(apps, intent)
            return self._clarification(intent, candidates, listed, started)

        app = matches[0]
        if not intent.confirmed:
            return self._confirmation(intent, app, listed, started)

        desired_disabled = intent.action == "disable"
        available = await self._available_tool_names()
        if "hub_set_app_disabled" not in available:
            return self._error(
                "The MCP server does not advertise `hub_set_app_disabled`. No app command was sent.",
                listed,
                started,
                app=app,
            )

        arguments = {"appId": app["id"], "disabled": desired_disabled}
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

        reported_disabled = _bool_value(_deep_value(result.data, "disabled"))
        command_verified = reported_disabled is desired_disabled
        readback_verified = False
        readback_state: bool | None = None
        try:
            refreshed = await self.mcp.call_tool("hub_list_apps", {})
            if not refreshed.is_error:
                refreshed_rows = self._app_rows(refreshed.data)
                current = next((row for row in refreshed_rows if str(row["id"]) == str(app["id"])), None)
                if current is not None:
                    readback_state = current["disabled"]
                    readback_verified = readback_state is desired_disabled
        except Exception:
            pass

        verified = command_verified or readback_verified
        verb = "disabled" if desired_disabled else "enabled"
        if verified:
            message = f"App {verb} for **{app['name']}**. Hubitat confirmed `disabled: {str(desired_disabled).lower()}`."
            title = f"App {verb}"
            note = "Confirmed by the write response." if command_verified else "Confirmed by app inventory read-back."
        else:
            message = f"The {intent.action} command was accepted for **{app['name']}**, but the new disabled state was not returned or verified."
            title = f"App {intent.action} requested"
            note = "The command was accepted without authoritative state confirmation."

        technical = {
            "requested_action": intent.action,
            "resolved_app": app,
            "tool": "hub_set_app_disabled",
            "arguments": arguments,
            "mcp": result.data,
            "command_verified": command_verified,
            "verification_source": (
                "hub_set_app_disabled response" if command_verified else "hub_list_apps read-back" if readback_verified else None
            ),
            "inventory_readback_verified": readback_verified,
            "inventory_reported_disabled": readback_state,
            "post_state_verified": verified,
        }
        return {
            "success": True,
            "route": "mcp-app-control",
            "intent": f"app-{intent.action}-{'verified' if verified else 'accepted'}",
            "message": message,
            "answered_by": "Hubitat MCP deterministic app controller",
            "display": display_payload(
                "app-control",
                title,
                subtitle=note,
                metrics=[
                    {"label": "Action", "value": intent.action.title(), "icon": "🎯"},
                    {"label": "App ID", "value": str(app["id"]), "icon": "🧩"},
                ],
                items=[
                    {
                        "icon": "🧩",
                        "title": app["name"],
                        "value": verb.title() if verified else "Accepted",
                        "subtitle": note,
                    }
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(technical),
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
            disabled = _bool_value(first_value(item, "disabled"))
            if disabled is None:
                status = str(first_value(item, "status") or "").strip().lower()
                if status in {"disabled", "inactive"}:
                    disabled = True
                elif status in {"enabled", "active"}:
                    disabled = False
            key = str(app_id)
            rows[key] = {
                "id": app_id,
                "name": normalise_text(name),
                "normalised": _normalise(name),
                "disabled": disabled,
                "type": normalise_text(first_value(item, "type", "appType") or ""),
            }
        return sorted(rows.values(), key=lambda row: (row["name"].lower(), str(row["id"])))

    @staticmethod
    def _requested_id(intent: AppIntent) -> str | None:
        match = re.fullmatch(r"(?:app\s+)?(?:id\s+)?#?(\d+)", _normalise(intent.requested_name))
        return match.group(1) if match else None

    @classmethod
    def _exact_matches(cls, apps: list[dict[str, Any]], intent: AppIntent) -> list[dict[str, Any]]:
        requested_id = cls._requested_id(intent)
        if requested_id is not None:
            return [app for app in apps if str(app["id"]) == requested_id]
        variants = set(intent.variants)
        return [app for app in apps if app["normalised"] in variants]

    @staticmethod
    def _possible_matches(apps: list[dict[str, Any]], intent: AppIntent) -> list[dict[str, Any]]:
        candidates = [
            app
            for app in apps
            if any(variant in app["normalised"] or app["normalised"] in variant for variant in intent.variants)
        ]
        return candidates[:8]

    def _inventory(self, intent: AppIntent, apps: list[dict[str, Any]], listed: Any, started: float) -> dict[str, Any]:
        state_filter = intent.state_filter
        filtered = apps
        if state_filter == "disabled":
            filtered = [app for app in apps if app["disabled"] is True]
        elif state_filter in {"enabled", "active"}:
            filtered = [app for app in apps if app["disabled"] is False]

        active_count = sum(app["disabled"] is False for app in apps)
        disabled_count = sum(app["disabled"] is True for app in apps)
        unknown_count = sum(app["disabled"] is None for app in apps)
        title = "Hubitat apps" if not state_filter else f"{state_filter.title()} Hubitat apps"
        message = f"{len(filtered)} apps returned. Overall: {active_count} enabled, {disabled_count} disabled, {unknown_count} unknown."
        return {
            "success": True,
            "route": "mcp-app-inventory",
            "intent": "app-inventory",
            "message": message,
            "answered_by": "Hubitat MCP deterministic app controller",
            "display": display_payload(
                "apps",
                title,
                subtitle=message,
                metrics=[
                    {"label": "Total", "value": str(len(apps)), "icon": "🧩"},
                    {"label": "Enabled", "value": str(active_count), "icon": "▶️"},
                    {"label": "Disabled", "value": str(disabled_count), "icon": "⏸️"},
                    {"label": "Unknown", "value": str(unknown_count), "icon": "❓"},
                ],
                items=[
                    {
                        "icon": "🧩",
                        "title": app["name"],
                        "value": "Disabled" if app["disabled"] is True else "Enabled" if app["disabled"] is False else "Unknown",
                        "subtitle": f"App ID {app['id']}" + (f" · {app['type']}" if app["type"] else ""),
                    }
                    for app in filtered
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"filter": state_filter, "apps": filtered, "mcp": listed.data}),
        }

    def _confirmation(self, intent: AppIntent, app: dict[str, Any], listed: Any, started: float) -> dict[str, Any]:
        display = display_payload(
            "app-control",
            f"Confirm app {intent.action}",
            subtitle="No command has been sent",
            items=[
                {
                    "icon": "🧩",
                    "title": app["name"],
                    "value": f"App ID {app['id']}",
                    "subtitle": "Select Confirm or Cancel",
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
            "intent": "app-control-confirmation",
            "message": f"Confirm {intent.action} for **{app['name']}**. No command has been sent.",
            "display": display,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested": intent.requested_name, "resolved_app": app, "mcp": listed.data}),
        }

    def _clarification(
        self,
        intent: AppIntent,
        candidates: list[dict[str, Any]],
        listed: Any,
        started: float,
    ) -> dict[str, Any]:
        if candidates:
            message = "I did not find one exact app match, so no command was sent. Select an app or cancel."
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
            "intent": "app-control-clarification",
            "message": message,
            "display": display,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested": intent.requested_name, "candidates": candidates, "mcp": listed.data}),
        }

    def _error(self, message: str, result: Any, started: float, *, app: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-app-control-error",
            "intent": "app-control-error",
            "message": message,
            "display": display_payload(
                "app-control",
                "App command not sent",
                subtitle=message,
                items=[{"icon": "🧩", "title": app["name"], "value": str(app["id"])}] if app else [],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"app": app, "mcp": getattr(result, "data", None), "error": getattr(result, "text", "")}),
        }


def install_named_app_controller(application: Any) -> NamedAppController:
    controller = NamedAppController(application)
    original_ask: AskHandler = application.ask

    async def ask(request: Any) -> dict[str, Any]:
        intent = parse_app_intent(getattr(request, "query", ""))
        if intent is None:
            return await original_ask(request)
        return await controller.handle(intent)

    application.ask = ask
    return controller


__all__ = ["AppIntent", "NamedAppController", "install_named_app_controller", "parse_app_intent"]
