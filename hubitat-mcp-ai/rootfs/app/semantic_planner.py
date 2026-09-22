from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from semantic_plan import SemanticPlan, semantic_plan_from_model_text


ChatCallable = Callable[
    [list[dict[str, Any]], list[dict[str, Any]]],
    Awaitable[dict[str, Any]],
]


_CONTROL_CANDIDATE = re.compile(
    r"\b(?:turn|switch|power|toggle|set|dim|brighten|bright|brighter|"
    r"increase|decrease|raise|lower|adjust|brightness|dimmer|make|warmer|"
    r"cooler|heat|heating|temperature|thermostat)\b",
    re.I,
)
_READ_QUESTION_PREFIX = re.compile(
    r"^\s*(?:why|when|what|which|where|who|how|is|are|was|were|did|does|do|"
    r"has|have|had)\b",
    re.I,
)


def is_semantic_control_candidate(prompt: str) -> bool:
    """Cheap broad gate for the AI control planner.

    This deliberately does not decide the action. It only avoids spending a
    provider round on prompts with no plausible routine-control language. The
    semantic planner remains responsible for deciding whether the user actually
    asked for an action versus a question/advice request.
    """

    text = str(prompt or "")
    if _READ_QUESTION_PREFIX.search(text):
        return False
    return _CONTROL_CANDIDATE.search(text) is not None


def _history_lines(history: Any, *, limit: int = 4) -> list[str]:
    if not isinstance(history, list):
        return []
    rows: list[str] = []
    for item in history[-limit:]:
        if isinstance(item, dict):
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
        else:
            role = str(getattr(item, "role", "") or "")
            content = str(getattr(item, "content", "") or "")
        if role in {"user", "assistant"} and content.strip():
            rows.append(f"{role}: {' '.join(content.strip().split())[:500]}")
    return rows


class SemanticPlanner:
    """Translate natural-language goals into a narrow typed semantic plan.

    The planner never receives Hubitat tool names, device IDs, or wire formats.
    Its job is meaning only. Execution and safety remain deterministic.
    """

    def __init__(self, chat: ChatCallable) -> None:
        self._chat = chat

    @staticmethod
    def system_prompt() -> str:
        return (
            "You are the semantic planning layer for a smart-home assistant. "
            "Translate the user's meaning into ONE JSON object only. Do not emit "
            "markdown, prose, tool names, device IDs, API fields, or explanations. "
            "You do not execute anything and you do not know live device state.\n\n"
            "JSON contract:\n"
            "{"
            "\"version\":\"1\","
            "\"domain\":\"device_control|other\","
            "\"timing\":\"now|scheduled|unknown\","
            "\"target\":{\"scope\":\"room|device|home|selection|unknown\","
            "\"name\":\"...\",\"names\":[\"...\"]|[],"
            "\"kind\":\"light|switch|thermostat|auto\"}|null,"
            "\"action\":{\"operation\":\"turn_on|turn_off|toggle|set_level|adjust_level|set_temperature|adjust_temperature\","
            "\"value\":0-100|null,\"delta\":-100..100|null,"
            "\"direction\":\"increase|decrease\"|null,"
            "\"magnitude\":\"small|default|large\"}|null,"
            "\"needs_clarification\":true|false,"
            "\"clarification_question\":\"...\","
            "\"confidence\":\"high|medium|low\""
            "}\n\n"
            "Planning rules:\n"
            "- device_control means an actual request to change an ordinary light, "
            "switch, or heating thermostat now. Questions such as 'why did the light "
            "turn off?' or 'how do I increase brightness?' are domain=other.\n"
            "- Locks, doors, garages, security, firmware, network blocking, rule "
            "authoring, and other sensitive/admin actions are domain=other.\n"
            "- Scheduled/future/recurring actions use timing=scheduled so another "
            "planner can handle them.\n"
            "- Interpret natural paraphrases semantically: brighter/turn up/raise "
            "brightness -> adjust_level upward; dimmer/turn down/lower brightness "
            "-> adjust_level downward. Warmer/turn the heating up/raise the "
            "temperature -> adjust_temperature upward; cooler/turn the heating down/"
            "lower the temperature -> adjust_temperature downward.\n"
            "- If the user explicitly gives an absolute light level, use set_level "
            "with value. If the user explicitly gives an absolute thermostat "
            "temperature/setpoint, use set_temperature with value. Relative light "
            "changes use adjust_level; relative thermostat changes use "
            "adjust_temperature, with signed delta and matching direction when an "
            "amount is explicit.\n"
            "- If the user asks for a relative brightness or temperature change but "
            "gives no amount, use the corresponding adjust operation with delta=null, "
            "the correct direction, and magnitude=default. Do NOT ask for an amount; "
            "HomeBrain has stable configured defaults. 'a little/slightly' uses "
            "magnitude=small; 'a lot/much' uses magnitude=large.\n"
            "- Preserve the user's target meaning. Use room when the user clearly "
            "targets a room/group (for example 'living room lights' or 'make Bedroom "
            "1 warmer'); for room scope put only the room identity in name and use "
            "names=[]. Use device for one named device, also with names=[]. When the "
            "user explicitly names two or more individual devices, use selection, "
            "put their canonical names in names, and leave name empty. Do not use "
            "selection for an ordinary room/group reference. When capability-grounded "
            "home context is "
            "provided, prefer its exact canonical room/device names and never invent "
            "a device or room that is not present there.\n"
            "- Capability-grounded home context is identity/capability metadata only, "
            "not live state. Never infer whether something is on, off, hot, cold, or "
            "currently at a particular level from that context.\n"
            "- For thermostat temperature actions, only choose a target whose context "
            "advertises heating_setpoint; otherwise ask for clarification or use "
            "domain=other rather than guessing.\n"
            "- Ask for clarification only when the requested action or target itself "
            "is genuinely missing/unclear, not merely because a relative amount was "
            "omitted.\n"
            "- confidence=high only when action, target, and timing are clear."
        )

    async def plan(
        self,
        prompt: str,
        *,
        history: Any = None,
        selected_device: str = "",
        world_context: str = "",
    ) -> SemanticPlan:
        context: list[str] = []
        if selected_device.strip():
            context.append(f"Current selected device hint: {selected_device.strip()}")
        context.extend(_history_lines(history))
        if world_context.strip():
            context.append(
                "Capability-grounded home context (identity/capability metadata; "
                "NOT live state):\n" + world_context.strip()
            )
        user_content = str(prompt or "").strip()
        if context:
            user_content = (
                "Conversation context (identity/reference hints only):\n"
                + "\n".join(context)
                + "\n\nCurrent user request:\n"
                + user_content
            )
        response = await self._chat(
            [
                {"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": user_content},
            ],
            [],
        )
        plan = semantic_plan_from_model_text(str(response.get("content") or ""))
        # Source is host metadata, never a field the model gets to choose.
        plan.source = "model"
        return plan


__all__ = [
    "SemanticPlanner",
    "is_semantic_control_candidate",
]
