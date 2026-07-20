from __future__ import annotations

import re
from typing import Any

import ai_evidence_planner as planner_module
from control_agent_intent import is_control_candidate
from control_focus_mode import ControlFocusMode, is_control_followup
from presenter import display_payload, safe_debug


_READ_PREFIXES = (
    "what ",
    "what's ",
    "why ",
    "how ",
    "which ",
    "is ",
    "are ",
    "show ",
    "list ",
    "display ",
    "get ",
    "check ",
    "tell me ",
    "give me ",
    "summarise ",
    "summarize ",
    "explain ",
    "compare ",
    "analyse ",
    "analyze ",
    "diagnose ",
    "recommend ",
    "suggest ",
)
_WRITE_PREFIXES = (
    "turn ",
    "switch ",
    "set ",
    "dim ",
    "raise ",
    "lower ",
    "increase ",
    "decrease ",
    "lock ",
    "unlock ",
    "open ",
    "close ",
    "start ",
    "stop ",
    "run ",
    "create ",
    "delete ",
    "modify ",
    "change ",
    "repair ",
)
_WRITE_TERMS = (
    "create automation",
    "create rule",
    "delete automation",
    "delete rule",
    "modify automation",
    "modify rule",
    "change automation",
    "change rule",
    "repair rule",
)
_EXTRA_HOME_TERMS = (
    "electricity",
    "octopus",
    "bathroom",
    "toilet",
    "kitchen",
    "living room",
    "bedroom",
    "hallway",
    "ventilation",
    "dehumidifier",
    "air purifier",
    "camera",
    "appliance",
)


def _query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).strip(" .!?")


def is_control_safe_ai_read(query: str) -> bool:
    """Return True only for read-only home questions suitable for evidence planning."""

    q = _query(query)
    if not q or is_control_candidate(q) or is_control_followup(q):
        return False
    if q.startswith(_WRITE_PREFIXES) or any(term in q for term in _WRITE_TERMS):
        return False

    # Proven deterministic Octopus family/period reads must stay on their faster route.
    try:
        from control_focus_octopus_energy import is_octopus_energy_query

        if is_octopus_energy_query(q):
            return False
    except Exception:
        pass

    domains = tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ())) + _EXTRA_HOME_TERMS
    if not any(term in q for term in domains):
        return False
    return q.startswith(_READ_PREFIXES) or any(
        term in q
        for term in (
            " why ",
            " unusual",
            " issue",
            " problem",
            " improve",
            " recommend",
            " summary",
            " consumption",
            " usage",
            " today",
            " yesterday",
        )
    )


def install_control_focus_ai_fallback_scope() -> None:
    """Let Control Focus protect writes while unanswered reads fall through to AI.

    The AI Evidence Planner remains read-only and receives no command tools. Existing
    deterministic routes are evaluated first by its matcher, while this extension
    captures ordinary home questions that older phrase gates would otherwise block.
    """

    original_matcher = planner_module.is_ai_evidence_query

    def control_safe_matcher(query: str) -> bool:
        try:
            from control_focus_octopus_energy import is_octopus_energy_query

            if is_octopus_energy_query(query):
                return False
        except Exception:
            pass
        return bool(original_matcher(query) or is_control_safe_ai_read(query))

    planner_module.is_ai_evidence_query = control_safe_matcher

    def scope_response(self: ControlFocusMode, query: str) -> dict[str, Any]:
        ai_enabled = bool(getattr(self, "ai_read_fallback_enabled", False))
        if ai_enabled:
            message = (
                "HomeBrain could not classify this as a safe read-only home question or a "
                "supported device control. Clear controls remain deterministic and verified; "
                "recognised read-only questions are sent to the AI Evidence Planner."
            )
            subtitle = "Controls protected; AI read fallback enabled"
        else:
            message = (
                "HomeBrain is in strict Control Focus mode. It can control selected devices and "
                "answer verified device-state questions, while broader AI analysis is disabled."
            )
            subtitle = "Device control and verified live reads only"

        display = display_payload(
            "control-focus-scope",
            "Control Focus mode",
            subtitle=subtitle,
            metrics=[
                {"label": "Device controls", "value": "Deterministic", "icon": "🎛️"},
                {"label": "Verified reads", "value": "Enabled" if self.allow_verified_reads else "Disabled", "icon": "📡"},
                {"label": "AI read fallback", "value": "Enabled" if ai_enabled else "Disabled", "icon": "🧠"},
            ],
            note=(
                "AI may choose approved read-only evidence, but it receives no Hubitat write tools."
                if ai_enabled
                else "Enable control_focus_ai_read_fallback_enabled to allow bounded AI answers."
            ),
        )
        display["summary"] = message
        return {
            "success": True,
            "route": "control-focus",
            "intent": "control-focus-scope",
            "message": message,
            "display": display,
            "answered_by": "HomeBrain Control Focus safety policy",
            "technical": safe_debug(
                {
                    "query": query,
                    "control_focus_enabled": self.enabled,
                    "verified_reads_enabled": self.allow_verified_reads,
                    "ai_read_fallback_enabled": ai_enabled,
                    "write_tools_available_to_ai": False,
                }
            ),
        }

    ControlFocusMode.scope_response = scope_response


__all__ = [
    "install_control_focus_ai_fallback_scope",
    "is_control_safe_ai_read",
]
