"""Format-independent evidence guard for adaptive performance diagnostics.

0.16.82 introduced adaptive evidence classification, but its validator still
expected model prose to use numbered diagnostic headings. 0.16.83 made the gate
format-independent; 0.16.84 preserves diagnostic section/target context across
numbered entity subheadings and child fields such as Evidence and Verification.
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
_CHILD_LABELS = {
    "finding",
    "evidence",
    "conclusion",
    "diagnostic interpretation",
    "diagnostic hypothesis",
    "hypothesis",
    "verification",
    "action",
    "next step",
    "recommended action",
}
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
        name = str(target.get("name") or "")
        name_words = _normalize_words(name)
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


def _evidence_summary(target: dict[str, Any]) -> str:
    count = int(target.get("logCount") or 0)
    window = str(target.get("requestedWindow") or "the requested window")
    classification = str(target.get("classification") or "")
    activity = str(target.get("activityLabel") or "repeated scoped activity")
    if classification == "repeated_activity":
        cadence = (
            "Host-derived timing established a regular cadence for this target."
            if target.get("hasRegularCadence")
            else "No host-derived regular cadence was established for this target."
        )
        return (
            f"The scoped diagnostic read returned {count} log rows in {window}, including "
            f"repeated `{activity}` activity. {cadence} The repeated observations do not "
            "establish that this activity caused the measured performance statistics or "
            "reveal the implementation mechanism."
        )
    return f"The scoped diagnostic read returned {count} log rows in {window}."


def _diagnostic_interpretation(target: dict[str, Any]) -> str:
    classification = str(target.get("classification") or "")
    count = int(target.get("logCount") or 0)
    activity = str(target.get("activityLabel") or "repeated scoped activity")
    if classification == "repeated_activity":
        return (
            f"The scoped logs show repeated `{activity}` activity, but they do not establish "
            "that this activity caused the measured performance statistics or reveal the "
            "implementation mechanism."
        )
    if classification in {"sparse_or_neutral", "no_observations"}:
        return (
            f"The target-scoped diagnostic read returned {count} non-diagnostic log "
            "observation(s) and did not establish a mechanism for this measured outlier; "
            "the mechanism remains unresolved."
        )
    return ""


def _same_second_clusters(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        if not isinstance(details, dict):
            continue
        timing = details.get("hostDerivedTiming")
        if not isinstance(timing, dict):
            continue
        raw = timing.get("sameSecondClusters")
        if isinstance(raw, list):
            clusters.extend(item for item in raw if isinstance(item, dict))
    return clusters


def _regular_cadence_facts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        if not isinstance(details, dict):
            continue
        timing = details.get("hostDerivedTiming")
        if not isinstance(timing, dict):
            continue
        cadence = timing.get("cadence")
        if not isinstance(cadence, list):
            continue
        for fact in cadence:
            if not isinstance(fact, dict):
                continue
            if str(fact.get("timingKind") or "").casefold() == "regular_cadence" or fact.get("regularCadence") is True:
                facts.append(fact)
    return facts


def _memory_event_facts(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        if not isinstance(details, dict):
            continue
        logs = details.get("logs")
        if not isinstance(logs, list):
            continue
        for item in logs:
            if not isinstance(item, dict):
                continue
            raw = html.unescape(str(item.get("message") or ""))
            match = _MEMORY_EVENT.search(raw)
            if not match:
                continue
            facts.append({
                "appId": match.group("id"),
                "name": match.group("name"),
                "value": match.group("value"),
            })
    return facts


def _is_child_label(label: str) -> bool:
    return str(label or "").strip().casefold() in _CHILD_LABELS


def guard_format_independent_performance_diagnostics(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Enforce adaptive evidence boundaries without depending on Markdown shape."""

    original = str(message or "")
    if not original:
        return original, False

    targets = classify_adaptive_diagnostics(evidence)
    clusters = _same_second_clusters(evidence)
    cluster_counts = {int(item.get("rowCount") or 0) for item in clusters}
    regular_cadence = _regular_cadence_facts(evidence)
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
        numbered_entity_heading = False
        if heading:
            title = heading.group("title").strip()
            numbered_entity_heading = bool(
                bold_heading is not None and _NUMBERED_ENTITY_TITLE.match(title)
            )
            if numbered_entity_heading:
                # This is an entity block inside the enclosing section, not a new
                # section. Preserve diagnostic/recommendation mode, but bind (or
                # explicitly clear) the scoped target for this entity.
                current_target = _match_target(title, targets)
            else:
                folded = title.casefold()
                in_diagnostics = "diagnostic" in folded or "hypoth" in folded
                in_recommendations = (
                    "recommend" in folded or "next step" in folded or "inspection" in folded
                )
                current_target = None

        parsed = _line_label(line)
        line_target = _match_target(line, targets)
        if parsed is not None:
            _, label, _ = parsed
            if line_target is not None:
                current_target = line_target
            elif not _is_child_label(label):
                # A non-child labeled line starts a new subject. If it does not map
                # to one of the scoped adaptive targets, clear inherited context so
                # an unscoped entity cannot borrow the previous entity's evidence.
                current_target = None
            # Child fields (Finding/Evidence/Verification/...) inherit current_target
            # unless they explicitly name a different target.
        elif line_target is not None:
            current_target = line_target

        candidate = line
        effective_target = line_target or current_target

        # If there is exactly one host-established regular cadence, attribute a
        # generic Cadence line to that source/signal rather than leaving it anonymous.
        if parsed is not None and parsed[1].strip().casefold() == "cadence" and len(regular_cadence) == 1:
            fact = regular_cadence[0]
            source = str(fact.get("source") or "").strip()
            signal = str(fact.get("signal") or "").strip()
            if source and source.casefold() not in candidate.casefold():
                attribution = " ".join(part for part in (source, signal) if part).strip()
                body = parsed[2].strip()
                candidate = _render_with_label(candidate, f"{attribution} — {body}")

        # Adaptive cadence is an evidence property, not a prose-section property.
        # Apply this anywhere the answer describes or inherits a scoped target.
        if (
            effective_target is not None
            and not bool(effective_target.get("hasRegularCadence"))
            and _CADENCE_CLAIM.search(candidate)
        ):
            candidate = _render_with_label(candidate, _evidence_summary(effective_target))

        # Diagnostic inference is entity/evidence gated even when Gemma emits one
        # inline bullet rather than numbered subheadings.
        if in_diagnostics and (_INFERENCE_LANGUAGE.search(candidate) or _MECHANISM_LANGUAGE.search(candidate)):
            if effective_target is None:
                candidate = _render_with_label(
                    candidate,
                    "No target-scoped diagnostic evidence was read for this outlier in this turn, "
                    "so the mechanism remains unresolved.",
                )
            else:
                classification = str(effective_target.get("classification") or "")
                if classification in {"repeated_activity", "sparse_or_neutral", "no_observations"}:
                    candidate = _render_with_label(
                        candidate,
                        _diagnostic_interpretation(effective_target),
                    )

        # A mechanism-specific recommendation/verification also needs target-scoped
        # support. Combined headings such as "Diagnostic Hypotheses & Recommendations"
        # intentionally set both modes; child Verification lines inherit that mode.
        if (in_recommendations or in_diagnostics) and _MECHANISM_ACTION.search(candidate):
            if effective_target is None or str(effective_target.get("classification") or "") in {
                "sparse_or_neutral", "no_observations"
            }:
                candidate = _render_with_label(
                    candidate,
                    "Collect target-scoped diagnostic evidence for this outlier before choosing "
                    "a mechanism-specific network, driver, polling, retry, timeout, or API investigation.",
                )

        # One observed same-second cluster is not a recurring events/second rate.
        def _rate_replacement(match: re.Match[str]) -> str:
            count = int(match.group("count"))
            if count in cluster_counts:
                return f"{count} log rows observed within one reported second"
            return match.group(0)

        if cluster_counts:
            candidate = _PER_SECOND_RATE.sub(_rate_replacement, candidate)
            candidate = _SIMULTANEOUS_REPORTING.sub("same-second clustered reporting", candidate)
            candidate = _SIMULTANEOUS.sub("within the same reported second", candidate)

        # A log row whose app name contains a threshold label and whose payload says
        # Event: freeMemory <value> proves event processing/logging, not that the
        # threshold condition evaluated true or an alert action fired.
        if memory_facts and _MEMORY_TRIGGER_PROMOTION.search(candidate):
            fact = memory_facts[0]
            candidate = _render_with_label(
                candidate,
                f"The current log row shows app {fact['appId']} processing/logging a freeMemory "
                f"event of {fact['value']} MB; it does not establish that its <200MB condition "
                "evaluated true or that an alert action fired.",
            )

        output.append(candidate + newline)

    corrected = "".join(output)
    return corrected, corrected != original


__all__ = ["guard_format_independent_performance_diagnostics"]
