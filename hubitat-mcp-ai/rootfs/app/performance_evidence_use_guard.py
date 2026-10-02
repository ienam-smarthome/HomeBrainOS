"""Final evidence-use integrity guard for broad performance synthesis.

This backstop operates on structured current-turn evidence after the older generic
semantic guards have run. It deliberately does not acquire more evidence or add a
model round. Its job is to keep three distinctions intact:

* explicit long-running operations are diagnostic evidence, but are not themselves
  proof of a network/connectivity cause;
* literal WARN/ERROR observations remain literal after generic prose repairs; and
* a same-second cluster is an observation, not proof that staggering/frequency
  changes are configurable, necessary, or performance-improving.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from performance_diagnostic_evidence_gate import classify_adaptive_diagnostics


_LABEL = re.compile(
    r"^(?P<prefix>\s*(?:[-*+]\s+|\d+[.)]\s+)?)"
    r"(?:\*\*(?P<label>[^*]+?)\*\*(?::)?\s*)?(?P<body>.*)$"
)
_MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+.+$")
_NUMBERED_BOLD_ENTITY = re.compile(r"^\s*\*\*\s*\d+[.)]?\s*(?P<title>.+?)\s*\*\*\s*$")
_NETWORK_LANGUAGE = re.compile(
    r"(?i)\b(?:network|connectivity|reachability|api\s+latency|api\s+response|"
    r"mdns|vlan|dhcp|connection)\b"
)
_LONG_OPERATION_LANGUAGE = re.compile(
    r"(?i)\b(?:long[- ]running|very\s+long|stalled|runq|setvolume|operation\s+duration|"
    r"ran\s+for|execution\s+duration)\b"
)
_NON_DIAGNOSTIC = re.compile(r"(?i)\bnon-diagnostic\s+log\s+observation")
_WARNING_WORD = re.compile(r"(?i)\b(?:warn(?:ing)?|error)\b")
_GENERIC_WARN_REPAIR = re.compile(
    r"(?i)\b(?:returned\s+activity\s+is\s+worth\s+reviewing|"
    r"does\s+not\s+establish\s+material\s+background\s+overhead|"
    r"recent\s+log\s+observation|performance\s+statistics)\b"
)
_CLUSTER_REFERENCE = re.compile(r"(?i)\b(?:same-second|cluster(?:ed|ing)?|burst)\b")
_CLUSTER_TUNING = re.compile(
    r"(?i)\b(?:stagger(?:ed|ing)?|offset(?:ting)?|spread\s+out|change|reduce|increase|adjust|tune)\b"
    r"[^\n]{0,180}\b(?:frequency|interval|reporting|updates?|schedule|timing|stagger|offset)\b"
)
_NESTED_MESSAGE = re.compile(r'"message"\s*:\s*"(?P<message>[^"\\]*(?:\\.[^"\\]*)*)')


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict):
        return str(arguments.get("tool") or "")
    return ""


def _line_parts(line: str) -> tuple[str, str, str]:
    match = _LABEL.match(line)
    if match is None:
        return "", "", line
    return match.group("prefix") or "", (match.group("label") or "").strip(), match.group("body") or ""


def _render(line: str, body: str) -> str:
    prefix, label, _ = _line_parts(line)
    if label:
        return f"{prefix}**{label.rstrip(':')}:** {body}"
    return prefix + body


def _normalize_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").casefold())
    stop = {
        "the", "and", "settings", "configuration", "activity", "latency",
        "performance", "device", "app", "diagnostic", "hypothesis", "resource",
        "usage", "execution", "time", "tv",
    }
    return {word for word in words if len(word) > 1 and word not in stop}


def _adaptive_metadata(evidence: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in evidence:
        if not isinstance(row, dict) or str(row.get("evidence_kind") or "") != "host_planned_performance_diagnostic":
            continue
        details = row.get("details")
        target = details.get("adaptiveTarget") if isinstance(details, dict) else None
        if not isinstance(target, dict):
            continue
        kind = str(target.get("kind") or "")
        identifier = str(target.get("id") or "")
        if kind and identifier:
            result[(kind, identifier)] = target
    return result


def _targets(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metadata = _adaptive_metadata(evidence)
    targets = classify_adaptive_diagnostics(evidence)
    for target in targets:
        key = (str(target.get("scopeKind") or ""), str(target.get("scopeId") or ""))
        meta = metadata.get(key)
        if not isinstance(meta, dict):
            continue
        if not str(target.get("name") or "").strip():
            target["name"] = str(meta.get("name") or "").strip()
        target["selectedPerformanceRow"] = meta.get("performanceRow")
        target["selectedFromExactRow"] = meta.get("selectedFromExactRow")
    return targets


def _match_target(text: str, targets: list[dict[str, Any]]) -> dict[str, Any] | None:
    folded = str(text or "").casefold()
    words = _normalize_words(text)
    best: tuple[int, dict[str, Any]] | None = None
    for target in targets:
        identifier = str(target.get("scopeId") or "").strip().casefold()
        name = str(target.get("name") or "").strip()
        if identifier and re.search(rf"(?<!\d){re.escape(identifier)}(?!\d)", folded):
            score = 100
        else:
            name_words = _normalize_words(name)
            if not name_words:
                continue
            score = len(words & name_words)
            required = 1 if len(name_words) <= 2 else 2
            if score < required:
                continue
        if best is None or score > best[0]:
            best = (score, target)
    return best[1] if best else None


def _long_operation_summary(target: dict[str, Any]) -> str:
    values = sorted(set(int(value) for value in target.get("longCallMs") or []))
    range_text = (
        f"{values[0]}–{values[-1]} ms" if len(values) > 1 else f"{values[0]} ms"
        if values else "very long operation durations"
    )
    return (
        f"The scoped diagnostic logs contain explicit very long operation durations ({range_text}). "
        "That supports a calibrated long-running/stalled-operation hypothesis. The current evidence "
        "does not establish a network/connectivity cause, the exact implementation defect, worker-thread "
        "blocking, or user-visible delay."
    )


def _failure_summary(target: dict[str, Any]) -> str:
    signals = [str(value) for value in target.get("failureSignals") or [] if str(value)]
    signal_text = ", ".join(dict.fromkeys(signals)) or "explicit failure evidence"
    extra = " Very long operation durations were also observed." if target.get("longCallMs") else ""
    return (
        f"The scoped diagnostic logs contain explicit failure signal(s): {signal_text}.{extra} "
        "These observations support a calibrated failure/connectivity hypothesis, but they do not "
        "establish the exact implementation defect or how much the failures contribute to the measured "
        "performance percentages."
    )


def _source_parts(raw: str) -> tuple[str, str, str] | None:
    parts = str(raw or "").split("|", 3)
    if len(parts) < 4 or parts[0].casefold() not in {"app", "dev"}:
        return None
    return parts[0].casefold(), parts[1].strip(), parts[2].strip()


def _literal_detail(raw: str) -> str:
    text = str(raw or "").strip()
    nested = _NESTED_MESSAGE.search(text)
    if nested is not None:
        detail = nested.group("message").replace(r"\n", " ").replace(r'\"', '"')
    else:
        parts = text.split("|", 3)
        detail = parts[3] if len(parts) == 4 else text
    detail = re.sub(r"\s+", " ", detail).strip(" .\"").replace("`", "'")
    return detail[:217].rstrip() + "..." if len(detail) > 220 else detail


def _warn_rows(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is False or _sub_tool(receipt) != "hub_get_logs":
            continue
        details = receipt.get("details")
        logs = details.get("logs") if isinstance(details, dict) else None
        if not isinstance(logs, list):
            continue
        for item in logs:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level") or "").strip().upper()
            raw = str(item.get("message") or "")
            parts = _source_parts(raw)
            if level not in {"WARN", "WARNING", "ERROR"} or parts is None:
                continue
            kind, identifier, name = parts
            rows.append({
                "level": "WARN" if level == "WARNING" else level,
                "kind": kind,
                "id": identifier,
                "name": name,
                "source": "|".join(parts),
                "detail": _literal_detail(raw),
            })
    return rows


def _warn_matches(line: str, row: dict[str, str], name_counts: Counter[str]) -> bool:
    folded = line.casefold()
    source = row["source"].casefold()
    name = row["name"].casefold()
    identifier = row["id"].casefold()
    if source in folded:
        return True
    if name and identifier and name in folded and re.search(rf"(?<!\d){re.escape(identifier)}(?!\d)", folded):
        return True
    return bool(name and name_counts.get(name, 0) == 1 and name in folded)


def _has_cluster(evidence: list[dict[str, Any]]) -> bool:
    for row in evidence:
        details = row.get("details") if isinstance(row, dict) else None
        timing = details.get("hostDerivedTiming") if isinstance(details, dict) else None
        clusters = timing.get("sameSecondClusters") if isinstance(timing, dict) else None
        if isinstance(clusters, list) and any(isinstance(item, dict) for item in clusters):
            return True
    return False


def guard_direct_performance_evidence_use(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Apply final current-turn evidence integrity after generic semantic guards."""

    original = str(message or "")
    if not original:
        return original, False
    targets = _targets(evidence)
    warnings = _warn_rows(evidence)
    name_counts = Counter(row["name"].casefold() for row in warnings if row.get("name"))
    clusters_present = _has_cluster(evidence)

    current_target: dict[str, Any] | None = None
    output: list[str] = []
    for raw_line in original.splitlines(keepends=True):
        newline = "\n" if raw_line.endswith("\n") else ""
        line = raw_line[:-1] if newline else raw_line
        candidate = line

        if _MARKDOWN_HEADING.match(candidate):
            current_target = None
        numbered = _NUMBERED_BOLD_ENTITY.match(candidate)
        if numbered is not None:
            current_target = _match_target(numbered.group("title"), targets)

        line_target = _match_target(candidate, targets)
        if line_target is not None:
            current_target = line_target
        target = line_target or current_target

        if target is not None and str(target.get("classification") or "") == "diagnostic_signal":
            failures = target.get("failureSignals") or []
            long_calls = target.get("longCallMs") or []
            if _NON_DIAGNOSTIC.search(candidate):
                candidate = _render(candidate, _failure_summary(target) if failures else _long_operation_summary(target))
            elif long_calls and not failures and _NETWORK_LANGUAGE.search(candidate):
                candidate = _render(candidate, _long_operation_summary(target))
            elif failures and (_NETWORK_LANGUAGE.search(candidate) or _LONG_OPERATION_LANGUAGE.search(candidate)):
                candidate = _render(candidate, _failure_summary(target))

        if _WARNING_WORD.search(candidate) and _GENERIC_WARN_REPAIR.search(candidate):
            for warning in warnings:
                if not _warn_matches(candidate, warning, name_counts):
                    continue
                candidate = _render(
                    candidate,
                    f"{warning['level']} from `{warning['source']}` reported `{warning['detail']}`. "
                    "This is a current-turn log observation; it does not by itself establish that the "
                    "warning caused the longer-window performance statistics.",
                )
                break

        if clusters_present and _CLUSTER_REFERENCE.search(candidate) and _CLUSTER_TUNING.search(candidate):
            candidate = _render(
                candidate,
                "Review the cited integration configuration to determine whether the observed same-second "
                "cluster is expected and whether update scheduling/reporting is configurable; the current "
                "evidence does not establish that staggering, offsetting, or changing frequency is necessary "
                "or performance-improving.",
            )

        output.append(candidate + newline)

    corrected = "".join(output)
    return corrected, corrected != original


__all__ = ["guard_direct_performance_evidence_use"]
