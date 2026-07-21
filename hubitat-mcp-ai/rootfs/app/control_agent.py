from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from control_agent_graph import ControlDeviceGraph, DeviceNode, DeviceResolution
from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
    is_control_candidate,
)
from control_agent_state import (
    ControlContextStore,
    LearnedAliasStore,
    PendingControlStore,
)
from control_language import canonicalise_basic_control
from device_intelligence_index import _attributes, _device_id, _label
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, safe_debug
from spoken_device_name import spoken_name_key


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_YES = {"yes", "yeah", "yep", "confirm", "confirmed", "do it", "go ahead", "please do"}
_NO = {"no", "nope", "cancel", "stop", "do not", "don't", "never mind", "nevermind"}
_ALIAS_ADD = re.compile(
    r'^remember\s+["\']?(.+?)["\']?\s+(?:means|is|as)\s+["\']?(.+?)["\']?[.!?]*$',
    re.IGNORECASE,
)
_ALIAS_CALL = re.compile(
    r'^call\s+["\']?(.+?)["\']?\s+["\']?(.+?)["\']?[.!?]*$',
    re.IGNORECASE,
)
_ALIAS_FORGET = re.compile(r'^forget\s+(?:the\s+)?alias\s+["\']?(.+?)["\']?[.!?]*$', re.IGNORECASE)


@dataclass(slots=True)
class ResolvedControlAction:
    intent: ControlActionIntent
    nodes: list[DeviceNode] = field(default_factory=list)
    candidates: list[DeviceNode] = field(default_factory=list)
    resolution_confidence: float = 0.0
    resolution_method: str = "unresolved"
    resolution_reason: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "command": self.intent.command,
            "value": self.intent.value,
            "target": self.intent.target.response_dict(),
            "resolved": [item.public_dict() for item in self.nodes],
            "candidates": [item.public_dict() for item in self.candidates],
            "resolution_confidence": self.resolution_confidence,
            "resolution_method": self.resolution_method,
            "resolution_reason": self.resolution_reason,
        }


@dataclass(slots=True)
class ControlPlan:
    query: str
    intent: ControlIntent
    actions: list[ResolvedControlAction]
    diagnostics: dict[str, Any]
    created_at: float = field(default_factory=time.time)

    @property
    def nodes(self) -> list[DeviceNode]:
        found: dict[str, DeviceNode] = {}
        for action in self.actions:
            for node in action.nodes:
                found.setdefault(node.id, node)
        return list(found.values())

    @property
    def candidates(self) -> list[DeviceNode]:
        found: dict[str, DeviceNode] = {}
        for action in self.actions:
            for node in action.candidates:
                found.setdefault(node.id, node)
        return list(found.values())

    @property
    def confidence(self) -> float:
        values = [self.intent.confidence]
        values.extend(item.resolution_confidence for item in self.actions if item.nodes)
        return min(values) if values else 0.0

    @property
    def sensitive(self) -> bool:
        return any(node.risk == "sensitive" for node in self.nodes)

    def public_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent.response_dict(),
            "actions": [item.public_dict() for item in self.actions],
            "confidence": self.confidence,
            "sensitive": self.sensitive,
        }


class HomeBrainControlAgent:
    """Structured AI interpretation with deterministic Hubitat execution."""

    def __init__(
        self,
        application: Any,
        device_index: Any,
        fallback: Any,
        *,
        intent_timeout_seconds: float = 5.0,
        context_ttl_seconds: float = 600.0,
        confirmation_ttl_seconds: float = 120.0,
        max_sessions: int = 128,
        auto_execute_confidence: float = 0.88,
        block_below_confidence: float = 0.50,
        group_confirmation_size: int = 6,
        alias_path: str = "/data/control_agent_aliases.json",
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.fallback = fallback
        self.interpreter = ControlIntentInterpreter(
            application,
            timeout_seconds=intent_timeout_seconds,
        )
        self.contexts = ControlContextStore(
            ttl_seconds=context_ttl_seconds,
            max_sessions=max_sessions,
        )
        self.pending = PendingControlStore(
            ttl_seconds=confirmation_ttl_seconds,
            max_sessions=max_sessions,
        )
        self.aliases = LearnedAliasStore(alias_path)
        self.auto_execute_confidence = max(0.6, min(1.0, float(auto_execute_confidence)))
        self.block_below_confidence = max(0.0, min(self.auto_execute_confidence, float(block_below_confidence)))
        self.group_confirmation_size = max(2, min(30, int(group_confirmation_size)))

    async def answer(self, request: Any, original_ask: AskHandler) -> dict[str, Any]:
        session_id = self.contexts.session_id(request)
        query = str(getattr(request, "query", "") or "").strip()

        pending = await self.pending.get(session_id)
        if pending is not None:
            handled = await self._handle_pending(request, pending)
            if handled is not None:
                return handled
            if is_control_candidate(query):
                await self.pending.clear(session_id)

        graph = await self._graph()
        alias_answer = await self._handle_alias_command(query, graph)
        if alias_answer is not None:
            return alias_answer

        if not is_control_candidate(query):
            return await original_ask(request)

        context = await self.contexts.get(session_id)
        history = [
            {
                "role": str(getattr(item, "role", "") or (item.get("role") if isinstance(item, dict) else "")),
                "content": str(getattr(item, "content", "") or (item.get("content") if isinstance(item, dict) else "")),
            }
            for item in list(getattr(request, "history", None) or [])[-4:]
        ]
        intent, diagnostics = await self.interpreter.interpret(
            query,
            history=history,
            context=context.public_dict(),
            inventory=graph.inventory_summary(),
        )
        if intent is None:
            return await original_ask(request)

        plan = self._resolve_plan(query, intent, diagnostics, graph, context.graph_context())
        unresolved = [item for item in plan.actions if not item.nodes]
        if unresolved:
            return await self._clarify_unresolved(session_id, plan, unresolved)

        policy = self._policy(plan)
        if policy["decision"] == "block":
            return self._blocked_response(plan, policy)
        if policy["decision"] == "confirm":
            await self.pending.put(session_id, kind="confirm-plan", plan=plan)
            return self._confirmation_response(plan, policy)
        return await self._execute_plan(session_id, plan, confirmed=False)

    async def _graph(self) -> ControlDeviceGraph:
        aliases = await self.aliases.all()
        devices = await self.device_index.summary_devices()
        return ControlDeviceGraph(devices, learned_aliases=aliases)

    def _resolve_plan(
        self,
        query: str,
        intent: ControlIntent,
        diagnostics: dict[str, Any],
        graph: ControlDeviceGraph,
        context: Any,
    ) -> ControlPlan:
        actions: list[ResolvedControlAction] = []
        for action in intent.actions:
            target = graph.expand_plural_room_group(action.target)
            resolved_intent = action
            if target != action.target:
                resolved_intent = ControlActionIntent(
                    command=action.command,
                    value=action.value,
                    target=target,
                )
            resolution = graph.resolve(target, context=context)
            actions.append(
                ResolvedControlAction(
                    intent=resolved_intent,
                    nodes=list(resolution.nodes),
                    candidates=list(resolution.candidates),
                    resolution_confidence=resolution.confidence,
                    resolution_method=resolution.method,
                    resolution_reason=resolution.reason,
                )
            )
        return ControlPlan(
            query=query,
            intent=intent,
            actions=actions,
            diagnostics=dict(diagnostics),
        )

    def _policy(self, plan: ControlPlan) -> dict[str, Any]:
        count = len(plan.nodes)
        reasons: list[str] = []
        decision = "execute"
        if plan.confidence < self.block_below_confidence:
            decision = "block"
            reasons.append("Resolution confidence is below the safe control threshold.")
        elif plan.sensitive:
            decision = "confirm"
            reasons.append("A sensitive device type always requires confirmation.")
        elif count >= self.group_confirmation_size:
            decision = "confirm"
            reasons.append(f"The command affects {count} devices.")
        elif plan.confidence < self.auto_execute_confidence:
            decision = "confirm"
            reasons.append("The intent or device resolution is not confident enough for automatic execution.")
        if any(
            item.intent.target.quantifier == "all"
            and not item.intent.target.room_hint
            and not item.intent.target.device_type
            for item in plan.actions
        ):
            decision = "confirm"
            reasons.append("An unrestricted all-device command requires confirmation.")
        return {
            "decision": decision,
            "confidence": round(plan.confidence, 3),
            "device_count": count,
            "sensitive": plan.sensitive,
            "reasons": reasons,
        }

    async def _clarify_unresolved(
        self,
        session_id: str,
        plan: ControlPlan,
        unresolved: list[ResolvedControlAction],
    ) -> dict[str, Any]:
        if len(unresolved) == 1 and len(plan.actions) == 1 and unresolved[0].candidates:
            action = unresolved[0]
            candidates = action.candidates[:5]
            await self.contexts.record_candidates(session_id, [item.id for item in candidates])
            await self.pending.put(
                session_id,
                kind="choose-device",
                plan=plan,
                action_index=0,
                candidate_ids=[item.id for item in candidates],
            )
            lines = ["Which device did you mean?"]
            lines.extend(
                f"{index}. {item.label} (Hubitat ID {item.id}{f', {item.room}' if item.room else ''})"
                for index, item in enumerate(candidates, start=1)
            )
            lines.append("Reply with the number or exact device name. Reply No to cancel.")
            return {
                "success": False,
                "route": "control-agent",
                "intent": "control-agent-device-choice-required",
                "message": "\n".join(lines),
                "confirmation_required": True,
                "alternatives": [f"{item.label} (Hubitat ID {item.id})" for item in candidates],
                "display": display_payload(
                    "control-agent-choice",
                    "Choose device",
                    subtitle="No command has been sent",
                    metrics=[
                        {"label": "Action", "value": self._action_text(action), "icon": "🎯"},
                        {"label": "Candidates", "value": str(len(candidates)), "icon": "🔎"},
                    ],
                    items=[
                        {
                            "icon": "📱",
                            "title": item.label,
                            "value": str(index),
                            "subtitle": (
                                f"{item.room or 'No room assigned'} · Hubitat ID {item.id}"
                                + (
                                    f" · {str(item.current_states.get('switch')).title()}"
                                    if item.current_states.get("switch") is not None
                                    else ""
                                )
                            ),
                        }
                        for index, item in enumerate(candidates, start=1)
                    ],
                    note="These are different Hubitat device IDs. Choose once; HomeBrain will remember this spoken target.",
                ),
                "technical": safe_debug(plan.public_dict()),
                "control_intent": plan.intent.response_dict(),
                "model": plan.intent.model,
                "ai_provider": "Local Ollama control interpreter" if plan.intent.model else None,
            }

        details = []
        for action in unresolved:
            target = action.intent.target.name_hint or action.intent.target.room_hint or action.intent.target.device_type or "device"
            details.append(f"- {target}: {action.resolution_reason}")
        return {
            "success": False,
            "route": "control-agent",
            "intent": "control-agent-unresolved",
            "message": "No command was sent because every target could not be resolved safely.\n" + "\n".join(details),
            "display": display_payload(
                "control-agent-unresolved",
                "Control target unresolved",
                subtitle="No devices changed",
                metrics=[
                    {"label": "Requested", "value": str(len(plan.actions)), "icon": "🎛️"},
                    {"label": "Unresolved", "value": str(len(unresolved)), "icon": "⚠️"},
                ],
                note="Use an exact label, room plus device type, or a numbered device such as Livingroom Light 2.",
            ),
            "technical": safe_debug(plan.public_dict()),
            "control_intent": plan.intent.response_dict(),
        }

    def _confirmation_response(self, plan: ControlPlan, policy: dict[str, Any]) -> dict[str, Any]:
        items = []
        for action in plan.actions:
            for node in action.nodes:
                items.append(
                    {
                        "icon": "🎛️",
                        "title": node.label,
                        "value": self._action_text(action),
                        "subtitle": node.room or "No room assigned",
                    }
                )
        reason = " ".join(policy["reasons"]) or "Confirmation is required by policy."
        return {
            "success": False,
            "route": "control-agent",
            "intent": "control-agent-confirmation-required",
            "message": self._plan_summary(plan) + f"\n{reason}\nReply Yes to continue or No to cancel.",
            "confirmation_required": True,
            "display": display_payload(
                "control-agent-confirmation",
                "Confirm control plan",
                subtitle="No command has been sent",
                metrics=[
                    {"label": "Devices", "value": str(len(plan.nodes)), "icon": "🎛️"},
                    {"label": "Confidence", "value": f"{plan.confidence * 100:.0f}%", "icon": "🧠"},
                    {"label": "Risk", "value": "Sensitive" if plan.sensitive else "Low", "icon": "🛡️"},
                ],
                items=items,
                note=reason,
            ),
            "technical": safe_debug({"plan": plan.public_dict(), "policy": policy}),
            "control_intent": plan.intent.response_dict(),
            "model": plan.intent.model,
            "ai_provider": "Local Ollama control interpreter" if plan.intent.model else None,
        }

    def _blocked_response(self, plan: ControlPlan, policy: dict[str, Any]) -> dict[str, Any]:
        reason = " ".join(policy["reasons"]) or "The plan did not meet the safe execution policy."
        return {
            "success": False,
            "route": "control-agent",
            "intent": "control-agent-policy-blocked",
            "message": f"No command was sent. {reason}",
            "display": display_payload(
                "control-agent-blocked",
                "Control blocked",
                subtitle="No devices changed",
                metrics=[
                    {"label": "Confidence", "value": f"{plan.confidence * 100:.0f}%", "icon": "🧠"},
                    {"label": "Devices", "value": str(len(plan.nodes)), "icon": "🎛️"},
                ],
                note=reason,
            ),
            "technical": safe_debug({"plan": plan.public_dict(), "policy": policy}),
        }

    async def _handle_pending(self, request: Any, pending: Any) -> dict[str, Any] | None:
        session_id = self.contexts.session_id(request)
        query = str(getattr(request, "query", "") or "").strip()
        normal = " ".join(query.lower().split())
        if normal in _NO:
            await self.pending.clear(session_id)
            return {
                "success": True,
                "route": "control-agent-confirmation",
                "intent": "control-agent-cancelled",
                "message": "Cancelled. No device command was sent.",
                "display": display_payload(
                    "control-agent-cancelled",
                    "Command cancelled",
                    subtitle="No devices changed",
                    metrics=[{"label": "Command", "value": "Cancelled", "icon": "🛑"}],
                ),
            }

        if pending.kind == "confirm-plan":
            if normal in _YES:
                await self.pending.clear(session_id)
                return await self._execute_plan(session_id, pending.plan, confirmed=True)
            if not is_control_candidate(query):
                return self._confirmation_response(pending.plan, self._policy(pending.plan))
            return None

        if pending.kind == "choose-device":
            graph = await self._graph()
            candidates = [graph.by_id[item] for item in pending.candidate_ids if item in graph.by_id]
            selected: DeviceNode | None = None
            if normal.isdigit():
                index = int(normal) - 1
                if 0 <= index < len(candidates):
                    selected = candidates[index]
            if selected is None:
                key = spoken_name_key(query)
                matches = [item for item in candidates if spoken_name_key(item.label) == key]
                if len(matches) == 1:
                    selected = matches[0]
            if selected is None:
                if is_control_candidate(query):
                    return None
                lines = ["Please choose one device:"]
                lines.extend(
                    f"{index}. {item.label} (Hubitat ID {item.id})"
                    for index, item in enumerate(candidates, start=1)
                )
                lines.append("Reply No to cancel.")
                return {
                    "success": False,
                    "route": "control-agent-confirmation",
                    "intent": "control-agent-device-choice-required",
                    "message": "\n".join(lines),
                    "confirmation_required": True,
                }
            plan: ControlPlan = pending.plan
            action = plan.actions[int(pending.action_index or 0)]
            action.nodes = [selected]
            action.resolution_confidence = 1.0
            action.resolution_method = "user-selected-candidate"
            action.resolution_reason = "The user selected the exact candidate."
            name_hint = action.intent.target.name_hint.strip()
            if name_hint:
                await self.aliases.add(name_hint, f"device-id:{selected.id}")
            await self.pending.clear(session_id)
            return await self._execute_plan(session_id, plan, confirmed=True)
        return None

    async def _execute_plan(
        self,
        session_id: str,
        plan: ControlPlan,
        *,
        confirmed: bool,
    ) -> dict[str, Any]:
        preflight = await self._preflight_selected(plan)
        if preflight is not None:
            return preflight

        child_results: list[dict[str, Any]] = []
        successful_nodes: list[DeviceNode] = []
        for action in plan.actions:
            for node in action.nodes:
                if action.intent.command in {"on", "off"}:
                    result = dict(await self.fallback._control_device(node.label, action.intent.command))
                elif action.intent.command == "set_level":
                    result = await self._set_level(node, float(action.intent.value or 0.0))
                else:
                    result = {
                        "success": False,
                        "message": f"Unsupported command: {action.intent.command}",
                        "intent": "control-agent-command-unsupported",
                    }
                result["control_agent_device"] = node.public_dict()
                result["control_agent_action"] = action.intent.command
                child_results.append(result)
                if result.get("success"):
                    successful_nodes.append(node)

        success = bool(child_results) and all(item.get("success") for item in child_results)
        partial = bool(successful_nodes) and not success
        if successful_nodes:
            first = successful_nodes[0]
            action_name = plan.actions[0].intent.command if plan.actions else ""
            await self.contexts.record_success(
                session_id,
                device_ids=[item.id for item in successful_nodes],
                candidate_ids=[item.id for item in plan.candidates or plan.nodes],
                room=first.room,
                device_type=next(iter(sorted(first.types - {"device", "switch", "sensor"})), "device"),
                action=action_name,
            )

        items = []
        lines = []
        for result in child_results:
            node = result["control_agent_device"]
            state = "Confirmed" if result.get("success") else "Failed"
            message = str(result.get("message") or "")
            lines.append(f"- {node['label']}: {message}")
            items.append(
                {
                    "icon": "✅" if result.get("success") else "⚠️",
                    "title": node["label"],
                    "value": state,
                    "subtitle": message,
                    "tone": "good" if result.get("success") else "warning",
                }
            )

        title = "Control confirmed" if success else "Control partly completed" if partial else "Control failed"
        message = (
            f"{len(successful_nodes)} of {len(child_results)} device commands were confirmed."
            + ("\n" + "\n".join(lines) if lines else "")
        )
        tools_used: list[dict[str, Any]] = []
        for item in child_results:
            for tool in item.get("tools_used") or []:
                if isinstance(tool, dict):
                    tools_used.append(tool)
        answer = {
            "success": success,
            "route": "control-agent+mcp",
            "intent": "control-agent-confirmed" if success else "control-agent-partial" if partial else "control-agent-failed",
            "message": message,
            "display": display_payload(
                "control-agent-result",
                title,
                subtitle="Fresh Hubitat state verification used",
                metrics=[
                    {"label": "Requested", "value": str(len(child_results)), "icon": "🎛️"},
                    {"label": "Confirmed", "value": str(len(successful_nodes)), "icon": "✅"},
                    {"label": "Interpreter", "value": "Local AI" if plan.intent.model else "Deterministic", "icon": "🧠"},
                ],
                items=items,
                note=(
                    "The interpreter never received command tools. Python resolved every selected-device ID "
                    "before the first write, then the existing MCP control engine read final states back from Hubitat."
                ),
            ),
            "control_intent": plan.intent.response_dict(),
            "control_plan": plan.public_dict(),
            "control_confirmed_by_user": confirmed,
            "tools_used": tools_used,
            "technical": safe_debug(
                {
                    "plan": plan.public_dict(),
                    "confirmed_by_user": confirmed,
                    "results": [
                        {
                            "device": item.get("control_agent_device"),
                            "success": item.get("success"),
                            "intent": item.get("intent"),
                            "message": item.get("message"),
                        }
                        for item in child_results
                    ],
                }
            ),
        }
        if plan.intent.model:
            answer["model"] = plan.intent.model
            answer["planner_model"] = plan.intent.model
            answer["ai_provider"] = "Local Ollama control interpreter"
            answer["answered_by"] = "Local AI intent + deterministic verified Hubitat MCP"
        else:
            answer["answered_by"] = "Deterministic Control Agent + verified Hubitat MCP"
        return answer

    async def _preflight_selected(self, plan: ControlPlan) -> dict[str, Any] | None:
        try:
            fresh = await self.fallback._direct_fresh_devices("Switch", detailed=False)
            if fresh is None:
                rows = await self.device_index.capability_devices("Switch", force=True)
            else:
                rows = self.fallback._device_rows(fresh.data)
        except Exception as exc:
            return self._preflight_error(f"Fresh selected-device preflight failed: {exc}", plan)
        ids = {str(_device_id(item)) for item in rows if _device_id(item) not in (None, "")}
        missing = [node for node in plan.nodes if node.id not in ids]
        if not missing:
            return None
        return self._preflight_error(
            "No command was sent because these resolved targets are no longer in the live selected Switch inventory: "
            + ", ".join(item.label for item in missing),
            plan,
        )

    @staticmethod
    def _preflight_error(message: str, plan: ControlPlan) -> dict[str, Any]:
        return {
            "success": False,
            "route": "control-agent+mcp",
            "intent": "control-agent-preflight-blocked",
            "message": message,
            "display": display_payload(
                "control-agent-preflight",
                "Control preflight blocked",
                subtitle="No command was sent",
                metrics=[{"label": "Resolved targets", "value": str(len(plan.nodes)), "icon": "🎛️"}],
                note="Refresh Hubitat devices if the MCP selected-device allowlist changed.",
            ),
            "technical": safe_debug({"plan": plan.public_dict(), "preflight_error": message}),
        }

    async def _set_level(self, node: DeviceNode, value: float) -> dict[str, Any]:
        value = max(0.0, min(100.0, value))
        client = self.fallback.client
        tool = await client.get_tool("hub_call_device_command")
        properties = (tool.input_schema or {}).get("properties", {}) if tool else {}
        arguments: dict[str, Any] = {}
        for key in ("deviceId", "id", "device_id"):
            if not properties or key in properties:
                arguments[key] = node.id
                break
        arguments["command"] = "setLevel"
        arguments["params"] = [round(value)]
        result = await client.call_tool("hub_call_device_command", arguments)
        if result.is_error:
            return {
                "success": False,
                "intent": "control-agent-level-error",
                "message": result.text or f"Failed to set {node.label} to {value:g}%.",
                "tools_used": [{"name": "hub_call_device_command", "success": False}],
            }
        invalidate = getattr(client, "invalidate", None)
        if callable(invalidate):
            await invalidate("devices")

        deadline = time.monotonic() + float(getattr(self.fallback, "control_verification_timeout_seconds", 7.0))
        await asyncio.sleep(float(getattr(self.fallback, "control_verification_initial_delay_seconds", 0.2)))
        observed: float | None = None
        while time.monotonic() < deadline:
            fresh = await self.fallback._direct_fresh_devices("Switch Level", detailed=False)
            if fresh is None:
                break
            rows = self.fallback._device_rows(fresh.data)
            match = next((item for item in rows if str(_device_id(item)) == node.id), None)
            if match is not None:
                attrs = _attributes(match)
                raw = attrs.get("level", match.get("level"))
                try:
                    observed = float(str(raw).replace("%", "").strip())
                except Exception:
                    observed = None
                if observed is not None and abs(observed - value) <= 1.0:
                    return {
                        "success": True,
                        "intent": "control-agent-level-confirmed",
                        "message": f"{node.label} is confirmed at {observed:g}%.",
                        "tools_used": [
                            {"name": "hub_call_device_command", "success": True},
                            {"name": "hub_list_devices", "success": True},
                        ],
                    }
            await asyncio.sleep(0.35)
        return {
            "success": False,
            "intent": "control-agent-level-unverified",
            "message": (
                f"{node.label} received setLevel {value:g}%, but the final level could not be verified"
                + (f"; last reading was {observed:g}%." if observed is not None else ".")
            ),
            "tools_used": [
                {"name": "hub_call_device_command", "success": True},
                {"name": "hub_list_devices", "success": False},
            ],
        }

    async def _handle_alias_command(
        self,
        query: str,
        graph: ControlDeviceGraph,
    ) -> dict[str, Any] | None:
        forget = _ALIAS_FORGET.match(query)
        if forget:
            alias = forget.group(1).strip()
            removed = await self.aliases.remove(alias)
            return {
                "success": removed,
                "route": "control-agent-alias",
                "intent": "control-agent-alias-forgotten" if removed else "control-agent-alias-not-found",
                "message": f'Forgot the alias "{alias}".' if removed else f'I do not have a saved alias named "{alias}".',
            }

        alias = ""
        device_text = ""
        add = _ALIAS_ADD.match(query)
        if add:
            alias, device_text = add.group(1).strip(), add.group(2).strip()
        else:
            call = _ALIAS_CALL.match(query)
            if call:
                device_text, alias = call.group(1).strip(), call.group(2).strip()
        if not alias or not device_text:
            return None

        resolution = graph.resolve(ControlTargetIntent(name_hint=device_text))
        if not resolution.resolved or len(resolution.nodes) != 1:
            candidates = ", ".join(item.label for item in resolution.candidates[:5])
            return {
                "success": False,
                "route": "control-agent-alias",
                "intent": "control-agent-alias-device-unresolved",
                "message": (
                    f'I could not uniquely resolve "{device_text}" to save the alias.'
                    + (f" Closest selected devices: {candidates}." if candidates else "")
                ),
            }
        node = resolution.nodes[0]
        if spoken_name_key(alias) == spoken_name_key(node.label):
            return {
                "success": True,
                "route": "control-agent-alias",
                "intent": "control-agent-alias-redundant",
                "message": f'{node.label} already matches the spoken name "{alias}".',
            }
        await self.aliases.add(alias, f"device-id:{node.id}")
        return {
            "success": True,
            "route": "control-agent-alias",
            "intent": "control-agent-alias-saved",
            "message": f'Remembered: "{alias}" means {node.label}.',
            "display": display_payload(
                "control-agent-alias",
                "Alias saved",
                subtitle=node.label,
                metrics=[{"label": "Spoken alias", "value": alias, "icon": "🧠"}],
                note="Aliases are explicit, persistent and removable with: forget alias <name>.",
            ),
        }

    @staticmethod
    def _action_text(action: ResolvedControlAction) -> str:
        if action.intent.command == "set_level":
            return f"Set to {float(action.intent.value or 0):g}%"
        return action.intent.command.title()

    @classmethod
    def _plan_summary(cls, plan: ControlPlan) -> str:
        parts = []
        for action in plan.actions:
            labels = ", ".join(node.label for node in action.nodes)
            parts.append(f"{cls._action_text(action)}: {labels}")
        return "\n".join(parts)


def install_control_agent(
    application: Any,
    device_index: Any,
    fallback: Any,
    **kwargs: Any,
) -> HomeBrainControlAgent:
    original_ask: AskHandler = application.ask
    agent = HomeBrainControlAgent(application, device_index, fallback, **kwargs)

    async def ask_with_control_agent(request: Any) -> dict[str, Any]:
        if not application.option_bool("control_agent_enabled", True):
            return await original_ask(request)
        return await agent.answer(request, original_ask)

    application.ask = ask_with_control_agent
    return agent


__all__ = [
    "ControlPlan",
    "HomeBrainControlAgent",
    "ResolvedControlAction",
    "install_control_agent",
]
