"""Preserve literal log observations and host-derived timing facts.

Generic semantic guards should correct conclusions around a log observation, not
rewrite the log payload itself. This module restores cited WARN/ERROR facts from
current-turn `hub_get_logs` evidence and validates cadence/same-second wording
against host-derived timing summaries produced from the full bounded log result.

0.16.86 matches literal observations by structured source identity as well as the
raw `app|id|name` token. Model prose normally says `MCP Rule Server (ID 4151)`, so
requiring the raw source token allowed later generic performance repairs to mangle
an otherwise concrete WARN observation. Same-second cluster observations are also
kept inspection-first: a cluster does not establish that staggering/offsetting or
changing report frequency is configurable, necessary, or performance-improving.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any


_MARKDOWN_PREFIX = re.compile(
    r"^(?P<prefix>\s*(?:[-*+]\s+)?(?:\*\*[^*\n]+:\*\*\s*)?)(?P<body>.*)$",
    re.S,
)
_WARNING_WORD = re.compile(r"(?i)\b(?:warn(?:ing)?|error)\b")
_CAUSAL_OR_REPAIR = re.compile(
    r"(?i)\b(?:cause|causes|caused|causing|impact|overhead|log\s+growth|"
    r"history\s+lookup|history\s+lookups|slow(?:er|ing)?\s+history|"
    r"returned\s+activity\s+is\s+worth\s+reviewing|performance\s+statistics)\b"
)
_NESTED_MESSAGE = re.compile(r'"message"\s*:\s*"(?P<message>[^"\\]*(?:\\.[^"\\]*)*)')
_CADENCE_CLAIM = re.compile(
    r"(?i)(?:approximately\s+|about\s+|roughly\s+)?every\s+(?P<seconds>\d+(?:\.\d+)?)\s*seconds?"
)
_TIMING_WORD = re.compile(r"(?i)\b(?:cadence|interval|intervals|gap|every|seconds?)\b")
_OBSERVED_CADENCE_HEADING = re.compile(r"(?i)observed\s+cadence")
_SIMULTANEOUS = re.compile(r"(?i)\bsimultaneously\b")
_CLUSTER_REFERENCE = re.compile(r"(?i)\b(?:same-second|cluster(?:ed|ing)?|burst)\b")
_CLUSTER_TUNING = re.compile(
    r"(?i)\b(?:stagger(?:ed|ing)?|offset(?:ting)?|spread\s+out|change|reduce|increase|adjust|tune|review)\b"
    r"[^\n]{0,180}\b(?:frequency|interval|reporting|updates?|schedule|timing|stagger|offset)\b"
)
_CLUSTER_INSPECTION = (
    "Review the cited integration configuration to determine whether the observed same-second "
    "cluster is expected and whether update scheduling/reporting is configurable; the current "
    "evidence does not establish that staggering, offsetting, or changing frequency is necessary "
    "or performance-improving."
)


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def _source_parts(raw_message: str) -> tuple[str, str, str] | None:
    parts = str(raw_message or "").split("|", 3)
    if len(parts) >= 3 and parts[0].casefold() in {"app", "dev"}:
        return parts[0].casefold(), parts[1].strip(), parts[2].strip()
    return None


def _source_key(raw_message: str) -> str:
    parts = _source_parts(raw_message)
    return "|".join(parts) if parts is not None else ""


def _literal_detail(raw_message: str) -> str:
    raw = str(raw_message or "").strip()
    match = _NESTED_MESSAGE.search(raw)
    if match is not None:
        detail = match.group("message")
        detail = detail.replace(r"\n", " ").replace(r'\"', '"')
    else:
        parts = raw.split("|", 3)
        detail = parts[3] if len(parts) == 4 else raw
    detail = re.sub(r"\s+", " ", detail).strip(" .\"")
    detail = detail.replace("`", "'")
    if len(detail) > 220:
        detail = detail[:217].rstrip() + "..."
    return detail


def _log_rows(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for receipt in evidence:
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is False
            or _sub_tool(receipt) != "hub_get_logs"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        logs = details.get("logs")
        if not isinstance(logs, list):
            continue
        for item in logs:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level") or "").strip().upper()
            raw = str(item.get("message") or "").strip()
            parts = _source_parts(raw)
            if level not in {"WARN", "WARNING", "ERROR"} or parts is None or not raw:
                continue
            kind, identifier, name = parts
            rows.append(
                {
                    "level": "WARN" if level == "WARNING" else level,
                    "source": "|".join(parts),
                    "kind": kind,
                    "id": identifier,
                    "name": name,
                    "detail": _literal_detail(raw),
                }
            )
    return rows


def _observation_matches_line(
    observation: dict[str, str],
    comparable: str,
    name_counts: Counter[str],
) -> bool:
    """Match model prose to a current-turn WARN/ERROR without fuzzy attribution."""

    folded = str(comparable or "").casefold()
    raw_source = observation.get("source", "").casefold()
    name = observation.get("name", "").strip().casefold()
    identifier = observation.get("id", "").strip().casefold()
    if raw_source and raw_source in folded:
        return True
    if name and identifier and name in folded and re.search(
        rf"(?<!\d){re.escape(identifier)}(?!\d)", folded
    ):
        return True
    return bool(name and name_counts.get(name, 0) == 1 and name in folded)


def _timing_facts(evidence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cadence: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    for receipt in evidence:
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is False
            or _sub_tool(receipt) != "hub_get_logs"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        timing = details.get("hostDerivedTiming")
        if not isinstance(timing, dict):
            continue
        raw_cadence = timing.get("cadence")
        raw_clusters = timing.get("sameSecondClusters")
        if isinstance(raw_cadence, list):
            cadence.extend(row for row in raw_cadence if isinstance(row, dict))
        if isinstance(raw_clusters, list):
            clusters.extend(row for row in raw_clusters if isinstance(row, dict))
    return cadence, clusters


def _format_seconds(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _timing_kind(fact: dict[str, Any]) -> str:
    explicit = str(fact.get("timingKind") or "").strip().casefold()
    if explicit in {"regular_cadence", "irregular_intervals", "observed_gap"}:
        return explicit
    if fact.get("observedGapSeconds") not in (None, ""):
        return "observed_gap"
    if fact.get("regularCadence") is True or fact.get("approxCadenceSeconds") not in (None, ""):
        return "regular_cadence"
    if fact.get("regularCadence") is False:
        return "irregular_intervals"
    return ""


def _timing_subject_prefix(line: str) -> str:
    marker = ":**"
    if marker in line:
        end = line.index(marker) + len(marker)
        return line[:end]
    colon = line.find(":")
    if colon >= 0:
        return line[: colon + 1]
    match = _MARKDOWN_PREFIX.match(line)
    return match.group("prefix").rstrip() if match is not None else ""


def _canonical_timing_text(fact: dict[str, Any]) -> str:
    kind = _timing_kind(fact)
    median_seconds = fact.get("medianIntervalSeconds")
    min_seconds = fact.get("minIntervalSeconds")
    max_seconds = fact.get("maxIntervalSeconds")
    approx_seconds = fact.get("approxCadenceSeconds")
    gap_seconds = fact.get("observedGapSeconds")

    if kind == "regular_cadence":
        pieces = ["Regular cadence"]
        if median_seconds not in (None, ""):
            pieces.append(f"median interval {_format_seconds(median_seconds)} seconds")
        if approx_seconds not in (None, ""):
            pieces.append(f"approximately every {_format_seconds(approx_seconds)} seconds")
        if min_seconds not in (None, "") and max_seconds not in (None, ""):
            pieces.append(
                f"observed range {_format_seconds(min_seconds)}–{_format_seconds(max_seconds)} seconds"
            )
        return "; ".join(pieces) + "."

    if kind == "irregular_intervals":
        pieces = ["Irregular observed intervals"]
        if median_seconds not in (None, ""):
            pieces.append(f"median {_format_seconds(median_seconds)} seconds")
        if min_seconds not in (None, "") and max_seconds not in (None, ""):
            pieces.append(
                f"observed range {_format_seconds(min_seconds)}–{_format_seconds(max_seconds)} seconds"
            )
        return "; ".join(pieces) + ". No regular cadence was established."

    if kind == "observed_gap" and gap_seconds not in (None, ""):
        return (
            f"Single observed gap: {_format_seconds(gap_seconds)} seconds between the cited observations. "
            "This does not establish a recurring cadence."
        )
    return ""


def _repair_timing_line(
    line: str,
    cadence: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
) -> str:
    repaired = line
    comparable = re.sub(r"[*_`]", "", repaired).casefold()

    plain = re.sub(r"[*_`]", "", repaired).strip().casefold()
    if plain in {"observed cadence", "observed cadence:"} and any(
        _timing_kind(fact) in {"irregular_intervals", "observed_gap"}
        for fact in cadence
    ):
        repaired = _OBSERVED_CADENCE_HEADING.sub("Observed Timing", repaired, count=1)
        comparable = re.sub(r"[*_`]", "", repaired).casefold()

    for fact in cadence:
        source_ref = str(fact.get("sourceRef") or "")
        source_id = source_ref.split("|", 1)[1] if "|" in source_ref else ""
        source = str(fact.get("source") or "")
        signal = str(fact.get("signal") or "")
        if signal and signal.casefold() not in comparable:
            continue
        if not (
            (source_id and source_id.casefold() in comparable)
            or (source and source.casefold() in comparable)
        ):
            continue
        if not _TIMING_WORD.search(comparable):
            continue

        canonical = _canonical_timing_text(fact)
        if canonical:
            prefix = _timing_subject_prefix(repaired)
            repaired = f"{prefix} {canonical}" if prefix else canonical
            break

        match = _CADENCE_CLAIM.search(repaired)
        if match is None:
            continue
        claimed = float(match.group("seconds"))
        cadence_seconds = fact.get("approxCadenceSeconds")
        if cadence_seconds not in (None, ""):
            expected = float(cadence_seconds)
            if abs(claimed - expected) > max(0.5, expected * 0.05):
                repaired = _CADENCE_CLAIM.sub(
                    f"approximately every {_format_seconds(expected)} seconds",
                    repaired,
                    count=1,
                )
            break
        gap_seconds = fact.get("observedGapSeconds")
        if gap_seconds not in (None, ""):
            repaired = _CADENCE_CLAIM.sub(
                f"with an observed gap of {_format_seconds(gap_seconds)} seconds between the cited observations",
                repaired,
                count=1,
            )
            break

    if _SIMULTANEOUS.search(repaired):
        for cluster in clusters:
            second = str(cluster.get("second") or "")
            clock = second.rsplit(" ", 1)[-1] if second else ""
            if clock and clock in repaired:
                repaired = _SIMULTANEOUS.sub("within the same reported second", repaired, count=1)
                break
    return repaired


def _cluster_tuning_repair(line: str, clusters: list[dict[str, Any]]) -> str:
    if not clusters or not _CLUSTER_REFERENCE.search(line) or not _CLUSTER_TUNING.search(line):
        return line
    match = _MARKDOWN_PREFIX.match(line)
    prefix = match.group("prefix") if match is not None else ""
    return prefix + _CLUSTER_INSPECTION


def guard_performance_log_observations(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Protect WARN/ERROR facts and correct model-authored log timing semantics."""

    original = str(message or "")
    if not original:
        return original, False
    observations = _log_rows(evidence)
    cadence, clusters = _timing_facts(evidence)
    if not observations and not cadence and not clusters:
        return original, False

    name_counts = Counter(
        observation.get("name", "").casefold()
        for observation in observations
        if observation.get("name")
    )
    changed = False
    output: list[str] = []
    for line in original.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        core = line[:-1] if newline else line
        comparable = re.sub(r"[*_`]", "", core).casefold()
        replacement: str | None = None
        if _WARNING_WORD.search(comparable) and _CAUSAL_OR_REPAIR.search(comparable):
            for observation in observations:
                if not _observation_matches_line(observation, comparable, name_counts):
                    continue
                match = _MARKDOWN_PREFIX.match(core)
                prefix = match.group("prefix") if match is not None else ""
                replacement = (
                    f"{prefix}{observation['level']} from `{observation['source']}` reported "
                    f"`{observation['detail']}`. This is a recent log observation; this turn "
                    "does not establish that it caused the longer-window performance statistics."
                )
                break
        candidate = replacement if replacement is not None else core
        candidate = _repair_timing_line(candidate, cadence, clusters)
        candidate = _cluster_tuning_repair(candidate, clusters)
        if candidate != core:
            changed = True
        output.append(candidate + newline)
    corrected = "".join(output)
    return corrected, changed


__all__ = ["guard_performance_log_observations"]
