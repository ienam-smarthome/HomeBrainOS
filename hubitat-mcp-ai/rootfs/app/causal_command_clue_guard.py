"""Evidence-specific guard for false external-controller conclusions.

A bridge producedBy state event identifies the reporting source, NOT an
upstream controller. A preceding Hubitat on/off command prevents the claim
that no Hubitat path could have initiated the transition.
"""
from __future__ import annotations

import re
from typing import Any

from causal_command_provenance import (
    prompt_focal_transition_boundary, preceding_command_candidates,
)
from causal_subject_prefetch import switch_transition_from_prompt


_EXTERNAL_CLAIM = re.compile(
    r"(?i)(?:the\s+)?(?:trigger|activation|command|initiating\s+(?:action|cause))"
    r"\s+(?:originated|came)\s+from\s+(?:a\s+)?(?:controller|source)\s+"
    r"outside\s+(?:the\s+)?Hubitat(?:\s+ecosystem)?[^.]*\."
)
_NO_INTERNAL = re.compile(
    r"(?i)\\bno\\s+Hubitat[- ]native\\s+[^.]{0,150}?"
    r"(?:triggered|initiated|caused)\\s+(?:the\\s+)?(?:event|activation|transition)[^.]*\\."
)
_LIKELY_EXTERNAL = re.compile(
    r"(?i)(?:the\s+)?activation\s+was\s+likely\s+triggered\s+by\s+"
    r"(?:an?\s+)?external\s+(?:source|controller)[^.]*\."
)


def guard_causal_exclusion_with_command_clue(
    message: str, evidence: list[dict[str, Any]], original_user: str,
) -> tuple[str, bool]:
    """Downgrade unsound external attribution using targeted command receipts.

    Only activate when the user's focal event is uniquely established in
    evidence and its subject can be read from a matching command event.
    A 2-30 s predecessor is a clue, not causal proof.
    """
    transition = switch_transition_from_prompt(original_user)
    if transition not in {"on", "off"}:
        return message, False
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("sub_tool") != "hub_list_device_events":
            continue
        detail = receipt.get("details")
        if not isinstance(detail, dict) or not detail.get("label"):
            continue
        subject = str(detail["label"])
        if subject.casefold() not in original_user.casefold():
            continue
        boundary = prompt_focal_transition_boundary(
            evidence, transition, original_user,
        )
        if boundary:
            for clue in preceding_command_candidates(
                evidence, subject=subject, transition=transition,
                requested_boundary=boundary,
            ):
                candidates.append((subject, boundary, clue))
        break
    if not candidates:
        return message, False
    candidates.sort(key=lambda row: row[2]["delaySeconds"])
    subject, boundary, clue = candidates[0]
    corrected = str(message or "")
    replacement = (
        "The recorded state change does not by itself identify an external "
        "initiating controller. An internal Hubitat command is recorded "
        "before this transition, but its causal effect remains unverified."
    )
    for pattern in (_EXTERNAL_CLAIM, _NO_INTERNAL, _LIKELY_EXTERNAL):
        corrected = pattern.sub(replacement, corrected)
    label = str(clue["producer"].get("label") or "an identified Hubitat app")
    if label.casefold() not in corrected.casefold():
        corrected += (
            "\n\n**Preceding command clue (not proven cause):** "
            f"{label} issued {clue['command']} at {clue['commandTime']}, "
            f"{clue['delaySeconds']:.3f} seconds before the requested "
            f"{transition.upper()} boundary. Command delivery, effect and "
            "the upstream initiator are unverified."
        )
    return corrected, corrected != str(message or "")


__all__ = ["guard_causal_exclusion_with_command_clue"]
