"""Source-bound verification of claims about causal action, logs and event order.

The causal graph supplies *typed facts*. Model synthesis supplies explanations,
but it must not reassign the actor of a recorded command, turn an empty log
window into proof of non-execution, or claim a sensor was before a boundary
when its recorded timestamp is after it.

This module operates on one uniquely focused observed event and fails closed
when provenance is absent/ambiguous. It is independent of room names, brands
and application IDs and is shared by synthesis validation and API serialization.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from focal_evidence_reconciliation import (
    guard_unproven_on_button_initiation,
    guard_sensor_history_source_contradiction,
)
from causal_answer_plan import guard_causal_answer_claim_boundaries
from causal_history_coverage import guard_history_gap_claims
from causal_certainty_contract import guard_off_certainty_contract
from off_hypothesis_synthesis_guard import guard_off_hypothesis_summary
from causal_evidence_graph import build_causal_evidence_graph


def _scoped_question(
    evidence: list[dict[str, Any]], original_user: str,
) -> str:
    if str(original_user or "").strip():
        return original_user
    # The API serializer lacks the original prompt. Recover only an explicit
    # focal boundary supplied by the host's current-turn correlation receipt.
    candidates: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        if item.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        details = item.get("details") or {}
        if not isinstance(details, dict):
            continue
        moment_text = str(details.get("requestedBoundary") or "")
        subject = str(details.get("subject") or "")
        if not moment_text or not subject:
            continue
        try:
            when = datetime.fromisoformat(moment_text.replace("Z", "+00:00"))
        except ValueError:
            continue
        candidates.add(
            f"Why did {subject} turn on at {when:%H:%M:%S} "
            f"on {when.day} {when:%B %Y}?"
        )
    return next(iter(candidates)) if len(candidates) == 1 else ""


def _graph(
    evidence: list[dict[str, Any]], original_user: str,
) -> dict[str, Any]:
    question = _scoped_question(evidence, original_user)
    return build_causal_evidence_graph(evidence, question) if question else {}


def _simple_app_label(label: str) -> str:
    name = str(label or "").strip()
    # Dynamic status suffixes are not part of a stable installed-app identity.
    return re.sub(r"\s+\([^)]*(?:Lights\s+(?:On|Off)|Motion\s+(?:Active|Idle))[^)]*\)$", "", name).strip()


def _match_name(line: str, name: str) -> bool:
    if not name:
        return False
    lowered = line.casefold()
    full = name.casefold()
    short = _simple_app_label(name).casefold()
    return full in lowered or (
        len(short) >= 7 and re.search(r"(?<!\w)" + re.escape(short) + r"(?!\w)", lowered) is not None
    )


_ACTION_VERB = re.compile(
    r"\bsetLevel\s*\(|\b(?:set|sets|setting|adjusted?|adjusts?|"
    r"corrected?|changes?|changing|reappl\w*)\b.{0,90}?\b(?:brightness|level)\b",
    re.I,
)
_LEVEL_CLAIM = re.compile(
    r"\bsetLevel\s*\(\s*(\d+(?:\.\d+)?)\s*\)"
    r"|\b(?:brightness|level)\s+(?:to|at|of)\s*(\d+(?:\.\d+)?)\s*%?",
    re.I,
)
_APP_PRONOUN = re.compile(
    r"\b(?:the\s+app|the\s+automation|it)\b", re.I
)
_CONSEQUENTIAL_CONFIG = re.compile(
    r"\b(?:its|the\s+app(?:'s)?)\s+configuration\b", re.I
)
_LIST_MARKER = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+))")
_STRONG_NEGATIVE_LOG = re.compile(
    r"\b(?:confirm(?:s|ed|ing)?|prov(?:e|es|ed|ing)|demonstrat\w*|"
    r"establish\w*|therefore|thus|show(?:s|ed|ing)?)\b"
    r".{0,180}?\b(?:no|none|not|never|did\s+not)\b"
    r".{0,130}?\b(?:execut\w*|initiat\w*|trigg\w*|rule\s+logic|"
    r"internal\s+(?:rule\s+)?logic)\b",
    re.I,
)
_ZERO_LOG_LINE = re.compile(
    r"\b(?:log(?:s|ging)?|execution\s+log)\b.{0,180}"
    r"(?:\b(?:empty|zero|none|no\s+(?:entries|rows|events))\b"
    r"|\b0\s+(?:entries|rows)\b)",
    re.I,
)


def _verified_level_action(graph: dict[str, Any]) -> dict[str, Any] | None:
    # Avoid inferring one unique command when separate apps acted in the
    # same response window, or a command lacks source attribution.
    commands = graph.get("postOnCommands") or []
    verified = [
        row for row in commands
        if isinstance(row, dict)
        and str((row.get("producer") or {}).get("type") or "").casefold() == "app"
        and str((row.get("producer") or {}).get("id") or "")
        and re.search(r"\bsetLevel\s*\(\s*\d+", str(row.get("command") or ""), re.I)
    ]
    if len(verified) != 1:
        return None
    return verified[0]


def _action_value(text: str) -> str:
    match = _LEVEL_CLAIM.search(text)
    if not match:
        return ""
    try:
        return f"{float(match.group(1) or match.group(2)):g}"
    except (ValueError, TypeError):
        return ""


def _listeners(graph: dict[str, Any], owner_id: str) -> list[dict[str, str]]:
    return [
        row for row in ((graph.get("physicalStateBoundary") or {}).get("listenersNotified") or [])
        if isinstance(row, dict)
        and str(row.get("appId") or "")
        and str(row.get("appId") or "") != owner_id
        and str(row.get("label") or "")
    ]


def _correct_actor_sentence(
    owner: dict[str, Any], wrong_name: str,
) -> str:
    producer = owner["producer"]
    label = _simple_app_label(str(producer.get("label") or ""))
    actor = f"{label} (app {producer['id']})" if label else f"App {producer['id']}"
    command = re.search(r"setLevel\s*\(\s*[^)]+\)", str(owner.get("command") or ""), re.I)
    action = command.group(0) if command else "the recorded brightness command"
    delay = owner.get("afterOnMs")
    elapsed = f" {delay:g} ms after ON" if isinstance(delay, (float, int)) else " after ON"
    return (
        f"{actor} issued {action}{elapsed}. "
        f"{wrong_name} was notified of the state event, but is not the "
        "recorded producer of this brightness command."
    )


def guard_causal_action_ownership(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
    *, graph: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """Do not attribute a verified post-ON command to a listener/other app.

    Recognizes explicit app names/IDs and anaphoric 'the app' when the closest
    named app is a different verified listener. It does not invent an owner
    when there are zero or multiple possible producers.
    """
    source = str(message or "")
    graph = graph if graph is not None else _graph(evidence, original_user)
    if graph.get("scope") != "single-observed-event":
        return source, False
    owner = _verified_level_action(graph)
    if not owner:
        return source, False
    producer = owner["producer"]
    owner_id = str(producer["id"])
    expected_level = _action_value(str(owner.get("command") or ""))
    wrong_listeners = _listeners(graph, owner_id)
    if not wrong_listeners or not expected_level:
        return source, False

    nearest_listener: dict[str, str] | None = None
    lines_since_listener = 999
    changed = False
    output: list[str] = []
    for raw in source.splitlines(keepends=True):
        suffix = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if suffix else raw
        if not line.strip():
            output.append(raw)
            lines_since_listener += 1
            continue

        mentioned_wrong = next((
            row for row in wrong_listeners
            if _match_name(line, str(row.get("label") or ""))
            or re.search(r"(?i)\bapp\s*#?\s*" + re.escape(str(row["appId"])) + r"\b", line)
        ), None)
        named_owner = (
            _match_name(line, str(producer.get("label") or ""))
            or re.search(r"(?i)\bapp\s*#?\s*" + re.escape(owner_id) + r"\b", line) is not None
        )
        if mentioned_wrong and not named_owner:
            nearest_listener, lines_since_listener = mentioned_wrong, 0
        elif named_owner:
            nearest_listener, lines_since_listener = None, 999
        else:
            lines_since_listener += 1

        level = _action_value(line)
        action_matches = (
            bool(_ACTION_VERB.search(line))
            and bool(level)
            and level == expected_level
        )
        wrong_actor = (
            mentioned_wrong is not None and not named_owner
            or (
                nearest_listener is not None
                and lines_since_listener <= 3
                and not named_owner
                and _APP_PRONOUN.search(line) is not None
            )
        )
        if action_matches and wrong_actor:
            person = mentioned_wrong or nearest_listener
            assert person is not None
            prefix = (_LIST_MARKER.match(line).group(1) if _LIST_MARKER.match(line) else "")
            line = prefix + _correct_actor_sentence(
                owner, str(person.get("label") or "the notified app")
            )
            changed = True
        elif (
            not named_owner and nearest_listener is not None
            and lines_since_listener <= 3
            and _CONSEQUENTIAL_CONFIG.search(line)
            and not _ACTION_VERB.search(line)
            and ((graph.get("reactiveApp") or {}).get("configuration") or {}).get("checked")
        ):
            prefix = (_LIST_MARKER.match(line).group(1) if _LIST_MARKER.match(line) else "")
            owner_name = _simple_app_label(str(producer.get("label") or "")) or f"App {owner_id}"
            line = (
                prefix
                + f"The checked configuration belongs to {owner_name} (app {owner_id}); "
                + f"the state-event listener {nearest_listener['label']} is not "
                + "established as the brightness command producer."
            )
            changed = True
        output.append(line + suffix)
    return "".join(output), changed


def _checked_empty_logs(graph: dict[str, Any]) -> bool:
    sources = (
        graph.get("executionLogs") or {},
        (graph.get("reactiveApp") or {}).get("executionLogs") or {},
    )
    return any(
        row.get("checked") is True
        and row.get("matchingWindow") is True
        and row.get("result") == "zero-observed-entries"
        for row in sources
    )


def guard_causal_empty_log_inference(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
    *, graph: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """A successful 0-row app-log query cannot prove the app did not execute."""
    source = str(message or "")
    graph = graph if graph is not None else _graph(evidence, original_user)
    if graph.get("scope") != "single-observed-event" or not _checked_empty_logs(graph):
        return source, False
    changed = False
    output: list[str] = []
    for raw in source.splitlines(keepends=True):
        suffix = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if suffix else raw
        if _ZERO_LOG_LINE.search(line) and _STRONG_NEGATIVE_LOG.search(line):
            # Keep the observed zero result but remove only the unsupported
            # assertion about execution. Split off the claim at its inference
            # marker, not at the time string or log source's app identity.
            match = re.search(
                r"(?i)(?:,\s*|\s+)(?:confirm(?:s|ed|ing)?|prov(?:e|es|ed|ing)|"
                r"demonstrat\w*|establish\w*|therefore|thus|show(?:s|ed|ing)?)\b",
                line,
            )
            if match:
                line = (
                    line[:match.start()].rstrip(" .,:;")
                    + "; no execution entries were returned, but this does "
                    "not establish whether internal rule logic executed."
                )
                changed = True
        output.append(line + suffix)
    return "".join(output), changed


def _off_sensor_events(graph: dict[str, Any]) -> list[dict[str, Any]]:
    per_name: dict[str, dict[str, Any]] = {}
    for row in graph.get("offSensorCorrelations") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("sensor") or "")
        if not name or str(row.get("value") or "").casefold() not in {
            "inactive", "not present", "absent", "off"
        }:
            continue
        delta = row.get("signedDeltaMs")
        if not isinstance(delta, (float, int)):
            continue
        if name not in per_name or abs(delta) < abs(per_name[name]["signedDeltaMs"]):
            per_name[name] = row
    return list(per_name.values())


def _mentions_sensor(line: str, name: str) -> bool:
    reduced = re.sub(r"(?i)^.*?\b(?:bedroom|bathroom|livingroom|living\s+room)\s+\d*\s*", "", name)
    name_parts = name.split()
    aliases = [name]
    if len(name_parts) > 1:
        aliases.append(" ".join(name_parts[-2:]))
    if reduced:
        aliases.append(reduced)
    return any(
        len(alias.strip()) >= 5 and alias.casefold() in line.casefold()
        for alias in aliases
    )


def _sensor_order_sentence(graph: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    boundary_text = str((graph.get("focus") or {}).get("off") or "")
    try:
        timestamp = datetime.fromisoformat(boundary_text.replace("Z", "+00:00"))
        boundary = timestamp.strftime("%H:%M:%S.%f")[:-3]
    except ValueError:
        boundary = "the recorded OFF transition"
    pieces = []
    for row in sorted(rows, key=lambda x: float(x["signedDeltaMs"])):
        delta = float(row["signedDeltaMs"])
        relation = "before" if delta < 0 else "after" if delta > 0 else "at"
        measured = f"{abs(delta):g} ms"
        pieces.append(
            f"{row['sensor']} reported {row['value']} {measured} {relation} OFF"
        )
    return (
        f"At OFF ({boundary}), " + "; ".join(pieces)
        + ". These are recorded timing correlations, not proof of who "
        "issued the OFF command."
    )


def guard_causal_sensor_event_order(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
    *, graph: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """Never report a sensor event occurring *after* OFF as *before* it."""
    source = str(message or "")
    graph = graph if graph is not None else _graph(evidence, original_user)
    if graph.get("scope") != "single-observed-event":
        return source, False
    rows = _off_sensor_events(graph)
    if not rows or not any(float(row["signedDeltaMs"]) > 0 for row in rows):
        return source, False
    changed = False
    output: list[str] = []
    for raw in source.splitlines(keepends=True):
        suffix = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if suffix else raw
        # Preserve unrelated paragraphs and already correct mixed-order
        # analyses. Apply only to a sentence that wrongly places a measured
        # *after*-OFF sensor before OFF.
        # Avoid splitting the abbreviation "approx. 69ms" mid-claim.
        fragments = re.split(r"(?<=[.!?])\s+(?=[A-Z*])", line)
        fixed_fragments: list[str] = []
        for part in fragments:
            after_rows = [
                row for row in rows
                if float(row["signedDeltaMs"]) > 0
                and _mentions_sensor(part, str(row["sensor"]))
            ]
            before_asserted = re.search(
                r"(?i)\b(?:before|prior\s+to|preced(?:ed|ing)|earlier\s+than)\b"
                r".{0,36}\b(?:off|turn[- ]off)\b",
                part,
            )
            if (
                after_rows
                and before_asserted
                and not re.search(r"(?i)\bafter\s+(?:the\s+)?(?:off|turn[- ]off)\b", part)
                and ("inactive" in part.casefold() or "motion" in part.casefold())
            ):
                mentioned = [
                    row for row in rows
                    if _mentions_sensor(part, str(row["sensor"]))
                ]
                prefix = (_LIST_MARKER.match(part).group(1) if _LIST_MARKER.match(part) else "")
                part = prefix + _sensor_order_sentence(graph, mentioned)
                changed = True
            fixed_fragments.append(part)
        output.append(" ".join(fixed_fragments) + suffix)
    return "".join(output), changed



_OFF_TRIGGERS = re.compile(
    r"\b(?:turn[- ]off|turning\s+off|turned\s+off|switch[- ]off|"
    r"switching\s+off|switched\s+off|off\s+(?:event|transition|action))\b",
    re.I,
)
_SENSOR_INPUT = re.compile(
    r"\b(?:motion|occupancy|presence|sensor|inactiv\w*)\b", re.I
)
_CAUSAL_ASSERTION = re.compile(
    r"\b(?:trigger(?:ed|ing|s)?|caus(?:e|ed|ing|es)|initiated?|"
    r"because|responsible|result(?:ed|ing)?\s+(?:from|in)|due\s+to)\b",
    re.I,
)
_SPECULATIVE_LINK = re.compile(
    r"\b(?:likely|probably|most\s+likely|high(?:ly)?\s+confidence|"
    r"consistent)\b", re.I,
)


def guard_off_trigger_attribution(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
    *, graph: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """An OFF-edge sensor correlation is not an OFF automation trigger.

    Even a verified app-issued off() identifies the direct producer, *not*
    the internal timer or upstream motion edge. Preserve the user's ON
    attribution and already-cautious OFF hypotheses. A specific confirmed
    log/decision receipt may later set internalTimerExecutionVerified=true.
    """
    text = str(message or "")
    graph = graph if graph is not None else _graph(evidence, original_user)
    off = (graph.get("transitionEvidence") or {}).get("off") or {}
    if not off.get("observed") or off.get("internalTimerExecutionVerified"):
        return text, False
    corrected: list[str] = []
    changed = False
    for raw in text.splitlines(keepends=True):
        newline = "\n" if raw.endswith("\n") else ""
        line = raw[:-1] if newline else raw
        if (
            _OFF_TRIGGERS.search(line)
            and _SENSOR_INPUT.search(line)
            and _CAUSAL_ASSERTION.search(line)
            and not re.search(
                r"\b(?:not\s+(?:established|verified|confirmed|proven)"
                r"|cannot\s+(?:confirm|prove)|unverified|unknown)\b",
                line, re.I,
            )
        ):
            # Preserve a table's metadata (e.g. Likely | Detail) and the
            # original list formatting. Only replace the unsupported
            # free-text causal attribution with an evidence-scoped statement.
            result = (
                "The OFF transition occurred near sensor inactivity, but "
                "the sensor/timer trigger is unverified"
                + (
                    " and the OFF command producer is unidentified."
                    if off.get("directCommand") is None else "."
                )
            )
            if "|" in line and line.strip().startswith("|"):
                parts = line.split("|")
                for i in range(1, len(parts) - 1):
                    if (
                        _OFF_TRIGGERS.search(parts[i]) or
                        (_SENSOR_INPUT.search(parts[i]) and _CAUSAL_ASSERTION.search(parts[i]))
                    ):
                        parts[i] = f" {result} "
                line = "|".join(parts)
            else:
                prefix_match = _LIST_MARKER.match(line)
                prefix = prefix_match.group(1) if prefix_match else ""
                line = prefix + result
            changed = True
        corrected.append(line + newline)
    return "".join(corrected), changed


def verify_causal_claims(
    message: str,
    evidence: list[dict[str, Any]],
    original_user: str = "",
) -> tuple[str, list[str]]:
    """One shared validation boundary for all three source/claim relations."""
    corrected = str(message or "")
    graph = _graph(evidence, original_user)
    issues: list[str] = []
    for checker, code in (
        (guard_causal_action_ownership, "causal_action_ownership"),
        (guard_causal_empty_log_inference, "causal_empty_log_inference"),
        (guard_causal_sensor_event_order, "causal_sensor_event_order"),
        (guard_off_trigger_attribution, "causal_off_trigger_overclaim"),
    ):
        corrected, changed = checker(
            corrected, evidence, original_user, graph=graph
        )
        if changed:
            issues.append(code)
    corrected, changed = guard_off_certainty_contract(
        corrected, graph, original_user
    )
    if changed:
        issues.append("causal_off_certainty_contract")
    corrected, changed = guard_off_hypothesis_summary(corrected, graph)
    if changed:
        issues.append("off_hypothesis_summary")
    corrected, changed = guard_causal_answer_claim_boundaries(
        corrected, graph, original_user
    )
    if changed:
        issues.append("causal_answer_claim_boundaries")
    corrected, changed = guard_unproven_on_button_initiation(corrected, graph)
    if changed:
        issues.append("causal_on_button_initiation_not_proven")
    # Mathematical status glyphs should be readable as literal text in the
    # HomeBrain UI, which renders a Markdown subset rather than MathJax.
    for marker, symbol in (
        (r"$\times$", "✗"), (r"$\checkmark$", "✓"), (r"$\sim$", "~")
    ):
        if marker in corrected:
            corrected = corrected.replace(marker, symbol)
            issues.append("unsupported_math_status_notation")
    corrected, changed = guard_history_gap_claims(corrected, graph)
    if changed:
        issues.append("causal_history_gap_claims")
    corrected, changed = guard_sensor_history_source_contradiction(
        corrected, graph
    )
    if changed:
        issues.append("archived_sensor_not_absent")
    return corrected, issues


__all__ = [
    "guard_causal_action_ownership",
    "guard_causal_empty_log_inference",
    "guard_causal_sensor_event_order",
    "guard_off_trigger_attribution",
    "verify_causal_claims",
]
