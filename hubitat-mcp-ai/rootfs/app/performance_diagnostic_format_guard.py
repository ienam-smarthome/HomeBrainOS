"""Format-independent evidence guard for adaptive performance diagnostics.

0.16.85 consolidates the presentation boundary around structured evidence:
child diagnostic fields are recognized by semantic role rather than exact label
text, and timing statements are rendered atomically from one host timing record
so a source/signal can never inherit another signal's cadence numbers.

0.16.86 distinguishes the kind of diagnostic signal before allowing a hypothesis:
explicit timeouts/reachability failures can support a calibrated connectivity/failure
hypothesis, while WARN-level multi-second/minute method durations support a
stalled/excessively-long-running-operation hypothesis. Neither proves the exact
implementation cause or downstream user impact.
"""

from __future__ import annotations

import html
import re
from typing import Any

from performance_diagnostic_evidence_gate import classify_adaptive_diagnostics


_MARKDOWN_HEADING = re.compile(r"^\s*#{2,6}\s+(?P<title>.+?)\s*$")
_BOLD_SECTION = re.compile(r"^\s*\*\*(?P<title>[^*]+?)\*\*\s*$")
_NUMBERED_ENTITY_TITLE = re.compile(r"^\s*\d+[.)]\s+.+$")
_BULLET_LABEL = re.compile(
    r"^(?P<prefix>\s*[-*+]\s+)\*\*(?P<label>[^*]+?)\*\*(?::)?\s*(?P<body>.*)$"
)
_NUMBERED_LABEL = re.compile(
    r"^(?P<prefix>\s*\d+[.)]\s+)\*\*(?P<label>[^*]+?)\*\*(?::)?\s*(?P<body>.*)$"
)
_INFERENCE_LANGUAGE = re.compile(
    r"(?i)\b(?:suggests?|indicates?|consistent\s+with|likely|possibly|possible\s+|"
    r"may\s+be\s+due\s+to|could\s+be\s+due\s+to|appears\s+to\s+be|points?\s+to)\b"
)
_CADENCE_CLAIM = re.compile(
    r"(?i)\b(?:recurring|regular(?:ly)?|consistent(?:ly)?|cadence|"
    r"every\s+\d+(?:\.\d+)?(?:\s*(?:-|to)\s*\d+(?:\.\d+)?)?\s*(?:seconds?|minutes?|hours?))\b"
)
_MECHANISM_LANGUAGE = re.compile(
    r"(?i)\b(?:network\s+latency|device\s+communication|response\s+times?|polling|"
    r"state\s+updates?|blocking|worker\s+threads?|timeout|timed\s+out|connectivity|"
    r"unreachable|api\s+latency|stalled\s+i/?o|driver\s+defect)\b"
)
_MECHANISM_ACTION = re.compile(
    r"(?i)\b(?:inspect|check|change|increase|reduce|lengthen|shorten|tune|adjust|review)\b[^\n]{0,160}\b"
    r"(?:network\s+connectivity|driver\s+settings?|poll(?:ing)?\s+interval|timeout|retries?|"
    r"api\s+response|api\s+response\s+logs?|mdns|vlan|dhcp)\b"
)
_FALSE_NO_SCOPED_EVIDENCE = re.compile(
    r"(?i)\bno\s+target-scoped\s+diagnostic\s+evidence\s+was\s+read\b"
)
_COLLECT_SCOPED_EVIDENCE = re.compile(r"(?i)\bcollect\s+target-scoped\s+diagnostic\s+evidence\b")
_PER_SECOND_RATE = re.compile(
    r"(?i)\b(?P<count>\d+)\s+(?:events?|updates?|rows?)\s+per\s+second\b"
)
_SIMULTANEOUS_REPORTING = re.compile(r"(?i)\bsimultaneous(?:ly)?\s+reporting\b")
_SIMULTANEOUS = re.compile(r"(?i)\bsimultaneously\b")
_MEMORY_TRIGGER_PROMOTION = re.compile(
    r"(?i)(?:\btriggered?\b|\bfired\b|\bactivated\b)[^\n]{0,120}\blow\s+memory\b|"
    r"\blow\s+memory\b[^\n]{0,120}(?:\btriggered?\b|\bfired\b|\bactivated\b)"
)
_MEMORY_EVENT = re.compile(
    r"(?i)^app\|(?P<id>\d+)\|(?P<name>[^|]*low\s+memory[^|]*)\|"
    r"Event:\s*[^|]*?freeMemory\s+(?P<value>\d+(?:\.\d+)?)"
)


def _normalize_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").casefold())
    stop = {
        "the", "and", "settings", "configuration", "activity", "latency",
        "performance", "device", "app", "diagnostic", "hypothesis", "tv",
        "resource", "usage", "execution", "time",
    }
    return {word for word in words if len(word) > 1 and word not in stop}


def _match_target(text: str, targets: list[dict[str, Any]]) -> dict[str, Any] | None:
    text_words = _normalize_words(text)
    best: tuple[int, dict[str, Any]] | None = None
    for target in targets:
        name_words = _normalize_words(str(target.get("name") or ""))
        if not name_words:
            continue
        overlap = len(text_words & name_words)
        required = 1 if len(name_words) <= 2 else 2
        if overlap < required:
            continue
        if best is None or overlap > best[0]:
            best = (overlap, target)
    return best[1] if best else None


def _line_label(line: str) -> tuple[str, str, str] | None:
    for pattern in (_BULLET_LABEL, _NUMBERED_LABEL):
        match = pattern.match(line)
        if match:
            label = match.group("label").strip().rstrip(":").strip()
            return match.group("prefix"), label, match.group("body")
    return None


def _render_with_label(line: str, body: str) -> str:
    parsed = _line_label(line)
    if parsed is None:
        prefix_match = re.match(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+)?)", line)
        prefix = prefix_match.group(1) if prefix_match else ""
        return prefix + body
    prefix, label, _ = parsed
    return f"{prefix}**{label}:** {body}"


def _child_role(label: str) -> str | None:
    """Map free-form model labels to stable diagnostic field roles."""

    folded = re.sub(r"[^a-z0-9]+", " ", str(label or "").casefold()).strip()
    if not folded:
        return None
    if "next step" in folded:
        return "action"
    if "verification" in folded or "verify" in folded:
        return "verification"
    if "evidence" in folded:
        return "evidence"
    if "finding" in folded:
        return "finding"
    if "conclusion" in folded:
        return "conclusion"
    if "interpretation" in folded:
        return "interpretation"
    if "hypothesis" in folded:
        return "hypothesis"
    if "action" in folded:
        return "action"
    return None


def _fmt_seconds(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    rendered = f"{number:.3f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _timing_facts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        if not isinstance(details, dict):
            continue
        timing = details.get("hostDerivedTiming")
        if not isinstance(timing, dict):
            continue
        raw = timing.get("cadence")
        if isinstance(raw, list):
            facts.extend(item for item in raw if isinstance(item, dict))
    return facts


def _regular_cadence_facts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        fact
        for fact in _timing_facts(evidence)
        if str(fact.get("timingKind") or "").casefold() == "regular_cadence"
        or fact.get("regularCadence") is True
    ]


def _match_timing_fact(text: str, facts: list[dict[str, Any]]) -> dict[str, Any] | None:
    folded = str(text or "").casefold()
    matches: list[dict[str, Any]] = []
    for fact in facts:
        source = str(fact.get("source") or "").strip().casefold()
        signal = str(fact.get("signal") or "").strip().casefold()
        if source and source in folded and (not signal or signal in folded):
            matches.append(fact)
    return matches[0] if len(matches) == 1 else None


def _render_timing_fact(fact: dict[str, Any]) -> str:
    source = str(fact.get("source") or "").strip()
    signal = str(fact.get("signal") or "").strip()
    subject = " ".join(part for part in (source, signal) if part).strip() or "Observed signal"
    kind = str(fact.get("timingKind") or "").casefold()
    if kind == "regular_cadence" or fact.get("regularCadence") is True:
        median = _fmt_seconds(fact.get("medianIntervalSeconds"))
        minimum = _fmt_seconds(fact.get("minIntervalSeconds"))
        maximum = _fmt_seconds(fact.get("maxIntervalSeconds"))
        approx = fact.get("approxCadenceSeconds")
        approx_text = _fmt_seconds(approx if approx is not None else fact.get("medianIntervalSeconds"))
        return (
            f"{subject} — Regular cadence; median interval {median} seconds; approximately every "
            f"{approx_text} seconds; observed range {minimum}–{maximum} seconds."
        )
    if kind == "irregular_intervals":
        median = _fmt_seconds(fact.get("medianIntervalSeconds"))
        minimum = _fmt_seconds(fact.get("minIntervalSeconds"))
        maximum = _fmt_seconds(fact.get("maxIntervalSeconds"))
        return (
            f"{subject} — Irregular observed intervals; median {median} seconds; observed range "
            f"{minimum}–{maximum} seconds. No regular cadence was established."
        )
    if kind == "observed_gap":
        gap = _fmt_seconds(fact.get("observedGapSeconds"))
        return f"{subject} — Single observed gap of {gap} seconds; no recurring cadence is established."
    return subject


def _diagnostic_signal_text(target: dict[str, Any]) -> tuple[str, str]:
    failures = [str(item) for item in target.get("failureSignals") or [] if str(item)]
    long_count = int(target.get("longCallCount") or 0)
    long_min = target.get("longCallMinMs")
    long_max = target.get("longCallMaxMs")
    warn_count = int(target.get("longCallWarnCount") or 0)
    parts = list(failures)
    if long_count and long_min not in (None, "") and long_max not in (None, ""):
        level = "WARN/ERROR " if warn_count else ""
        parts.append(f"{level}very long operation durations {long_min}–{long_max} ms")
    signal_text = ", ".join(dict.fromkeys(parts)) or "an explicit diagnostic signal"
    if long_count and not failures:
        hypothesis = "a calibrated stalled/excessively-long-running-operation hypothesis"
    elif failures and not long_count:
        hypothesis = "a calibrated connectivity/failure hypothesis"
    else:
        hypothesis = "a calibrated hypothesis consistent with the observed failure and long-operation signals"
    return signal_text, hypothesis


def _evidence_summary(target: dict[str, Any]) -> str:
    count = int(target.get("logCount") or 0)
    window = str(target.get("requestedWindow") or "the requested window")
    classification = str(target.get("classification") or "")
    activity = str(target.get("activityLabel") or "repeated scoped activity")
    if classification == "diagnostic_signal":
        signal_text, hypothesis = _diagnostic_signal_text(target)
        return (
            f"The scoped diagnostic read returned {count} log rows in {window}, including "
            f"explicit diagnostic signal(s): {signal_text}. These observations support {hypothesis}, "
            "but do not prove the exact implementation mechanism, worker-thread blocking, network cause, "
            "or how much the signal contributes to the measured performance statistics."
        )
    if classification == "repeated_activity":
        cadence = (
            "Host-derived timing established a regular cadence for this target."
            if target.get("hasRegularCadence")
            else "No host-derived regular cadence was established for this target."
        )
        return (
            f"The scoped diagnostic read returned {count} log rows in {window}, including repeated "
            f"`{activity}` activity. {cadence} The repeated observations do not establish that this "
            "activity caused the measured performance statistics or reveal the implementation mechanism."
        )
    if classification in {"sparse_or_neutral", "no_observations"}:
        return (
            f"The target-scoped diagnostic read returned {count} non-diagnostic log observation(s) "
            "and did not establish a mechanism for this measured outlier; the mechanism remains unresolved."
        )
    return f"The scoped diagnostic read returned {count} log rows in {window}."


def _diagnostic_interpretation(target: dict[str, Any]) -> str:
    classification = str(target.get("classification") or "")
    if classification == "diagnostic_signal":
        return _evidence_summary(target)
    if classification == "repeated_activity":
        activity = str(target.get("activityLabel") or "repeated scoped activity")
        return (
            f"The scoped logs show repeated `{activity}` activity, but they do not establish that "
            "this activity caused the measured performance statistics or reveal the implementation mechanism."
        )
    if classification in {"sparse_or_neutral", "no_observations"}:
        return _evidence_summary(target)
    return ""


def _same_second_clusters(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        timing = details.get("hostDerivedTiming") if isinstance(details, dict) else None
        raw = timing.get("sameSecondClusters") if isinstance(timing, dict) else None
        if isinstance(raw, list):
            clusters.extend(item for item in raw if isinstance(item, dict))
    return clusters


def _memory_event_facts(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        logs = details.get("logs") if isinstance(details, dict) else None
        if not isinstance(logs, list):
            continue
        for item in logs:
            if not isinstance(item, dict):
                continue
            match = _MEMORY_EVENT.search(html.unescape(str(item.get("message") or "")))
            if match:
                facts.append({"appId": match.group("id"), "name": match.group("name"), "value": match.group("value")})
    return facts


def guard_format_independent_performance_diagnostics(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Enforce adaptive evidence boundaries without depending on model formatting."""

    original = str(message or "")
    if not original:
        return original, False

    targets = classify_adaptive_diagnostics(evidence)
    timing_facts = _timing_facts(evidence)
    regular_cadence = _regular_cadence_facts(evidence)
    clusters = _same_second_clusters(evidence)
    cluster_counts = {int(item.get("rowCount") or 0) for item in clusters}
    memory_facts = _memory_event_facts(evidence)

    in_diagnostics = False
    in_recommendations = False
    current_target: dict[str, Any] | None = None
    output: list[str] = []

    for raw_line in original.splitlines(keepends=True):
        newline = "\n" if raw_line.endswith("\n") else ""
        line = raw_line[:-1] if newline else raw_line

        markdown_heading = _MARKDOWN_HEADING.match(line)
        bold_heading = _BOLD_SECTION.match(line)
        heading = markdown_heading or bold_heading
        if heading:
            title = heading.group("title").strip()
            numbered_entity_heading = bool(bold_heading is not None and _NUMBERED_ENTITY_TITLE.match(title))
            if numbered_entity_heading:
                current_target = _match_target(title, targets)
            else:
                folded = title.casefold()
                in_diagnostics = "diagnostic" in folded or "hypoth" in folded
                in_recommendations = "recommend" in folded or "next step" in folded or "inspection" in folded
                current_target = None

        parsed = _line_label(line)
        role = _child_role(parsed[1]) if parsed is not None else None
        action_child = role in {"verification", "action"}
        line_target = _match_target(line, targets)
        if parsed is not None:
            if line_target is not None:
                current_target = line_target
            elif role is None:
                current_target = None
        elif line_target is not None:
            current_target = line_target

        candidate = line
        effective_target = line_target or current_target

        if parsed is not None and "cadence" in parsed[1].casefold():
            matched_fact = _match_timing_fact(parsed[2], timing_facts)
            if matched_fact is None and len(regular_cadence) == 1:
                matched_fact = regular_cadence[0]
            if matched_fact is not None:
                candidate = _render_with_label(candidate, _render_timing_fact(matched_fact))

        if effective_target is not None and _FALSE_NO_SCOPED_EVIDENCE.search(candidate):
            body = (
                _diagnostic_interpretation(effective_target)
                if role in {"hypothesis", "conclusion", "interpretation"}
                else _evidence_summary(effective_target)
            )
            candidate = _render_with_label(candidate, body)

        if (
            effective_target is not None
            and not bool(effective_target.get("hasRegularCadence"))
            and _CADENCE_CLAIM.search(candidate)
        ):
            candidate = _render_with_label(candidate, _evidence_summary(effective_target))

        if (
            in_diagnostics
            and not action_child
            and (_INFERENCE_LANGUAGE.search(candidate) or _MECHANISM_LANGUAGE.search(candidate))
        ):
            if effective_target is None:
                candidate = _render_with_label(
                    candidate,
                    "No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved.",
                )
            else:
                interpretation = _diagnostic_interpretation(effective_target)
                if interpretation:
                    candidate = _render_with_label(candidate, interpretation)

        if action_child and effective_target is not None and _COLLECT_SCOPED_EVIDENCE.search(candidate):
            classification = str(effective_target.get("classification") or "")
            if classification == "diagnostic_signal":
                failures = bool(effective_target.get("failureSignals"))
                long_calls = int(effective_target.get("longCallCount") or 0)
                if long_calls and not failures:
                    action = (
                        "Use the existing scoped long-operation evidence to correlate the WARN timestamps "
                        "with the integration/driver execution path and identify which operation is stalled; "
                        "do not assume a network cause without separate connectivity evidence."
                    )
                elif failures:
                    action = (
                        "Use the existing scoped failure evidence to verify reachability/recovery and correlate "
                        "those failure timestamps with app/device executions before attributing the measured "
                        "performance percentage to the failures."
                    )
                else:
                    action = "Use the existing scoped diagnostic evidence before choosing a mechanism-specific investigation."
                candidate = _render_with_label(candidate, action)
            elif classification in {"repeated_activity", "sparse_or_neutral"}:
                candidate = _render_with_label(
                    candidate,
                    "The target was already scoped in this turn; inspect a different evidence source only if a mechanism-specific conclusion is still required.",
                )

        if (in_recommendations or in_diagnostics) and _MECHANISM_ACTION.search(candidate):
            if effective_target is None or str(effective_target.get("classification") or "") in {"sparse_or_neutral", "no_observations"}:
                candidate = _render_with_label(
                    candidate,
                    "Collect target-scoped diagnostic evidence for this outlier before choosing a mechanism-specific network, driver, polling, retry, timeout, or API investigation.",
                )

        def _rate_replacement(match: re.Match[str]) -> str:
            count = int(match.group("count"))
            return f"{count} log rows observed within one reported second" if count in cluster_counts else match.group(0)

        if cluster_counts:
            candidate = _PER_SECOND_RATE.sub(_rate_replacement, candidate)
            candidate = _SIMULTANEOUS_REPORTING.sub("same-second clustered reporting", candidate)
            candidate = _SIMULTANEOUS.sub("within the same reported second", candidate)

        if memory_facts and _MEMORY_TRIGGER_PROMOTION.search(candidate):
            fact = memory_facts[0]
            candidate = _render_with_label(
                candidate,
                f"The current log row shows app {fact['appId']} processing/logging a freeMemory event of {fact['value']} MB; it does not establish that its <200MB condition evaluated true or that an alert action fired.",
            )

        output.append(candidate + newline)

    corrected = "".join(output)
    return corrected, corrected != original


__all__ = ["guard_format_independent_performance_diagnostics"]
