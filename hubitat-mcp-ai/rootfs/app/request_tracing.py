from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from collections import deque
from typing import Any, Awaitable, Callable

from mcp_state_broker import MCPStateBroker, begin_mcp_trace, end_mcp_trace
from routing_policy import classify_query


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class RequestTraceStore:
    """Bounded in-memory request history for route and latency diagnostics."""

    def __init__(self, broker: MCPStateBroker, limit: int = 20) -> None:
        self.broker = broker
        self.limit = max(5, min(100, int(limit)))
        self._items: deque[dict[str, Any]] = deque(maxlen=self.limit)

    def add(self, item: dict[str, Any]) -> None:
        self._items.appendleft(item)

    def recent(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._items]

    def response(self) -> dict[str, Any]:
        items = self.recent()
        return {
            "success": True,
            "count": len(items),
            "requests": items,
            "cache": self.broker.stats(),
        }


def _performance(trace: dict[str, Any], answer: dict[str, Any] | None) -> dict[str, Any]:
    events = [
        event
        for event in trace.get("mcp_events", [])
        if isinstance(event, dict)
    ]
    tools = [
        str(event.get("tool"))
        for event in events
        if event.get("tool") and event.get("tool") != "cache.invalidate"
    ]
    return {
        "trace_id": trace["trace_id"],
        "route_selected": trace["route_selected"],
        "route_reason": trace["route_reason"],
        "final_route": (answer or {}).get("route") or trace.get("final_route") or "error",
        "elapsed_ms": trace.get("elapsed_ms", 0),
        "mcp_duration_ms": sum(
            int(event.get("duration_ms") or 0)
            for event in events
            if event.get("tool") != "cache.invalidate"
        ),
        "mcp_calls": len(tools),
        "mcp_tools": tools,
        "cache_hits": sum(event.get("cache") == "hit" for event in events),
        "cache_misses": sum(event.get("cache") == "miss" for event in events),
        "cache_coalesced": sum(event.get("cache") == "coalesced" for event in events),
        "cache_bypassed": sum(
            event.get("cache") in {"bypass", "disabled"} for event in events
        ),
        "cancelled": bool(trace.get("cancelled")),
        "model": (answer or {}).get("model") or (answer or {}).get("response_model"),
    }


def _agent_execution(answer: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, safe account of what the agent actually executed."""

    tools: list[dict[str, Any]] = []
    for item in answer.get("tools_used") or []:
        if isinstance(item, str):
            tools.append({"name": item})
            continue
        if not isinstance(item, dict) or not item.get("name"):
            continue
        record: dict[str, Any] = {"name": str(item["name"])}
        for key in ("success", "blocked", "error", "evidence"):
            if item.get(key) not in (None, "", {}):
                record[key] = item[key]
        tools.append(record)

    execution: dict[str, Any] = {}
    if tools:
        execution["tools_used"] = tools
    for key in (
        "agent_orchestrator",
        "tool_rounds",
        "tool_policy_corrected",
        "synthesis_policy_corrected",
        "authoritative_recovery",
        "targeted_device_search",
        "conversation_history_used",
        "legacy_fallback_used",
    ):
        if answer.get(key) not in (None, ""):
            execution[key] = answer[key]
    return execution


def _attach_performance(answer: dict[str, Any], performance: dict[str, Any]) -> None:
    answer["trace_id"] = performance["trace_id"]
    answer["performance"] = performance
    heading = "Request performance\n" + json.dumps(
        performance,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    execution = _agent_execution(answer)
    if execution:
        heading += "\n\nAgent execution\n" + json.dumps(
            execution,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    technical = answer.get("technical")
    if technical not in (None, ""):
        answer["technical"] = heading + "\n\nMCP response\n" + str(technical)
    else:
        answer["technical"] = heading


def install_request_tracing(
    application: Any,
    broker: MCPStateBroker,
    *,
    limit: int = 20,
) -> RequestTraceStore:
    """Wrap the active ask handler and expose recent route/performance diagnostics."""
    original_ask: AskHandler = application.ask
    store = RequestTraceStore(broker, limit=limit)

    async def traced_ask(request: Any) -> dict[str, Any]:
        query = str(request.query or "").strip()
        decision = classify_query(query)
        trace: dict[str, Any] = {
            "trace_id": uuid.uuid4().hex[:10],
            "query": query[:300],
            "route_selected": decision.route,
            "route_reason": decision.reason,
            "started_at": time.time(),
            "mcp_events": [],
        }
        token = begin_mcp_trace(trace)
        started = time.perf_counter()
        answer: dict[str, Any] | None = None
        try:
            answer = await original_ask(request)
            trace["final_route"] = answer.get("route")
            return answer
        except asyncio.CancelledError:
            trace["cancelled"] = True
            trace["final_route"] = "cancelled"
            raise
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            trace["error"] = message
            trace["exception_type"] = type(exc).__name__
            trace["final_route"] = "server-error"
            answer = {
                "success": False,
                "route": "server-error",
                "intent": "backend-exception",
                "message": (
                    "HomeBrain stopped safely because the backend raised "
                    f"{type(exc).__name__}: {message}"
                ),
                "answered_by": "HomeBrain error boundary",
                "technical": json.dumps(
                    {
                        "exception_type": type(exc).__name__,
                        "error": message,
                        "traceback": traceback.format_exc(limit=12),
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            }
            return answer
        finally:
            trace["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
            trace["completed_at"] = time.time()
            performance = _performance(trace, answer)
            trace["performance"] = performance
            if answer is not None:
                _attach_performance(answer, performance)
            store.add(
                {
                    "trace_id": trace["trace_id"],
                    "query": trace["query"],
                    "route_selected": trace["route_selected"],
                    "route_reason": trace["route_reason"],
                    "final_route": performance["final_route"],
                    "elapsed_ms": performance["elapsed_ms"],
                    "mcp_duration_ms": performance["mcp_duration_ms"],
                    "mcp_calls": performance["mcp_calls"],
                    "mcp_tools": performance["mcp_tools"],
                    "cache_hits": performance["cache_hits"],
                    "cache_misses": performance["cache_misses"],
                    "cache_coalesced": performance["cache_coalesced"],
                    "cancelled": performance["cancelled"],
                    "model": performance["model"],
                    "completed_at": trace["completed_at"],
                    "error": trace.get("error"),
                    "exception_type": trace.get("exception_type"),
                }
            )
            end_mcp_trace(token)

    application.ask = traced_ask

    @application.app.get("/api/recent-requests", response_model=None)
    async def recent_requests():
        return store.response()

    @application.app.get("/api/mcp-cache", response_model=None)
    async def mcp_cache():
        return {"success": True, "cache": broker.stats()}

    @application.app.post("/api/mcp-cache/clear", response_model=None)
    async def clear_mcp_cache():
        removed = await broker.clear()
        return {
            "success": True,
            "removed": removed,
            "cache": broker.stats(),
        }

    return store


__all__ = ["RequestTraceStore", "_agent_execution", "install_request_tracing"]
