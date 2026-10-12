"""Source-backed certainty contract for narrative and tables about OFF events.

The graph, not the prose, decides whether OFF has a verified command producer,
a verified internal trigger and a verified external automation identity.
This final-pass checker keeps narrative and Markdown table verdicts consistent
with the *same* structured proof obligations, including for unresolved causes.

This is a generic logical contract, not a fixed device/app/room patch.
"""
from __future__ import annotations

import re
from typing import Any

from causal_completion_policy import requested_transition_scope


_LIST_PREFIX = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+))")
_OFF_TOPIC = re.compile(
    r"\b(?:off|turn(?:ed|ing)?\s+off|switch(?:ed|ing)?\s+off)\b", re.I
)
_PROOF_EXCLUSION = re.compile(
    r"\b(?:prov(?:e|es|ed|ing)|confirm(?:s|ed|ing)?|establish(?:es|ed|ing)?|"
    r"demonstrat\w*|rul(?:e|es|ed|ing)\s+out)\b", re.I
)
_NO_HUB_CAUSE = re.compile(
    r"\b(?:no|none|not|never|did\s+not|was\s+not|could\s+not)\b.{0,105}"
    r"\b(?:Hubitat|app|rule|automation|dashboard|manual|button|physical|"
    r"command|initiated?|trigg\w*)\b",
    re.I,
)
_EXTERNAL_LIKELY = re.compile(
    r"\b(?:likely|probably|most\s+likely|confirmed)\b.{0,45}"
    r"\b(?:external|non[- ]Hubitat|motion[- ]based\s+automation)\b"
    r"|\b(?:external|motion[- ]based\s+automation)\b.{0,45}"
    r"\b(?:likely|probably|trigger(?:ed|ing)?)\b",
    re.I,
)
_CAUSAL_ARROW = re.compile(
    r"(?:→|⇒|-->|\\rightarrow|\u2192)", re.I
)
_ABSOLUTE_NO_COMMAND = re.compile(
    r"\b(?:no|not\s+a\s+single)\s+(?:Hubitat[- ]side\s+)?"
    r"(?:on|off\s+)?command\s+(?:was|had\s+been|could\s+be)\s+"
    r"(?:issued|sent|executed)\b",
    re.I,
)
_FALSE_LOG_INFERENCE = re.compile(
    r"\b(?:no\s+(?:entries|logs|rows)|empty\s+(?:logs|execution)|"
    r"logs?\s+(?:were|was|returned)\s+(?:empty|zero))\b"
    r".{0,170}?\b(?:prov\w*|confirm\w*|rul\w*|exclud\w*)\b",
    re.I,
)
_OFF_TRIGGER = re.compile(
    r"\b(?:sensor|motion|presence|inactiv\w*|occupancy|FP\d+)\b"
    r".{0,95}?\b(?:trigger\w*|caus\w*|initiated?|responsible)\b"
    r"|\b(?:trigger\w*|caus\w*|initiated?|responsible)\b"
    r".{0,95}?\b(?:sensor|motion|presence|inactiv\w*|occupancy|FP\d+)\b",
    re.I,
)


def _line_marker(line: str) -> str:
    matched = _LIST_PREFIX.match(line)
    return matched.group(1) if matched else ""


def _safe_off_summary(has_direct: bool) -> str:
    if has_direct:
        return (
            "The recorded OFF command identifies its direct producer; "
            "the upstream sensor or inactivity-timer trigger remains unverified."
        )
    return (
        "The OFF event was observed, but its command producer and initiating "
        "automation are unverified. Nearby sensor inactivity is a temporal "
        "correlation, not proof of the OFF cause."
    )


def _table_cells(line: str) -> list[str] | None:
    if "|" not in line or line.count("|") < 2:
        return None
    # Preserve the exact column count and delimiter layout.
    return line.split("|")


def _is_divider(line: str) -> bool:
    return bool(re.fullmatch(r"[\s|:\-]+", line))


def _update_table(
    line: str, headers: list[str], *,
    off_only: bool, has_direct: bool, trigger_proven: bool,
) -> tuple[str, bool]:
    parts = _table_cells(line)
    if parts is None or _is_divider(line):
        return line, False
    indexes = [i for i,p in enumerate(parts) if p.strip()]
    if not indexes:
        return line, False
    cells = [parts[i].strip() for i in indexes]
    if len(cells) != len(headers):
        return line, False
    rowname = cells[0].casefold()
    head = [h.casefold() for h in headers]
    changed = False

    def assign(column: int, replacement: str) -> None:
        nonlocal changed
        if cells[column] != replacement:
            cells[column] = replacement
            parts[indexes[column]] = " " + replacement + " "
            changed = True

    if rowname in {"off", "turn-off", "switched off"}:
        if not has_direct:
            for col, name in enumerate(head):
                if name in {"proven actor", "command producer", "initiating app"}:
                    assign(col, "Not established")
                if name in {"likely actor", "likely initiator", "likely cause"}:
                    assign(col, "Unverified")
            for col, name in enumerate(head):
                if name == "evidence" and any(
                    "unverified" in c.casefold()
                    or "not established" in c.casefold() for c in cells
                ):
                    assign(col, "Sensor proximity only; no OFF command owner established")
        return "|".join(parts), changed

    # These roles are about an OFF-only result, not the same table's ON row.
    if off_only and not trigger_proven:
        if rowname in {"trigger", "likely", "causal link", "likely cause",
                       "off cause", "external automation", "physical interaction"}:
            for col, name in enumerate(head):
                if name in {"status", "certainty", "confidence", "likely actor"}:
                    assign(col, "Unverified")
                if name in {"detail", "evidence", "explanation", "causal link"}:
                    assign(col, _safe_off_summary(has_direct))
    return "|".join(parts), changed


def guard_off_certainty_contract(
    message: str, graph: dict[str, Any], original_user: str = "",
) -> tuple[str, bool]:
    """Reconcile an ON/OFF narrative and its summary table with graph facts.

    Never infer "confirmed absent" from a zero-row log page. Never infer an
    external controller or a causal sensor path from correlation alone.
    Fail closed if there is no uniquely observed OFF boundary.
    """
    source = str(message or "")
    off = (graph.get("transitionEvidence") or {}).get("off") or {}
    if graph.get("scope") != "single-observed-event" or not off.get("observed"):
        return source, False
    command = off.get("directCommand")
    has_direct = bool(command)
    trigger_proven = bool(off.get("internalTimerExecutionVerified"))
    external_verified = bool(off.get("externalAutomationIdentityVerified"))
    off_only = (
        requested_transition_scope(original_user) == "off"
        or (
            not str(original_user or "").strip()
            and requested_transition_scope(source) == "off"
        )
    )
    # The question is unavailable at the final serialization boundary. An
    # explicitly scoped event graph still permits correction of OFF table rows
    # and OFF-specific prose, but not unrelated ON/manual statements.
    lines = source.splitlines(keepends=True)
    headers: list[str] = []
    off_section = off_only
    changed = False
    result: list[str] = []

    for raw in lines:
        nl = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if nl else raw
        stripped = line.strip()
        if re.match(r"^(?:#{1,6}\s*)?(?:\d+[.)]\s+)?(?:turn[- ]off|off[- ]event|off[- ]investigation)", stripped, re.I):
            off_section = True
        elif re.match(r"^(?:#{1,6}\s*)?(?:\d+[.)]\s+)?(?:turn[- ]on|on[- ]investigation)", stripped, re.I):
            off_section = False

        table = _table_cells(line)
        if table and not _is_divider(line):
            filled = [x.strip() for x in table if x.strip()]
            keys = {x.casefold() for x in filled}
            if {"transition","time"} <= keys or (
                "status" in keys and ("detail" in keys or "evidence" in keys)
            ) or ("element" in keys and "status" in keys) or (
                "likely actor" in keys and "proven actor" in keys
            ):
                headers = filled
                result.append(raw)
                continue
            if headers:
                amended, hit = _update_table(
                    line, headers, off_only=off_only or off_section,
                    has_direct=has_direct,
                    trigger_proven=trigger_proven or external_verified,
                )
                if hit:
                    changed = True
                result.append(amended + nl)
                continue
        if not stripped or _is_divider(line):
            if not stripped:
                headers = []
            result.append(raw)
            continue
        in_off = off_only or off_section or bool(
            _OFF_TOPIC.search(line)
        )
        if not in_off:
            result.append(raw)
            continue

        unsupported_absence = bool(
            not has_direct
            and (
                (_PROOF_EXCLUSION.search(line) and _NO_HUB_CAUSE.search(line))
                or _FALSE_LOG_INFERENCE.search(line)
                or _ABSOLUTE_NO_COMMAND.search(line)
                or re.search(
                    r"(?i)\bphysical\s+interaction\s*:\s*ruled\s+out\b",
                    line
                )
            )
        )
        unsupported_external = bool(
            not external_verified and _EXTERNAL_LIKELY.search(line)
        )
        unsupported_trigger = bool(
            not trigger_proven and _OFF_TRIGGER.search(line)
            and re.search(r"(?i)\b(?:likely|probably|triggered|caused|confirmed)\b", line)
            and not re.search(
                r"(?i)\b(?:not\s+verified|not\s+confirmed|unverified|"
                r"could\s+not\s+confirm|unresolved|no\s+proven)\b",
                line
            )
        )
        if unsupported_absence or unsupported_external or unsupported_trigger:
            result.append(_line_marker(line) + _safe_off_summary(has_direct) + nl)
            changed = True
        else:
            result.append(raw)
    return "".join(result), changed


__all__ = ["guard_off_certainty_contract"]
