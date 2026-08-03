from __future__ import annotations

from copy import deepcopy
from typing import Any

from technical_metrics_presenter import (
    present_request_metrics,
    present_request_outcome,
)


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

    return {
        "success": True,
        "route": getattr(outcome, "route", "unified-mcp-agent"),
        "intent": "native-function-calling",
        "request_class": str(getattr(outcome, "request_class", "tool-driven")),
        "message": str(getattr(outcome, "message", "")),
        "choices": list(getattr(outcome, "choices", []) or []),
        "confirmation_required": bool(
            getattr(outcome, "confirmation_required", False)
        ),
        "confirmation_count": int(getattr(outcome, "confirmation_count", 0) or 0),
        "automation_items": list(getattr(outcome, "automation_items", []) or []),
        "evidence": deepcopy(list(getattr(outcome, "evidence", []) or [])),
        "metrics": deepcopy(metrics),
        "metric_rows": present_request_metrics(metrics),
        "outcome_presentation": deepcopy(outcome_presentation),
        "model": str(model),
        "elapsed_ms": max(0, int(elapsed_ms)),
        "version": str(version),
    }


__all__ = ["build_agent_response"]
