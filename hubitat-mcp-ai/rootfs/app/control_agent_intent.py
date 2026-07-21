from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from control_language import canonicalise_basic_control
from contextual_control import parse_contextual_device_control


_SUPPORTED_COMMANDS = {"on", "off", "set_level"}
_SUPPORTED_QUANTIFIERS = {"one", "all"}
_SUPPORTED_REFERENCES = {"none", "last", "scope", "other", "both"}

_CONTROL_INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["device_control", "unsupported"]},
        "actions": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "enum": sorted(_SUPPORTED_COMMANDS)},
                    "value": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                    "target": {
                        "type": "object",
                        "properties": {
                            "name_hint": {"type": "string", "maxLength": 120},
                            "room_hint": {"type": "string", "maxLength": 80},
                            "device_type": {"type": "string", "maxLength": 50},
                            "ordinal": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                            "quantifier": {
                                "type": "string",
                                "enum": sorted(_SUPPORTED_QUANTIFIERS),
                            },
                            "reference": {
                                "type": "string",
                                "enum": sorted(_SUPPORTED_REFERENCES),
                            },
                            "exclusions": {
                                "type": "array",
                                "items": {"type": "string", "maxLength": 100},
                                "maxItems": 8,
                            },
                        },
                        "required": [
                            "name_hint",
                            "room_hint",
                            "device_type",
                            "ordinal",
                            "quantifier",
                            "reference",
                            "exclusions",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["command", "value", "target"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["intent", "actions", "confidence"],
    "additionalProperties": False,
}

_CONTROL_VERBS = re.compile(
    r"\b(?:turn|switch|toggle|set|dim|brighten|make|kill|shut|activate|deactivate|power)\b",
    re.IGNORECASE,
)
_LEVEL_RE = re.compile(
    r"^(?:please\s+)?(?:set|dim|make)\s+(?:the\s+)?(.+?)\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)
_COMPLEX_TARGET_WORDS = {
    "all",
    "every",
    "except",
    "other",
    "both",
    "them",
    "it",
    "that",
    "those",
    "these",
    "same",
    "back",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
}


@dataclass(frozen=True, slots=True)
class ControlTargetIntent:
    name_hint: str = ""
    room_hint: str = ""
    device_type: str = ""
    ordinal: int | None = None
    quantifier: str = "one"
    reference: str = "none"
    exclusions: tuple[str, ...] = ()

    def response_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["exclusions"] = list(self.exclusions)
        return value


@dataclass(frozen=True, slots=True)
class ControlActionIntent:
    command: str
    value: float | None
    target: ControlTargetIntent

    def response_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "value": self.value,
            "target": self.target.response_dict(),
        }


@dataclass(frozen=True, slots=True)
class ControlIntent:
    intent: str
    actions: tuple[ControlActionIntent, ...]
    confidence: float
    interpreter: str
    model: str | None = None

    def response_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "actions": [item.response_dict() for item in self.actions],
            "confidence": self.confidence,
            "interpreter": self.interpreter,
            "model": self.model,
        }


def is_control_candidate(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    if canonicalise_basic_control(text) is not None or _LEVEL_RE.match(text):
        return True
    if _CONTROL_VERBS.search(text) and any(
        term in text
        for term in (" on", " off", " light", " lamp", " fan", " switch", " socket", " tv", " it", " them", " one")
    ):
        return True
    return text in {
        "turn it back on",
        "turn it back off",
        "the other one",
        "both of them",
        "switch them off",
        "switch them on",
    }


class ControlIntentInterpreter:
    """Interpret controls into a strict schema without giving the model MCP tools."""

    def __init__(self, application: Any, *, timeout_seconds: float = 5.0) -> None:
        self.application = application
        self.timeout_seconds = max(1.0, min(15.0, float(timeout_seconds)))

    async def interpret(
        self,
        query: str,
        *,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
        inventory: str = "",
    ) -> tuple[ControlIntent | None, dict[str, Any]]:
        deterministic = self._deterministic_intent(query)
        if deterministic is not None:
            return deterministic, {
                "interpreter": "deterministic-control-parser",
                "ai_used": False,
            }

        diagnostics: dict[str, Any] = {
            "interpreter": "local-ollama-control-intent",
            "ai_used": False,
        }
        if not is_control_candidate(query):
            return None, diagnostics
        if not self.application.option_bool("ollama_enabled", True):
            return None, diagnostics

        try:
            intent, details = await self._interpret_with_ai(
                query,
                history=list(history or [])[-4:],
                context=dict(context or {}),
                inventory=inventory,
            )
            diagnostics.update(details)
            return intent, diagnostics
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            diagnostics["ai_error"] = str(exc).strip() or type(exc).__name__
            return None, diagnostics

    @staticmethod
    def _deterministic_intent(query: str) -> ControlIntent | None:
        contextual = parse_contextual_device_control(query)
        if contextual is not None:
            action, spoken_target = contextual
            normal = " ".join(spoken_target.lower().strip(" .!?").split())
            if normal in {"it", "that", "this", "them", "those", "these", "all of them"}:
                return ControlIntent(
                    intent="device_control",
                    actions=(
                        ControlActionIntent(
                            command=action,
                            value=None,
                            target=ControlTargetIntent(reference="scope"),
                        ),
                    ),
                    confidence=1.0,
                    interpreter="deterministic-control-context-parser",
                )

        basic = canonicalise_basic_control(query)
        if basic is not None:
            words = set(re.findall(r"[a-z0-9]+", basic.target.lower()))
            if not words.intersection(_COMPLEX_TARGET_WORDS) and not any(
                term in f" {basic.target.lower()} "
                for term in (" if ", " unless ", " when ", " before ", " after ")
            ):
                return ControlIntent(
                    intent="device_control",
                    actions=(
                        ControlActionIntent(
                            command=basic.action,
                            value=None,
                            target=ControlTargetIntent(name_hint=basic.target),
                        ),
                    ),
                    confidence=1.0,
                    interpreter="deterministic-control-parser",
                )

        match = _LEVEL_RE.match(str(query or "").strip())
        if not match:
            return None
        target = match.group(1).strip()
        words = set(re.findall(r"[a-z0-9]+", target.lower()))
        if words.intersection(_COMPLEX_TARGET_WORDS):
            return None
        value = max(0.0, min(100.0, float(match.group(2))))
        return ControlIntent(
            intent="device_control",
            actions=(
                ControlActionIntent(
                    command="set_level",
                    value=value,
                    target=ControlTargetIntent(name_hint=target),
                ),
            ),
            confidence=0.98,
            interpreter="deterministic-control-parser",
        )

    async def _interpret_with_ai(
        self,
        query: str,
        *,
        history: list[dict[str, str]],
        context: dict[str, Any],
        inventory: str,
    ) -> tuple[ControlIntent | None, dict[str, Any]]:
        agent = self.application.ollama
        client = getattr(agent, "_http", None)
        post = getattr(client, "post", None)
        if not callable(post):
            raise RuntimeError("Ollama HTTP client is unavailable")

        model = str(
            getattr(agent, "planner_model", "")
            or getattr(agent, "local_fallback_model", "")
            or getattr(agent, "model", "")
        ).strip()
        if not model:
            raise RuntimeError("No local control-intent model is configured")

        recent = "\n".join(
            f"{str(item.get('role') or '')}: {str(item.get('content') or '')[:240]}"
            for item in history[-4:]
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ) or "None"
        context_text = json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:1200]
        inventory_text = inventory[:5000] or "No inventory summary supplied."
        system = (
            "/no_think\n"
            "You are the read-free intent interpreter for a smart-home control agent. "
            "You cannot call tools and must never claim that a command succeeded. Convert only "
            "device controls into the supplied JSON schema. Supported commands are on, off and "
            "set_level (0-100). Resolve language semantically into room_hint, device_type, ordinal, "
            "quantifier and reference, but do not invent a device ID. Use reference scope for it/that/them "
            "when referring to the complete last successful control, last for one device, other for the "
            "other one, and both for an explicitly offered pair when conversation context supports it. "
            "Use quantifier all for room/group controls and put exception names in exclusions. Return "
            "unsupported for conditions, schedules, rule creation, locks, alarms, doors, heating changes, "
            "or anything outside these commands. Interpret lounge as Living Room when that room exists. "
            "Return JSON only."
        )
        user = (
            f"Selected device inventory (label | room | inferred types):\n{inventory_text}\n\n"
            f"Structured recent context:\n{context_text}\n\n"
            f"Recent conversation:\n{recent}\n\nCurrent request:\n{query.strip()}"
        )
        response = await post(
            f"{str(agent.base_url).rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "think": False,
                "format": _CONTROL_INTENT_SCHEMA,
                "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                "options": {
                    "num_ctx": 2048,
                    "num_predict": 260,
                    "temperature": 0,
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Ollama returned a non-object control intent")
        if str(body.get("done_reason") or "").lower() == "length":
            raise RuntimeError("Control intent response was truncated")
        content = str((body.get("message") or {}).get("content") or "").strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
        intent = self.validate_payload(json.loads(content), model=model)
        return intent, {
            "ai_used": True,
            "ai_model": model,
            "ai_provider": "Local Ollama control interpreter",
            "ai_success": intent is not None,
        }

    @staticmethod
    def validate_payload(value: Any, *, model: str | None = None) -> ControlIntent | None:
        if not isinstance(value, dict) or value.get("intent") != "device_control":
            return None
        raw_actions = value.get("actions")
        if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= 4:
            return None

        actions: list[ControlActionIntent] = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                return None
            command = str(raw.get("command") or "").strip().lower()
            if command not in _SUPPORTED_COMMANDS:
                return None
            raw_target = raw.get("target")
            if not isinstance(raw_target, dict):
                return None
            quantifier = str(raw_target.get("quantifier") or "one").strip().lower()
            reference = str(raw_target.get("reference") or "none").strip().lower()
            if quantifier not in _SUPPORTED_QUANTIFIERS or reference not in _SUPPORTED_REFERENCES:
                return None
            ordinal_raw = raw_target.get("ordinal")
            ordinal: int | None = None
            if ordinal_raw not in (None, ""):
                try:
                    ordinal = max(1, min(20, int(ordinal_raw)))
                except Exception:
                    return None
            exclusions_raw = raw_target.get("exclusions") or []
            if not isinstance(exclusions_raw, list):
                return None
            exclusions = tuple(
                dict.fromkeys(
                    str(item).strip()[:100]
                    for item in exclusions_raw[:8]
                    if str(item).strip()
                )
            )
            value_raw = raw.get("value")
            command_value: float | None = None
            if command == "set_level":
                try:
                    command_value = max(0.0, min(100.0, float(value_raw)))
                except Exception:
                    return None
            actions.append(
                ControlActionIntent(
                    command=command,
                    value=command_value,
                    target=ControlTargetIntent(
                        name_hint=str(raw_target.get("name_hint") or "").strip()[:120],
                        room_hint=str(raw_target.get("room_hint") or "").strip()[:80],
                        device_type=str(raw_target.get("device_type") or "").strip()[:50].lower(),
                        ordinal=ordinal,
                        quantifier=quantifier,
                        reference=reference,
                        exclusions=exclusions,
                    ),
                )
            )
        try:
            confidence = max(0.0, min(1.0, float(value.get("confidence") or 0.0)))
        except Exception:
            confidence = 0.0
        return ControlIntent(
            intent="device_control",
            actions=tuple(actions),
            confidence=confidence,
            interpreter="local-ollama-control-intent",
            model=model,
        )


__all__ = [
    "ControlActionIntent",
    "ControlIntent",
    "ControlIntentInterpreter",
    "ControlTargetIntent",
    "is_control_candidate",
]
