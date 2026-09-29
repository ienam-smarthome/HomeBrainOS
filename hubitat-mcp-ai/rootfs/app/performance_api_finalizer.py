from __future__ import annotations

import json
import time
from typing import Any

from final_answer_coordinator import FinalAnswerCoordinator
from performance_live_semantic_guard import guard_live_performance_semantics

_PERFORMANCE_TOOL = "hub_get_performance_stats"
_LOG_TOOL = "hub_get_logs"
_LOG_ARGS = {"since": "30m", "limit": 100}


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def _successful(evidence: list[dict[str, Any]], sub_tool: str) -> bool:
    return any(
        isinstance(row, dict)
        and row.get("success") is not False
        and _sub_tool(row) == sub_tool
        for row in evidence
    )


def _tool_content(result: Any) -> str:
    text = str(getattr(result, "text", "") or "").strip()
    if text:
        return text
    data = getattr(result, "data", None)
    if data is None:
        return ""
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return str(data)


def _summary(result: Any, *, success: bool) -> str:
    if not success:
        text = str(getattr(result, "text", "") or "").strip()
        return (text or "bounded recent log read failed")[:500]
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return "object fields: " + ", ".join(str(key) for key in list(data)[:20])
    if isinstance(data, list):
        return f"{len(data)} recent log rows"
    return "bounded recent log read succeeded"


def _counter(outcome: Any, name: str, amount: int = 1) -> None:
    metrics = getattr(outcome, "metrics", None)
    if not isinstance(metrics, dict):
        return
    counters = metrics.setdefault("counters", {})
    if not isinstance(counters, dict):
        return
    counters[name] = int(counters.get(name) or 0) + int(amount)


def _add_finalize_timing(outcome: Any, elapsed_ms: int) -> None:
    metrics = getattr(outcome, "metrics", None)
    if not isinstance(metrics, dict):
        return
    timings = metrics.setdefault("timings_ms", {})
    if isinstance(timings, dict):
        timings["performance_api_finalize"] = int(elapsed_ms)


async def finalize_performance_api_outcome(
    agent: Any,
    mcp: Any,
    outcome: Any,
    user_prompt: str,
) -> Any:
    """Finalize measured performance answers on the actual `/api/ask` path.

    `process_user_request_result()` intentionally closes its request-local evidence
    scope before returning. 0.16.66 proved that interpreter-startup routing was not
    present in the serving process, so this boundary works from the returned
    outcome instead: it performs the bounded recent-log read with the live MCP
    client, extends the outcome evidence explicitly, runs the shared synthesis
    coordinator over that evidence, then applies the deterministic semantic guard
    before API serialization.
    """

    evidence = [
        dict(row)
        for row in (getattr(outcome, "evidence", None) or [])
        if isinstance(row, dict)
    ]
    if not _successful(evidence, _PERFORMANCE_TOOL):
        return outcome

    started = time.monotonic()
    log_content = ""
    attempts = 0

    if not _successful(evidence, _LOG_TOOL):
        _counter(outcome, "broad_performance_log_api_attempt")
        for gateway in ("hub_manage_logs", "hub_read_diagnostics"):
            attempts += 1
            call_started = time.monotonic()
            try:
                result = await mcp.call_tool(
                    gateway,
                    {"tool": _LOG_TOOL, "args": dict(_LOG_ARGS)},
                )
                success = bool(agent._tool_succeeded(result))
                evidence.append(
                    {
                        "tool": gateway,
                        "sub_tool": _LOG_TOOL,
                        "timestamp": None,
                        "elapsed_ms": round((time.monotonic() - call_started) * 1000),
                        "success": success,
                        "supports_live_claim": True,
                        "evidence_kind": "authoritative_recent_performance_logs",
                        "mutates": False,
                        "effect": "read",
                        "arguments": {"tool": _LOG_TOOL, "args": dict(_LOG_ARGS)},
                        "summary": _summary(result, success=success),
                    }
                )
                if success:
                    log_content = _tool_content(result)
                    _counter(outcome, "broad_performance_log_api_success")
                    break
            except Exception as exc:
                evidence.append(
                    {
                        "tool": gateway,
                        "sub_tool": _LOG_TOOL,
                        "timestamp": None,
                        "elapsed_ms": round((time.monotonic() - call_started) * 1000),
                        "success": False,
                        "supports_live_claim": False,
                        "evidence_kind": "authoritative_recent_performance_logs",
                        "mutates": False,
                        "effect": "read",
                        "arguments": {"tool": _LOG_TOOL, "args": dict(_LOG_ARGS)},
                        "summary": f"bounded recent log read failed: {str(exc)[:300]}",
                    }
                )
            _counter(outcome, "broad_performance_log_api_retry")

        if not _successful(evidence, _LOG_TOOL):
            _counter(outcome, "broad_performance_log_api_failed")
    else:
        _counter(outcome, "broad_performance_log_api_reused")

    if attempts:
        _counter(outcome, "tool_calls", attempts)

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": str(user_prompt).strip()},
        {"role": "assistant", "content": str(getattr(outcome, "message", "") or "")},
    ]
    if log_content:
        messages.append(
            {
                "role": "user",
                "content": (
                    "HOST BROAD PERFORMANCE LOG READ\n"
                    "A bounded recent Hubitat log window was read directly on the "
                    "production API path. Treat these rows as observations, not "
                    "automatic proof of performance causation:\n"
                    + log_content[:24000]
                ),
            }
        )
    elif not _successful(evidence, _LOG_TOOL):
        messages.append(
            {
                "role": "user",
                "content": (
                    "HOST BROAD PERFORMANCE LOG STATUS\n"
                    "The production API attempted the required bounded recent-log "
                    "read but it did not succeed. State this limitation explicitly "
                    "and do not present the analysis as log-complete."
                ),
            }
        )

    model_rounds = 0

    async def counted_chat(
        chat_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        nonlocal model_rounds
        model_rounds += 1
        return await agent._chat(chat_messages, tools)

    coordinator = FinalAnswerCoordinator(counted_chat, lambda: evidence)
    message = await coordinator.answer(messages)
    if model_rounds:
        _counter(outcome, "model_rounds", model_rounds)

    guarded, _changed = guard_live_performance_semantics(message, evidence)
    outcome.message = guarded
    outcome.evidence = evidence
    _add_finalize_timing(outcome, round((time.monotonic() - started) * 1000))
    return outcome


__all__ = ["finalize_performance_api_outcome"]
