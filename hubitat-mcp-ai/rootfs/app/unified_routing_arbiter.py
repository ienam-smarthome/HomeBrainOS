from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from route_registry import RouteRegistry, RouteSelection


IntentTier = Literal[
    "control",
    "deterministic-read",
    "diagnostics",
    "open-ended",
]


@dataclass(frozen=True, slots=True)
class RoutingInterpretation:
    """One validated routing interpretation shared by diagnostics and tracing."""

    capability_id: str
    intent_tier: IntentTier
    slots: dict[str, Any]
    confidence: float
    reason: str
    selection: RouteSelection

    def response_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "intent_tier": self.intent_tier,
            "slots": dict(self.slots),
            "confidence": self.confidence,
            "reason": self.reason,
        }


def _tier_for(capability_id: str, safety_class: str) -> IntentTier:
    if safety_class in {"mutate", "destructive"}:
        return "control"
    if capability_id.startswith("diagnostics."):
        return "diagnostics"
    if capability_id.startswith(("ai.", "assistant.")):
        return "open-ended"
    return "deterministic-read"


class UnifiedRoutingArbiter:
    """Single four-tier interpretation surface over the capability catalogue.

    This release uses the arbiter for production shadow decisions and trace
    metadata. Existing handlers remain the dispatcher until their catalogue
    capabilities pass the fixed eval and shadow-agreement gates.
    """

    def __init__(self, registry: RouteRegistry) -> None:
        self.registry = registry

    def interpret(self, query: str) -> RoutingInterpretation:
        selection = self.registry.select(query)
        selected = selection.selected
        if selected is None:
            return RoutingInterpretation(
                capability_id="assistant.general",
                intent_tier="open-ended",
                slots={},
                confidence=0.35,
                reason="No deterministic capability matched; use the open-ended tier.",
                selection=selection,
            )

        capability_id = selected.capability_id or selected.name
        tier = _tier_for(capability_id, selected.safety_class)
        confidence = 0.55 if tier == "open-ended" else 1.0
        return RoutingInterpretation(
            capability_id=capability_id,
            intent_tier=tier,
            slots={},
            confidence=confidence,
            reason=selected.reason,
            selection=selection,
        )


__all__ = [
    "IntentTier",
    "RoutingInterpretation",
    "UnifiedRoutingArbiter",
]
