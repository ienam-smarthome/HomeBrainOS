from __future__ import annotations

from collections.abc import Mapping


_OUTCOME_COUNTER_PRECEDENCE: tuple[tuple[str, str], ...] = (
    ("grounding_refusals", "refused"),
    ("mutation_verification_failures", "failed"),
    ("request_cancellations", "cancelled"),
    ("confirmation_expired", "unresolved"),
    ("device_resolution_ambiguous", "unresolved"),
    ("device_resolution_missing", "unresolved"),
)


def classify_completed_request(counters: Mapping[str, int] | None) -> str:
    """Classify a normally returned request from fixed privacy-safe counters."""

    values = counters or {}
    for counter, outcome in _OUTCOME_COUNTER_PRECEDENCE:
        if int(values.get(counter, 0) or 0) > 0:
            return outcome
    return "success"


__all__ = ["classify_completed_request"]
