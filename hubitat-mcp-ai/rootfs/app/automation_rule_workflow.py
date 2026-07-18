from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from device_intelligence_index import _attributes, _label, _room_name
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_BUILD = {
    "build this rule",
    "build rule",
    "prepare this rule",
    "draft this rule",
}
_CREATE = {
    "create this rule",
    "yes create this rule",
    "confirm create this rule",
    "create paused rule",
}
_TEST = {
    "run test once",
    "test this rule",
    "run this rule once",
}
_ENABLE = {
    "enable this rule",
    "activate this rule",
}
_PAUSE = {
    "pause this rule",
    "disable this rule",
}
_CANCEL = {
    "cancel rule draft",
    "cancel this rule",
    "discard this rule",
}


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def _session_id(request: Any) -> str:
    value = str(getattr(request, "session_id", "") or "default").strip()
    return value[:160] or "default"


def _tool_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            rows.extend(_tool_rows(item))
        return rows
    if not isinstance(value, dict):
        return rows
    name = value.get("name") or value.get("tool") or value.get("toolName")
    schema = value.get("inputSchema") or value.get("input_schema") or value.get("schema")
    if name and isinstance(schema, dict):
        rows.append(
            {
                "name": str(name),
                "description": str(value.get("description") or ""),
                "schema": schema,
            }
        )
    for key, item in value.items():
        if key in {"inputSchema", "input_schema", "schema"}:
            continue
        rows.extend(_tool_rows(item))
    return rows


def _result_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        for key in ("result", "data", "rule", "app", "value"):
            nested = value.get(key)
            if isinstance(nested, dict):
                merged = dict(value)
                merged.update(nested)
                return merged
        return value
    return {}


def _first(value: Any, *names: str) -> Any:
    wanted = {_normalise(name).replace(" ", "") for name in names}
    if isinstance(value, dict):
        for key, item in value.items():
            compact = _normalise(key).replace(" ", "")
            if compact in wanted and item not in (None, ""):
                return item
        for item in value.values():
            found = _first(item, *names)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for item in value:
            found = _first(item, *names)
            if found not in (None, ""):
                return found
    return None


def _as_schema_value(schema: dict[str, Any], value: Any) -> Any:
    kind = str(schema.get("type") or "").lower()
    if kind == "string" and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if kind == "array" and not isinstance(value, list):
        return [value]
    return value


@dataclass(slots=True)
class RuleTool:
    name: str
    description: str
    schema: dict[str, Any]


@dataclass(slots=True)
class PendingRule:
    session_id: str
    recommendation: dict[str, Any]
    created_at: float
    expires_at: float
    stage: str = "recommended"
    draft: dict[str, Any] | None = None
    create_tool: RuleTool | None = None
    create_args: dict[str, Any] | None = None
    created_rule: dict[str, Any] | None = None
    discovered_tools: dict[str, RuleTool] | None = None
    compile_error: str | None = None


class RuleWorkflowStore:
    def __init__(self, *, ttl_seconds: float = 600.0, max_sessions: int = 128) -> None:
        self.ttl_seconds = max(120.0, min(3600.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self._items: dict[str, PendingRule] = {}
        self._lock = asyncio.Lock()

    async def remember(self, session_id: str, recommendation: dict[str, Any]) -> PendingRule:
        now = time.time()
        pending = PendingRule(
            session_id=session_id,
            recommendation=dict(recommendation),
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        async with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_sessions and session_id not in self._items:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.session_id, None)
            self._items[session_id] = pending
        return pending

    async def get(self, session_id: str) -> PendingRule | None:
        async with self._lock:
            self._purge_locked()
            return self._items.get(session_id)

    async def clear(self, session_id: str) -> bool:
        async with self._lock:
            return self._items.pop(session_id, None) is not None

    def _purge_locked(self) -> None:
        now = time.time()
        for key in [key for key, item in self._items.items() if item.expires_at <= now]:
            self._items.pop(key, None)


class AutomationRuleWorkflow:
    """Compile recommendations into guarded, schema-aware MCP rule writes.

    Recommendations remain read-only until the user explicitly builds a draft and
    then sends the exact create command. Tool names and input schemas are learned
    from the live MCP gateways so server upgrades do not require hard-coded JSON.
    A create call is refused unless its schema can request a paused/disabled rule.
    Testing, enabling and pausing are separate explicit operations.
    """

    def __init__(
        self,
        application: Any,
        device_index: Any,
        *,
        ttl_seconds: float = 600.0,
        max_sessions: int = 128,
        write_enabled: bool = True,
        require_paused_create: bool = True,
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.client = application.mcp
        self.store = RuleWorkflowStore(
            ttl_seconds=ttl_seconds,
            max_sessions=max_sessions,
        )
        self.write_enabled = bool(write_enabled)
        self.require_paused_create = bool(require_paused_create)

    @staticmethod
    def command(query: str) -> str | None:
        value = _normalise(query)
        if value in _BUILD:
            return "build"
        if value in _CREATE:
            return "create"
        if value in _TEST:
            return "test"
        if value in _ENABLE:
            return "enable"
        if value in _PAUSE:
            return "pause"
        if value in _CANCEL:
            return "cancel"
        return None

    async def remember_answer(self, session_id: str, answer: dict[str, Any]) -> None:
        recommendation = answer.get("recommendation")
        if not isinstance(recommendation, dict):
            return
        await self.store.remember(session_id, recommendation)
        display = answer.get("display")
        if isinstance(display, dict):
            display["actions"] = [
                {
                    "label": "Build rule",
                    "query": "Build this rule",
                    "tone": "primary",
                    "icon": "🧱",
                }
            ]
            note = str(display.get("note") or "").strip()
            addition = " Build creates a reviewable draft first; it does not write to Hubitat."
            if addition.strip() not in note:
                display["note"] = (note + addition).strip()

    async def handle(self, request: Any, command: str) -> dict[str, Any]:
        session_id = _session_id(request)
        if command == "cancel":
            cleared = await self.store.clear(session_id)
            return self._cancelled(cleared)
        pending = await self.store.get(session_id)
        if pending is None:
            return self._missing()
        if command == "build":
            return await self._build(pending)
        if command == "create":
            return await self._create(pending)
        if command == "test":
            return await self._operate(pending, "run")
        if command == "enable":
            return await self._operate(pending, "enable")
        if command == "pause":
            return await self._operate(pending, "pause")
        return self._missing()

    async def _build(self, pending: PendingRule) -> dict[str, Any]:
        started = time.perf_counter()
        draft = await self._draft(pending.recommendation)
        tools = await self._discover_rule_tools(refresh=True)
        create_tool, create_args, compile_error = self._choose_create_tool(tools, draft)
        pending.draft = draft
        pending.discovered_tools = tools
        pending.create_tool = create_tool
        pending.create_args = create_args
        pending.compile_error = compile_error
        pending.stage = "draft"
        pending.expires_at = time.time() + self.store.ttl_seconds

        ready = bool(self.write_enabled and create_tool and create_args)
        message = (
            f"Draft ready for **{draft['name']}**. Review the trigger, actions and cancellation "
            "below. No rule has been written to Hubitat."
        )
        if not self.write_enabled:
            message += " Rule writes are disabled in the HomeBrain add-on configuration."
        elif not ready:
            message += f" Automatic paused creation is not available: {compile_error or 'no compatible MCP create tool was found'}."
        else:
            message += " Press Create paused rule only when you are satisfied with the draft."

        display = self._draft_display(pending, ready)
        return {
            "success": True,
            "route": "mcp-rule-draft",
            "intent": "automation-rule-draft",
            "message": message,
            "answered_by": "HomeBrain rule compiler",
            "evidence_source": "Grounded recommendation and live MCP tool schemas",
            "display": display,
            "rule_draft": draft,
            "write_ready": ready,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "stage": pending.stage,
                    "create_tool": create_tool.name if create_tool else None,
                    "create_arguments": create_args,
                    "compile_error": compile_error,
                    "discovered_rule_tools": sorted(tools),
                }
            ),
        }

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        if pending.stage != "draft" or pending.draft is None:
            return self._wrong_stage("Build this rule first, then review the draft before creating it.")
        if not self.write_enabled:
            return self._wrong_stage("Rule writes are disabled in the HomeBrain add-on configuration.")
        if pending.create_tool is None or pending.create_args is None:
            return self._wrong_stage(
                f"This draft cannot be created safely: {pending.compile_error or 'no compatible paused-create tool is available'}."
            )

        existing = await self._existing_rule(pending.draft["name"])
        if existing is not None:
            pending.created_rule = existing
            pending.stage = "created-paused" if self._looks_paused(existing) else "created"
            return self._duplicate(existing)

        started = time.perf_counter()
        result = await self.client.call_tool(pending.create_tool.name, dict(pending.create_args))
        if result.is_error:
            return self._tool_error("create", result.text or "Hubitat rejected the rule creation request")

        created = self._created_rule(result.data, pending.draft["name"])
        created["tool"] = pending.create_tool.name
        created["requested_paused"] = True
        pending.created_rule = created
        pending.stage = "created-paused"
        pending.expires_at = time.time() + self.store.ttl_seconds

        # If the response explicitly says the rule is active, pause it immediately.
        if self._looks_active(created):
            pause_answer = await self._call_operation(pending, "pause")
            if pause_answer.get("success"):
                created["status"] = "Paused"
                pending.stage = "created-paused"
            else:
                created["warning"] = "The create response appeared active and the automatic pause failed. Review it in Hubitat immediately."
                pending.stage = "created"

        return {
            "success": True,
            "route": "mcp-rule-created",
            "intent": "automation-rule-created",
            "message": (
                f"Created **{created.get('name') or pending.draft['name']}** in Hubitat and requested it paused. "
                "It will not monitor the fridge until you explicitly enable it."
            ),
            "answered_by": "Hubitat MCP",
            "display": self._created_display(pending),
            "created_rule": created,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "create_tool": pending.create_tool.name,
                    "create_arguments": pending.create_args,
                    "created_rule": created,
                }
            ),
        }

    async def _operate(self, pending: PendingRule, operation: str) -> dict[str, Any]:
        if pending.created_rule is None:
            return self._wrong_stage("Create the paused rule first.")
        if not self.write_enabled:
            return self._wrong_stage("Rule writes are disabled in the HomeBrain add-on configuration.")
        return await self._call_operation(pending, operation)

    async def _call_operation(self, pending: PendingRule, operation: str) -> dict[str, Any]:
        tools = pending.discovered_tools or await self._discover_rule_tools(refresh=True)
        tool = self._choose_operation_tool(tools, operation)
        if tool is None:
            return self._wrong_stage(f"The connected MCP server does not expose a compatible {operation} rule tool.")
        args, error = self._compile_reference_args(tool, pending, operation)
        if error:
            return self._wrong_stage(error)
        started = time.perf_counter()
        result = await self.client.call_tool(tool.name, args)
        if result.is_error:
            return self._tool_error(operation, result.text or f"Hubitat rejected the {operation} request")

        title = str((pending.created_rule or {}).get("name") or (pending.draft or {}).get("name") or "Rule")
        if operation == "run":
            message = f"Ran **{title}** once as an explicit test. Check that the expected notification or action occurred."
            route = "mcp-rule-tested"
            intent = "automation-rule-tested"
        elif operation == "enable":
            pending.stage = "enabled"
            pending.created_rule["status"] = "Active"
            message = f"Enabled **{title}**. It can now run automatically when its trigger conditions are met."
            route = "mcp-rule-enabled"
            intent = "automation-rule-enabled"
        else:
            pending.stage = "created-paused"
            pending.created_rule["status"] = "Paused"
            message = f"Paused **{title}**. It will not run automatically until enabled again."
            route = "mcp-rule-paused"
            intent = "automation-rule-paused"

        pending.expires_at = time.time() + self.store.ttl_seconds
        return {
            "success": True,
            "route": route,
            "intent": intent,
            "message": message,
            "answered_by": "Hubitat MCP",
            "display": self._created_display(pending, operation=operation),
            "created_rule": pending.created_rule,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(
                {
                    "operation": operation,
                    "tool": tool.name,
                    "arguments": args,
                    "result": result.data,
                }
            ),
        }

    async def _draft(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        refs: list[dict[str, Any]] = []
        for label in recommendation.get("devices") or []:
            exact = None
            try:
                exact, _ = await self.device_index.exact_device(str(label))
            except Exception:
                exact = None
            if isinstance(exact, dict):
                refs.append(
                    {
                        "id": str(exact.get("id") or exact.get("deviceId") or ""),
                        "label": _label(exact) or str(label),
                        "room": _room_name(exact) or recommendation.get("room"),
                        "attributes": _attributes(exact),
                    }
                )
            else:
                refs.append({"id": "", "label": str(label), "room": recommendation.get("room")})

        kind = str(recommendation.get("type") or "").strip()
        name = str(recommendation.get("title") or "HomeBrain automation").strip()
        primary = refs[0] if refs else {"id": "", "label": "Device", "room": recommendation.get("room")}
        trigger: dict[str, Any]
        actions: list[dict[str, Any]]
        cancel_when: dict[str, Any] | None = None

        if kind == "cold-storage-door":
            trigger = {
                "type": "device-attribute-duration",
                "device": primary,
                "attribute": "contact",
                "operator": "equals",
                "value": "open",
                "duration_seconds": 120,
            }
            actions = [
                {
                    "type": "notification",
                    "priority": "high",
                    "message": f"{primary['label']} has been open for 2 minutes.",
                },
                {"type": "delay", "seconds": 300},
                {
                    "type": "conditional-notification",
                    "condition": {
                        "device": primary,
                        "attribute": "contact",
                        "operator": "equals",
                        "value": "open",
                    },
                    "message": f"{primary['label']} is still open.",
                },
            ]
            cancel_when = {
                "device": primary,
                "attribute": "contact",
                "operator": "equals",
                "value": "closed",
            }
        elif kind == "motion-lighting":
            sensors = refs[:2]
            lights = refs[2:] or refs[1:]
            trigger = {
                "type": "any-device-attribute",
                "devices": sensors,
                "attribute": "motion",
                "operator": "equals",
                "value": "active",
            }
            actions = [
                {"type": "device-command", "devices": lights, "command": "on"},
                {"type": "wait-until-inactive", "devices": sensors, "duration_seconds": 180},
                {"type": "device-command", "devices": lights, "command": "off"},
            ]
            cancel_when = None
        elif kind == "humidity-ventilation":
            trigger = {
                "type": "device-threshold",
                "device": primary,
                "attribute": "humidity",
                "operator": "greater-than",
                "value": 65,
            }
            actions = [
                {"type": "device-command", "device": refs[1] if len(refs) > 1 else {}, "command": "on"},
                {
                    "type": "wait-threshold-duration",
                    "device": primary,
                    "attribute": "humidity",
                    "operator": "less-than",
                    "value": 60,
                    "duration_seconds": 300,
                },
                {"type": "device-command", "device": refs[1] if len(refs) > 1 else {}, "command": "off"},
            ]
            cancel_when = None
        else:
            trigger = {
                "type": "grounded-description",
                "description": recommendation.get("trigger"),
            }
            actions = [
                {
                    "type": "grounded-description",
                    "description": recommendation.get("action"),
                }
            ]
            cancel_when = {
                "type": "grounded-description",
                "description": recommendation.get("safeguard"),
            }

        return {
            "name": name,
            "description": str(recommendation.get("reason") or "Created from a grounded HomeBrain recommendation."),
            "application": "Visual Rules Builder",
            "enabled": False,
            "paused": True,
            "type": kind,
            "room": recommendation.get("room"),
            "devices": refs,
            "trigger": trigger,
            "actions": actions,
            "cancel_when": cancel_when,
            "review": {
                "trigger_text": recommendation.get("trigger"),
                "action_text": recommendation.get("action"),
                "safeguard_text": recommendation.get("safeguard"),
            },
        }

    async def _discover_rule_tools(self, *, refresh: bool) -> dict[str, RuleTool]:
        found: dict[str, RuleTool] = {}
        visible = await self.client.list_tools(refresh=refresh)
        for tool in visible:
            if "rule" not in str(tool.name).lower():
                continue
            found[str(tool.name)] = RuleTool(
                name=str(tool.name),
                description=str(getattr(tool, "description", "") or ""),
                schema=dict(getattr(tool, "input_schema", {}) or {}),
            )

        gateway_map = (
            await self.client.gateway_map(refresh=refresh)
            if hasattr(self.client, "gateway_map")
            else {}
        )
        gateways = {
            gateway
            for hidden, gateway in gateway_map.items()
            if "rule" in hidden.lower()
        }
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
                found[name] = RuleTool(
                    name=name,
                    description=str(row.get("description") or ""),
                    schema=dict(row.get("schema") or {}),
                )
        return found

    def _choose_create_tool(
        self,
        tools: dict[str, RuleTool],
        draft: dict[str, Any],
    ) -> tuple[RuleTool | None, dict[str, Any] | None, str | None]:
        candidates = [
            tool
            for tool in tools.values()
            if "create" in tool.name.lower() and "rule" in tool.name.lower()
        ]
        candidates.sort(key=self._create_rank)
        errors: list[str] = []
        for tool in candidates:
            args, error = self._compile_create_args(tool, draft)
            if args is not None:
                return tool, args, None
            if error:
                errors.append(f"{tool.name}: {error}")
        if not candidates:
            return None, None, "MCP Write/rule creation tools are not enabled or were not advertised"
        return None, None, "; ".join(errors[:4]) or "no create schema could be compiled safely"

    @staticmethod
    def _create_rank(tool: RuleTool) -> tuple[int, str]:
        text = (tool.name + " " + tool.description).lower()
        if "visual" in text or "vrb" in text:
            return 0, tool.name
        if "simple" in text:
            return 1, tool.name
        if "rule_machine" in text or "rule machine" in text or "rm_rule" in text:
            return 4, tool.name
        return 2, tool.name

    def _compile_create_args(
        self,
        tool: RuleTool,
        draft: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        schema = tool.schema if isinstance(tool.schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = {str(item) for item in (schema.get("required") or [])}
        args: dict[str, Any] = {}
        pause_field = False
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
                pause_field = True
            elif key in {"paused", "ispaused", "pause"}:
                value = True
                pause_field = True
            elif key in {"draft", "isdraft", "createasdraft"}:
                value = True
                pause_field = True
            elif key in {"rule", "definition", "ruledefinition", "spec", "config", "payload", "request"}:
                value = draft
                structured_field = True
            elif key in {"trigger", "triggers"}:
                value = draft["trigger"]
                structured_field = True
            elif key in {"action", "actions"}:
                value = draft["actions"]
                structured_field = True
            elif key in {"condition", "conditions", "cancelwhen", "cancellation"}:
                value = draft.get("cancel_when") or {}
                structured_field = True
            elif key in {"application", "apptype", "ruletype", "builder"}:
                value = draft["application"]
            elif key in {"deviceid", "sensorid", "contactsensorid", "triggerdeviceid"}:
                value = str(((draft.get("devices") or [{}])[0]).get("id") or "")
            elif key in {"device", "sensor", "contactsensor", "triggerdevice"}:
                value = (draft.get("devices") or [{}])[0]
            if value not in (None, ""):
                args[name] = _as_schema_value(prop, value)

        unknown_required = [name for name in required if name not in args]
        if unknown_required:
            return None, "unresolved required fields: " + ", ".join(sorted(unknown_required))
        if not structured_field:
            return None, "schema has no supported structured rule field"
        if self.require_paused_create and not pause_field and "draft" not in tool.name.lower():
            return None, "schema cannot guarantee paused or disabled creation"
        return args, None

    @staticmethod
    def _choose_operation_tool(
        tools: dict[str, RuleTool],
        operation: str,
    ) -> RuleTool | None:
        names = {
            "run": ("run_rule", "call_rule", "test_rule"),
            "enable": ("resume_rule", "enable_rule", "update_rule", "set_rule"),
            "pause": ("pause_rule", "disable_rule", "update_rule", "set_rule"),
        }[operation]
        candidates = [
            tool
            for tool in tools.values()
            if any(token in tool.name.lower() for token in names)
        ]
        candidates.sort(
            key=lambda tool: (
                next(
                    (index for index, token in enumerate(names) if token in tool.name.lower()),
                    len(names),
                ),
                tool.name,
            )
        )
        return candidates[0] if candidates else None

    def _compile_reference_args(
        self,
        tool: RuleTool,
        pending: PendingRule,
        operation: str,
    ) -> tuple[dict[str, Any], str | None]:
        schema = tool.schema if isinstance(tool.schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = {str(item) for item in (schema.get("required") or [])}
        created = pending.created_rule or {}
        rule_id = str(created.get("id") or created.get("ruleId") or created.get("appId") or "")
        rule_name = str(created.get("name") or (pending.draft or {}).get("name") or "")
        args: dict[str, Any] = {}
        for name, property_schema in properties.items():
            prop = property_schema if isinstance(property_schema, dict) else {}
            key = _normalise(name).replace(" ", "")
            value: Any = None
            if key in {"id", "ruleid", "appid", "rule", "ruleidentifier"}:
                value = rule_id or rule_name
            elif key in {"name", "rulename", "title", "label"}:
                value = rule_name
            elif key in {"enabled", "active", "isenabled"}:
                value = operation == "enable"
            elif key in {"paused", "ispaused", "pause"}:
                value = operation == "pause"
            elif key in {"test", "dryrun", "runonce"}:
                value = operation == "run"
            if value not in (None, ""):
                args[name] = _as_schema_value(prop, value)
        unknown_required = [name for name in required if name not in args]
        if unknown_required:
            return {}, f"The {tool.name} schema requires unresolved fields: {', '.join(sorted(unknown_required))}."
        if not args and properties:
            return {}, f"The {tool.name} schema does not expose a recognised rule identifier."
        return args, None

    async def _existing_rule(self, name: str) -> dict[str, Any] | None:
        try:
            result = await self.client.call_tool("hub_list_rules", {})
        except Exception:
            return None
        if result.is_error:
            return None
        target = _normalise(name)
        for item in self._rule_rows(result.data):
            if _normalise(item.get("name")) == target:
                return item
        return None

    @classmethod
    def _rule_rows(cls, value: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if isinstance(value, list):
            for item in value:
                rows.extend(cls._rule_rows(item))
            return rows
        if not isinstance(value, dict):
            return rows
        name = _first(value, "name", "ruleName", "label", "appName")
        rule_id = _first(value, "id", "ruleId", "appId")
        if name and rule_id not in (None, ""):
            rows.append(
                {
                    "name": str(name),
                    "id": str(rule_id),
                    "status": str(_first(value, "status", "state") or "Available"),
                    "paused": _first(value, "paused", "isPaused"),
                    "enabled": _first(value, "enabled", "active"),
                }
            )
            return rows
        for item in value.values():
            rows.extend(cls._rule_rows(item))
        return rows

    @staticmethod
    def _created_rule(value: Any, fallback_name: str) -> dict[str, Any]:
        mapping = _result_mapping(value)
        return {
            "id": str(_first(mapping, "id", "ruleId", "appId") or ""),
            "name": str(_first(mapping, "name", "ruleName", "label", "appName") or fallback_name),
            "status": str(_first(mapping, "status", "state") or "Paused"),
            "paused": _first(mapping, "paused", "isPaused"),
            "enabled": _first(mapping, "enabled", "active"),
        }

    @staticmethod
    def _looks_paused(rule: dict[str, Any]) -> bool:
        if rule.get("paused") is True or rule.get("enabled") is False:
            return True
        return _normalise(rule.get("status")) in {"paused", "disabled", "inactive"}

    @staticmethod
    def _looks_active(rule: dict[str, Any]) -> bool:
        if rule.get("paused") is False or rule.get("enabled") is True:
            return True
        return _normalise(rule.get("status")) in {"active", "enabled", "running"}

    @staticmethod
    def _draft_display(pending: PendingRule, ready: bool) -> dict[str, Any]:
        draft = pending.draft or {}
        review = draft.get("review") or {}
        display = display_payload(
            "automation-rule-draft",
            str(draft.get("name") or "Rule draft"),
            subtitle="Review only · nothing has been written",
            metrics=[
                {"label": "Status", "value": "Ready" if ready else "Needs setup", "icon": "🧱"},
                {"label": "Starts as", "value": "Paused", "icon": "⏸️"},
                {"label": "Devices", "value": str(len(draft.get("devices") or [])), "icon": "📱"},
                {
                    "label": "MCP tool",
                    "value": pending.create_tool.name if pending.create_tool else "Unavailable",
                    "icon": "🧰",
                },
            ],
            items=[
                {"icon": "⚡", "title": "Trigger", "value": "", "subtitle": review.get("trigger_text")},
                {"icon": "▶️", "title": "Actions", "value": "", "subtitle": review.get("action_text")},
                {"icon": "🛡️", "title": "Cancellation / safeguard", "value": "", "subtitle": review.get("safeguard_text")},
            ],
            note=(
                "Creation requires a separate explicit confirmation. The rule is requested paused and enabling/testing are separate operations."
            ),
        )
        actions = [{"label": "Cancel", "query": "Cancel rule draft", "tone": "secondary", "icon": "✖️"}]
        if ready:
            actions.insert(0, {"label": "Create paused rule", "query": "Create this rule", "tone": "danger", "icon": "🧱"})
        display["actions"] = actions
        return display

    @staticmethod
    def _created_display(pending: PendingRule, operation: str | None = None) -> dict[str, Any]:
        rule = pending.created_rule or {}
        draft = pending.draft or {}
        status = str(rule.get("status") or ("Active" if pending.stage == "enabled" else "Paused"))
        display = display_payload(
            "automation-rule-created",
            str(rule.get("name") or draft.get("name") or "Automation rule"),
            subtitle=f"Hubitat rule · {status}",
            metrics=[
                {"label": "Rule ID", "value": rule.get("id") or "Returned by name", "icon": "🆔"},
                {"label": "Status", "value": status, "icon": "▶️" if pending.stage == "enabled" else "⏸️"},
                {"label": "Last action", "value": operation or "Created", "icon": "🧰"},
            ],
            note=(
                "Run test once is an explicit manual execution. Enable rule starts automatic monitoring; pause stops it again."
            ),
        )
        if pending.stage == "enabled":
            display["actions"] = [
                {"label": "Run test once", "query": "Run test once", "tone": "warning", "icon": "🧪"},
                {"label": "Pause rule", "query": "Pause this rule", "tone": "danger", "icon": "⏸️"},
            ]
        else:
            display["actions"] = [
                {"label": "Run test once", "query": "Run test once", "tone": "warning", "icon": "🧪"},
                {"label": "Enable rule", "query": "Enable this rule", "tone": "danger", "icon": "▶️"},
            ]
        return display

    @staticmethod
    def _missing() -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-rule-workflow",
            "intent": "automation-rule-workflow-missing",
            "message": "No recent automation recommendation is waiting in this browser session. Ask for a recommendation first.",
            "display": display_payload(
                "automation-rule-workflow",
                "No pending rule",
                subtitle="Start with Suggest one useful automation",
            ),
        }

    @staticmethod
    def _wrong_stage(message: str) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-rule-workflow",
            "intent": "automation-rule-workflow-blocked",
            "message": message,
            "display": display_payload(
                "automation-rule-workflow",
                "Rule operation blocked",
                subtitle="No unsafe write was sent",
                note=message,
            ),
        }

    @staticmethod
    def _tool_error(operation: str, error: str) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-rule-workflow",
            "intent": f"automation-rule-{operation}-failed",
            "message": f"Hubitat could not {operation} the rule: {error}",
            "display": display_payload(
                "automation-rule-workflow",
                "Rule operation failed",
                subtitle=f"{operation.title()} was not completed",
                note=error,
            ),
        }

    @staticmethod
    def _cancelled(cleared: bool) -> dict[str, Any]:
        return {
            "success": True,
            "route": "mcp-rule-workflow",
            "intent": "automation-rule-workflow-cancelled",
            "message": "Rule draft cancelled. No new Hubitat rule was created." if cleared else "There was no pending rule draft to cancel.",
            "display": display_payload(
                "automation-rule-workflow",
                "Rule draft cancelled",
                subtitle="No rule write was sent",
            ),
        }

    @staticmethod
    def _duplicate(existing: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "route": "mcp-rule-duplicate",
            "intent": "automation-rule-duplicate",
            "message": f"A Hubitat rule named **{existing.get('name')}** already exists. HomeBrain did not create a duplicate.",
            "display": display_payload(
                "automation-rule-duplicate",
                "Existing rule found",
                subtitle=str(existing.get("name") or "Matching rule"),
                metrics=[
                    {"label": "Rule ID", "value": existing.get("id") or "Available", "icon": "🆔"},
                    {"label": "Status", "value": existing.get("status") or "Available", "icon": "⚙️"},
                ],
                note="Review the existing rule in Hubitat before changing it.",
            ),
            "existing_rule": existing,
        }


def install_automation_rule_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> AutomationRuleWorkflow:
    original_ask: AskHandler = application.ask
    service = AutomationRuleWorkflow(
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
    "AutomationRuleWorkflow",
    "PendingRule",
    "RuleTool",
    "RuleWorkflowStore",
    "install_automation_rule_workflow",
]
