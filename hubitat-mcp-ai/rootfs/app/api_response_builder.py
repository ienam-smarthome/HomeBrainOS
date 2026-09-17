from __future__ import annotations

from copy import deepcopy
from typing import Any

from history_temporal_analysis import guard_history_duration_claim
from technical_metrics_presenter import (
    present_request_metrics,
    present_request_outcome,
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


def _guard_history_message(
    message: str,
    evidence: list[dict[str, Any]],
) -> str:
    """Keep the serialized answer consistent with deterministic history proof."""

    corrected, applied = guard_history_duration_claim(message, evidence)
    if applied:
        for receipt in evidence:
            if not isinstance(receipt, dict):
                continue
            if receipt.get("tool") != "homebrain_device_history":
                continue
            details = receipt.get("details")
            if isinstance(details, dict):
                details["finalAnswerCorrectionApplied"] = True
                break
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
