"""Evidence-aware gate for adaptive performance diagnostic conclusions.

0.16.81 proved that bounded source-scoped follow-up reads can cheaply deepen a
performance review. This module makes the result of those reads authoritative:
scoped evidence may support a calibrated hypothesis, repeated neutral activity may
support an observed-pattern interpretation, and sparse/no diagnostic evidence must
remain explicitly unresolved rather than inviting a plausible model guess.

0.16.86 also treats Hubitat's comma-formatted execution durations (for example
``166,621ms``) as numeric long-call evidence instead of silently classifying those
WARN rows as neutral observations.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any


_SCOPE_SOURCE = re.compile(r"^(?P<kind>app|dev)\|(?P<id>[^|]+)\|(?P<name>[^|]+)\|")
_NUMBERED_BOLD_HEADING = re.compile(r"^\s*\*\*\s*\d+[.)]?\s*(?P<title>.+?)\s*\*\*\s*$")
_MARKDOWN_HEADING = re.compile(r"^\s*#{2,6}\s+(?P<title>.+?)\s*$")
_HYPOTHESIS_LINE = re.compile(r"(?i)\*\*hypothesis:\*\*|\bhypothesis:\s*")
_EVIDENCE_LINE = re.compile(r"(?i)\*\*evidence:\*\*|\bevidence:\s*")
_CADENCE_LANGUAGE = re.compile(
    r"(?i)\b(?:consistently|regular(?:ly)?|cadence|frequency|every\s+\d+(?:\.\d+)?\s*(?:seconds?|minutes?|hours?))\b"
)
_MECHANISM_LANGUAGE = re.compile(
    r"(?i)\b(?:network\s+latency|slow\s+response|polling|state\s+updates?|blocking|worker\s+threads?|"
    r"timeout|timed\s+out|connectivity|unreachable|api\s+latency|stalled\s+i/?o|driver\s+defect)\b"
)
_FAILURE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bno\s+route\s+to\s+host\b"), "no route to host"),
    (re.compile(r"(?i)\bconnection\s+refused\b"), "connection refused"),
    (re.compile(r"(?i)\bconnection\s+reset\b"), "connection reset"),
    (re.compile(r"(?i)\b(?:timed\s*out|timeout)\b"), "timeout"),
    (re.compile(r"(?i)\bhttp\s*408\b"), "HTTP 408"),
    (re.compile(r"(?i)\bunreachable\b"), "unreachable"),
    (re.compile(r"(?i)\bfailed\s+to\s+(?:connect|reach|open|confirm|play)\b"), "failed operation"),
)
_LONG_CALL = re.compile(
    r"(?i)\b(?:completed|took|elapsed|duration|runq|setvolume)[^\n]{0,120}?\b"
    r"(?P<ms>(?:\d{1,3}(?:,\d{3})+|\d{4,}))\s*ms\b"
)
_SIMULTANEOUS_REPORTING = re.compile(r"(?i)\bsimultaneous(?:ly)?\s+reporting\b")
_SIMULTANEOUS = re.compile(r"(?i)\bsimultaneously\b")
_HIGHEST_RESOURCE_USAGE = re.compile(r"(?i)highest\s+resource\s+usage")
_HIGH_AVERAGE_EXECUTION = re.compile(r"(?i)\bhigh\s+average\s+execution\s+time\b")


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def _inner_args(row: dict[str, Any]) -> dict[str, Any]:
    arguments = row.get("arguments")
    arguments = arguments if isinstance(arguments, dict) else {}
    inner = arguments.get("args")
    return inner if isinstance(inner, dict) else arguments


def _raw_logs(row: dict[str, Any]) -> list[dict[str, Any]]:
    details = row.get("details")
    if not isinstance(details, dict):
        return []
    logs = details.get("logs")
    if not isinstance(logs, list):
        return []
    return [item for item in logs if isinstance(item, dict)]


def _target_name(logs: list[dict[str, Any]], *, scope_kind: str, scope_id: str) -> str:
    expected = "dev" if scope_kind == "device" else "app"
    names: Counter[str] = Counter()
    for item in logs:
        raw = str(item.get("message") or "")
        match = _SCOPE_SOURCE.match(raw)
        if match is None:
            continue
        if match.group("kind") != expected or match.group("id") != scope_id:
            continue
        name = " ".join(match.group("name").split()).strip()
        if name:
            names[name] += 1
    return names.most_common(1)[0][0] if names else ""


def _detail(raw_message: str) -> str:
    parts = str(raw_message or "").split("|", 3)
    return " ".join((parts[3] if len(parts) == 4 else str(raw_message or "")).split())


def _activity_signature(detail: str, target_name: str) -> str:
    text = str(detail or "")
    if target_name and text.casefold().startswith(target_name.casefold()):
        text = text[len(target_name) :].strip(" :-")
    text = re.sub(r"https?://\S+", "<endpoint>", text, flags=re.I)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "#", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:180]


def _activity_label(logs: list[dict[str, Any]], target_name: str) -> tuple[str, int]:
    signatures: Counter[str] = Counter()
    for item in logs:
        signature = _activity_signature(_detail(str(item.get("message") or "")), target_name)
        if signature:
            signatures[signature] += 1
    if not signatures:
        return "", 0
    signature, count = signatures.most_common(1)[0]
    readable = signature.replace("<endpoint>", "endpoint").replace("#", "value")
    return readable, count


def _timing_for_scope(row: dict[str, Any], *, scope_kind: str, scope_id: str) -> list[dict[str, Any]]:
    details = row.get("details")
    if not isinstance(details, dict):
        return []
    timing = details.get("hostDerivedTiming")
    if not isinstance(timing, dict):
        return []
    cadence = timing.get("cadence")
    if not isinstance(cadence, list):
        return []
    prefix = "dev" if scope_kind == "device" else "app"
    expected = f"{prefix}|{scope_id}"
    return [
        fact
        for fact in cadence
        if isinstance(fact, dict) and str(fact.get("sourceRef") or "") == expected
    ]


def classify_adaptive_diagnostics(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify each successful adaptive log receipt by what it can establish."""

    targets: list[dict[str, Any]] = []
    for row in evidence:
        if (
            not isinstance(row, dict)
            or row.get("success") is False
            or str(row.get("evidence_kind") or "") != "host_planned_performance_diagnostic"
            or _sub_tool(row) != "hub_get_logs"
        ):
            continue
        inner = _inner_args(row)
        if inner.get("deviceId") not in (None, ""):
            scope_kind = "device"
            scope_id = str(inner.get("deviceId"))
        elif inner.get("appId") not in (None, ""):
            scope_kind = "app"
            scope_id = str(inner.get("appId"))
        else:
            continue
        logs = _raw_logs(row)
        retained_count = len(logs)
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        log_count = int(details.get("logCount") or retained_count)
        name = _target_name(logs, scope_kind=scope_kind, scope_id=scope_id)
        joined = "\n".join(str(item.get("message") or "") for item in logs)
        failure_signals = [label for pattern, label in _FAILURE_PATTERNS if pattern.search(joined)]
        long_calls: list[int] = []
        for match in _LONG_CALL.finditer(joined):
            try:
                value = int(match.group("ms").replace(",", ""))
            except (TypeError, ValueError):
                continue
            if value >= 5000:
                long_calls.append(value)
        label, repeated_count = _activity_label(logs, name)
        timing = _timing_for_scope(row, scope_kind=scope_kind, scope_id=scope_id)
        has_regular_cadence = any(
            str(fact.get("timingKind") or "").casefold() == "regular_cadence"
            or fact.get("regularCadence") is True
            for fact in timing
        )

        if failure_signals or long_calls:
            classification = "diagnostic_signal"
        elif retained_count >= 4 and repeated_count >= max(3, int(retained_count * 0.5)):
            classification = "repeated_activity"
        elif log_count:
            classification = "sparse_or_neutral"
        else:
            classification = "no_observations"

        targets.append(
            {
                "scopeKind": scope_kind,
                "scopeId": scope_id,
                "name": name,
                "classification": classification,
                "logCount": log_count,
                "retainedLogCount": retained_count,
                "activityLabel": label,
                "activityCount": repeated_count,
                "failureSignals": failure_signals,
                "longCallMs": sorted(set(long_calls)),
                "hasRegularCadence": has_regular_cadence,
                "requestedWindow": str(inner.get("since") or ""),
            }
        )
    return targets


def render_diagnostic_evidence_gate(evidence: list[dict[str, Any]]) -> str:
    """Render deterministic per-target conclusion boundaries for synthesis."""

    targets = classify_adaptive_diagnostics(evidence)
    if not targets:
        return (
            "HOST DIAGNOSTIC EVIDENCE GATE\n"
            "No source-scoped adaptive diagnostic receipt is present. Do not state a mechanism hypothesis for an outlier merely from performance statistics; mark the mechanism unresolved and recommend the next targeted evidence read."
        )

    lines = [
        "HOST DIAGNOSTIC EVIDENCE GATE",
        "Treat these classifications as authoritative conclusion boundaries. 'Unresolved' is a valid diagnostic result and must not be filled with a plausible cause.",
    ]
    for target in targets:
        label = target.get("name") or f"{target['scopeKind']}Id={target['scopeId']}"
        classification = target["classification"]
        count = target["logCount"]
        if classification == "diagnostic_signal":
            signals = [*target["failureSignals"]]
            signals.extend(f"very long call {value} ms" for value in target["longCallMs"][:3])
            lines.append(
                f"- {label}: classification=diagnostic_signal; scoped rows={count}; observed signals={', '.join(signals) or 'diagnostic signal'}. A calibrated hypothesis consistent with those observed signals is allowed, but the exact implementation defect, worker-thread blocking, and user-visible delay remain unproven without stronger evidence."
            )
        elif classification == "repeated_activity":
            activity = target.get("activityLabel") or "repeated activity"
            cadence = (
                "A host-derived regular cadence exists and may be quoted exactly."
                if target.get("hasRegularCadence")
                else "No host-derived regular cadence exists for this scoped target; do not invent 'every X' timing from raw rows."
            )
            lines.append(
                f"- {label}: classification=repeated_activity; scoped rows={count}; repeated pattern={activity!r}. The activity pattern may be reported and compared with the measured statistics, but causality and the implementation mechanism remain unproven. {cadence}"
            )
        elif classification == "sparse_or_neutral":
            lines.append(
                f"- {label}: classification=sparse_or_neutral; scoped rows={count}. The targeted read did not reveal a diagnostic mechanism. Do not infer polling, state-update frequency, network/API latency, timeout, blocking, or connectivity from the performance statistic alone. State that the mechanism remains unresolved."
            )
        else:
            lines.append(
                f"- {label}: classification=no_observations; scoped rows=0. The targeted read did not reveal a diagnostic mechanism. State that the mechanism remains unresolved and identify the next evidence source rather than inventing a cause."
            )
    lines.append(
        "Any outlier discussed as a mechanism hypothesis that is not one of the scoped targets above has no target-scoped diagnostic evidence in this turn; its mechanism must be described as unresolved."
    )
    return "\n".join(lines)


def _normalize_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").casefold())
    stop = {"the", "and", "settings", "configuration", "activity", "latency", "performance", "device", "app"}
    return {word for word in words if len(word) > 1 and word not in stop}


def _match_target(title: str, targets: list[dict[str, Any]]) -> dict[str, Any] | None:
    title_words = _normalize_words(title)
    best: tuple[int, dict[str, Any]] | None = None
    for target in targets:
        name = str(target.get("name") or "")
        name_words = _normalize_words(name)
        if not name_words:
            continue
        overlap = len(title_words & name_words)
        required = 1 if len(name_words) <= 2 else 2
        if overlap < required:
            continue
        if best is None or overlap > best[0]:
            best = (overlap, target)
    return best[1] if best else None


def _prefix(line: str) -> str:
    match = re.match(r"^(\s*(?:[-*+]\s+)?)", line)
    return match.group(1) if match else ""


def _evidence_summary(target: dict[str, Any]) -> str:
    count = int(target.get("logCount") or 0)
    window = str(target.get("requestedWindow") or "the requested window")
    activity = str(target.get("activityLabel") or "repeated activity")
    if target.get("classification") == "repeated_activity":
        cadence = (
            "Host-derived timing established a regular cadence for this target."
            if target.get("hasRegularCadence")
            else "No host-derived regular cadence was established for this target."
        )
        return f"The scoped diagnostic read returned {count} log rows in {window}, including repeated `{activity}` activity. {cadence}"
    return f"The scoped diagnostic read returned {count} log rows in {window}."


def guard_performance_diagnostic_hypotheses(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Fail closed when final diagnostic prose outruns adaptive scoped evidence."""

    original = str(message or "")
    if not original:
        return original, False
    targets = classify_adaptive_diagnostics(evidence)
    clusters_present = any(
        isinstance(row, dict)
        and isinstance(row.get("details"), dict)
        and isinstance(row["details"].get("hostDerivedTiming"), dict)
        and bool(row["details"]["hostDerivedTiming"].get("sameSecondClusters"))
        for row in evidence
    )

    in_diagnostics = False
    current_target: dict[str, Any] | None = None
    current_scoped = False
    output: list[str] = []

    for raw_line in original.splitlines(keepends=True):
        newline = "\n" if raw_line.endswith("\n") else ""
        line = raw_line[:-1] if newline else raw_line
        heading = _MARKDOWN_HEADING.match(line)
        if heading:
            title = heading.group("title")
            folded = title.casefold()
            if "diagnostic" in folded and ("hypoth" in folded or "analysis" in folded):
                in_diagnostics = True
                current_target = None
                current_scoped = False
            elif in_diagnostics and not folded.startswith("diagnostic"):
                in_diagnostics = False
                current_target = None
                current_scoped = False

        numbered = _NUMBERED_BOLD_HEADING.match(line)
        if in_diagnostics and numbered:
            title = numbered.group("title")
            current_target = _match_target(title, targets)
            current_scoped = current_target is not None

        candidate = line
        if in_diagnostics and _HYPOTHESIS_LINE.search(candidate):
            if not current_scoped:
                candidate = (
                    f"{_prefix(candidate)}**Conclusion:** No target-scoped diagnostic evidence was read for this outlier in this turn, so the mechanism remains unresolved."
                )
            elif current_target is not None:
                classification = str(current_target.get("classification") or "")
                if classification in {"sparse_or_neutral", "no_observations"}:
                    count = int(current_target.get("logCount") or 0)
                    candidate = (
                        f"{_prefix(candidate)}**Conclusion:** The target-scoped diagnostic read returned {count} non-diagnostic log observation(s) and did not establish a mechanism for this measured outlier; the mechanism remains unresolved."
                    )
                elif classification == "repeated_activity":
                    activity = str(current_target.get("activityLabel") or "repeated activity")
                    candidate = (
                        f"{_prefix(candidate)}**Diagnostic interpretation:** The scoped logs show repeated `{activity}` activity, but they do not establish that this activity caused the measured performance statistics or reveal the implementation mechanism."
                    )

        if (
            in_diagnostics
            and current_target is not None
            and _EVIDENCE_LINE.search(candidate)
            and _CADENCE_LANGUAGE.search(candidate)
            and not bool(current_target.get("hasRegularCadence"))
        ):
            candidate = f"{_prefix(candidate)}**Evidence:** {_evidence_summary(current_target)}"

        if in_diagnostics and current_target is not None:
            classification = str(current_target.get("classification") or "")
            if classification in {"sparse_or_neutral", "no_observations"} and _MECHANISM_LANGUAGE.search(candidate) and not _HYPOTHESIS_LINE.search(line):
                if "finding" not in candidate.casefold() and "conclusion" not in candidate.casefold():
                    candidate = (
                        f"{_prefix(candidate)}The targeted diagnostic evidence did not establish a mechanism; this outlier remains unresolved."
                    )

        candidate = _HIGHEST_RESOURCE_USAGE.sub("Highest returned performance percentages", candidate)
        candidate = _HIGH_AVERAGE_EXECUTION.sub("average execution time", candidate)
        if clusters_present:
            candidate = _SIMULTANEOUS_REPORTING.sub("same-second clustered reporting", candidate)
            candidate = _SIMULTANEOUS.sub("within the same reported second", candidate)

        output.append(candidate + newline)

    corrected = "".join(output)
    return corrected, corrected != original


__all__ = [
    "classify_adaptive_diagnostics",
    "guard_performance_diagnostic_hypotheses",
    "render_diagnostic_evidence_gate",
]
