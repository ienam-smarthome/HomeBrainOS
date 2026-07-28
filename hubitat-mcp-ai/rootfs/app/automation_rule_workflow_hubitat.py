from __future__ import annotations

import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from automation_rule_workflow import (
    AutomationRuleWorkflow,
    PendingRule,
    RuleTool,
    _first,
    _normalise,
    _result_mapping,
    _session_id,
    _tool_rows,
)
from device_intelligence_catalogue import _capability_names
from device_intelligence_index import _attributes, _label, _room_name
from presenter import display_payload, safe_debug


# Preserve the release layer's patch of the live-schema module global.
live_module = sys.modules[__name__]

# Live

AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

@dataclass(slots=True)
class LiveRuleTool:
    name: str
    description: str
    schema: dict[str, Any]
    gateway: str | None = None

def _command_names(item: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("supportedCommands", "commands"):
        value = item.get(key)
        if isinstance(value, str):
            names.add(value)
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("command")
                    if name:
                        names.add(str(name))
                elif entry not in (None, ""):
                    names.add(str(entry))
        elif isinstance(value, dict):
            names.update(str(name) for name in value)
    return {_normalise(name).replace(" ", "") for name in names}

def _is_notification_device(item: dict[str, Any]) -> bool:
    capabilities = {
        _normalise(name).replace(" ", "")
        for name in _capability_names(item)
    }
    commands = _command_names(item)
    return bool(
        capabilities.intersection(
            {
                "notification",
                "devicenotification",
                "pushnotification",
                "speechsynthesis",
            }
        )
        or commands.intersection(
            {
                "devicenotification",
                "sendnotification",
                "notify",
            }
        )
    )

class LiveSchemaAutomationRuleWorkflow(AutomationRuleWorkflow):
    """Guarded rule workflow for both current and legacy MCP naming.

    Current MCP releases expose create_rule/update_rule/list_rules as core tools and
    test_rule through manage_rules_admin. Older installations may expose hub_*
    equivalents behind gateways. This implementation stores the gateway alongside
    each discovered schema and invokes hidden tools through {tool,args}, avoiding
    assumptions about one server version.
    """

    async def _discover_rule_tools(self, *, refresh: bool) -> dict[str, LiveRuleTool]:
        found: dict[str, LiveRuleTool] = {}
        gateways: set[str] = set()
        visible = await self.client.list_tools(refresh=refresh)
        for tool in visible:
            name = str(tool.name)
            description = str(getattr(tool, "description", "") or "")
            schema = dict(getattr(tool, "input_schema", {}) or {})
            text = f"{name} {description}".lower()
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            is_gateway = (
                {"tool", "args"}.issubset(properties)
                or "gateway" in text
                or name.startswith(("manage_", "hub_manage_"))
            )
            if "rule" in text and is_gateway:
                gateways.add(name)
            if "rule" in name.lower() and not is_gateway:
                found[name] = LiveRuleTool(name, description, schema, None)

        # Preserve compatibility with the older hub_* gateway mapper.
        if hasattr(self.client, "gateway_map"):
            try:
                gateway_map = await self.client.gateway_map(refresh=refresh)
            except Exception:
                gateway_map = {}
            for hidden, gateway in gateway_map.items():
                if "rule" in str(hidden).lower():
                    gateways.add(str(gateway))

        for gateway in sorted(gateways):
            try:
                catalogue = await self.client.call_tool(gateway, {})
            except Exception:
                continue
            if catalogue.is_error:
                continue
            for row in _tool_rows(catalogue.data):
                name = str(row["name"])
                if "rule" not in name.lower():
                    continue
                found[name] = LiveRuleTool(
                    name=name,
                    description=str(row.get("description") or ""),
                    schema=dict(row.get("schema") or {}),
                    gateway=gateway,
                )
        return found

    async def _call_rule_tool(
        self,
        tool: LiveRuleTool | RuleTool,
        arguments: dict[str, Any],
    ):
        gateway = getattr(tool, "gateway", None)
        if gateway:
            return await self.client.call_tool(
                str(gateway),
                {"tool": tool.name, "args": dict(arguments)},
            )
        return await self.client.call_tool(tool.name, dict(arguments))

    async def _draft(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        recommendation_labels = [
            str(value).strip()
            for value in (recommendation.get("devices") or [])
            if str(value).strip()
        ]
        refs: list[dict[str, Any]] = []
        for label in recommendation_labels:
            exact = None
            try:
                exact, _ = await self.device_index.exact_device(label)
            except Exception:
                exact = None
            if isinstance(exact, dict):
                refs.append(self._device_ref(exact, fallback_label=label))
            else:
                refs.append(
                    {
                        "id": "",
                        "label": label,
                        "room": recommendation.get("room"),
                        "attributes": {},
                    }
                )

        selected: list[dict[str, Any]] = []
        try:
            selected = list(await self.device_index.enriched_devices(force=True))
        except Exception:
            selected = []
        notification_targets = [
            self._device_ref(item)
            for item in selected
            if item.get("disabled") is not True and _is_notification_device(item)
        ]
        notification_targets = self._dedupe_refs(notification_targets)

        kind = str(recommendation.get("type") or "").strip()
        name = str(recommendation.get("title") or "HomeBrain automation").strip()
        unresolved: list[str] = []
        triggers: list[dict[str, Any]] = []
        conditions: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []

        if kind == "cold-storage-door":
            contact = next(
                (
                    item
                    for item in refs
                    if "contact" in (item.get("attributes") or {})
                ),
                refs[0] if refs else None,
            )
            if not contact or not contact.get("id"):
                unresolved.append("The contact sensor could not be resolved to one selected MCP device ID.")
            if len(notification_targets) == 0:
                notifier = None
                unresolved.append(
                    "No selected Notification-capable device was found. Add a Hubitat mobile/push notification device to the MCP selected-device list, refresh the cache, and build again."
                )
            elif len(notification_targets) > 1:
                notifier = None
                names = ", ".join(item["label"] for item in notification_targets[:8])
                unresolved.append(
                    "More than one Notification-capable device is selected. HomeBrain will not guess the recipient. Keep one intended notification device selected or choose one in a future recipient selector. Candidates: "
                    + names
                )
            else:
                notifier = notification_targets[0]

            if contact and contact.get("id"):
                contact_id = str(contact["id"])
                triggers = [
                    {
                        "type": "device_event",
                        "deviceId": contact_id,
                        "attribute": "contact",
                        "value": "open",
                        "duration": 120,
                    },
                    {
                        "type": "device_event",
                        "deviceId": contact_id,
                        "attribute": "contact",
                        "value": "closed",
                    },
                ]
                closed_condition = {
                    "type": "device_state",
                    "deviceId": contact_id,
                    "attribute": "contact",
                    "operator": "==",
                    "value": "closed",
                }
                open_condition = {
                    "type": "device_state",
                    "deviceId": contact_id,
                    "attribute": "contact",
                    "operator": "==",
                    "value": "open",
                }
                else_actions: list[dict[str, Any]] = []
                if notifier:
                    notifier_id = str(notifier["id"])
                    else_actions = [
                        {
                            "type": "send_notification",
                            "deviceId": notifier_id,
                            "message": f"{contact['label']} has been open for 2 minutes.",
                        },
                        {
                            "type": "delay",
                            "seconds": 300,
                            "delayId": "homebrain-fridge-door-repeat",
                        },
                        {
                            "type": "if_then_else",
                            "condition": open_condition,
                            "thenActions": [
                                {
                                    "type": "send_notification",
                                    "deviceId": notifier_id,
                                    "message": f"{contact['label']} is still open.",
                                }
                            ],
                            "elseActions": [],
                        },
                    ]
                actions = [
                    {
                        "type": "if_then_else",
                        "condition": closed_condition,
                        "thenActions": [
                            {
                                "type": "cancel_delayed",
                                "delayId": "homebrain-fridge-door-repeat",
                            }
                        ],
                        "elseActions": else_actions,
                    }
                ]
                if notifier:
                    refs = self._dedupe_refs(refs + [notifier])

        elif kind == "motion-lighting":
            sensors = [item for item in refs if "motion" in (item.get("attributes") or {})]
            lights = [item for item in refs if item not in sensors]
            if not sensors or any(not item.get("id") for item in sensors):
                unresolved.append("No exact motion-sensor ID was available.")
            if not lights or any(not item.get("id") for item in lights):
                unresolved.append("No exact controllable light ID was available.")
            if sensors and lights and not unresolved:
                sensor_ids = [str(item["id"]) for item in sensors]
                triggers = [
                    {
                        "type": "device_event",
                        "deviceIds": sensor_ids,
                        "attribute": "motion",
                        "value": "active",
                        "matchMode": "any",
                    }
                ]
                actions = [{"type": "cancel_delayed", "delayId": "homebrain-motion-off"}]
                actions.extend(
                    {
                        "type": "device_command",
                        "deviceId": str(light["id"]),
                        "command": "on",
                    }
                    for light in lights
                )
                actions.append(
                    {"type": "delay", "seconds": 180, "delayId": "homebrain-motion-off"}
                )
                actions.extend(
                    {
                        "type": "device_command",
                        "deviceId": str(light["id"]),
                        "command": "off",
                    }
                    for light in lights
                )

        else:
            unresolved.append(
                f"Automatic rule compilation is not implemented yet for candidate type {kind or 'unknown'}."
            )

        if not triggers:
            unresolved.append("No valid MCP rule trigger was compiled.")
        if not actions:
            unresolved.append("No valid MCP rule action was compiled.")

        return {
            "name": name,
            "description": str(
                recommendation.get("reason")
                or "Created from a grounded HomeBrain recommendation."
            ),
            "enabled": False,
            "testRule": False,
            "triggers": triggers,
            "conditions": conditions,
            "conditionLogic": "all",
            "actions": actions,
            "type": kind,
            "room": recommendation.get("room"),
            "devices": refs,
            "notification_candidates": notification_targets,
            "unresolved": list(dict.fromkeys(unresolved)),
            "review": {
                "trigger_text": recommendation.get("trigger"),
                "action_text": recommendation.get("action"),
                "safeguard_text": recommendation.get("safeguard"),
            },
        }

    @staticmethod
    def _device_ref(item: dict[str, Any], fallback_label: str = "") -> dict[str, Any]:
        return {
            "id": str(item.get("id") or item.get("deviceId") or item.get("device_id") or ""),
            "label": _label(item) or fallback_label or "Unnamed device",
            "room": _room_name(item),
            "attributes": _attributes(item),
        }

    @staticmethod
    def _dedupe_refs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values: dict[str, dict[str, Any]] = {}
        for item in items:
            key = str(item.get("id") or _normalise(item.get("label")))
            if key:
                values[key] = item
        return list(values.values())

    def _compile_create_args(
        self,
        tool: LiveRuleTool | RuleTool,
        draft: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        unresolved = [str(item) for item in (draft.get("unresolved") or []) if str(item)]
        if unresolved:
            return None, " ".join(unresolved)

        schema = tool.schema if isinstance(tool.schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = {str(item) for item in (schema.get("required") or [])}
        args: dict[str, Any] = {}
        paused_field = False
        structured_field = False

        for name, property_schema in properties.items():
            prop = property_schema if isinstance(property_schema, dict) else {}
            key = _normalise(name).replace(" ", "")
            value: Any = None
            if key in {"name", "rulename", "title", "label"}:
                value = draft["name"]
            elif key in {"description", "summary", "notes"}:
                value = draft["description"]
            elif key in {"enabled", "active", "isenabled"}:
                value = False
                paused_field = True
            elif key in {"paused", "ispaused", "pause"}:
                value = True
                paused_field = True
            elif key in {"draft", "isdraft", "createasdraft"}:
                value = True
                paused_field = True
            elif key in {"testrule", "istestrule"}:
                value = False
            elif key in {"confirm", "confirmed"}:
                value = True
            elif key in {"rule", "definition", "ruledefinition", "spec", "config", "payload", "request"}:
                value = {
                    field: draft[field]
                    for field in (
                        "name",
                        "description",
                        "enabled",
                        "testRule",
                        "triggers",
                        "conditions",
                        "conditionLogic",
                        "actions",
                    )
                }
                structured_field = True
            elif key in {"trigger", "triggers"}:
                value = draft["triggers"] if key == "triggers" else draft["triggers"][0]
                structured_field = True
            elif key in {"condition", "conditions"}:
                value = draft["conditions"] if key == "conditions" else (draft["conditions"][0] if draft["conditions"] else {})
                structured_field = True
            elif key in {"conditionlogic", "logic"}:
                value = draft["conditionLogic"]
            elif key in {"action", "actions"}:
                value = draft["actions"] if key == "actions" else draft["actions"][0]
                structured_field = True
            if value is not None:
                kind = str(prop.get("type") or "").lower()
                if kind == "string" and not isinstance(value, str):
                    import json

                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                elif kind == "array" and not isinstance(value, list):
                    value = [value]
                args[name] = value

        missing = [name for name in required if name not in args]
        if missing:
            return None, "unresolved required fields: " + ", ".join(sorted(missing))
        if not structured_field:
            return None, "schema has no supported trigger/action or structured rule fields"
        if self.require_paused_create and not paused_field and "draft" not in tool.name.lower():
            return None, "schema cannot guarantee disabled or paused creation"
        return args, None

    async def _existing_rule(self, name: str) -> dict[str, Any] | None:
        tools = await self._discover_rule_tools(refresh=False)
        candidates = [
            tool
            for tool in tools.values()
            if tool.name.lower() in {"list_rules", "hub_list_rules"}
            or "list_rules" in tool.name.lower()
        ]
        candidates.sort(key=lambda tool: (0 if tool.name == "list_rules" else 1, tool.name))
        for tool in candidates:
            try:
                result = await self._call_rule_tool(tool, {})
            except Exception:
                continue
            if result.is_error:
                continue
            target = _normalise(name)
            for item in self._rule_rows(result.data):
                if _normalise(item.get("name")) == target:
                    return item
        return None

    @staticmethod
    def _choose_operation_tool(
        tools: dict[str, LiveRuleTool],
        operation: str,
    ) -> LiveRuleTool | None:
        preferences = {
            "run": ("test_rule", "dry_run_rule", "run_rule", "call_rule"),
            "enable": ("resume_rule", "enable_rule", "update_rule", "set_rule"),
            "pause": ("pause_rule", "disable_rule", "update_rule", "set_rule"),
        }[operation]
        candidates = [
            tool
            for tool in tools.values()
            if any(token in tool.name.lower() for token in preferences)
        ]
        candidates.sort(
            key=lambda tool: (
                next(
                    (index for index, token in enumerate(preferences) if token in tool.name.lower()),
                    len(preferences),
                ),
                tool.name,
            )
        )
        return candidates[0] if candidates else None

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        if pending.stage != "draft" or pending.draft is None:
            return self._wrong_stage("Build this rule first, then review the draft before creating it.")
        if not self.write_enabled:
            return self._wrong_stage("Rule writes are disabled in the HomeBrain add-on configuration.")
        if pending.create_tool is None or pending.create_args is None:
            return self._wrong_stage(
                f"This draft cannot be created safely: {pending.compile_error or 'no compatible disabled-create tool is available'}."
            )
        existing = await self._existing_rule(pending.draft["name"])
        if existing is not None:
            pending.created_rule = existing
            pending.stage = "created-paused" if self._looks_paused(existing) else "created"
            return self._duplicate(existing)

        started = time.perf_counter()
        result = await self._call_rule_tool(pending.create_tool, dict(pending.create_args))
        if result.is_error:
            return self._tool_error("create", result.text or "Hubitat rejected the rule creation request")
        created = self._created_rule(result.data, pending.draft["name"])
        created["tool"] = pending.create_tool.name
        created["requested_enabled"] = False
        pending.created_rule = created
        pending.stage = "created-paused"
        pending.expires_at = time.time() + self.store.ttl_seconds

        if self._looks_active(created):
            pause_answer = await self._call_operation(pending, "pause")
            if pause_answer.get("success"):
                created["status"] = "Disabled"
            else:
                created["warning"] = "The create response appeared active and automatic disable failed. Review it in Hubitat immediately."
                pending.stage = "created"

        return {
            "success": True,
            "route": "mcp-rule-created",
            "intent": "automation-rule-created",
            "message": (
                f"Created **{created.get('name') or pending.draft['name']}** in Hubitat with enabled=false. "
                "It will not monitor the fridge until you explicitly enable it."
            ),
            "answered_by": "Hubitat MCP",
            "display": self._created_display(pending),
            "created_rule": created,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "create_tool": pending.create_tool.name,
                    "create_gateway": getattr(pending.create_tool, "gateway", None),
                    "create_arguments": pending.create_args,
                    "created_rule": created,
                }
            ),
        }

    async def _call_operation(self, pending: PendingRule, operation: str) -> dict[str, Any]:
        tools = pending.discovered_tools or await self._discover_rule_tools(refresh=True)
        tool = self._choose_operation_tool(tools, operation)
        if tool is None:
            return self._wrong_stage(f"The connected MCP server does not expose a compatible {operation} rule tool.")
        args, error = self._compile_reference_args(tool, pending, operation)
        if error:
            return self._wrong_stage(error)
        started = time.perf_counter()
        result = await self._call_rule_tool(tool, args)
        if result.is_error:
            return self._tool_error(operation, result.text or f"Hubitat rejected the {operation} request")

        title = str((pending.created_rule or {}).get("name") or (pending.draft or {}).get("name") or "Rule")
        dry_run = "test_rule" in tool.name.lower() or "dry" in tool.description.lower()
        if operation == "run":
            if dry_run:
                message = f"Dry-run tested **{title}**. Hubitat evaluated the rule without executing its actions."
                last_action = "Dry-run tested"
            else:
                message = f"Ran **{title}** once after your explicit test command. Check that the expected action occurred."
                last_action = "Ran once"
            route = "mcp-rule-tested"
            intent = "automation-rule-tested"
        elif operation == "enable":
            pending.stage = "enabled"
            pending.created_rule["status"] = "Active"
            message = f"Enabled **{title}**. It can now run automatically when its trigger conditions are met."
            last_action = "Enabled"
            route = "mcp-rule-enabled"
            intent = "automation-rule-enabled"
        else:
            pending.stage = "created-paused"
            pending.created_rule["status"] = "Disabled"
            message = f"Disabled **{title}**. It will not run automatically until enabled again."
            last_action = "Disabled"
            route = "mcp-rule-paused"
            intent = "automation-rule-paused"
        pending.expires_at = time.time() + self.store.ttl_seconds
        display = self._created_display(pending, operation=last_action)
        if dry_run:
            display["note"] = "This was a dry-run only. No notification or device action was executed. Enable the rule separately when ready."
        return {
            "success": True,
            "route": route,
            "intent": intent,
            "message": message,
            "answered_by": "Hubitat MCP",
            "display": display,
            "created_rule": pending.created_rule,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "operation": operation,
                    "dry_run": dry_run,
                    "tool": tool.name,
                    "gateway": getattr(tool, "gateway", None),
                    "arguments": args,
                    "result": result.data,
                }
            ),
        }

    @staticmethod
    def _created_display(pending: PendingRule, operation: str | None = None) -> dict[str, Any]:
        rule = pending.created_rule or {}
        draft = pending.draft or {}
        status = str(rule.get("status") or ("Active" if pending.stage == "enabled" else "Disabled"))
        display = display_payload(
            "automation-rule-created",
            str(rule.get("name") or draft.get("name") or "Automation rule"),
            subtitle=f"Hubitat rule · {status}",
            metrics=[
                {"label": "Rule ID", "value": rule.get("id") or "Returned by name", "icon": "🆔"},
                {"label": "Status", "value": status, "icon": "▶️" if pending.stage == "enabled" else "⏸️"},
                {"label": "Last action", "value": operation or "Created", "icon": "🧰"},
            ],
            note="Dry-run test evaluates the rule without actions. Enable starts automatic monitoring; disable stops it again.",
        )
        if pending.stage == "enabled":
            display["actions"] = [
                {"label": "Dry-run test", "query": "Run test once", "tone": "warning", "icon": "🧪"},
                {"label": "Disable rule", "query": "Pause this rule", "tone": "danger", "icon": "⏸️"},
            ]
        else:
            display["actions"] = [
                {"label": "Dry-run test", "query": "Run test once", "tone": "warning", "icon": "🧪"},
                {"label": "Enable rule", "query": "Enable this rule", "tone": "danger", "icon": "▶️"},
            ]
        return display

def install_live_automation_rule_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> LiveSchemaAutomationRuleWorkflow:
    original_ask: AskHandler = application.ask
    service = LiveSchemaAutomationRuleWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        command = service.command(query)
        if command:
            answer = await service.handle(request, command)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        await service.remember_answer(_session_id(request), answer)
        return answer

    application.ask = ask_with_rule_workflow
    application.automation_rule_workflow = service
    return service

# Release

def _strict_notification_device(item: dict[str, Any]) -> bool:
    """Accept only devices that can receive Hubitat notification actions.

    Speech-synthesis devices are intentionally excluded: ``send_notification``
    requires a Notification-capable target and must not silently become text to
    speech on a speaker. Custom notification drivers remain supported when they
    expose a recognised notification command.
    """
    capabilities = {
        _normalise(name).replace(" ", "")
        for name in _capability_names(item)
    }
    commands: set[str] = set()
    for key in ("supportedCommands", "commands"):
        value = item.get(key)
        if isinstance(value, str):
            commands.add(value)
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("command")
                    if name:
                        commands.add(str(name))
                elif entry not in (None, ""):
                    commands.add(str(entry))
        elif isinstance(value, dict):
            commands.update(str(name) for name in value)
    commands = {_normalise(name).replace(" ", "") for name in commands}
    return bool(
        capabilities.intersection(
            {
                "notification",
                "devicenotification",
                "pushnotification",
            }
        )
        or commands.intersection(
            {
                "devicenotification",
                "sendnotification",
                "notify",
            }
        )
    )

live_module._is_notification_device = _strict_notification_device

class ReleaseAutomationRuleWorkflow(LiveSchemaAutomationRuleWorkflow):
    """Release wrapper with visible safety reasons and write invalidation."""

    async def remember_answer(self, session_id: str, answer: dict[str, Any]) -> None:
        recommendation = answer.get("recommendation")
        if isinstance(recommendation, dict) and recommendation.get("type") == "cold-storage-door":
            previous_action = str(recommendation.get("action") or "")
            supported_action = (
                "Send a notification through one selected Hubitat Notification device, "
                "then repeat once after 5 minutes if the contact is still open."
            )
            supported_safeguard = (
                "Cancel the pending repeat immediately when the contact closes."
            )
            recommendation["action"] = supported_action
            recommendation["safeguard"] = supported_safeguard
            message = str(answer.get("message") or "")
            if previous_action and previous_action in message:
                answer["message"] = message.replace(previous_action, supported_action)
            display = answer.get("display")
            if isinstance(display, dict):
                items = display.get("items")
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = str(item.get("title") or "").lower()
                        if title == "action":
                            item["subtitle"] = supported_action
                        elif title == "safeguard":
                            item["subtitle"] = supported_safeguard
                summary = str(display.get("summary") or "")
                if previous_action and previous_action in summary:
                    display["summary"] = summary.replace(previous_action, supported_action)
        await super().remember_answer(session_id, answer)

    async def _build(self, pending):
        answer = await super()._build(pending)
        display = answer.get("display")
        if isinstance(display, dict):
            display["summary"] = answer.get("message")
            unresolved = (answer.get("rule_draft") or {}).get("unresolved") or []
            if unresolved:
                display["note"] = " ".join(str(item) for item in unresolved)
        return answer

    async def _create(self, pending):
        answer = await super()._create(pending)
        if not answer.get("success") or pending.created_rule is None:
            return answer

        # Some MCP releases confirm creation but omit the child app/rule ID from
        # the create response. Resolve the exact new name immediately so Dry-run,
        # Enable and Disable never send a rule name where the schema requires ID.
        if not str(pending.created_rule.get("id") or "").strip():
            draft_name = str((pending.draft or {}).get("name") or "").strip()
            resolved = await self._existing_rule(draft_name) if draft_name else None
            if resolved and resolved.get("id"):
                pending.created_rule.update(resolved)
                answer["created_rule"] = dict(pending.created_rule)
                answer["display"] = self._created_display(pending)
                technical = answer.get("technical")
                if isinstance(technical, dict):
                    technical["created_rule_id_resolved_by_name"] = True
            else:
                pending.stage = "created"
                warning = (
                    "The rule was created, but Hubitat did not return its ID and an exact "
                    "name lookup could not resolve it. Review the rule in Hubitat before "
                    "testing or enabling it."
                )
                pending.created_rule["warning"] = warning
                answer["message"] = str(answer.get("message") or "") + " " + warning
                display = answer.get("display")
                if isinstance(display, dict):
                    display["actions"] = []
                    display["note"] = warning
        return answer

    async def _operate(self, pending, operation: str):
        if pending.created_rule is not None and not str(
            pending.created_rule.get("id") or ""
        ).strip():
            return self._wrong_stage(
                "The created rule ID could not be verified. Review it in Hubitat before testing or enabling it."
            )
        return await super()._operate(pending, operation)

    @staticmethod
    def _choose_operation_tool(tools, operation: str):
        if operation == "run":
            # The UI promises a dry-run. Never substitute run_rule/call_rule, which
            # may execute real actions on older servers.
            candidates = [
                tool
                for tool in tools.values()
                if "test_rule" in tool.name.lower()
                or "dry_run_rule" in tool.name.lower()
                or "dry run" in str(tool.description or "").lower()
            ]
            candidates.sort(
                key=lambda tool: (
                    0 if "test_rule" in tool.name.lower() else 1,
                    tool.name,
                )
            )
            return candidates[0] if candidates else None
        return LiveSchemaAutomationRuleWorkflow._choose_operation_tool(
            tools,
            operation,
        )

    async def _call_rule_tool(self, tool, arguments):
        result = await super()._call_rule_tool(tool, arguments)
        if result.is_error:
            return result
        name = str(getattr(tool, "name", "") or "").lower()
        unprefixed = name[4:] if name.startswith("hub_") else name
        changes_rule = unprefixed.startswith(
            (
                "create_rule",
                "create_visual_rule",
                "update_rule",
                "pause_rule",
                "resume_rule",
                "enable_rule",
                "disable_rule",
                "set_rule",
            )
        )
        if changes_rule and hasattr(self.client, "invalidate"):
            try:
                await self.client.invalidate("catalog")
            except Exception:
                # A successful Hubitat write must not be turned into a failure by
                # optional local cache invalidation.
                pass
        return result

def install_release_automation_rule_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> ReleaseAutomationRuleWorkflow:
    original_ask: AskHandler = application.ask
    service = ReleaseAutomationRuleWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        command = service.command(query)
        if command:
            answer = await service.handle(request, command)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        await service.remember_answer(_session_id(request), answer)
        return answer

    application.ask = ask_with_rule_workflow
    application.automation_rule_workflow = service
    return service

# Native Rm

_NATIVE_SET_RULE_NAMES = {"hub_set_rule", "set_rule"}

_NATIVE_PAUSE_NAMES = {"hub_set_rule_paused", "set_rule_paused"}

_GUIDE_NAMES = {"hub_get_tool_guide", "get_tool_guide"}

_BACKUP_NAMES = {"hub_create_backup", "create_backup"}

def _positive_int(value: Any) -> int | None:
    try:
        number = int(str(value).strip())
    except Exception:
        return None
    return number if number > 0 else None

def _nested_value(value: Any, *names: str) -> Any:
    wanted = {_normalise(name).replace(" ", "") for name in names}
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalise(key).replace(" ", "") in wanted and item not in (None, ""):
                return item
        for item in value.values():
            found = _nested_value(item, *names)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for item in value:
            found = _nested_value(item, *names)
            if found not in (None, ""):
                return found
    return None

def _best_practice_key(value: Any) -> str | None:
    direct = _nested_value(
        value,
        "bestPracticeKey",
        "best_practice_key",
        "acknowledgmentKey",
        "acknowledgementKey",
    )
    if direct not in (None, ""):
        return str(direct).strip()

    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value or "")
    patterns = (
        r"bestPracticeKey\s*[=:]\s*[\"']?([A-Za-z0-9._-]{4,128})",
        r"best[ -]?practice\s+(?:acknowledg(?:e)?ment\s+)?key\s*[=:]\s*[\"']?([A-Za-z0-9._-]{4,128})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def _native_rule_plan(draft: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if str(draft.get("type") or "") != "cold-storage-door":
        return None, "Native Rule Machine compilation is currently limited to the fridge/freezer door alert."

    unresolved = [str(item) for item in (draft.get("unresolved") or []) if str(item)]
    if unresolved:
        return None, " ".join(unresolved)

    devices = list(draft.get("devices") or [])
    contact = next(
        (
            item
            for item in devices
            if isinstance(item, dict) and "contact" in (item.get("attributes") or {})
        ),
        devices[0] if devices else None,
    )
    notifiers = list(draft.get("notification_candidates") or [])
    notifier = notifiers[0] if len(notifiers) == 1 else None
    contact_id = _positive_int((contact or {}).get("id"))
    notifier_id = _positive_int((notifier or {}).get("id"))
    if contact_id is None:
        return None, "The contact sensor could not be resolved to one positive Hubitat device ID."
    if notifier_id is None:
        return None, "Exactly one selected Notification-capable device is required."

    contact_label = str((contact or {}).get("label") or "Fridge Door")
    condition_closed = {
        "capability": "Contact",
        "deviceIds": [contact_id],
        "state": "closed",
    }
    condition_open = {
        "capability": "Contact",
        "deviceIds": [contact_id],
        "state": "open",
    }
    triggers = [
        {
            "capability": "Contact",
            "deviceIds": [contact_id],
            "state": "open",
            "andStays": {"seconds": 120},
        },
        {
            "capability": "Contact",
            "deviceIds": [contact_id],
            "state": "closed",
        },
    ]
    actions = [
        {
            "capability": "ifThen",
            "expression": {"conditions": [condition_closed], "operator": "AND"},
        },
        {"capability": "cancelDelay"},
        {"capability": "else"},
        {
            "capability": "notification",
            "deviceIds": [notifier_id],
            "message": f"{contact_label} has been open for 2 minutes.",
        },
        {"capability": "delay", "seconds": 300, "cancelable": True},
        {
            "capability": "ifThen",
            "expression": {"conditions": [condition_open], "operator": "AND"},
        },
        {
            "capability": "notification",
            "deviceIds": [notifier_id],
            "message": f"{contact_label} is still open.",
        },
        {"capability": "endIf"},
        {"capability": "endIf"},
    ]
    return {
        "triggers": triggers,
        "actions": actions,
        "contact_id": contact_id,
        "notification_device_id": notifier_id,
    }, None

class NativeRuleMachineAutomationWorkflow(ReleaseAutomationRuleWorkflow):
    """Guarded native RM 5.1 creation for current MCP Rule Server releases.

    Current MCP 3.4.x creates Rule Machine rules through ``hub_set_rule`` rather
    than a create_rule tool. An empty shell is created first, paused immediately,
    populated while paused, and left paused until the user explicitly enables it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._best_practice_cache: tuple[float, str | None] | None = None

    @staticmethod
    def _is_native_set_rule(tool: Any) -> bool:
        return str(getattr(tool, "name", "") or "").lower() in _NATIVE_SET_RULE_NAMES

    def _choose_create_tool(self, tools, draft):
        plan, plan_error = _native_rule_plan(draft)
        native = [tool for tool in tools.values() if self._is_native_set_rule(tool)]
        native.sort(key=lambda tool: (0 if tool.name == "hub_set_rule" else 1, tool.name))
        if native and plan is not None:
            token = "homebrain-" + uuid.uuid4().hex[:20]
            draft["native_rule_machine_plan"] = plan
            draft["native_rule_machine_op_token"] = token
            # Creation intentionally starts with an EMPTY shell. _create pauses it
            # before any trigger or action is written.
            return native[0], {"name": draft["name"], "confirm": True, "opToken": token}, None
        if native and plan_error:
            return None, None, plan_error
        return super()._choose_create_tool(tools, draft)

    async def _find_tool(self, names: set[str], *, refresh: bool = False) -> LiveRuleTool | None:
        visible = await self.client.list_tools(refresh=refresh)
        for tool in visible:
            if str(tool.name).lower() in names:
                return LiveRuleTool(
                    name=str(tool.name),
                    description=str(getattr(tool, "description", "") or ""),
                    schema=dict(getattr(tool, "input_schema", {}) or {}),
                    gateway=None,
                )

        gateway_map: dict[str, str] = {}
        if hasattr(self.client, "gateway_map"):
            try:
                gateway_map = await self.client.gateway_map(refresh=refresh)
            except Exception:
                gateway_map = {}
        for requested in sorted(names):
            gateway = gateway_map.get(requested)
            if not gateway:
                continue
            try:
                catalogue = await self.client.call_tool(gateway, {})
            except Exception:
                catalogue = None
            if catalogue is not None and not catalogue.is_error:
                for row in _tool_rows(catalogue.data):
                    if str(row.get("name") or "").lower() == requested:
                        return LiveRuleTool(
                            name=str(row["name"]),
                            description=str(row.get("description") or ""),
                            schema=dict(row.get("schema") or {}),
                            gateway=str(gateway),
                        )
            # The broker map is already authoritative enough to execute the hidden
            # tool, even if the gateway catalogue response was trimmed.
            return LiveRuleTool(requested, "", {}, str(gateway))
        return None

    @staticmethod
    def _argument_name(tool: LiveRuleTool, normalised: str, fallback: str) -> str:
        schema = tool.schema if isinstance(tool.schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for name in properties:
            if _normalise(name).replace(" ", "") == normalised:
                return str(name)
        return fallback

    def _add_best_practice_key(
        self,
        tool: LiveRuleTool,
        arguments: dict[str, Any],
        key: str | None,
    ) -> dict[str, Any]:
        result = dict(arguments)
        if key:
            field = self._argument_name(tool, "bestpracticekey", "bestPracticeKey")
            result[field] = key
        return result

    async def _read_best_practice_key(self) -> str | None:
        now = time.monotonic()
        if self._best_practice_cache and now - self._best_practice_cache[0] < 600:
            return self._best_practice_cache[1]
        tool = await self._find_tool(_GUIDE_NAMES, refresh=True)
        if tool is None:
            self._best_practice_cache = (now, None)
            return None
        section_field = self._argument_name(tool, "section", "section")
        result = await self._call_rule_tool(tool, {section_field: "best_practice_reference"})
        key = None if result.is_error else (_best_practice_key(result.data) or _best_practice_key(result.text))
        self._best_practice_cache = (now, key)
        return key

    async def _ensure_backup(self, key: str | None) -> tuple[bool, dict[str, Any]]:
        details: dict[str, Any] = {"created": False, "recent": False}
        try:
            info = await self.client.call_tool("hub_get_info", {})
            epoch = _nested_value(info.data, "lastBackupEpoch") if not info.is_error else None
            if epoch is not None:
                age_ms = int(time.time() * 1000) - int(epoch)
                details.update({"last_backup_epoch": int(epoch), "age_ms": age_ms})
                if 0 <= age_ms < 23 * 60 * 60 * 1000:
                    details["recent"] = True
                    return True, details
        except Exception as exc:
            details["info_error"] = str(exc)

        tool = await self._find_tool(_BACKUP_NAMES, refresh=True)
        if tool is None:
            details["error"] = "hub_create_backup was not advertised"
            return False, details
        args = self._add_best_practice_key(tool, {}, key)
        try:
            result = await self._call_rule_tool(tool, args)
        except Exception as exc:
            details["error"] = str(exc)
            return False, details
        details["tool"] = tool.name
        details["gateway"] = tool.gateway
        details["result"] = result.data
        if result.is_error or _nested_value(result.data, "success") is False:
            details["error"] = result.text or str(_nested_value(result.data, "error") or "Backup failed")
            return False, details
        if str(_nested_value(result.data, "status") or "").lower() == "in_progress":
            details["error"] = "Hub backup is still in progress"
            return False, details
        details["created"] = True
        details["recent"] = True
        return True, details

    async def _existing_rule(self, name: str) -> dict[str, Any] | None:
        tools = await self._discover_rule_tools(refresh=False)
        candidates = [
            tool
            for tool in tools.values()
            if "list_rules" in tool.name.lower()
        ]
        candidates.sort(key=lambda tool: (0 if tool.name == "hub_list_rules" else 1, tool.name))
        target = _normalise(name)
        for tool in candidates:
            try:
                result = await self._call_rule_tool(tool, {})
            except Exception:
                continue
            if result.is_error:
                continue
            for item in self._rule_rows(result.data):
                label = item.get("label") or item.get("name")
                if _normalise(label) == target:
                    normalised = dict(item)
                    normalised.setdefault("name", label)
                    return normalised
        return None

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        if pending.create_tool is None or not self._is_native_set_rule(pending.create_tool):
            return await super()._create(pending)
        if pending.stage != "draft" or pending.draft is None:
            return self._wrong_stage("Build this rule first, then review the draft before creating it.")
        if not self.write_enabled:
            return self._wrong_stage("Rule writes are disabled in the HomeBrain add-on configuration.")
        if pending.create_args is None:
            return self._wrong_stage("The native Rule Machine draft did not compile safely.")

        existing = await self._existing_rule(pending.draft["name"])
        if existing is not None:
            pending.created_rule = existing
            pending.stage = "created"
            return self._duplicate(existing)

        plan = pending.draft.get("native_rule_machine_plan") or {}
        started = time.perf_counter()
        key = await self._read_best_practice_key()
        backup_ok, backup = await self._ensure_backup(key)
        if not backup_ok:
            return {
                "success": False,
                "route": "mcp-rule-preflight-blocked",
                "intent": "automation-rule-backup-required",
                "message": (
                    "The rule was not created because HomeBrain could not verify or create the "
                    f"required recent hub backup. {backup.get('error') or ''}"
                ).strip(),
                "answered_by": "HomeBrain rule safety",
                "display": display_payload(
                    "automation-rule-preflight",
                    str(pending.draft.get("name") or "Automation rule"),
                    subtitle="Creation blocked safely",
                    metrics=[
                        {"label": "Backup", "value": "Required", "icon": "💾"},
                        {"label": "Rule written", "value": "No", "icon": "🛡️"},
                    ],
                    note="Keep Enable Write Tools on and make hub_create_backup available through MCP, then press Create again.",
                ),
                "technical": safe_debug({"backup": backup, "best_practice_key_found": bool(key)}),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }

        shell_args = self._add_best_practice_key(
            pending.create_tool,
            dict(pending.create_args),
            key,
        )
        shell = await self._call_rule_tool(pending.create_tool, shell_args)
        shell_data = _result_mapping(shell.data)
        if shell.is_error or shell_data.get("success") is False:
            return self._tool_error("create", shell.text or str(shell_data.get("error") or "Hubitat rejected the Rule Machine shell"))
        if str(shell_data.get("status") or "").lower() == "in_progress":
            return self._wrong_stage(
                "Hubitat is still creating the Rule Machine shell. Press Create this rule again; the same idempotency token will poll/replay rather than duplicate it."
            )

        rule_id = _positive_int(_first(shell_data, "ruleId", "appId", "id"))
        if rule_id is None:
            resolved = await self._existing_rule(pending.draft["name"])
            rule_id = _positive_int((resolved or {}).get("id"))
        if rule_id is None:
            return self._tool_error(
                "create",
                "Hubitat created or accepted the Rule Machine shell but did not return a verifiable rule ID. Review Rule Machine before retrying.",
            )

        created = {
            "id": str(rule_id),
            "name": pending.draft["name"],
            "status": "Empty shell",
            "tool": pending.create_tool.name,
            "native_rule_machine": True,
        }
        pending.created_rule = created
        pending.stage = "created"
        pending.expires_at = time.time() + self.store.ttl_seconds

        pause_tool = await self._find_tool(_NATIVE_PAUSE_NAMES, refresh=True)
        if pause_tool is None:
            created["warning"] = "The empty rule shell was created, but hub_set_rule_paused was not advertised. No triggers or actions were added."
            return self._native_partial_failure(pending, created["warning"], backup, shell_data)
        pause_args = {
            self._argument_name(pause_tool, "ruleid", "ruleId"): rule_id,
            self._argument_name(pause_tool, "paused", "paused"): True,
        }
        pause_args = self._add_best_practice_key(pause_tool, pause_args, key)
        paused = await self._call_rule_tool(pause_tool, pause_args)
        if paused.is_error or _nested_value(paused.data, "success") is False:
            created["warning"] = "The empty rule shell was created, but HomeBrain could not verify it was paused. No triggers or actions were added."
            return self._native_partial_failure(pending, created["warning"], backup, paused.data)

        created["status"] = "Paused"
        pending.stage = "created-paused"
        populate_token = str(pending.draft.get("native_rule_machine_op_token") or "homebrain") + "-populate"
        populate_args = {
            "appId": rule_id,
            "addTriggers": list(plan.get("triggers") or []),
            "addActions": list(plan.get("actions") or []),
            "confirm": True,
            "opToken": populate_token,
        }
        populate_args = self._add_best_practice_key(pending.create_tool, populate_args, key)
        populated = await self._call_rule_tool(pending.create_tool, populate_args)
        populated_data = _result_mapping(populated.data)
        if populated.is_error or populated_data.get("success") is False:
            created["warning"] = "The Rule Machine shell remains paused, but its trigger/actions were not fully written."
            return self._native_partial_failure(
                pending,
                created["warning"] + " " + (populated.text or str(populated_data.get("error") or "")),
                backup,
                populated_data,
            )
        if populated_data.get("partial") is True or populated_data.get("partialTriggers") or populated_data.get("partialActions"):
            created["warning"] = "Hubitat reported a partial Rule Machine build. The rule remains paused for review."
            return self._native_partial_failure(pending, created["warning"], backup, populated_data)

        # Reassert pause after the multi-step authoring call. This is idempotent and
        # closes any platform-specific chance that updateRule resumed subscriptions.
        await self._call_rule_tool(pause_tool, pause_args)
        created.update(
            {
                "status": "Paused",
                "trigger_count": len(plan.get("triggers") or []),
                "action_count": len(plan.get("actions") or []),
            }
        )
        pending.stage = "created-paused"
        return {
            "success": True,
            "route": "mcp-native-rule-created",
            "intent": "automation-rule-created",
            "message": (
                f"Created **{created['name']}** as a native Rule Machine rule and left it paused. "
                "Review it in Hubitat Rule Machine, then press Enable rule when ready."
            ),
            "answered_by": "Hubitat MCP native Rule Machine",
            "display": self._created_display(pending),
            "created_rule": created,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "create_tool": pending.create_tool.name,
                    "create_gateway": pending.create_tool.gateway,
                    "rule_id": rule_id,
                    "backup": backup,
                    "best_practice_key_found": bool(key),
                    "shell": shell_data,
                    "populate": populated_data,
                }
            ),
        }

    def _native_partial_failure(
        self,
        pending: PendingRule,
        message: str,
        backup: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        display = self._created_display(pending)
        display["actions"] = []
        display["note"] = "The shell is empty or paused. Inspect it in Rule Machine before any retry."
        return {
            "success": False,
            "route": "mcp-native-rule-paused-partial",
            "intent": "automation-rule-create-partial",
            "message": message,
            "answered_by": "HomeBrain rule safety",
            "display": display,
            "created_rule": pending.created_rule,
            "technical": safe_debug({"backup": backup, "result": result}),
        }

    async def _call_operation(self, pending: PendingRule, operation: str) -> dict[str, Any]:
        native = bool((pending.created_rule or {}).get("native_rule_machine"))
        if not native:
            return await super()._call_operation(pending, operation)
        if operation == "run":
            return self._wrong_stage(
                "The current native Rule Machine API does not expose a genuine non-executing dry-run. Review the paused rule, enable it, then test with the real fridge contact."
            )

        tool = await self._find_tool(_NATIVE_PAUSE_NAMES, refresh=True)
        if tool is None:
            return self._wrong_stage("hub_set_rule_paused is not available through the connected MCP server.")
        rule_id = _positive_int((pending.created_rule or {}).get("id"))
        if rule_id is None:
            return self._wrong_stage("The native Rule Machine rule ID could not be verified.")
        key = await self._read_best_practice_key()
        paused_value = operation == "pause"
        args = {
            self._argument_name(tool, "ruleid", "ruleId"): rule_id,
            self._argument_name(tool, "paused", "paused"): paused_value,
        }
        args = self._add_best_practice_key(tool, args, key)
        started = time.perf_counter()
        result = await self._call_rule_tool(tool, args)
        if result.is_error or _nested_value(result.data, "success") is False:
            return self._tool_error(operation, result.text or str(_nested_value(result.data, "error") or "Hubitat rejected the pause change"))

        title = str((pending.created_rule or {}).get("name") or "Rule")
        if operation == "enable":
            pending.stage = "enabled"
            pending.created_rule["status"] = "Active"
            message = f"Enabled **{title}**. It can now monitor the fridge contact automatically."
            route = "mcp-rule-enabled"
            intent = "automation-rule-enabled"
            last_action = "Enabled"
        else:
            pending.stage = "created-paused"
            pending.created_rule["status"] = "Paused"
            message = f"Paused **{title}**. It will not run automatically until enabled again."
            route = "mcp-rule-paused"
            intent = "automation-rule-paused"
            last_action = "Paused"
        pending.expires_at = time.time() + self.store.ttl_seconds
        return {
            "success": True,
            "route": route,
            "intent": intent,
            "message": message,
            "answered_by": "Hubitat MCP native Rule Machine",
            "display": self._created_display(pending, operation=last_action),
            "created_rule": pending.created_rule,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"tool": tool.name, "gateway": tool.gateway, "arguments": args, "result": result.data}),
        }

    @staticmethod
    def _created_display(pending: PendingRule, operation: str | None = None) -> dict[str, Any]:
        rule = pending.created_rule or {}
        draft = pending.draft or {}
        status = str(rule.get("status") or ("Active" if pending.stage == "enabled" else "Paused"))
        display = display_payload(
            "automation-rule-created",
            str(rule.get("name") or draft.get("name") or "Automation rule"),
            subtitle=f"Native Rule Machine · {status}",
            metrics=[
                {"label": "Rule ID", "value": rule.get("id") or "—", "icon": "🆔"},
                {"label": "Status", "value": status, "icon": "▶️" if pending.stage == "enabled" else "⏸️"},
                {"label": "Last action", "value": operation or "Created", "icon": "🧰"},
            ],
            note=(
                "Review the rule in Hubitat Rule Machine. The native MCP API can execute a rule, "
                "but it does not provide a genuine action-free dry-run, so HomeBrain does not show a misleading test button."
            ),
        )
        if pending.stage == "enabled":
            display["actions"] = [
                {"label": "Pause rule", "query": "Pause this rule", "tone": "danger", "icon": "⏸️"},
            ]
        else:
            display["actions"] = [
                {"label": "Enable rule", "query": "Enable this rule", "tone": "danger", "icon": "▶️"},
            ]
        return display

def install_native_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> NativeRuleMachineAutomationWorkflow:
    original_ask: AskHandler = application.ask
    service = NativeRuleMachineAutomationWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        command = service.command(query)
        if command:
            answer = await service.handle(request, command)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        await service.remember_answer(_session_id(request), answer)
        return answer

    application.ask = ask_with_rule_workflow
    application.automation_rule_workflow = service
    return service

__all__ = [
    "AskHandler",
    "LiveRuleTool",
    "LiveSchemaAutomationRuleWorkflow",
    "NativeRuleMachineAutomationWorkflow",
    "ReleaseAutomationRuleWorkflow",
    "_best_practice_key",
    "_native_rule_plan",
    "_nested_value",
    "_positive_int",
    "install_live_automation_rule_workflow",
    "install_native_rule_machine_workflow",
    "install_release_automation_rule_workflow",
]
