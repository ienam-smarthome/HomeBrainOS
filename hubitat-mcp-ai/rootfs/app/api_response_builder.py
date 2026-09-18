from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from history_temporal_analysis import guard_history_duration_claim
from technical_metrics_presenter import (
    present_request_metrics,
    present_request_outcome,
)


_NO_HISTORY_DATA = re.compile(
    r"\b(?:no\s+(?:recorded\s+)?data|no\s+history|no\s+(?:recorded\s+)?events?|"
    r"nothing\s+(?:was\s+)?recorded)\b",
    re.I,
)


def _participating_model(metrics: dict[str, Any], model: str) -> str | None:
    counters = metrics.get("counters")
    if not isinstance(counters, dict):
        return str(model)
    try:
        model_rounds = int(counters.get("model_rounds") or 0)
    except (TypeError, ValueError):
        model_rounds = 0
    return str(model) if model_rounds > 0 else None


def _mark_history_correction(receipt: dict[str, Any]) -> None:
    details = receipt.get("details")
    if isinstance(details, dict):
        details["finalAnswerCorrectionApplied"] = True


def _history_absence_replacement(receipt: dict[str, Any]) -> str | None:
    """Return a compact deterministic correction for a false no-history claim."""

    details = receipt.get("details")
    if not isinstance(details, dict):
        return None
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None
    try:
        interval_count = int(temporal.get("intervalCount") or 0)
    except (TypeError, ValueError):
        return None
    if interval_count <= 0:
        return None

    label = str(details.get("label") or "").strip()
    duration = str(temporal.get("totalActiveDuration") or "").strip()
    lower_bound = bool(temporal.get("totalIsLowerBound"))
    noun = "interval" if interval_count == 1 else "intervals"
    qualifier = "at least " if lower_bound and duration else ""
    if duration:
        return (
            f"{label} has recorded history in this evidence: {interval_count} active "
            f"{noun} totaling {qualifier}{duration}."
        )
    return f"{label} has recorded history in this evidence: {interval_count} active {noun}."


def _partial_zero_replacement(receipt: dict[str, Any]) -> str | None:
    """Describe zero observed active time without turning a lower bound into zero."""

    details = receipt.get("details")
    if not isinstance(details, dict):
        return None
    temporal = details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None
    try:
        interval_count = int(temporal.get("intervalCount") or 0)
    except (TypeError, ValueError):
        return None
    if interval_count != 0 or not bool(temporal.get("totalIsLowerBound")):
        return None

    label = str(details.get("label") or "The device").strip() or "The device"
    active = str(temporal.get("activeState") or "active").strip() or "active"
    inactive = str(temporal.get("inactiveState") or "inactive").strip() or "inactive"
    window = str(temporal.get("windowLabel") or "the requested window").strip()
    return (
        f"No {active} interval was established for {label} during {window}, but the "
        f"history boundary is incomplete, so this does not prove it stayed "
        f"{inactive} throughout that window."
    )


def _sentence_pieces(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(?P<space>\s+)", text)


def _guard_partial_zero_claims(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Reject model wording that upgrades a partial zero lower bound to proof."""

    text = str(message or "")
    receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and _partial_zero_replacement(receipt) is not None
    ]
    if not receipts:
        return text, False

    pieces = _sentence_pieces(text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        comparable = re.sub(r"[*_`]", "", sentence).casefold()
        for receipt in receipts:
            details = receipt.get("details") or {}
            temporal = details.get("temporalAnalysis") or {}
            label = str(details.get("label") or "").strip()
            active = str(temporal.get("activeState") or "active").strip()
            inactive = str(temporal.get("inactiveState") or "inactive").strip()
            if not label or label.casefold() not in comparable:
                continue
            unsupported_zero = bool(_NO_HISTORY_DATA.search(sentence))
            unsupported_zero = unsupported_zero or bool(
                re.search(
                    rf"\b(?:was|is|were|are)\s+(?:not|never)\s+{re.escape(active)}\b",
                    comparable,
                    re.I,
                )
            )
            unsupported_zero = unsupported_zero or bool(
                re.search(
                    rf"\b(?:stayed|remained|was|is)\s+{re.escape(inactive)}\b.*\b(?:throughout|all)\b",
                    comparable,
                    re.I,
                )
            )
            if not unsupported_zero:
                continue
            replacement = _partial_zero_replacement(receipt)
            if replacement is None:
                continue
            pieces[index] = replacement
            _mark_history_correction(receipt)
            changed = True
            break
    return "".join(pieces), changed


def _guard_history_absence_claims(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct a named no-data claim contradicted by current-turn history proof.

    This guard is intentionally narrow. It only edits a sentence that both names
    the exact history device and contains an explicit no-data/no-history phrase,
    and only when that same request has deterministic temporal proof of one or
    more active intervals for the device. It does not infer anything from prior
    conversation or from unrelated receipts.
    """

    text = str(message or "")
    receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and isinstance(receipt.get("details"), dict)
    ]
    if not receipts or not _NO_HISTORY_DATA.search(text):
        return text, False

    # Split only on sentence whitespace so formatting/newlines are preserved well
    # enough for the WebUI while keeping the replacement local to the contradiction.
    pieces = _sentence_pieces(text)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _NO_HISTORY_DATA.search(sentence):
            continue
        comparable = re.sub(r"[*_`]", "", sentence).casefold()
        for receipt in receipts:
            details = receipt.get("details") or {}
            label = str(details.get("label") or "").strip()
            if not label or label.casefold() not in comparable:
                continue
            replacement = _history_absence_replacement(receipt)
            if replacement is None:
                continue
            pieces[index] = replacement
            _mark_history_correction(receipt)
            changed = True
            break
    return "".join(pieces), changed


def _guard_history_message(
    message: str,
    evidence: list[dict[str, Any]],
) -> str:
    """Keep the serialized answer consistent with deterministic history proof."""

    corrected, partial_zero_applied = _guard_partial_zero_claims(message, evidence)
    corrected, absence_applied = _guard_history_absence_claims(corrected, evidence)
    corrected, duration_applied = guard_history_duration_claim(corrected, evidence)
    if duration_applied:
        for receipt in evidence:
            if not isinstance(receipt, dict):
                continue
            if receipt.get("tool") != "homebrain_device_history":
                continue
            if isinstance(receipt.get("details"), dict):
                _mark_history_correction(receipt)
                break
    # Keep the local variable explicit so future guards can share this boundary
    # without losing whether any serializer-side correction happened.
    _ = partial_zero_applied or absence_applied or duration_applied
    return corrected


def build_agent_response(
    outcome: Any,
    *,
    model: str,
    elapsed_ms: int,
    version: str,
) -> dict[str, Any]:
    """Build the stable /api/ask response without exposing private request data."""

    metrics = getattr(outcome, "metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    outcome_presentation = present_request_outcome(metrics.get("outcome"))
    evidence = deepcopy(list(getattr(outcome, "evidence", []) or []))
    message = _guard_history_message(
        str(getattr(outcome, "message", "")),
        evidence,
    )

    return {
        "success": True,
        "route": getattr(outcome, "route", "unified-mcp-agent"),
        "intent": "native-function-calling",
        "request_class": str(getattr(outcome, "request_class", "tool-driven")),
        "message": message,
        "choices": list(getattr(outcome, "choices", []) or []),
        "confirmation_required": bool(
            getattr(outcome, "confirmation_required", False)
        ),
        "confirmation_count": int(getattr(outcome, "confirmation_count", 0) or 0),
        "automation_items": list(getattr(outcome, "automation_items", []) or []),
        "evidence": evidence,
        "metrics": deepcopy(metrics),
        "metric_rows": present_request_metrics(metrics),
        "outcome_presentation": deepcopy(outcome_presentation),
        "model": _participating_model(metrics, model),
        "elapsed_ms": max(0, int(elapsed_ms)),
        "version": str(version),
    }


__all__ = ["build_agent_response"]
