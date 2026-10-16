"""Evidence-calibrated post-synthesis gate, shared by all HomeBrain API routes.

This does not determine causes. It prevents model prose from turning partial,
sampled histories into complete/physical-causation claims; it also removes
duplicate free-standing summary sentences. Direct observations and numerical
history remain unchanged. Do not treat a tool's success as source completeness.
"""
from __future__ import annotations

import re
from typing import Any


def _partial_history(receipts: list[dict[str, Any]]) -> bool:
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        temporal = details.get("temporalAnalysis")
        if isinstance(temporal, dict) and (
            temporal.get("coverage") == "partial"
            or temporal.get("totalIsLowerBound") is True
        ):
            return True
        if (
            details.get("historySourceIntegrityVerified") is False
            or details.get("observedEventsTruncated") is True
            or details.get("eventsTruncated") is True
        ):
            return True
    return False


def _sampled_watchdog_no_data(receipts: list[dict[str, Any]]) -> bool:
    """Require real source-scoped watchdog messages, not model claims."""
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("sub_tool") != "hub_get_logs":
            continue
        args = row.get("arguments") or {}
        if not isinstance(args, dict):
            continue
        if isinstance(args.get("args"), dict):
            args = args["args"]
            if isinstance(args.get("args"), dict):
                args = args["args"]
        if not isinstance(args, dict) or not (
            args.get("deviceId") or args.get("pattern")
        ):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            continue
        for item in details.get("logs") or []:
            if isinstance(item, dict) and re.search(
                r"\bwatchdog fired after \d+s without data\b",
                str(item.get("message") or ""), flags=re.I,
            ):
                return True
    return False


def _dedupe_repeated_summary_lines(text: str) -> tuple[str, bool]:
    """Remove repeated non-table, non-list standalone claims, keeping first.

    Only lines of substantial length are eligible. Structural headings,
    event rows and repeated terms in a legitimate multi-row table remain.
    """
    changed = False
    output = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if (
            len(stripped) >= 65
            and not stripped.startswith(("-", "* ", "|", "#", ">", "\x60"))
            and not stripped.endswith(":")
        ):
            plain = re.sub(r"[*_]", "", stripped).strip().casefold()
            if plain in seen:
                changed = True
                continue
            seen.add(plain)
        output.append(line)
    updated = "\n".join(output)
    if changed:
        updated = re.sub(r"\n{3,}", "\n\n", updated).rstrip()
    return updated, changed


def calibrate_supported_conclusions(
    message: str,
    receipts: list[dict[str, Any]],
    *,
    domain: str | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Calibrate only provably risky assertion classes using receipt quality.

    Preserve original model output when source evidence cannot classify the
    risk. No blanket edits to legitimate, source-verified positive assertions.
    """
    draft = str(message or "")
    labels: list[str] = []
    draft, reduced = _dedupe_repeated_summary_lines(draft)
    if reduced:
        labels.append("duplicate_summary_removed")
    if _partial_history(receipts):
        confident = re.compile(
            r"(?im)^\s*(?:\*{0,2}Confidence\*{0,2})\s*:\s*"
            r"(?:\*{0,2})High(?:\*{0,2})[^\n]*$"
        )
        draft, count = confident.subn(
            "**Confidence:** The returned observations support the stated "
            "event/log pattern; historical completeness and initiating cause "
            "are not independently verified.",
            draft,
        )
        if count:
            labels.append("unqualified_high_confidence")
        phrases = (
            (
                r"(?i)\bperfectly aligned\b",
                "consistent within the returned records",
            ),
            (
                r"(?i)\bfunctioned exactly as configured\b",
                "logged decisions consistent with the configured conditions "
                "in the sampled interval",
            ),
            (
                r"(?i)\bwere caused by physical interactions\b",
                "were reported as physical-origin transitions; the initiating "
                "person or controller was not independently established",
            ),
            (
                r"(?i)\bno other controlling devices or mode changes were "
                r"observed in the same window\b",
                "no alternative controller or mode change was established "
                "in the returned, bounded evidence",
            ),
        )
        for expression, replacement in phrases:
            draft, n = re.subn(expression, replacement, draft)
            if n:
                labels.append("partial_history_causal_scope")
    if domain == "device_telemetry" and _sampled_watchdog_no_data(receipts):
        for expression, replacement in (
            (
                r"(?i)\bcomplete telemetry failure\b",
                "prolonged watchdog-reported absence of device data",
            ),
            (
                r"(?i)\bdead connection\b",
                "unverified device communication path",
            ),
            (
                r"(?i)\blast recorded successful MQTT connection\b",
                "last recorded MQTT 'connected' status (not independent "
                "broker or physical proof)",
            ),
            (
                r"(?i)\bintermittent connectivity:\s*contradicted by the logs\b",
                "intermittent connectivity: not established by the sampled "
                "logs; not excluded outside their coverage",
            ),
            (
                r"(?i)\b(?:proves? that )?the .reconnecting. attempts are "
                r"failing to produce any actual telemetry\b",
                "the sampled watchdog counters did not reset; successful "
                "device-originated telemetry or recovery was not established",
            ),
        ):
            draft, n = re.subn(expression, replacement, draft)
            if n:
                labels.append("watchdog_communication_scope")
    return draft, tuple(dict.fromkeys(labels))


class CalibratedOutcome:
    """Preserve original API outcome metadata without mutating the receipt."""
    def __init__(self, original: Any, message: str, metrics: dict[str, Any]):
        self._original = original
        self.message = message
        self.metrics = metrics

    def __getattr__(self, key: str) -> Any:
        return getattr(self._original, key)


def calibrate_api_outcome(outcome: Any, request: str) -> Any:
    evidence = list(getattr(outcome, "evidence", ()) or ())
    coverage = getattr(outcome, "investigation_coverage", None)
    domain = coverage.get("domain") if isinstance(coverage, dict) else None
    if domain is None:
        # This evidence-derived fallback applies to delegated incident
        # selection as well as domain-classified investigation routes.
        from investigation_intelligence import plan_investigation
        plan = plan_investigation(str(request or ""))
        domain = plan.domain if plan is not None else None
    new_message, issues = calibrate_supported_conclusions(
        getattr(outcome, "message", ""), evidence, domain=domain,
    )
    if not issues:
        return outcome
    metrics = dict(getattr(outcome, "metrics", None) or {})
    counts = dict(metrics.get("counters") or {})
    counts["evidence_claim_calibrations"] = len(issues)
    metrics["counters"] = counts
    return CalibratedOutcome(outcome, new_message, metrics)


__all__ = [
    "calibrate_supported_conclusions", "calibrate_api_outcome",
    "CalibratedOutcome",
]
