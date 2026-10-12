"""Evidence-based completion of a bounded causal investigation.

A completed investigation does not require a *proven* initiator. It requires
an observed, uniquely identified transition and checked applicable source
classes. Negative/empty sources remain limitations, not proof of non-execution.

User wording (e.g. "possible external causes" vs "alternative causes") is
not a completion criterion. It can select ON/OFF scope and explicit optional
checks, never force a loop after the evidence budget has been satisfied.
"""
from __future__ import annotations

import re
from typing import Any

_TRANSITION_ON = re.compile(
    r"\b(?:turn(?:ed|ing)?|switch(?:ed|ing)?|went|go(?:es)?)\s+on\b",
    re.I,
)
_TRANSITION_OFF = re.compile(
    r"\b(?:turn(?:ed|ing)?|switch(?:ed|ing)?|went|go(?:es)?)\s+off\b",
    re.I,
)


def requested_transition_scope(question: str) -> str:
    text = str(question or "")
    has_on = bool(_TRANSITION_ON.search(text))
    has_off = bool(_TRANSITION_OFF.search(text))
    if has_off and not has_on:
        return "off"
    if has_on and not has_off:
        return "on"
    if has_on and has_off:
        return "both"
    return "unspecified"


def evaluate_causal_completion(
    graph: dict[str, Any],
    question: str,
    *,
    mode_history_required: bool = False,
) -> dict[str, Any]:
    """Typed evidence obligations for the one-pass reasoning fast path.

    The paths for ON and OFF have distinct checked-source requirements. An
    unsuccessful command log or a missing historical decision is a documented
    uncertainty, not a reason to search unrelated rooms indefinitely.
    """
    scope = requested_transition_scope(question)
    if graph.get("scope") != "single-observed-event":
        return {
            "complete": False, "transition": scope,
            "outcome": "ambiguous-focal-event",
            "unchecked": ["unique-focal-event"],
        }
    if mode_history_required:
        return {
            "complete": False, "transition": scope,
            "outcome": "optional-mode-history-not-checked",
            "unchecked": ["requested-mode-history"],
        }
    transition_evidence = graph.get("transitionEvidence") or {}
    if scope == "off":
        off = transition_evidence.get("off") or {}
        actor = off.get("appProducerContext") or {}
        listener = off.get("notifiedListenerContext") or {}
        command_history = off.get("commandHistory") or {}
        action_verified = bool(off.get("directCommand"))
        history_attempted = bool(
            command_history.get("checked")
            or command_history.get("result") == "unavailable"
        )
        config_checked = bool(
            (actor.get("configuration") or {}).get("checked")
            or (listener.get("configuration") or {}).get("checked")
        )
        logs_checked = bool(
            (actor.get("executionLogs") or {}).get("checked")
            or (listener.get("executionLogs") or {}).get("checked")
        )
        # A completed room-local correlation check is enough even when the
        # result contains zero relevant sensor events. Do not require a strong
        # association (let alone proof) just to stop exploration.
        sensors_checked = bool(graph.get("otherSensorEvidenceChecked"))
        obligations = {
            "observed-off-transition": bool(off.get("observed")),
            "off-command-checked-or-proven": action_verified or history_attempted,
            "relevant-app-configuration-checked": config_checked,
            "off-event-log-window-checked": logs_checked,
            "room-sensor-evidence-checked": sensors_checked,
        }
        missing = [key for key, satisfied in obligations.items() if not satisfied]
        return {
            "complete": not missing,
            "transition": "off",
            "unchecked": missing,
            "checked": [key for key, satisfied in obligations.items() if satisfied],
            "outcome": (
                "confirmed-direct-command" if action_verified
                else "completed-unresolved" if not missing
                else "partial"
            ),
            "externalAutomationUnverified": not off.get(
                "externalAutomationIdentityVerified", False
            ),
            "absenceOfLoggedCommandIsNotExclusion": True,
        }

    # Preserve the stronger ON proof obligations, already exercised by
    # Bathroom/Livingroom causal regressions.
    if scope == "on":
        on = transition_evidence.get("on") or {}
        candidate = graph.get("initiatorCandidate") or {}
        completed_app_chain = bool(
            graph.get("ready")
            and candidate.get("configured") is True
            and candidate.get("status") == "strongly-correlated-configured-sensor"
        )
        physical_chain = bool(graph.get("physicalEvidenceComplete"))
        return {
            "complete": completed_app_chain or physical_chain,
            "transition": "on",
            "outcome": (
                "confirmed-command-with-correlated-trigger"
                if completed_app_chain else
                "physical-controller-associated"
                if physical_chain else "partial"
            ),
            "unchecked": [] if (completed_app_chain or physical_chain) else [
                "complete-on-causal-source-checks"
            ],
        }
    return {
        "complete": False, "transition": scope,
        "outcome": "mixed-or-unspecified-transition-scope",
        "unchecked": ["single-requested-transition"],
    }


__all__ = [
    "requested_transition_scope",
    "evaluate_causal_completion",
]
