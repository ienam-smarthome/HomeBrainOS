"""Guard causal explanations against promoting missing commands into external causes.

The observed Hubitat switch event, its reporting bridge and the list of
notified apps describe a state transition. None of them proves an upstream
initiator. A bounded command-event query with no matching producer is an
unresolved provenance slot, not affirmative evidence that Hubitat or all
possible upstream integrations did *not* send a command.

This guard operates on source-qualified *claims* in the model's final answer,
not on individual device names or one known incident.
"""
from __future__ import annotations

import re
from typing import Any

from causal_evidence_graph import build_causal_evidence_graph
from causal_fail_closed_summary import _focal_sensor_correlations


_EXTERNAL = re.compile(
    r"\b(?:external|outside\s+(?:of\s+)?hubitat|hue[- ]native|"
    r"bridge[- ]native|third[- ]party|not\s+(?:within|inside)\s+hubitat)\b",
    re.I,
)
_ASSERTION = re.compile(
    r"\b(?:most\s+likely|probably|likely|must\s+have|certainly|definitely|"
    r"(?:was|is)\s+(?:responsible|the\s+cause)|"
    r"(?:initiating\s+logic|cause|command|trigger)\s+"
    r"(?:resid(?:e|es)|originat(?:e|ed|es)|came|comes))\b",
    re.I,
)
_STRONG_NO_HUB_COMMAND = re.compile(
    r"\b(?:hubitat\s+(?:did\s+not|didn't|never)\s+(?:issue|send)|"
    r"no\s+(?:hubitat(?:[- ]side|[- ]issued)?\s+)?"
    r"command(?:\s+producer)?\s+(?:was\s+)?(?:issued|sent|executed)|"
    r"there\s+(?:is|was)\s+no\s+record\s+of\s+a\s+"
    r"hubitat[- ]issued\s+command)\b",
    re.I,
)
_UNPROVEN_LISTENER_EXCLUSION = re.compile(
    r"(?:\b(?:were|was|are|is)\s+notified\b.{0,150}?\b(?:did\s+not|"
    r"didn't|could\s+not|weren't|wasn't)\s+initiat(?:e|ed)\b|"
    r"\b(?:were|was)\s+not\s+the\s+(?:initiating|commanding)\s+(?:app|controller)\b)",
    re.I,
)
_BULLET = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*[^*]+\*\*\s*)?)")


def guard_unverified_initiator_claims(
    message: str, evidence: list[dict[str, Any]],
    original_user: str, *, graph: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """Replace unsupported upstream conclusions with bounded source statements.

    Deliberately applies only when one requested state boundary has been
    independently observed. Do not invent a transition, broaden an unrelated
    investigation or discredit positive evidence from a verified actor.
    """
    original = str(message or "")
    graph = (graph if graph is not None else
             build_causal_evidence_graph(evidence, original_user))
    if graph.get("scope") != "single-observed-event":
        return original, False
    external_verified = (graph.get("externalInitiatorVerified") is True)
    positive_command = bool(graph.get("directCommand"))
    changed = False
    output: list[str] = []
    for raw in original.splitlines(keepends=True):
        nl = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if nl else raw
        stripped = line.strip()
        prefix = (_BULLET.match(line).group(1) if _BULLET.match(line) else "")
        # A verified direct command may establish who issued that *command*.
        # It still does not establish whether a Hue/Matter-native process
        # initiated a different physical report.
        external_guess = (
            not external_verified
            and bool(_EXTERNAL.search(stripped))
            and bool(_ASSERTION.search(stripped))
            and bool(re.search(r"\b(?:caus\w*|initiator|initiating|"
                               r"trigger\w*|command\w*|logic|"
                               r"automatio\w*|controlled|responsible)\b",
                               stripped, re.I))
        )
        absence_as_proof = bool(_STRONG_NO_HUB_COMMAND.search(stripped))
        listener_excluded = bool(_UNPROVEN_LISTENER_EXCLUSION.search(stripped))
        if external_guess:
            # A single paragraph can mix a correct observed sensor edge
            # with an invented upstream initiator: do not discard the
            # observation along with the unsupported causal leap.
            # Reproduce only a *source-verified* focal timing fact, never
            # preserve model prose merely because it mentions a sensor.
            leading = re.split(r"(?i)\\b(?:however|therefore|thus)\\s*[,;:]?\\s*", stripped, maxsplit=1)[0]
            focus = graph.get("focus") or {}
            off_requested = re.search(
                r"(?i)\\b(?:turn|turned|switch|switched|went)\\s+off\\b",
                str(original_user or ""),
            ) is not None
            timing_facts = _focal_sensor_correlations(
                evidence,
                str(focus.get("subject") or ""),
                str(focus.get("off" if off_requested else "on") or ""),
                "end" if off_requested else "start",
            )
            verified_observation = ""
            if leading != stripped and re.search(
                r"(?i)\\b(?:correlat\\w*|sensor|motion|occupancy)\\b",
                leading,
            ):
                for fact in timing_facts:
                    name = fact.split(" reported ", 1)[0].strip()
                    aliases = [name]
                    if name:
                        aliases.append(name.split()[0])
                    if any(len(alias) >= 4 and alias.casefold() in leading.casefold()
                           for alias in aliases):
                        verified_observation = fact + " "
                        break
            line = (
                prefix + verified_observation
                + "The bounded evidence does not identify an initiating "
                "controller. An external automation or manual action remains "
                "possible, but neither has been verified as the cause."
            )
        elif absence_as_proof and not positive_command:
            line = (
                prefix + "No matching direct Hubitat command producer was "
                "identified for this specific transition in the queried "
                "command-event records. This cannot rule out unobserved "
                "command paths, incomplete history or upstream integrations."
            )
        elif listener_excluded:
            line = (
                prefix + "These apps were notified as downstream event "
                "listeners. Receiving a notification does not identify "
                "them as initiators or prove that they could not have "
                "initiated the transition through another path."
            )
        if line != raw.rstrip("\n"):
            changed = True
        output.append(line + nl)
    return "".join(output), changed


__all__ = ["guard_unverified_initiator_claims"]
