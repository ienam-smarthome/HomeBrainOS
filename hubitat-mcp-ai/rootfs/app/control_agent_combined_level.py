from __future__ import annotations

import json
import re
import sys
from typing import Any, Callable

import control_agent_gate
import control_agent_intent
import control_agent_rescue
import request_tracing
import routing_policy
from control_agent_graph import install_control_graph_capability_filter
from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
)
from control_agent_rescue import RescueControlAgent
from presenter import display_payload, safe_debug


# Preserve the old module-object patch points after flattening the interpretation
# helpers into this owner.
control_agent_claude_first = sys.modules[__name__]
claude = control_agent_claude_first

# Claude First

_CONTROL_NOUNS = re.compile(
    r"\b(?:light|lights|lamp|lamps|bulb|bulbs|fan|fans|switch|switches|"
    r"socket|sockets|plug|plugs|outlet|outlets|tv|television|dehumidifier|"
    r"purifier|robot|roborock)\b",
    re.IGNORECASE,
)

_CONTROL_ACTIONS = re.compile(
    r"\b(?:turn|switch|set|put|make|bring|dim|brighten|lower|raise|increase|"
    r"decrease|reduce|kill|shut|power|activate|deactivate|start|stop)\b",
    re.IGNORECASE,
)

_READ_PREFIX = re.compile(
    r"^(?:what|which|who|where|when|why|how|is|are|was|were|show|list|tell|"
    r"compare|explain|check)\b",
    re.IGNORECASE,
)

_LEVEL_CUE = re.compile(
    r"(?:\d{1,3}\s*%|\bpercent\b|\bper\s+cent\b|\bbrightness\b|"
    r"\bhalf\b|\bquarter\b|\bfull\s+brightness\b)",
    re.IGNORECASE,
)

_NATURAL_LEVEL = re.compile(
    r"^(?:please\s+)?(?P<verb>put|set|make|bring|dim)\s+(?:the\s+)?"
    r"(?P<target>.+?)\s+(?:(?:down|up)\s+)?(?:to|at)\s+"
    r"(?P<approx>(?:about|around|roughly|approximately)\s+)?"
    r"(?P<value>[a-z0-9\-\s]+?)\s*(?:%|percent|per\s+cent|brightness)?[.!?]*$",
    re.IGNORECASE,
)

_NATURAL_LEVEL_BARE = re.compile(
    r"^(?:please\s+)?(?P<verb>put|set|make|dim)\s+(?:the\s+)?(?P<target>.+?)\s+"
    r"(?P<approx>(?:about|around|roughly|approximately)\s+)?"
    r"(?P<value>\d{1,3})\s*%[.!?]*$",
    re.IGNORECASE,
)

_ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_SPECIAL_LEVELS = {
    "quarter": 25,
    "a quarter": 25,
    "one quarter": 25,
    "half": 50,
    "a half": 50,
    "three quarters": 75,
    "three quarter": 75,
    "full": 100,
    "full brightness": 100,
    "maximum": 100,
    "max": 100,
    "off": 0,
}

_TRAILING_RELATIVE = re.compile(r"\b(?:dimmer|brighter|lower|higher|more|less)\b", re.I)

def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def percentage_value(value: str) -> int | None:
    text = _normalise(value).strip(" .!?%")
    text = re.sub(r"\b(?:percent|per\s+cent|brightness)\b", "", text).strip()
    if text in _SPECIAL_LEVELS:
        return _SPECIAL_LEVELS[text]
    if re.fullmatch(r"\d{1,3}", text):
        number = int(text)
        return number if 0 <= number <= 100 else None

    tokens = [item for item in re.split(r"[\s-]+", text) if item and item != "and"]
    if not tokens:
        return None
    current = 0
    for token in tokens:
        if token in _ONES:
            current += _ONES[token]
        elif token in _TENS:
            current += _TENS[token]
        elif token == "hundred":
            current = max(1, current) * 100
        else:
            return None
    return current if 0 <= current <= 100 else None

def is_probable_control_request(query: str) -> bool:
    """Recognise probable natural controls before the read-only router.

    The function does not resolve or execute anything. Questions with a read prefix
    remain on read routes; supported controls must still pass the strict schema,
    selected-device resolution, safety policy and final-state verification.
    """

    text = _normalise(query).strip(" .!?")
    if not text or _READ_PREFIX.match(text):
        return False
    if not _CONTROL_NOUNS.search(text):
        return False
    if _CONTROL_ACTIONS.search(text):
        return True
    return bool(_LEVEL_CUE.search(text) and re.search(r"\b(?:at|to|on|off)\b", text))

def parse_natural_level(query: str) -> ControlIntent | None:
    text = str(query or "").strip()
    match = _NATURAL_LEVEL.match(text) or _NATURAL_LEVEL_BARE.match(text)
    if not match:
        return None
    target = re.sub(r"\s+", " ", match.group("target").strip(" .!?"))
    raw_value = match.group("value")
    verb = str(match.group("verb") or "").lower()
    approximate = bool(match.groupdict().get("approx"))
    if not target or _TRAILING_RELATIVE.search(raw_value):
        return None

    # Preserve the proven exact numeric grammar for ordinary set/dim/make commands.
    # This parser owns natural verbs, approximation, spoken numbers and brightness
    # fractions that the older deterministic grammar cannot represent.
    if (
        verb in {"set", "dim", "make"}
        and not approximate
        and re.fullmatch(r"\d{1,3}", raw_value.strip())
    ):
        return None

    value = percentage_value(raw_value)
    if value is None:
        return None
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command="set_level",
                value=float(value),
                target=ControlTargetIntent(name_hint=target),
            ),
        ),
        confidence=0.99,
        interpreter="deterministic-natural-control-parser",
    )

def _model_candidates(interpreter: ControlIntentInterpreter) -> list[tuple[str, str, float]]:
    application = interpreter.application
    agent = application.ollama
    local = str(
        getattr(agent, "planner_model", "")
        or getattr(agent, "local_fallback_model", "")
        or getattr(agent, "model", "")
    ).strip()
    cloud = str(getattr(agent, "cloud_model", "") or "").strip()
    values: list[tuple[str, str, float]] = []
    if local:
        values.append((local, "Local Ollama structured control interpreter", interpreter.timeout_seconds))
    if (
        application.option_bool("control_agent_cloud_fallback_enabled", True)
        and bool(getattr(agent, "cloud_enabled", False))
        and cloud
        and cloud != local
    ):
        options = getattr(application, "OPTIONS", {})
        options = options if isinstance(options, dict) else {}
        timeout = float(
            options.get("control_agent_cloud_timeout_seconds")
            or options.get("ollama_cloud_timeout_seconds")
            or 12
        )
        values.append((cloud, "Ollama Cloud structured control interpreter", max(5.0, timeout)))
    return values

async def _interpret_with_model(
    interpreter: ControlIntentInterpreter,
    model: str,
    provider: str,
    timeout: float,
    query: str,
    *,
    history: list[dict[str, str]],
    context: dict[str, Any],
    inventory: str,
) -> tuple[ControlIntent | None, dict[str, Any]]:
    agent = interpreter.application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    if not callable(post):
        raise RuntimeError("Ollama HTTP client is unavailable")

    recent = "\n".join(
        f"{str(item.get('role') or '')}: {str(item.get('content') or '')[:240]}"
        for item in history[-4:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ) or "None"
    context_text = json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:1600]
    inventory_text = inventory[:7000] or "No selected-device inventory supplied."
    system = (
        "/no_think\n"
        "Act like a careful MCP smart-home control planner. First understand the user's "
        "natural instruction, then match it against the supplied selected-device inventory. "
        "You have no tools and cannot execute anything. Return only the strict JSON schema. "
        "Supported commands are on, off and set_level from 0 to 100. Convert spoken numbers "
        "and approximate wording such as about thirty percent into a numeric level. Put semantic "
        "room, type, ordinal, quantifier and reference information in dedicated fields. Never "
        "invent a device ID or claim success. Return unsupported for schedules, conditions, locks, "
        "alarms, doors, heating changes, rule changes or anything outside supported commands."
    )
    user = (
        f"Selected devices (label | room | types):\n{inventory_text}\n\n"
        f"Structured context:\n{context_text}\n\nRecent conversation:\n{recent}\n\n"
        f"Current request:\n{query.strip()}"
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
            "format": control_agent_intent._CONTROL_INTENT_SCHEMA,
            "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
            "options": {
                "num_ctx": 3072,
                "num_predict": 280,
                "temperature": 0,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{provider} returned a non-object control intent")
    content = str((body.get("message") or {}).get("content") or "").strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
    payload = json.loads(content)
    intent = interpreter.validate_payload(payload, model=model)
    return intent, {
        "ai_used": True,
        "ai_model": model,
        "ai_provider": provider,
        "ai_success": intent is not None,
        "raw_intent": str(payload.get("intent") or "") if isinstance(payload, dict) else "",
    }

def install_claude_first_control_interpreter() -> None:
    """Install agent-first triage and strong structured-model fallback.

    Clear deterministic controls still avoid AI. Other probable controls reach the
    inventory-aware Control Agent before any read-only or general answer route. The
    model never receives MCP command tools; deterministic Python remains responsible
    for device IDs, policy, execution and verification.
    """

    if getattr(ControlIntentInterpreter, "_claude_first_installed", False):
        return

    original_candidate = control_agent_intent.is_control_candidate
    original_deterministic: Callable[[str], ControlIntent | None] = (
        ControlIntentInterpreter._deterministic_intent
    )

    def combined_candidate(query: str) -> bool:
        return bool(original_candidate(query) or is_probable_control_request(query))

    def deterministic_first(query: str) -> ControlIntent | None:
        natural = parse_natural_level(query)
        return natural if natural is not None else original_deterministic(query)

    async def model_chain(
        self: ControlIntentInterpreter,
        query: str,
        *,
        history: list[dict[str, str]],
        context: dict[str, Any],
        inventory: str,
    ) -> tuple[ControlIntent | None, dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        for model, provider, timeout in _model_candidates(self):
            try:
                intent, details = await _interpret_with_model(
                    self,
                    model,
                    provider,
                    timeout,
                    query,
                    history=history,
                    context=context,
                    inventory=inventory,
                )
                attempts.append({**details, "error": None})
                if intent is not None:
                    return intent, {**details, "model_attempts": attempts}
                if details.get("raw_intent") == "unsupported":
                    return None, {**details, "model_attempts": attempts, "unsupported": True}
            except Exception as exc:
                attempts.append(
                    {
                        "ai_used": True,
                        "ai_model": model,
                        "ai_provider": provider,
                        "ai_success": False,
                        "error": str(exc).strip() or type(exc).__name__,
                    }
                )
        last_error = next(
            (str(item.get("error")) for item in reversed(attempts) if item.get("error")),
            "No configured control model produced a valid structured intent.",
        )
        raise RuntimeError(last_error)

    control_agent_intent.is_control_candidate = combined_candidate
    control_agent_gate.is_control_candidate = combined_candidate
    control_agent_rescue.is_control_candidate = combined_candidate
    ControlIntentInterpreter._deterministic_intent = staticmethod(deterministic_first)
    ControlIntentInterpreter._interpret_with_ai = model_chain

    original_trace_classify = request_tracing.classify_query

    def trace_classify(query: str) -> routing_policy.RouteDecision:
        if is_probable_control_request(query):
            return routing_policy.RouteDecision(
                "control-agent",
                "probable natural device control; inventory-aware structured interpretation runs before read-only routing",
            )
        return original_trace_classify(query)

    request_tracing.classify_query = trace_classify
    ControlIntentInterpreter._claude_first_installed = True

# Goal Based

_GOAL = re.compile(
    r"\b(?:comfortable|cosy|cozy|relax(?:ed|ing)?|watch(?:ing)?\s+(?:the\s+)?tv|"
    r"movie|cinema|reading|studying|working|cleaning|night\s*light|bedtime|"
    r"ambient|mood|soft|gentle)\b",
    re.I,
)

_LIGHT = re.compile(r"\b(?:light|lights|lamp|lamps|bulb|bulbs|dimmer)\b", re.I)

_EXPLICIT = re.compile(r"(?:\d{1,3}\s*%|\b(?:half|quarter|full|thirty|forty|fifty|sixty|seventy|eighty)\b\s*(?:percent|brightness)?)", re.I)

def is_goal_based_control(query: str) -> bool:
    text = " ".join(str(query or "").strip().split())
    return bool(
        text
        and claude.is_probable_control_request(text)
        and _LIGHT.search(text)
        and _GOAL.search(text)
        and not _EXPLICIT.search(text)
    )

def _goal_text(query: str) -> str:
    match = _GOAL.search(str(query or ""))
    return str(match.group(0) if match else "subjective lighting goal")[:120]

async def _interpret_goal(
    interpreter: ControlIntentInterpreter,
    model: str,
    provider: str,
    timeout: float,
    query: str,
    *,
    history: list[dict[str, str]],
    context: dict[str, Any],
    inventory: str,
) -> tuple[ControlIntent | None, dict[str, Any]]:
    agent = interpreter.application.ollama
    post = getattr(getattr(agent, "_http", None), "post", None)
    if not callable(post):
        raise RuntimeError("Ollama HTTP client is unavailable")

    system = (
        "/no_think\nYou are a careful smart-home lighting preference planner. The user gave a "
        "subjective lighting goal instead of a percentage. You have no tools and cannot execute. "
        "Match only selected lights/lamps from the inventory and return the strict JSON schema. "
        "Translate the goal into one conservative set_level value. Starting points: TV/movie 30, "
        "relaxing/ambient 35, generic comfortable 40, reading/studying 70, cleaning 85, bedtime/night "
        "15. Use confidence 0.60-0.78 so confirmation is required. Put room, type and ordinal in their "
        "dedicated fields. Never invent IDs, capabilities or success. Return unsupported for non-lights, "
        "unknown targets, colour requests or unsupported capabilities. JSON only."
    )
    recent = "\n".join(
        f"{item.get('role')}: {str(item.get('content') or '')[:200]}"
        for item in history[-4:]
        if item.get("content")
    ) or "None"
    user = (
        f"Selected devices:\n{inventory[:7000]}\n\nContext:\n"
        f"{json.dumps(context, ensure_ascii=False)[:1400]}\n\nRecent:\n{recent}\n\nRequest:\n{query}"
    )
    response = await post(
        f"{str(agent.base_url).rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "format": control_agent_intent._CONTROL_INTENT_SCHEMA,
            "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
            "options": {"num_ctx": 3072, "num_predict": 280, "temperature": 0},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    content = str((body.get("message") or {}).get("content") or "").strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
    payload = json.loads(content)
    intent = interpreter.validate_payload(payload, model=model)
    if intent is not None:
        if not intent.actions or any(a.command != "set_level" or a.value is None for a in intent.actions):
            intent = None
        else:
            intent = ControlIntent(
                intent=intent.intent,
                actions=intent.actions,
                confidence=min(0.78, max(0.60, float(intent.confidence))),
                interpreter="goal-based-ai-control-intent",
                model=intent.model,
            )
    proposed = intent.actions[0].value if intent and intent.actions else None
    return intent, {
        "ai_used": True,
        "ai_model": model,
        "ai_provider": provider,
        "ai_success": intent is not None,
        "raw_intent": str(payload.get("intent") or ""),
        "goal_based": True,
        "goal_text": _goal_text(query),
        "proposed_level": proposed,
    }

def _failed_response(query: str) -> dict[str, Any]:
    return {
        "success": False,
        "route": "control-agent",
        "intent": "control-agent-goal-needs-level",
        "message": "I understood the lighting goal, but I could not safely choose a brightness. Tell me a percentage, for example: Set Livingroom Light 1 to 30%.",
        "confirmation_required": False,
        "display": display_payload(
            "control-agent-goal-needs-level",
            "Choose a brightness",
            subtitle="No command has been sent",
            metrics=[{"label": "Request", "value": "Lighting goal", "icon": "🧠"}],
            note="The request stayed in Control Agent and was not passed to the general answer agent.",
        ),
        "technical": safe_debug({"goal_based": True, "query": query, "reason": "No safe structured set_level proposal."}),
        "answered_by": "HomeBrain goal-based control safety fallback",
        "model": None,
    }

def install_goal_based_control() -> None:
    if getattr(ControlIntentInterpreter, "_goal_based_control_installed", False):
        return

    original_ai = ControlIntentInterpreter._interpret_with_ai

    async def goal_ai(self: ControlIntentInterpreter, query: str, *, history: list[dict[str, str]], context: dict[str, Any], inventory: str):
        if not is_goal_based_control(query):
            return await original_ai(self, query, history=history, context=context, inventory=inventory)
        candidates = list(claude._model_candidates(self))
        if self.application.option_bool("control_agent_goal_prefer_cloud", True):
            candidates.sort(key=lambda item: 0 if "Cloud" in item[1] else 1)
        attempts: list[dict[str, Any]] = []
        for model, provider, timeout in candidates:
            try:
                intent, details = await _interpret_goal(
                    self, model, provider, timeout, query,
                    history=history, context=context, inventory=inventory,
                )
                attempts.append({**details, "error": None})
                if intent is not None:
                    return intent, {**details, "model_attempts": attempts}
            except Exception as exc:
                attempts.append({"ai_model": model, "ai_provider": provider, "ai_success": False, "error": str(exc).strip() or type(exc).__name__})
        return None, {"ai_used": bool(attempts), "ai_success": False, "goal_based": True, "goal_text": _goal_text(query), "model_attempts": attempts}

    ControlIntentInterpreter._interpret_with_ai = goal_ai

    original_answer = RescueControlAgent.answer

    async def goal_answer(self: RescueControlAgent, request: Any, original_ask: Any):
        query = str(getattr(request, "query", "") or "").strip()
        if not is_goal_based_control(query):
            return await original_answer(self, request, original_ask)
        async def safe_fallback(_request: Any):
            return _failed_response(query)
        return await original_answer(self, request, safe_fallback)

    RescueControlAgent.answer = goal_answer

    original_confirmation = RescueControlAgent._confirmation_response

    def goal_confirmation(self: RescueControlAgent, plan: Any, policy: dict[str, Any]):
        answer = original_confirmation(self, plan, policy)
        if not plan.diagnostics.get("goal_based"):
            return answer
        proposed = plan.diagnostics.get("proposed_level")
        if proposed is None and plan.actions:
            proposed = plan.actions[0].intent.value
        shown = f"{float(proposed):g}%" if proposed is not None else "the proposed level"
        devices = ", ".join(node.label for node in plan.nodes) or "the selected light"
        goal = str(plan.diagnostics.get("goal_text") or "your lighting goal")
        answer["message"] = f"I interpreted ‘{goal}’ as {shown} for {devices}. No command has been sent. Reply Yes to apply it or No to cancel."
        answer["display"] = display_payload(
            "control-agent-goal-confirmation",
            "Confirm AI lighting choice",
            subtitle="No command has been sent",
            metrics=[
                {"label": "Proposed level", "value": shown, "icon": "💡"},
                {"label": "AI confidence", "value": f"{plan.confidence * 100:.0f}%", "icon": "🧠"},
            ],
            items=[{"icon": "💡", "title": node.label, "value": shown, "subtitle": node.room or "No room"} for node in plan.nodes],
            note="This is an AI-proposed starting point for a subjective preference. Confirm before applying it.",
        )
        answer["answered_by"] = "AI lighting preference plan + deterministic Hubitat confirmation"
        answer["ai_provider"] = plan.diagnostics.get("ai_provider")
        answer["technical"] += "\n\nGoal-based AI plan\n" + safe_debug({"goal": goal, "proposed_level": proposed, "model": plan.intent.model, "confirmation_required": True})
        return answer

    RescueControlAgent._confirmation_response = goal_confirmation
    ControlIntentInterpreter._goal_based_control_installed = True

# Semantic Target

_NUMBER_WORDS = {
    "one": 1,
    "first": 1,
    "two": 2,
    "second": 2,
    "three": 3,
    "third": 3,
    "four": 4,
    "fourth": 4,
    "five": 5,
    "fifth": 5,
    "six": 6,
    "sixth": 6,
    "seven": 7,
    "seventh": 7,
    "eight": 8,
    "eighth": 8,
    "nine": 9,
    "ninth": 9,
    "ten": 10,
    "tenth": 10,
}

_NUMBER_PATTERN = (
    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2}(?:st|nd|rd|th)?)"
)

_TYPE_PATTERN = (
    r"(?:lights?|lamps?|bulbs?|dimmers?|fans?|switches?|sockets?|outlets?|plugs?|"
    r"dehumidifiers?|humidifiers?|televisions?|tvs?)"
)

_ORDINAL_BEFORE_TYPE = re.compile(
    rf"^(?P<room>.+?)\s+(?P<number>{_NUMBER_PATTERN})\s+(?P<type>{_TYPE_PATTERN})$",
    re.IGNORECASE,
)

_TYPE_BEFORE_ORDINAL = re.compile(
    rf"^(?P<room>.+?)\s+(?P<type>{_TYPE_PATTERN})\s+(?P<number>{_NUMBER_PATTERN})$",
    re.IGNORECASE,
)

_ORDINAL_PREFIX = re.compile(
    rf"^(?P<number>{_NUMBER_PATTERN})\s+(?P<room>.+?)\s+(?P<type>{_TYPE_PATTERN})$",
    re.IGNORECASE,
)

_TYPE_MAP = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "bulb": "light",
    "bulbs": "light",
    "dimmer": "light",
    "dimmers": "light",
    "fan": "fan",
    "fans": "fan",
    "switch": "switch",
    "switches": "switch",
    "socket": "outlet",
    "sockets": "outlet",
    "outlet": "outlet",
    "outlets": "outlet",
    "plug": "outlet",
    "plugs": "outlet",
    "dehumidifier": "dehumidifier",
    "dehumidifiers": "dehumidifier",
    "humidifier": "humidifier",
    "humidifiers": "humidifier",
    "television": "tv",
    "televisions": "tv",
    "tv": "tv",
    "tvs": "tv",
}

_TYPE_LABEL = {
    "light": "Light",
    "fan": "Fan",
    "switch": "Switch",
    "outlet": "Socket",
    "dehumidifier": "Dehumidifier",
    "humidifier": "Humidifier",
    "tv": "TV",
}

_ROOM_ALIASES = {
    "living room": "Living Room",
    "livingroom": "Living Room",
    "lounge": "Living Room",
    "bath room": "Bathroom",
    "bathroom": "Bathroom",
    "hall way": "Hallway",
    "hallway": "Hallway",
    "toilet": "Toilet",
    "kitchen": "Kitchen",
}

def _semantic_normalise(value: str) -> str:
    text = re.sub(r"[-_/]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip(" .!?")

def _semantic_number(value: str) -> int | None:
    text = _semantic_normalise(value).lower()
    if text in _NUMBER_WORDS:
        return _NUMBER_WORDS[text]
    match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", text)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 20 else None

def _semantic_room(value: str) -> str:
    text = _semantic_normalise(value)
    alias = _ROOM_ALIASES.get(text.lower())
    if alias:
        return alias
    return " ".join(part.capitalize() for part in text.split())

def decompose_natural_target(value: str) -> ControlTargetIntent:
    """Convert spoken room/number/type order into structured target fields.

    Numbered bedrooms are treated as room names because `Bedroom 1 Light` is a
    canonical household label. In non-numbered rooms, the number is an ordinal
    within the room, for example `living room one light` means the first light in
    Living Room.
    """

    target = _semantic_normalise(value)
    if not target:
        return ControlTargetIntent()

    match = (
        _ORDINAL_BEFORE_TYPE.match(target)
        or _TYPE_BEFORE_ORDINAL.match(target)
        or _ORDINAL_PREFIX.match(target)
    )
    if not match:
        return ControlTargetIntent(name_hint=target)

    number = _semantic_number(match.group("number"))
    raw_type = _semantic_normalise(match.group("type")).lower()
    device_type = _TYPE_MAP.get(raw_type, "")
    room_text = _semantic_normalise(match.group("room"))
    if number is None or not device_type or not room_text:
        return ControlTargetIntent(name_hint=target)

    # `bedroom one light` names the numbered room and its canonical light. This
    # remains exact even when Bedroom 3 contains additional lamps.
    if room_text.lower() in {"bedroom", "bed room"}:
        room_hint = f"Bedroom {number}"
        name_hint = f"{room_hint} {_TYPE_LABEL.get(device_type, raw_type.title())}"
        return ControlTargetIntent(
            name_hint=name_hint,
            room_hint=room_hint,
            device_type=device_type,
        )

    return ControlTargetIntent(
        room_hint=_semantic_room(room_text),
        device_type=device_type,
        ordinal=number,
    )

def install_semantic_natural_targets() -> None:
    """Upgrade natural level intents before they reach device resolution."""

    if getattr(control_agent_claude_first, "_semantic_target_installed", False):
        return

    original: Callable[[str], ControlIntent | None] = (
        control_agent_claude_first.parse_natural_level
    )

    def parse_with_semantic_target(query: str) -> ControlIntent | None:
        intent = original(query)
        if intent is None:
            return None

        actions: list[ControlActionIntent] = []
        changed = False
        for action in intent.actions:
            target = action.target
            if action.command == "set_level" and target.name_hint:
                semantic = decompose_natural_target(target.name_hint)
                if semantic != target:
                    target = semantic
                    changed = True
            actions.append(
                ControlActionIntent(
                    command=action.command,
                    value=action.value,
                    target=target,
                )
            )

        if not changed:
            return intent
        return ControlIntent(
            intent=intent.intent,
            actions=tuple(actions),
            confidence=intent.confidence,
            interpreter="deterministic-semantic-control-parser",
            model=intent.model,
        )

    control_agent_claude_first.parse_natural_level = parse_with_semantic_target
    control_agent_claude_first._semantic_target_installed = True

# Combined Level

_TURN_ON_THEN_LEVEL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+on\s+(?:the\s+)?(.+?)\s+"
    r"(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)

_TURN_TARGET_ON_THEN_LEVEL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(?:the\s+)?(.+?)\s+on\s+"
    r"(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)

_ABSOLUTE_LEVEL_WITH_PREPOSITION = re.compile(
    r"^(?:please\s+)?(?:set|dim|make)\s+(?:the\s+)?(.+?)\s+"
    r"(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)

_ABSOLUTE_LEVEL_BARE = re.compile(
    r"^(?:please\s+)?(?:set|dim|make)\s+(?:the\s+)?(.+?)\s+"
    r"(\d{1,3})\s*(?:%|percent)?[.!?]*$",
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

_COMPLEX_TARGET_TERMS = (" if ", " unless ", " when ", " before ", " after ", " and ")

_TRAILING_CONTROL_SYNTAX = re.compile(
    r"\b(?:to|at|percent)\b\s*$",
    re.IGNORECASE,
)

def _safe_unique_target(target: str) -> bool:
    normalised = re.sub(r"\s+", " ", str(target or "").strip(" .!?"))
    if not normalised or _TRAILING_CONTROL_SYNTAX.search(normalised):
        return False
    words = set(re.findall(r"[a-z0-9]+", normalised.lower()))
    if not words or words.intersection(_COMPLEX_TARGET_WORDS):
        return False
    padded = f" {normalised.lower()} "
    return not any(term in padded for term in _COMPLEX_TARGET_TERMS)

def _intent(target: str, value_text: str) -> ControlIntent | None:
    try:
        value = float(value_text)
    except Exception:
        return None
    # Never silently clamp a malformed control request. Out-of-range values must
    # fall through to guarded interpretation and cannot be auto-executed.
    if value < 0 or value > 100 or not _safe_unique_target(target):
        return None
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command="set_level",
                value=value,
                target=ControlTargetIntent(name_hint=target.strip()),
            ),
        ),
        confidence=0.99,
        interpreter="deterministic-control-parser",
    )

def install_combined_level_intent() -> None:
    """Install Control Agent language and actuable-device graph safeguards.

    This must run before ``HomeBrainControlAgent`` is constructed. It restricts
    the graph to devices with live control evidence, installs clean absolute-level
    grammar, then enables inventory-first natural and goal-based control interpretation.
    """

    install_control_graph_capability_filter()
    if not getattr(ControlIntentInterpreter, "_combined_level_installed", False):
        original: Callable[[str], ControlIntent | None] = (
            ControlIntentInterpreter._deterministic_intent
        )

        def deterministic_with_combined_level(query: str) -> ControlIntent | None:
            text = str(query or "").strip()
            for pattern in (_TURN_ON_THEN_LEVEL, _TURN_TARGET_ON_THEN_LEVEL):
                match = pattern.match(text)
                if match:
                    return _intent(match.group(1), match.group(2))

            # Ordered patterns guarantee that `at` and `to` are consumed as grammar,
            # never as part of the selected-device label.
            for pattern in (
                _ABSOLUTE_LEVEL_WITH_PREPOSITION,
                _ABSOLUTE_LEVEL_BARE,
            ):
                match = pattern.match(text)
                if match:
                    return _intent(match.group(1), match.group(2))

            return original(query)

        ControlIntentInterpreter._deterministic_intent = staticmethod(
            deterministic_with_combined_level
        )
        ControlIntentInterpreter._combined_level_installed = True

    # Install after the exact numeric grammar so natural phrasing and model fallback
    # wrap every proven deterministic parser instead of replacing them.
    install_claude_first_control_interpreter()
    install_semantic_natural_targets()
    install_goal_based_control()

__all__ = [
    "decompose_natural_target",
    "install_claude_first_control_interpreter",
    "install_combined_level_intent",
    "install_goal_based_control",
    "install_semantic_natural_targets",
    "is_goal_based_control",
    "is_probable_control_request",
    "parse_natural_level",
    "percentage_value",
]
