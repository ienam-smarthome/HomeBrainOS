from __future__ import annotations

import time
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


__all__ = [
    "LiveRuleTool",
    "LiveSchemaAutomationRuleWorkflow",
    "install_live_automation_rule_workflow",
]
