from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Awaitable, Callable

from assistant_contracts import ExecutionItem, ExecutionResult, VerificationOutcome
from control_agent_graph import (
    ControlDeviceGraph,
    DeviceNode,
    GraphContext,
    exact_non_control_matches,
    non_control_public,
)
from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
    is_control_candidate,
)
from control_language import canonicalise_basic_control
from device_intelligence_index import _attributes, _device_id, _label
from entity_resolver import EntityResolver
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, safe_debug
from spoken_device_name import spoken_name_key

# State

@dataclass(slots=True)
class ControlSessionContext:
    session_id: str
    last_device_ids: tuple[str, ...] = ()
    last_candidate_ids: tuple[str, ...] = ()
    last_room: str = ""
    last_device_type: str = ""
    last_action: str = ""
    updated_at: float = 0.0
    expires_at: float = 0.0

    def graph_context(self) -> GraphContext:
        return GraphContext(
            last_device_ids=self.last_device_ids,
            last_candidate_ids=self.last_candidate_ids,
            last_room=self.last_room,
            last_device_type=self.last_device_type,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "last_device_ids": list(self.last_device_ids),
            "last_candidate_ids": list(self.last_candidate_ids),
            "last_room": self.last_room,
            "last_device_type": self.last_device_type,
            "last_action": self.last_action,
        }

class ControlContextStore:
    def __init__(self, *, ttl_seconds: float = 600.0, max_sessions: int = 128) -> None:
        self.ttl_seconds = max(60.0, min(3600.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self._items: dict[str, ControlSessionContext] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def session_id(request: Any) -> str:
        value = str(getattr(request, "session_id", "") or "default").strip()
        return value[:160] or "default"

    async def get(self, session_id: str) -> ControlSessionContext:
        key = str(session_id or "default")[:160]
        async with self._lock:
            self._purge_locked()
            current = self._items.get(key)
            if current is not None:
                return current
            return ControlSessionContext(session_id=key)

    async def record_candidates(self, session_id: str, candidate_ids: list[str]) -> None:
        key = str(session_id or "default")[:160]
        now = time.time()
        async with self._lock:
            self._purge_locked()
            current = self._items.get(key) or ControlSessionContext(session_id=key)
            current.last_candidate_ids = tuple(dict.fromkeys(str(item) for item in candidate_ids if item))
            current.updated_at = now
            current.expires_at = now + self.ttl_seconds
            self._put_locked(current)

    async def record_success(
        self,
        session_id: str,
        *,
        device_ids: list[str],
        candidate_ids: list[str],
        room: str,
        device_type: str,
        action: str,
    ) -> None:
        key = str(session_id or "default")[:160]
        now = time.time()
        async with self._lock:
            self._purge_locked()
            current = self._items.get(key) or ControlSessionContext(session_id=key)
            current.last_device_ids = tuple(dict.fromkeys(str(item) for item in device_ids if item))
            current.last_candidate_ids = tuple(
                dict.fromkeys(str(item) for item in (candidate_ids or device_ids) if item)
            )
            current.last_room = str(room or "")[:100]
            current.last_device_type = str(device_type or "")[:50]
            current.last_action = str(action or "")[:30]
            current.updated_at = now
            current.expires_at = now + self.ttl_seconds
            self._put_locked(current)

    async def clear(self, session_id: str) -> bool:
        key = str(session_id or "default")[:160]
        async with self._lock:
            return self._items.pop(key, None) is not None

    def _put_locked(self, value: ControlSessionContext) -> None:
        if len(self._items) >= self.max_sessions and value.session_id not in self._items:
            oldest = min(self._items.values(), key=lambda item: item.updated_at)
            self._items.pop(oldest.session_id, None)
        self._items[value.session_id] = value

    def _purge_locked(self) -> None:
        now = time.time()
        for key in [key for key, value in self._items.items() if value.expires_at and value.expires_at <= now]:
            self._items.pop(key, None)

@dataclass(slots=True)
class PendingControl:
    session_id: str
    kind: str
    plan: Any = None
    action_index: int | None = None
    candidate_ids: tuple[str, ...] = ()
    created_at: float = 0.0
    expires_at: float = 0.0

class PendingControlStore:
    def __init__(self, *, ttl_seconds: float = 120.0, max_sessions: int = 128) -> None:
        self.ttl_seconds = max(30.0, min(600.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self._items: dict[str, PendingControl] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> PendingControl | None:
        key = str(session_id or "default")[:160]
        async with self._lock:
            self._purge_locked()
            return self._items.get(key)

    async def put(
        self,
        session_id: str,
        *,
        kind: str,
        plan: Any = None,
        action_index: int | None = None,
        candidate_ids: list[str] | tuple[str, ...] = (),
    ) -> PendingControl:
        key = str(session_id or "default")[:160]
        now = time.time()
        value = PendingControl(
            session_id=key,
            kind=kind,
            plan=plan,
            action_index=action_index,
            candidate_ids=tuple(dict.fromkeys(str(item) for item in candidate_ids if item)),
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        async with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_sessions and key not in self._items:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.session_id, None)
            self._items[key] = value
        return value

    async def clear(self, session_id: str) -> bool:
        key = str(session_id or "default")[:160]
        async with self._lock:
            return self._items.pop(key, None) is not None

    def _purge_locked(self) -> None:
        now = time.time()
        for key in [key for key, value in self._items.items() if value.expires_at <= now]:
            self._items.pop(key, None)

class LearnedAliasStore:
    """Small explicit alias store persisted in the add-on data directory."""

    def __init__(self, path: str = "/data/control_agent_aliases.json") -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self._aliases: dict[str, str] | None = None

    async def all(self) -> dict[str, str]:
        async with self._lock:
            self._load_locked()
            return dict(self._aliases or {})

    async def add(self, alias: str, device_label: str) -> None:
        clean_alias = " ".join(str(alias or "").strip().split())[:100]
        clean_label = " ".join(str(device_label or "").strip().split())[:140]
        if len(clean_alias) < 2 or not clean_label:
            raise ValueError("Alias and device label are required")
        async with self._lock:
            self._load_locked()
            assert self._aliases is not None
            self._aliases[clean_alias] = clean_label
            self._save_locked()

    async def remove(self, alias: str) -> bool:
        target = " ".join(str(alias or "").strip().split())
        async with self._lock:
            self._load_locked()
            assert self._aliases is not None
            key = next((item for item in self._aliases if item.lower() == target.lower()), None)
            if key is None:
                return False
            self._aliases.pop(key, None)
            self._save_locked()
            return True

    def _load_locked(self) -> None:
        if self._aliases is not None:
            return
        try:
            decoded = json.loads(self.path.read_text(encoding="utf-8"))
            self._aliases = {
                str(key): str(value)
                for key, value in decoded.items()
                if str(key).strip() and str(value).strip()
            } if isinstance(decoded, dict) else {}
        except FileNotFoundError:
            self._aliases = {}
        except Exception:
            self._aliases = {}

    def _save_locked(self) -> None:
        assert self._aliases is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._aliases, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

# Control Agent

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
    resolution_status: str = "not_found"
    resolution_trace: list[str] = field(default_factory=list)

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
            "resolution_status": self.resolution_status,
            "resolution_trace": list(self.resolution_trace),
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

    async def _graph(self) -> EntityResolver:
        aliases = await self.aliases.all()
        devices = await self.device_index.summary_devices()
        return EntityResolver(devices, learned_aliases=aliases)

    def _resolve_plan(
        self,
        query: str,
        intent: ControlIntent,
        diagnostics: dict[str, Any],
        graph: EntityResolver,
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
            resolution, contract = graph.resolve_for_action(
                target,
                action=resolved_intent.command,
                context=context,
            )
            actions.append(
                ResolvedControlAction(
                    intent=resolved_intent,
                    nodes=list(resolution.nodes),
                    candidates=list(resolution.candidates),
                    resolution_confidence=resolution.confidence,
                    resolution_method=resolution.method,
                    resolution_reason=resolution.reason,
                    resolution_status=contract.status.value,
                    resolution_trace=list(contract.trace),
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
        if (
            len(unresolved) == 1
            and len(plan.actions) == 1
            and unresolved[0].candidates
            and unresolved[0].resolution_status != "unsupported_action"
        ):
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
                            "query": self._candidate_choice_query(action, item),
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
            action = pending.plan.actions[int(pending.action_index or 0)]
            clicked = [
                item
                for item in candidates
                if normal == " ".join(self._candidate_choice_query(action, item).lower().split())
            ]
            if len(clicked) == 1:
                selected = clicked[0]
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
        submitted_nodes: list[DeviceNode] = []
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
                if result.get("success"):
                    outcome = VerificationOutcome.COMPLETED
                elif (
                    result.get("command_sent")
                    or result.get("command_accepted")
                    or result.get("intent") == "control-agent-level-unverified"
                ):
                    outcome = VerificationOutcome.SENT
                else:
                    outcome = VerificationOutcome.FAILED
                result["verification_outcome"] = outcome.value
                child_results.append(result)
                if result.get("success"):
                    successful_nodes.append(node)
                if outcome in {VerificationOutcome.COMPLETED, VerificationOutcome.SENT}:
                    submitted_nodes.append(node)

        success = bool(child_results) and all(item.get("success") for item in child_results)
        partial = bool(successful_nodes) and not success
        outcomes = [VerificationOutcome(item["verification_outcome"]) for item in child_results]
        if outcomes and all(item is VerificationOutcome.COMPLETED for item in outcomes):
            overall_outcome = VerificationOutcome.COMPLETED
        elif outcomes and all(
            item in {VerificationOutcome.COMPLETED, VerificationOutcome.SENT}
            for item in outcomes
        ):
            overall_outcome = VerificationOutcome.SENT
        elif outcomes and all(item is VerificationOutcome.FAILED for item in outcomes):
            overall_outcome = VerificationOutcome.FAILED
        else:
            overall_outcome = VerificationOutcome.UNCERTAIN
        if submitted_nodes:
            first = submitted_nodes[0]
            action_name = plan.actions[0].intent.command if plan.actions else ""
            await self.contexts.record_success(
                session_id,
                device_ids=[item.id for item in submitted_nodes],
                candidate_ids=[item.id for item in plan.candidates or plan.nodes],
                room=first.room,
                device_type=next(iter(sorted(first.types - {"device", "switch", "sensor"})), "device"),
                action=action_name,
            )

        items = []
        lines = []
        for result in child_results:
            node = result["control_agent_device"]
            outcome = VerificationOutcome(result["verification_outcome"])
            state = {
                VerificationOutcome.COMPLETED: "Completed",
                VerificationOutcome.SENT: "Sent",
                VerificationOutcome.FAILED: "Failed",
                VerificationOutcome.UNCERTAIN: "Uncertain",
            }[outcome]
            message = str(result.get("message") or "")
            lines.append(f"- {node['label']}: {message}")
            items.append(
                {
                    "icon": "✅" if outcome is VerificationOutcome.COMPLETED else "⏳" if outcome is VerificationOutcome.SENT else "⚠️",
                    "title": node["label"],
                    "value": state,
                    "subtitle": message,
                    "tone": "good" if outcome is VerificationOutcome.COMPLETED else "warning",
                }
            )

        sent_count = sum(item is VerificationOutcome.SENT for item in outcomes)
        failed_count = sum(item is VerificationOutcome.FAILED for item in outcomes)
        title = {
            VerificationOutcome.COMPLETED: "Control completed",
            VerificationOutcome.SENT: "Control sent",
            VerificationOutcome.FAILED: "Control failed",
            VerificationOutcome.UNCERTAIN: "Control partly completed",
        }[overall_outcome]
        message = (
            f"{len(successful_nodes)} completed, {sent_count} sent awaiting state verification, "
            f"and {failed_count} failed out of {len(child_results)} device commands."
            + ("\n" + "\n".join(lines) if lines else "")
        )
        tools_used: list[dict[str, Any]] = []
        for item in child_results:
            for tool in item.get("tools_used") or []:
                if isinstance(tool, dict):
                    tools_used.append(tool)
        execution_items = [
            ExecutionItem(
                device_id=str(item["control_agent_device"]["id"]),
                label=str(item["control_agent_device"]["label"]),
                action=str(item.get("control_agent_action") or ""),
                outcome=VerificationOutcome(item["verification_outcome"]),
                submitted=VerificationOutcome(item["verification_outcome"])
                in {VerificationOutcome.COMPLETED, VerificationOutcome.SENT},
                accepted_by_hub=bool(
                    item.get("command_accepted")
                    or item.get("command_sent")
                    or item.get("success")
                    or item.get("intent") == "control-agent-level-unverified"
                ),
                verified=True if item.get("success") else False if item["verification_outcome"] == "sent" else None,
                observed_state=str(item.get("verified_state") or "") or None,
                message=str(item.get("message") or ""),
            )
            for item in child_results
        ]
        execution_result = ExecutionResult(
            outcome=overall_outcome,
            success=success,
            submitted=bool(submitted_nodes),
            verified=True if success else False if submitted_nodes else None,
            targets=execution_items,
            warnings=[
                item.message
                for item in execution_items
                if item.outcome is not VerificationOutcome.COMPLETED
            ],
            evidence=[{"tools_used": tools_used}],
        )
        answer = {
            "success": success,
            "outcome": overall_outcome.value,
            "submitted": bool(submitted_nodes),
            "verified": True if success else False if submitted_nodes else None,
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
            "execution_result": execution_result.model_dump(mode="json"),
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
            "command_sent": True,
            "command_accepted": True,
            "confirmed": False,
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

    @staticmethod
    def _candidate_choice_query(action: ResolvedControlAction, node: DeviceNode) -> str:
        if action.intent.command == "set_level":
            return f"set {node.label} to {float(action.intent.value or 0):g}%"
        return f"turn {action.intent.command} {node.label}"

    @classmethod
    def _plan_summary(cls, plan: ControlPlan) -> str:
        parts = []
        for action in plan.actions:
            labels = ", ".join(node.label for node in action.nodes)
            parts.append(f"{cls._action_text(action)}: {labels}")
        return "\n".join(parts)

def install_base_control_agent(
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

# Level Verified

_LEVEL_READ_STRATEGIES: tuple[tuple[str | None, bool, str], ...] = (
    ("SwitchLevel", False, "summary-currentStates:SwitchLevel"),
    (None, False, "all-summary-currentStates"),
    ("Switch Level", False, "summary-currentStates:Switch Level"),
    ("SwitchLevel", True, "detailed-attributes:SwitchLevel"),
    (None, True, "all-detailed-attributes"),
)

_LEVEL_QUICK_RETRY_STRATEGIES = _LEVEL_READ_STRATEGIES[:2]

_CANONICAL_PARAMETER_KEY = "parameters"

_COMPATIBILITY_PARAMETER_KEYS = (
    "params",
    "arguments",
    "args",
    "commandParams",
    "commandArguments",
)

_DEVICE_ID_KEYS = ("deviceId", "id", "device_id")

def _level_number(value: Any) -> float | None:
    if isinstance(value, dict):
        for key in ("currentValue", "value", "currentState", "level", "finalValue"):
            if key in value:
                parsed = _level_number(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return None

def _parameter_value(schema: dict[str, Any], level: int, *, canonical: bool) -> Any:
    """Build the ordered command arguments advertised by the MCP tool schema.

    The MCP Rule Server's canonical ``hub_call_device_command`` contract is an
    array of strings under ``parameters``. Compatibility keys are retained only
    for older/custom servers that genuinely omit the canonical field.
    """

    if canonical:
        return [str(level)]
    declared_type = str(schema.get("type") or "").strip().lower()
    if declared_type == "array" or not declared_type:
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        item_type = str(item_schema.get("type") or "").strip().lower()
        return [str(level)] if item_type == "string" else [level]
    if declared_type == "string":
        return str(level)
    if declared_type in {"integer", "number"}:
        return level
    return [level]

def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}

def _response_state_level(data: dict[str, Any]) -> float | None:
    state = data.get("state")
    if not isinstance(state, dict):
        return None
    return _level_number(state.get("level"))

class FastVerifiedControlAgent(HomeBrainControlAgent):
    """Control Agent with canonical setLevel payload and authoritative verification."""

    def __init__(
        self,
        *args: Any,
        level_verification_timeout_seconds: float = 3.0,
        level_verification_poll_seconds: float = 0.25,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.level_verification_timeout_seconds = max(
            0.8,
            min(7.0, float(level_verification_timeout_seconds)),
        )
        self.level_verification_poll_seconds = max(
            0.1,
            min(0.75, float(level_verification_poll_seconds)),
        )

    async def _set_level(self, node: Any, value: float) -> dict[str, Any]:
        requested = max(0, min(100, round(float(value))))
        client = self.fallback.client
        try:
            tool = await client.get_tool("hub_call_device_command")
        except Exception as exc:
            return self._command_error(
                node.label,
                requested,
                f"Could not read the MCP command schema: {str(exc).strip() or type(exc).__name__}",
            )

        input_schema = getattr(tool, "input_schema", {}) if tool is not None else {}
        properties = (
            input_schema.get("properties", {})
            if isinstance(input_schema, dict)
            else {}
        )
        properties = properties if isinstance(properties, dict) else {}

        arguments: dict[str, Any] = {}
        device_key = next(
            (key for key in _DEVICE_ID_KEYS if not properties or key in properties),
            None,
        )
        if device_key is None:
            return self._command_error(
                node.label,
                requested,
                "The MCP command schema does not expose a device ID field.",
            )
        arguments[device_key] = node.id
        arguments["command"] = "setLevel"

        # The official MCP Rule Server contract is `parameters: ["30"]`.
        # Never prefer a compatibility alias when the canonical field exists.
        if not properties or _CANONICAL_PARAMETER_KEY in properties:
            parameter_key = _CANONICAL_PARAMETER_KEY
        else:
            parameter_key = next(
                (key for key in _COMPATIBILITY_PARAMETER_KEYS if key in properties),
                None,
            )
        if parameter_key is None:
            return self._command_error(
                node.label,
                requested,
                (
                    "The MCP command schema does not expose the canonical parameters field "
                    "or a recognised compatibility field for setLevel."
                ),
            )
        parameter_schema = properties.get(parameter_key)
        parameter_schema = parameter_schema if isinstance(parameter_schema, dict) else {}
        arguments[parameter_key] = _parameter_value(
            parameter_schema,
            requested,
            canonical=parameter_key == _CANONICAL_PARAMETER_KEY,
        )

        wait_for_supported = not properties or "waitFor" in properties
        wait_for_request: dict[str, Any] | None = None
        if wait_for_supported:
            wait_for_request = {
                "attribute": "level",
                "expectedValue": str(requested),
                "comparator": "eq",
                "timeoutMs": max(
                    800,
                    min(7000, round(self.level_verification_timeout_seconds * 1000)),
                ),
                "pollIntervalMs": max(
                    100,
                    min(750, round(self.level_verification_poll_seconds * 1000)),
                ),
            }
            arguments["waitFor"] = wait_for_request

        safe_arguments = {
            "deviceIdField": device_key,
            "deviceId": str(node.id),
            "command": "setLevel",
            "parameterField": parameter_key,
            "parameterValue": arguments[parameter_key],
            "waitFor": wait_for_request,
        }

        try:
            command_result = await client.call_tool("hub_call_device_command", arguments)
        except Exception as exc:
            return self._command_error(
                node.label,
                requested,
                f"The MCP command call failed: {str(exc).strip() or type(exc).__name__}",
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
            )
        if command_result.is_error:
            return self._command_error(
                node.label,
                requested,
                command_result.text or f"Failed to set {node.label} to {requested}%.",
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
            )

        response = _mapping(command_result.data)
        server_wait = _mapping(response.get("waitFor"))
        wait_converged = server_wait.get("converged") is True
        wait_final = _level_number(server_wait.get("finalValue"))
        response_level = _response_state_level(response)
        observed = wait_final if wait_final is not None else response_level

        if wait_converged and observed is not None and abs(observed - requested) <= 1.0:
            return self._confirmed_response(
                node.label,
                requested,
                observed,
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
                source="hub_call_device_command.waitFor",
                server_wait=server_wait,
                attempts=[],
            )

        invalidate = getattr(client, "invalidate", None)
        if callable(invalidate):
            try:
                await invalidate("devices")
            except Exception:
                pass

        # A current MCP server with waitFor has already spent the requested timeout
        # polling. Perform one independent fresh read for honesty, but do not wait for
        # another full timeout. Older servers without waitFor use the local polling path.
        if wait_for_supported and server_wait:
            independent, source, attempts = await self._read_level_once(node.id)
            if independent is not None:
                observed = independent
            if observed is not None and abs(observed - requested) <= 1.0:
                return self._confirmed_response(
                    node.label,
                    requested,
                    observed,
                    parameter_key=parameter_key,
                    command_arguments=safe_arguments,
                    source=source or "fresh-independent-read",
                    server_wait=server_wait,
                    attempts=attempts,
                )
            return self._unverified_response(
                node.label,
                requested,
                observed,
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
                server_wait=server_wait,
                attempts=attempts,
            )

        # Compatibility path for an older/custom MCP server that does not advertise
        # or return waitFor. Verification remains fresh and bounded.
        initial_delay = min(
            0.2,
            max(
                0.05,
                float(
                    getattr(
                        self.fallback,
                        "control_verification_initial_delay_seconds",
                        0.15,
                    )
                ),
            ),
        )
        await asyncio.sleep(initial_delay)
        verified, source, attempts = await self._poll_live_level(node.id, requested)
        if verified is not None and abs(verified - requested) <= 1.0:
            return self._confirmed_response(
                node.label,
                requested,
                verified,
                parameter_key=parameter_key,
                command_arguments=safe_arguments,
                source=source or "fresh-live-read",
                server_wait=server_wait,
                attempts=attempts,
            )
        return self._unverified_response(
            node.label,
            requested,
            verified if verified is not None else observed,
            parameter_key=parameter_key,
            command_arguments=safe_arguments,
            server_wait=server_wait,
            attempts=attempts,
        )

    async def _read_level_once(
        self,
        device_id: str,
    ) -> tuple[float | None, str | None, list[dict[str, Any]]]:
        attempts: list[dict[str, Any]] = []
        for capability, detailed, source in _LEVEL_READ_STRATEGIES:
            try:
                reading, present = await self._read_live_level(
                    device_id,
                    capability=capability,
                    detailed=detailed,
                )
                attempts.append(
                    {
                        "source": source,
                        "device_present": present,
                        "level": reading,
                        "success": True,
                    }
                )
            except Exception as exc:
                attempts.append(
                    {
                        "source": source,
                        "success": False,
                        "error": str(exc).strip() or type(exc).__name__,
                    }
                )
                continue
            if reading is not None:
                return reading, source, attempts
        return None, None, attempts

    async def _poll_live_level(
        self,
        device_id: str,
        requested: int,
    ) -> tuple[float | None, str | None, list[dict[str, Any]]]:
        deadline = time.monotonic() + self.level_verification_timeout_seconds
        preferred: tuple[str | None, bool, str] | None = None
        observed: float | None = None
        observed_source: str | None = None
        attempts: list[dict[str, Any]] = []
        no_value_passes = 0

        while time.monotonic() < deadline:
            if preferred is not None:
                strategies = (preferred,)
            elif no_value_passes:
                strategies = _LEVEL_QUICK_RETRY_STRATEGIES
            else:
                strategies = _LEVEL_READ_STRATEGIES

            numeric_seen = False
            for capability, detailed, source in strategies:
                try:
                    reading, present = await self._read_live_level(
                        device_id,
                        capability=capability,
                        detailed=detailed,
                    )
                    attempts.append(
                        {
                            "source": source,
                            "device_present": present,
                            "level": reading,
                            "success": True,
                        }
                    )
                except Exception as exc:
                    attempts.append(
                        {
                            "source": source,
                            "success": False,
                            "error": str(exc).strip() or type(exc).__name__,
                        }
                    )
                    continue
                if reading is None:
                    continue
                numeric_seen = True
                observed = reading
                observed_source = source
                preferred = (capability, detailed, source)
                if abs(reading - requested) <= 1.0:
                    return reading, source, attempts

            if numeric_seen:
                await asyncio.sleep(self.level_verification_poll_seconds)
                continue
            no_value_passes += 1
            if no_value_passes >= 2:
                break
            await asyncio.sleep(min(0.2, self.level_verification_poll_seconds))

        return observed, observed_source, attempts

    @staticmethod
    def _confirmed_response(
        label: str,
        requested: int,
        observed: float,
        *,
        parameter_key: str,
        command_arguments: dict[str, Any],
        source: str,
        server_wait: dict[str, Any],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "success": True,
            "intent": "control-agent-level-confirmed",
            "message": f"{label} is confirmed at {observed:g}%.",
            "tools_used": [
                {
                    "name": "hub_call_device_command",
                    "success": True,
                    "command": "setLevel",
                    "parameter_field": parameter_key,
                    "verification_source": source,
                    "observed_level": observed,
                }
            ],
            "level_verification": {
                "requested": requested,
                "observed": observed,
                "source": source,
                "command_arguments": command_arguments,
                "server_wait_for": server_wait,
                "fresh_read_attempts": attempts,
            },
        }

    @staticmethod
    def _unverified_response(
        label: str,
        requested: int,
        observed: float | None,
        *,
        parameter_key: str,
        command_arguments: dict[str, Any],
        server_wait: dict[str, Any],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reason = (
            f"; last reading was {observed:g}%."
            if observed is not None
            else "; no numeric level was returned by the command or fresh device reads."
        )
        return {
            "success": False,
            "intent": "control-agent-level-unverified",
            "message": (
                f"{label} received setLevel {requested}%, but the final level could not be verified"
                + reason
            ),
            "tools_used": [
                {
                    "name": "hub_call_device_command",
                    "success": True,
                    "command": "setLevel",
                    "parameter_field": parameter_key,
                    "server_wait_converged": server_wait.get("converged"),
                    "server_wait_final_value": server_wait.get("finalValue"),
                }
            ],
            "level_verification": {
                "requested": requested,
                "observed": observed,
                "source": "hub_call_device_command.waitFor"
                if server_wait
                else "fresh-live-read",
                "command_arguments": command_arguments,
                "server_wait_for": server_wait,
                "fresh_read_attempts": attempts,
            },
        }

    @staticmethod
    def _command_error(
        label: str,
        requested: int,
        message: str,
        *,
        parameter_key: str | None = None,
        command_arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool: dict[str, Any] = {
            "name": "hub_call_device_command",
            "success": False,
            "command": "setLevel",
        }
        if parameter_key:
            tool["parameter_field"] = parameter_key
        return {
            "success": False,
            "intent": "control-agent-level-error",
            "message": message or f"Failed to set {label} to {requested}%.",
            "tools_used": [tool],
            "level_verification": {
                "requested": requested,
                "command_arguments": command_arguments or {},
                "error": message,
            },
        }

    async def _read_live_level(
        self,
        device_id: str,
        *,
        capability: str | None,
        detailed: bool,
    ) -> tuple[float | None, bool]:
        fresh: MCPToolResult | None = await self.fallback._direct_fresh_devices(
            capability,
            detailed=detailed,
        )
        if fresh is not None:
            rows = self.fallback._device_rows(fresh.data)
        elif capability:
            try:
                rows = await self.device_index.capability_devices(
                    capability,
                    detailed=detailed,
                    force=True,
                )
            except TypeError:
                rows = await self.device_index.capability_devices(capability, force=True)
        else:
            rows = await self.device_index.summary_devices(force=True)

        match = next(
            (item for item in rows if str(_device_id(item)) == str(device_id)),
            None,
        )
        if match is None:
            return None, False
        attrs = _attributes(match)
        raw = attrs.get("level", match.get("level"))
        return _level_number(raw), True

def install_verified_control_agent(
    application: Any,
    device_index: Any,
    fallback: Any,
    **kwargs: Any,
) -> FastVerifiedControlAgent:
    original_ask: AskHandler = application.ask
    agent = FastVerifiedControlAgent(application, device_index, fallback, **kwargs)

    async def ask_with_control_agent(request: Any) -> dict[str, Any]:
        if not application.option_bool("control_agent_enabled", True):
            return await original_ask(request)
        return await agent.answer(request, original_ask)

    application.ask = ask_with_control_agent
    return agent

# Rescue

class RescueControlAgent(FastVerifiedControlAgent):
    """Control Agent that retries one failed deterministic interpretation locally.

    The rescue model remains read-free and tool-free. It may only return a strict
    ``ControlIntent``. Python then resolves that intent against the capability-
    filtered selected-device graph and accepts it only when it improves the plan.
    """

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
                "role": str(
                    getattr(item, "role", "")
                    or (item.get("role") if isinstance(item, dict) else "")
                ),
                "content": str(
                    getattr(item, "content", "")
                    or (item.get("content") if isinstance(item, dict) else "")
                ),
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

        plan = self._resolve_plan(
            query,
            intent,
            diagnostics,
            graph,
            context.graph_context(),
        )

        # A selected read-only sensor is not an ambiguous actuator. Check exact
        # names before fuzzy clarification or local AI rescue so HomeBrain never
        # substitutes nearby lights for a known Lux, motion or presence sensor.
        non_control = self._exact_non_control_targets(plan, graph)
        if non_control:
            return self._non_control_response(plan, non_control)

        rescue: dict[str, Any] | None = None
        unresolved = [item for item in plan.actions if not item.nodes]
        if unresolved and not intent.model:
            plan, rescue = await self._attempt_ai_rescue(
                query=query,
                history=history,
                context=context.public_dict(),
                graph=graph,
                graph_context=context.graph_context(),
                original_plan=plan,
            )
            unresolved = [item for item in plan.actions if not item.nodes]

        if unresolved:
            answer = await self._clarify_unresolved(session_id, plan, unresolved)
            return self._decorate_rescue(answer, rescue)

        policy = self._policy(plan)
        if policy["decision"] == "block":
            return self._decorate_rescue(self._blocked_response(plan, policy), rescue)
        if policy["decision"] == "confirm":
            await self.pending.put(session_id, kind="confirm-plan", plan=plan)
            return self._decorate_rescue(self._confirmation_response(plan, policy), rescue)
        answer = await self._execute_plan(session_id, plan, confirmed=False)
        return self._decorate_rescue(answer, rescue)

    @staticmethod
    def _exact_non_control_targets(plan: ControlPlan, graph: Any) -> list[dict[str, Any]]:
        blocked: list[dict[str, Any]] = []
        for index, action in enumerate(plan.actions):
            if action.nodes:
                continue
            requested = str(action.intent.target.name_hint or "").strip()
            if not requested:
                continue
            for raw in exact_non_control_matches(graph, requested):
                blocked.append(
                    {
                        "action_index": index,
                        "command": action.intent.command,
                        "value": action.intent.value,
                        "requested_name": requested,
                        "device": non_control_public(raw),
                    }
                )
        return blocked

    @classmethod
    def _non_control_response(
        cls,
        plan: ControlPlan,
        blocked: list[dict[str, Any]],
    ) -> dict[str, Any]:
        lines: list[str] = []
        items: list[dict[str, Any]] = []
        for item in blocked:
            device = item["device"]
            label = str(device.get("label") or item.get("requested_name") or "This device")
            kind = str(device.get("kind") or "read-only selected device")
            article = "an" if kind[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
            action = cls._blocked_action_text(str(item.get("command") or ""), item.get("value"))
            lines.append(f"{label} is {article} {kind} and cannot be {action}.")
            items.append(
                {
                    "icon": "📡",
                    "title": label,
                    "value": "Read-only",
                    "subtitle": str(device.get("room") or kind),
                    "tone": "warning",
                }
            )

        message = "\n".join(lines)
        message += "\nHomeBrain matched the exact selected device and did not substitute a different actuator."
        return {
            "success": False,
            "route": "control-agent",
            "intent": "control-agent-device-not-controllable",
            "message": message,
            "confirmation_required": False,
            "alternatives": [],
            "display": display_payload(
                "control-agent-not-controllable",
                "Device is not controllable",
                subtitle="No command has been sent",
                metrics=[
                    {"label": "Matched", "value": str(len(blocked)), "icon": "🎯"},
                    {"label": "Control", "value": "Unavailable", "icon": "🚫"},
                ],
                items=items,
                note=(
                    "The exact selected device is read-only and does not expose switch or level "
                    "control. No nearby device was offered or changed."
                ),
            ),
            "technical": safe_debug(
                {
                    "plan": plan.public_dict(),
                    "exact_non_controllable_targets": blocked,
                    "ai_rescue_attempted": False,
                }
            ),
            "control_intent": plan.intent.response_dict(),
            "answered_by": "Deterministic Control Agent capability guard",
            "model": None,
        }

    @staticmethod
    def _blocked_action_text(command: str, value: Any) -> str:
        if command == "on":
            return "turned on"
        if command == "off":
            return "turned off"
        if command == "set_level":
            try:
                number = float(value)
                shown = str(int(number)) if number.is_integer() else f"{number:g}"
            except Exception:
                shown = str(value or "the requested level")
            return f"set to {shown}%"
        return "controlled"

    async def _attempt_ai_rescue(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        context: dict[str, Any],
        graph: Any,
        graph_context: Any,
        original_plan: ControlPlan,
    ) -> tuple[ControlPlan, dict[str, Any]]:
        details: dict[str, Any] = {
            "attempted": False,
            "accepted": False,
            "reason": "AI rescue is disabled.",
            "original_intent": original_plan.intent.response_dict(),
            "original_plan_quality": self._plan_quality(original_plan),
        }
        if not self.application.option_bool("control_agent_ai_rescue_enabled", True):
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details
        if not self.application.option_bool("ollama_enabled", True):
            details["reason"] = "Local Ollama is disabled."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        rescue_context = dict(context)
        rescue_context["control_rescue"] = {
            "mode": "reinterpret_failed_deterministic_plan",
            "failed_intent": original_plan.intent.response_dict(),
            "failed_resolutions": [item.public_dict() for item in original_plan.actions],
            "instruction": (
                "Reinterpret the original user wording. Remove leftover command syntax from "
                "device names and express room, type, ordinal, level and references in their "
                "dedicated schema fields. Do not invent a device ID."
            ),
        }
        details["attempted"] = True

        try:
            rescued_intent, ai_details = await self.interpreter._interpret_with_ai(
                query,
                history=history,
                context=rescue_context,
                inventory=graph.inventory_summary(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            details["reason"] = str(exc).strip() or type(exc).__name__
            details["ai_error"] = details["reason"]
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        details["ai"] = dict(ai_details)
        if rescued_intent is None:
            details["reason"] = "The local model did not return a supported control intent."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details
        if rescued_intent.response_dict() == original_plan.intent.response_dict():
            details["reason"] = "The local model repeated the failed deterministic intent."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        rescued_plan = self._resolve_plan(
            query,
            rescued_intent,
            {**dict(ai_details), "rescue_mode": True},
            graph,
            graph_context,
        )
        original_quality = self._plan_quality(original_plan)
        rescued_quality = self._plan_quality(rescued_plan)
        details["rescued_intent"] = rescued_intent.response_dict()
        details["rescued_plan_quality"] = rescued_quality

        if not self._is_better_plan(original_quality, rescued_quality):
            details["reason"] = "The rescued interpretation did not improve safe device resolution."
            original_plan.diagnostics["ai_rescue"] = details
            return original_plan, details

        details["accepted"] = True
        details["reason"] = "Local AI produced a safer, better-resolved structured plan."
        rescued_plan.diagnostics["ai_rescue"] = details
        return rescued_plan, details

    @staticmethod
    def _plan_quality(plan: ControlPlan) -> dict[str, int]:
        unresolved = sum(1 for item in plan.actions if not item.nodes)
        resolved_actions = len(plan.actions) - unresolved
        resolved_devices = len(plan.nodes)
        candidates = sum(len(item.candidates) for item in plan.actions if not item.nodes)
        return {
            "unresolved_actions": unresolved,
            "resolved_actions": resolved_actions,
            "resolved_devices": resolved_devices,
            "unresolved_candidates": candidates,
        }

    @staticmethod
    def _is_better_plan(original: dict[str, int], rescued: dict[str, int]) -> bool:
        if rescued["unresolved_actions"] < original["unresolved_actions"]:
            return rescued["resolved_devices"] > 0
        if rescued["unresolved_actions"] > original["unresolved_actions"]:
            return False
        if rescued["resolved_actions"] > original["resolved_actions"]:
            return True
        if (
            rescued["unresolved_actions"] > 0
            and rescued["unresolved_candidates"] > 0
            and (
                original["unresolved_candidates"] == 0
                or rescued["unresolved_candidates"] < original["unresolved_candidates"]
            )
        ):
            return True
        return False

    @staticmethod
    def _decorate_rescue(
        answer: dict[str, Any],
        rescue: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not rescue:
            return answer
        enriched = dict(answer)
        enriched["control_ai_rescue"] = rescue
        if rescue.get("accepted"):
            enriched["control_rescue_used"] = True
        existing = str(enriched.get("technical") or "").strip()
        rescue_debug = safe_debug({"control_ai_rescue": rescue})
        enriched["technical"] = (
            f"{existing}\n\nAI rescue\n{rescue_debug}" if existing else rescue_debug
        )
        return enriched

def install_control_agent(
    application: Any,
    device_index: Any,
    fallback: Any,
    **kwargs: Any,
) -> RescueControlAgent:
    original_ask: AskHandler = application.ask
    agent = RescueControlAgent(application, device_index, fallback, **kwargs)

    async def ask_with_control_agent(request: Any) -> dict[str, Any]:
        if not application.option_bool("control_agent_enabled", True):
            return await original_ask(request)
        return await agent.answer(request, original_ask)

    application.ask = ask_with_control_agent
    return agent

__all__ = [
    "AskHandler",
    "ControlContextStore",
    "ControlPlan",
    "ControlSessionContext",
    "FastVerifiedControlAgent",
    "HomeBrainControlAgent",
    "LearnedAliasStore",
    "PendingControl",
    "PendingControlStore",
    "RescueControlAgent",
    "ResolvedControlAction",
    "install_base_control_agent",
    "install_control_agent",
    "install_verified_control_agent",
]
