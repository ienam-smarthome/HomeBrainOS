"""Guard controller provenance claims against interval-boundary direction."""

from __future__ import annotations

import re
from typing import Any

from causal_timeline import build_causal_timeline_rows


_CONTROLLER_TERM = re.compile(
    r"\b(?:button|controller|dimmer|physical|push(?:ed|es|ing)?)\b",
    re.I,
)
_TRIGGER_TERM = re.compile(
    r"\b(?:turn(?:ed|s)?\s+on|trigger(?:ed|s)?|caus(?:e|ed|es)|"
    r"provenance|correlat(?:e|es|ed|ion|ing))\b",
    re.I,
)
_END_QUALIFIER = re.compile(
    r"\b(?:interval\s+end|end\s+boundary|turn(?:ed|s)?\s+off|"
    r"off\s+boundary|not\s+(?:evidence|proof).{0,40}turn(?:ed)?\s+on)\b",
    re.I | re.S,
)


def _time_tokens(value: Any) -> set[str]:
    text = str(value or "").strip()
    match = re.search(r"T(\d{2}):(\d{2})", text)
    if not match:
        return set()
    hour24 = int(match.group(1))
    minute = int(match.group(2))
    hour12 = hour24 % 12 or 12
    suffix = "am" if hour24 < 12 else "pm"
    return {
        f"{hour24:02d}:{minute:02d}".casefold(),
        f"{hour24}:{minute:02d}".casefold(),
        f"{hour12}:{minute:02d}".casefold(),
        f"{hour12}:{minute:02d} {suffix}".casefold(),
    }


def guard_controller_boundary_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Repair claims that use end-aligned controller events as turn-on provenance."""

    suspects = [
        row
        for row in build_causal_timeline_rows(evidence)
        if not (row.get("triggerEvidence") or [])
        and (row.get("endControllerEvidence") or [])
    ]
    text = str(message or "")
    if not suspects or not _CONTROLLER_TERM.search(text) or not _TRIGGER_TERM.search(text):
        return text, False

    pieces = re.split(r"(?P<space>(?<=[.!?])\s+|\n+)", text)
    changed = False
    used_rows: set[str] = set()
    for index in range(0, len(pieces), 2):
        segment = pieces[index]
        if (
            not _CONTROLLER_TERM.search(segment)
            or not _TRIGGER_TERM.search(segment)
            or _END_QUALIFIER.search(segment)
        ):
            continue
        comparable = re.sub(r"\s+", " ", segment.casefold())
        matched = None
        for row in suspects:
            tokens = {
                *_time_tokens(row.get("start")),
                *_time_tokens(row.get("end")),
            }
            if tokens and any(token in comparable for token in tokens):
                matched = row
                break
        if matched is None and len(suspects) == 1:
            matched = suspects[0]
        if matched is None:
            continue

        row_id = str(matched.get("id") or "")
        if row_id in used_rows:
            pieces[index] = ""
            changed = True
            continue
        used_rows.add(row_id)
        start_text = str(
            matched.get("startNatural") or matched.get("start") or "the interval start"
        )
        pieces[index] = (
            f"For the interval starting {start_text}, the checked controller event "
            "aligns with the interval end/turn-off boundary, not the start, so it "
            "is not evidence that the controller caused that turn-on."
        )
        changed = True

    return "".join(pieces), changed


__all__ = ["guard_controller_boundary_claim"]
