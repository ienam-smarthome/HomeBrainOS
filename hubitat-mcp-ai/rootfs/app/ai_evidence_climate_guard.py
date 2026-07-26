from __future__ import annotations

from types import MethodType
from typing import Any, Awaitable, Callable

from ai_evidence_planner import EvidencePlan, EvidenceRequest, _normalised_query


_CLIMATE_TERMS: dict[str, tuple[str, ...]] = {
    "temperature": (
        "temperature",
        "warmest",
        "hottest",
        "coldest",
        "coolest",
        "too warm",
        "too hot",
        "too cold",
    ),
    "humidity": (
        "humidity",
        "humid",
        "most humid",
        "highest humidity",
        "damp",
        "moisture",
    ),
}


def climate_metrics(query: str) -> tuple[str, ...]:
    """Return authoritative measurement metrics required by a climate query."""

    normalised = _normalised_query(query)
    return tuple(
        metric
        for metric, terms in _CLIMATE_TERMS.items()
        if any(term in normalised for term in terms)
    )


def install_climate_measurement_guard(service: Any) -> Any:
    """Force climate questions onto live measurement evidence before AI planning."""

    original_plan: Callable[..., Awaitable[Any]] = service.plan

    async def guarded_plan(
        self: Any,
        query: str,
        request: Any,
        inventory: list[dict[str, Any]],
    ) -> tuple[EvidencePlan, list[dict[str, Any]], str | None]:
        metrics = climate_metrics(query)
        if metrics:
            return (
                EvidencePlan(
                    intent="analysis",
                    summary="Deterministic climate measurement evidence",
                    evidence=(EvidenceRequest("measurements", metrics, limit=40),),
                    confidence=1.0,
                    model=None,
                    provider="HomeBrain deterministic climate router",
                ),
                [],
                None,
            )
        return await original_plan(query, request, inventory)

    service.plan = MethodType(guarded_plan, service)
    return service


__all__ = ["climate_metrics", "install_climate_measurement_guard"]
