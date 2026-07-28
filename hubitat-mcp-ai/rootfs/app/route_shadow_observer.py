from __future__ import annotations

import json
import logging
from collections import Counter, deque
from typing import Any, Awaitable, Callable

from route_registry import RouteRegistry
from unified_routing_arbiter import RoutingInterpretation, UnifiedRoutingArbiter


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
LOGGER = logging.getLogger("homebrain.route_shadow")


class RouteShadowObserver:
    """Passive production observer for RouteRegistry overlap diagnostics.

    The observer never dispatches or changes an answer. It records what the
    existing route catalogue would have selected and compares that with the
    route which actually answered through the maintained request stack.
    """

    def __init__(
        self,
        registry: RouteRegistry,
        *,
        arbiter: UnifiedRoutingArbiter | None = None,
        limit: int = 200,
    ) -> None:
        self.registry = registry
        self.arbiter = arbiter or UnifiedRoutingArbiter(registry)
        self.limit = max(20, min(2000, int(limit)))
        self._items: deque[dict[str, Any]] = deque(maxlen=self.limit)
        self.total = 0
        self.overlaps = 0
        self.selected_counts: Counter[str] = Counter()
        self.actual_counts: Counter[str] = Counter()
        self.disagreements = 0
        self.agreements = 0
        self.comparable = 0
        self.unmapped = 0
        self.intent_tier_counts: Counter[str] = Counter()

    def record(
        self,
        query: str,
        answer: dict[str, Any],
        interpretation: RoutingInterpretation,
    ) -> dict[str, Any]:
        selection = interpretation.selection
        matches = [match.name for match in selection.matches]
        selected = selection.selected.name if selection.selected else None
        actual = str(answer.get("route") or "") or None
        actual_intent = str(answer.get("intent") or "") or None
        overlap = len(matches) > 1
        comparison = (
            selection.selected.compare_answer(answer)
            if selection.selected is not None
            else None
        )
        disagreement = comparison is False

        self.total += 1
        if overlap:
            self.overlaps += 1
        if selected:
            self.selected_counts[selected] += 1
        if actual:
            self.actual_counts[actual] += 1
        self.intent_tier_counts[interpretation.intent_tier] += 1
        if comparison is True:
            self.comparable += 1
            self.agreements += 1
        elif comparison is False:
            self.comparable += 1
            self.disagreements += 1
        else:
            self.unmapped += 1

        item = {
            "query": query,
            "matched_routes": matches,
            "selected_by_registry": selected,
            "selected_capability": (
                selection.selected.capability_id if selection.selected else None
            ),
            "intent_tier": interpretation.intent_tier,
            "routing_confidence": interpretation.confidence,
            "actual_route": actual,
            "actual_intent": actual_intent,
            "winning_router": actual,
            "winning_agent": (
                answer.get("answered_by")
                or answer.get("agent_orchestrator")
                or answer.get("answering_layer")
            ),
            "answering_layer": answer.get("answering_layer"),
            "overlap": overlap,
            "comparison": (
                "agree"
                if comparison is True
                else "disagree"
                if comparison is False
                else "unmapped"
            ),
            "disagreement": disagreement,
        }
        self._items.appendleft(item)

        LOGGER.info(
            "route_shadow_selection %s",
            json.dumps(item, ensure_ascii=False, separators=(",", ":")),
        )
        return item

    def response(self) -> dict[str, Any]:
        overlap_rate = (self.overlaps / self.total * 100.0) if self.total else 0.0
        disagreement_rate = (
            self.disagreements / self.comparable * 100.0 if self.comparable else 0.0
        )
        descriptors = self.registry.descriptors()
        safety_counts = {
            safety: sum(1 for item in descriptors if item.safety_class == safety)
            for safety in ("read", "mutate", "destructive")
        }
        declared_tools = sorted(
            {tool for item in descriptors for tool in item.mcp_tools}
        )
        return {
            "success": True,
            "mode": "passive-shadow-only",
            "dispatch_changed": False,
            "total_queries": self.total,
            "overlap_queries": self.overlaps,
            "overlap_rate_percent": round(overlap_rate, 2),
            "comparable_queries": self.comparable,
            "agreement_queries": self.agreements,
            "unmapped_queries": self.unmapped,
            "registry_actual_disagreements": self.disagreements,
            "disagreement_rate_percent": round(disagreement_rate, 2),
            "selected_by_registry": dict(self.selected_counts.most_common()),
            "actual_routes": dict(self.actual_counts.most_common()),
            "intent_tiers": dict(self.intent_tier_counts.most_common()),
            "capability_count": len(descriptors),
            "capability_safety_counts": safety_counts,
            "declared_mcp_tool_count": len(declared_tools),
            "declared_mcp_tools": declared_tools,
            "catalogue": self.registry.describe(),
            "recent": list(self._items),
        }


def install_route_shadow_observer(
    application: Any,
    registry: RouteRegistry,
    *,
    arbiter: UnifiedRoutingArbiter | None = None,
    limit: int = 200,
) -> RouteShadowObserver:
    """Wrap the final ask handler for diagnostics without changing dispatch."""

    real_ask: AskHandler = application.ask
    observer = RouteShadowObserver(registry, arbiter=arbiter, limit=limit)

    async def shadow_logged_ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        interpretation = observer.arbiter.interpret(query)
        answer = dict(await real_ask(request))
        routing_trace = observer.record(query, answer, interpretation)
        answer["routing_trace"] = {
            key: routing_trace.get(key)
            for key in (
                "winning_router",
                "winning_agent",
                "actual_intent",
                "answering_layer",
                "selected_by_registry",
                "selected_capability",
                "intent_tier",
                "routing_confidence",
                "matched_routes",
                "comparison",
            )
        }
        routing_technical = "Routing decision\n" + json.dumps(
            answer["routing_trace"],
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        if answer.get("technical") not in (None, ""):
            answer["technical"] = routing_technical + "\n\n" + str(answer["technical"])
        else:
            answer["technical"] = routing_technical
        return answer

    shadow_logged_ask.__name__ = "ask_with_route_registry_shadow_observer"
    application.ask = shadow_logged_ask
    application.route_shadow_observer = observer

    @application.app.get("/api/route-shadow", response_model=None)
    async def route_shadow():
        return observer.response()

    return observer


__all__ = ["RouteShadowObserver", "install_route_shadow_observer"]
