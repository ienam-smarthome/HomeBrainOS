from __future__ import annotations

from typing import Any


_COUNTER_LABELS = (
    ("model_rounds", "Model rounds"),
    ("tool_calls", "Tool calls"),
    ("tool_discovery_calls", "Tool discovery calls"),
    ("evidence_retries", "Evidence retries"),
    ("grounding_refusals", "Grounding refusals"),
    ("confirmation_queued", "Confirmations queued"),
    ("mutation_verification_failures", "Verification failures"),
    ("request_cancellations", "Cancellations"),
    ("ambiguous_resolutions", "Ambiguous resolutions"),
)

_DURATION_LABELS = (
    ("provider_ms", "Provider"),
    ("mcp_ms", "MCP"),
    ("discovery_ms", "Discovery"),
    ("verification_ms", "Verification"),
    ("total_ms", "Total"),
)


def _non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _duration_text(milliseconds: float) -> str:
    if milliseconds < 1000:
        return f"{round(milliseconds):d} ms"
    seconds = milliseconds / 1000
    return f"{seconds:.1f} s"


def present_request_metrics(metrics: Any) -> list[dict[str, str]]:
    """Return stable, human-readable technical rows for request metrics.

    Unknown keys are deliberately ignored so dynamic labels, prompts, device
    names, tool arguments, or future private fields cannot leak into the UI.
    Zero counters and unavailable durations are omitted to keep the panel small.
    """

    if not isinstance(metrics, dict):
        return []

    rows: list[dict[str, str]] = []
    for key, label in _COUNTER_LABELS:
        number = _non_negative_number(metrics.get(key))
        if number is None or number == 0:
            continue
        rows.append({"label": label, "value": str(int(number))})

    for key, label in _DURATION_LABELS:
        number = _non_negative_number(metrics.get(key))
        if number is None:
            continue
        rows.append({"label": label, "value": _duration_text(number)})

    outcome = metrics.get("outcome")
    if isinstance(outcome, str) and outcome in {"success", "failed", "cancelled"}:
        rows.append({"label": "Outcome", "value": outcome})

    return rows


__all__ = ["present_request_metrics"]
