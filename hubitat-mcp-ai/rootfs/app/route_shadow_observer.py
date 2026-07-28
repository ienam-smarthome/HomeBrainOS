from __future__ import annotations

import json
import logging
from collections import Counter, deque
from typing import Any, Awaitable, Callable

from route_registry import RouteRegistry


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
LOGGER = logging.getLogger("homebrain.route_shadow")


class RouteShadowObserver:
    """Passive production observer for RouteRegistry overlap diagnostics.

    The observer never dispatches or changes an answer. It records what the
    existing route catalogue would have selected and compares that with the
    route which actually answered through the maintained request stack.
    """

    def __init__(self, registry: RouteRegistry, *, limit: int = 200) -> None:
        self.registry = registry
        self.limit = max(20, min(2000, int(limit)))
        self._items: deque[dict[str, Any]] = deque(maxlen=self.limit)
        self.total = 0
        self.overlaps = 0
        self.selected_counts: Counter[str] = Counter()
        self.actual_counts: Counter[str] = Counter()
        self.disagreements = 0

    def record(self, query: str, answer: dict[str, Any], selection: Any) -> None:
        matches = [match.name for match in selection.matches]
        selected = selection.selected.name if selection.selected else None
        actual = str(answer.get("route") or "") or None
        overlap = len(matches) > 1
        disagreement = bool(selected and actual and selected != actual)

        self.total += 1
        if overlap:
            self.overlaps += 1
        if selected:
            self.selected_counts[selected] += 1
        if actual:
            self.actual_counts[actual] += 1
        if disagreement:
            self.disagreements += 1

        item = {
            "query": query,
            "matched_routes": matches,
            "selected_by_registry": selected,
            "actual_route": actual,
            "overlap": overlap,
            "disagreement": disagreement,
        }
        self._items.appendleft(item)

        LOGGER.info(
            "route_shadow_selection %s",
            json.dumps(item, ensure_ascii=False, separators=(",", ":")),
        )

    def response(self) -> dict[str, Any]:
        overlap_rate = (self.overlaps / self.total * 100.0) if self.total else 0.0
        disagreement_rate = (
            self.disagreements / self.total * 100.0 if self.total else 0.0
        )
        return {
            "success": True,
            "mode": "passive-shadow-only",
            "dispatch_changed": False,
            "total_queries": self.total,
            "overlap_queries": self.overlaps,
            "overlap_rate_percent": round(overlap_rate, 2),
            "registry_actual_disagreements": self.disagreements,
            "disagreement_rate_percent": round(disagreement_rate, 2),
            "selected_by_registry": dict(self.selected_counts.most_common()),
            "actual_routes": dict(self.actual_counts.most_common()),
            "recent": list(self._items),
        }


def install_route_shadow_observer(
    application: Any,
    registry: RouteRegistry,
    *,
    limit: int = 200,
) -> RouteShadowObserver:
    """Wrap the final ask handler for diagnostics without changing dispatch."""

    real_ask: AskHandler = application.ask
    observer = RouteShadowObserver(registry, limit=limit)

    async def shadow_logged_ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        selection = registry.select(query)
        answer = dict(await real_ask(request))
        observer.record(query, answer, selection)
        return answer

    shadow_logged_ask.__name__ = "ask_with_route_registry_shadow_observer"
    application.ask = shadow_logged_ask
    application.route_shadow_observer = observer

    @application.app.get("/api/route-shadow", response_model=None)
    async def route_shadow():
        return observer.response()

    return observer


__all__ = ["RouteShadowObserver", "install_route_shadow_observer"]
