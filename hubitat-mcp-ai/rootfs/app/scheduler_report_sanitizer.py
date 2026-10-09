"""Evidence-first correction of scheduler-only model-authored report sections.

The model can confuse grouped device/app *candidates* with confirmed owners and
misassociate plain cadence text with unrelated devices. Replace ONLY recognized
model sections with deterministic evidence derived from current request receipts.
Unrecognized text/inspection commentary remains authored by the model.
"""
from __future__ import annotations

import math
import re
from typing import Any

from performance_job_analysis import render_job_workload_summary

_JOB_HEADING = re.compile(
    r"^#{2,4}[ \t]+Scheduled Job Analysis[^\n]*\n.*?(?=^#{2,4}[ \t]+|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_CADENCE_HEADING = re.compile(
    r"^#{2,4}[ \t]+Observed High-Frequency Activity[^\n]*\n.*?"
    r"(?=^#{2,4}[ \t]+|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def _safe_text(value: Any, limit: int = 80) -> str:
    return " ".join(str(value or "").replace("|", "/").split())[:limit]


def _log_cadence_section(evidence: list[dict[str, Any]]) -> str:
    """Describe observed *log arrival* intervals, not CPU/scheduler cadence."""

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("sub_tool") != "hub_get_logs":
            continue
        details = receipt.get("details")
        timing = details.get("hostDerivedTiming") if isinstance(details, dict) else None
        series = timing.get("cadence") if isinstance(timing, dict) else None
        if not isinstance(series, list):
            continue
        for row in series:
            if not isinstance(row, dict) or row.get("timingKind") != "regular_cadence":
                continue
            try:
                interval = float(row.get("medianIntervalSeconds"))
                count = int(row.get("observationCount"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(interval) or interval <= 0 or count < 3:
                continue
            source, ref, signal = (
                _safe_text(row.get("source")),
                _safe_text(row.get("sourceRef"), 40),
                _safe_text(row.get("signal")),
            )
            if not source or not signal:
                continue
            key = (ref, source, signal)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "source": source, "ref": ref, "signal": signal,
                "seconds": interval, "observations": count,
            })
    records.sort(key=lambda row: (-row["observations"], row["source"], row["signal"]))
    result = ["### Observed device log cadences (read-only)",
              "Intervals below are from a bounded, capped log sample; they are "
              "**not** measurements of scheduled-job execution or CPU usage."]
    if records:
        result += [
            "| Log source | Signal | Median observed interval | Observations | Source |",
            "| --- | --- | ---: | ---: | --- |",
        ]
        for row in records[:6]:
            label = f"{row['source']} ({row['ref']})" if row["ref"] else row["source"]
            result.append(
                f"| {label} | {row['signal']} | {row['seconds']:.3f} s | "
                f"{row['observations']} | hub_get_logs |"
            )
    else:
        result.append("No sufficiently repeated, source-labelled log series was "
                      "established in the returned evidence.")
    return "\n".join(result)


def sanitize_scheduler_overview(
    message: str, digest: dict[str, Any] | None, evidence: list[dict[str, Any]],
) -> tuple[str, bool, bool]:
    """Correct known model overview sections without rewriting freeform advice."""

    text = str(message or "")
    job_replaced = False
    cadence_replaced = False
    if isinstance(digest, dict) and digest.get("status") == "parsed":
        canonical = render_job_workload_summary(digest)
        if canonical and _JOB_HEADING.search(text):
            text = _JOB_HEADING.sub(lambda _m: canonical + "\n\n", text, count=1)
            job_replaced = True
    if _CADENCE_HEADING.search(text):
        section = _log_cadence_section(evidence)
        text = _CADENCE_HEADING.sub(lambda _m: section + "\n\n", text, count=1)
        cadence_replaced = True
    return text, job_replaced, cadence_replaced


__all__ = ["sanitize_scheduler_overview"]
