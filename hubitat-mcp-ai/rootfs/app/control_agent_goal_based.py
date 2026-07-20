from __future__ import annotations

import json
import re
from typing import Any

import control_agent_claude_first as claude
import control_agent_intent
from control_agent_intent import ControlIntent, ControlIntentInterpreter
from control_agent_rescue import RescueControlAgent
from presenter import display_payload, safe_debug


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


__all__ = ["install_goal_based_control", "is_goal_based_control"]
