from __future__ import annotations

import json
import re
import time
from typing import Any

from final_answer_coordinator import FinalAnswerCoordinator
from performance_live_semantic_guard import guard_live_performance_semantics

_METRICS_TOOL = "hub_get_metrics"
_PERFORMANCE_TOOL = "hub_get_performance_stats"
_JOBS_TOOL = "hub_get_jobs"
_LOG_TOOL = "hub_get_logs"
_LOG_ARGS = {"since": "30m", "limit": 100}
_REPLAY_TOOLS = (_METRICS_TOOL, _PERFORMANCE_TOOL, _JOBS_TOOL)
_FALSE_EVIDENCE_DENIAL = re.compile(
    r"(?:no\s+mcp\s+tools?\s+(?:were\s+)?executed|"
    r"no\s+(?:current-turn\s+)?(?:mcp\s+)?evidence|"
    r"available\s+evidence.*does\s+not\s+establish\s+any\s+facts)",
    re.I | re.S,
)


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


def _first_successful(
    evidence: list[dict[str, Any]], sub_tool: str
) -> dict[str, Any] | None:
    for row in evidence:
        if (
            isinstance(row, dict)
            and row.get("success") is not False
            and _sub_tool(row) == sub_tool
        ):
            return row
    return None


def _tool_content(result: Any) -> str:
    data = getattr(result, "data", None)
    if data is not None:
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return str(data)
    return str(getattr(result, "text", "") or "").strip()


def _summary(result: Any, *, success: bool, fallback: str) -> str:
    if not success:
        text = str(getattr(result, "text", "") or "").strip()
        return (text or fallback)[:500]
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return "object fields: " + ", ".join(str(key) for key in list(data)[:20])
    if isinstance(data, list):
        return f"{len(data)} result rows"
    return fallback


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


def _existing_log_content(evidence: list[dict[str, Any]]) -> str:
    row = _first_successful(evidence, _LOG_TOOL)
    if row is None:
        return ""
    details = row.get("details")
    if not isinstance(details, dict) or not details:
        return ""
    try:
        return json.dumps(details, ensure_ascii=False, default=str)
    except Exception:
        return str(details)


def _receipt_arguments(row: dict[str, Any]) -> dict[str, Any]:
    arguments = row.get("arguments")
    return dict(arguments) if isinstance(arguments, dict) else {}


def _append_snapshot_receipt(
    evidence: list[dict[str, Any]],
    *,
    gateway: str,
    sub_tool: str,
    arguments: dict[str, Any],
    elapsed_ms: int,
    success: bool,
    summary: str,
) -> None:
    evidence.append(
        {
            "tool": gateway,
            "sub_tool": sub_tool,
            "timestamp": None,
            "elapsed_ms": elapsed_ms,
            "success": success,
            "supports_live_claim": success,
            "evidence_kind": "performance_api_synthesis_snapshot",
            "mutates": False,
            "effect": "read",
            "arguments": arguments,
            "summary": summary,
        }
    )


async def _replay_synthesis_sources(
    agent: Any,
    mcp: Any,
    outcome: Any,
    evidence: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """Re-read bounded measured sources so final synthesis receives actual values.

    0.16.67 proved that evidence receipts alone are only source-presence metadata;
    they do not preserve the measured performance payloads that the original model
    saw. Replaying the same read-only calls at the API boundary gives the second
    synthesis an authoritative, current-turn snapshot without treating the first
    assistant draft as evidence.
    """

    packets: list[tuple[str, str]] = []
    for sub_tool in _REPLAY_TOOLS:
        row = _first_successful(evidence, sub_tool)
        if row is None:
            continue
        gateway = str(row.get("tool") or "").strip()
        arguments = _receipt_arguments(row)
        if not gateway or not arguments:
            continue
        started = time.monotonic()
        _counter(outcome, "performance_api_snapshot_attempt")
        try:
            result = await mcp.call_tool(gateway, arguments)
            success = bool(agent._tool_succeeded(result))
            elapsed_ms = round((time.monotonic() - started) * 1000)
            _counter(outcome, "tool_calls")
            _append_snapshot_receipt(
                evidence,
                gateway=gateway,
                sub_tool=sub_tool,
                arguments=arguments,
                elapsed_ms=elapsed_ms,
                success=success,
                summary=_summary(
                    result,
                    success=success,
                    fallback=f"{sub_tool} synthesis snapshot",
                ),
            )
            if success:
                content = _tool_content(result)
                if content:
                    packets.append((sub_tool, content[:24000]))
                    _counter(outcome, "performance_api_snapshot_success")
            else:
                _counter(outcome, "performance_api_snapshot_failed")
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            _counter(outcome, "tool_calls")
            _counter(outcome, "performance_api_snapshot_failed")
            _append_snapshot_receipt(
                evidence,
                gateway=gateway,
                sub_tool=sub_tool,
                arguments=arguments,
                elapsed_ms=elapsed_ms,
                success=False,
                summary=f"{sub_tool} synthesis snapshot failed: {str(exc)[:300]}",
            )
    return packets


async def finalize_performance_api_outcome(
    agent: Any,
    mcp: Any,
    outcome: Any,
    user_prompt: str,
) -> Any:
    """Finalize measured performance answers on the actual `/api/ask` path."""

    evidence = [
        dict(row)
        for row in (getattr(outcome, "evidence", None) or [])
        if isinstance(row, dict)
    ]
    if not _successful(evidence, _PERFORMANCE_TOOL):
        return outcome

    started = time.monotonic()
    original_message = str(getattr(outcome, "message", "") or "")
    log_content = _existing_log_content(evidence)
    log_attempts = 0

    if not _successful(evidence, _LOG_TOOL):
        _counter(outcome, "broad_performance_log_api_attempt")
        for gateway in ("hub_manage_logs", "hub_read_diagnostics"):
            log_attempts += 1
            call_started = time.monotonic()
            try:
                arguments = {"tool": _LOG_TOOL, "args": dict(_LOG_ARGS)}
                result = await mcp.call_tool(gateway, arguments)
                success = bool(agent._tool_succeeded(result))
                _append_snapshot_receipt(
                    evidence,
                    gateway=gateway,
                    sub_tool=_LOG_TOOL,
                    arguments=arguments,
                    elapsed_ms=round((time.monotonic() - call_started) * 1000),
                    success=success,
                    summary=_summary(
                        result,
                        success=success,
                        fallback="bounded recent log read",
                    ),
                )
                if success:
                    log_content = _tool_content(result)
                    _counter(outcome, "broad_performance_log_api_success")
                    break
            except Exception as exc:
                _append_snapshot_receipt(
                    evidence,
                    gateway=gateway,
                    sub_tool=_LOG_TOOL,
                    arguments={"tool": _LOG_TOOL, "args": dict(_LOG_ARGS)},
                    elapsed_ms=round((time.monotonic() - call_started) * 1000),
                    success=False,
                    summary=f"bounded recent log read failed: {str(exc)[:300]}",
                )
            _counter(outcome, "broad_performance_log_api_retry")

        if not _successful(evidence, _LOG_TOOL):
            _counter(outcome, "broad_performance_log_api_failed")
    else:
        _counter(outcome, "broad_performance_log_api_reused")

    if log_attempts:
        _counter(outcome, "tool_calls", log_attempts)

    source_packets = await _replay_synthesis_sources(agent, mcp, outcome, evidence)

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": str(user_prompt).strip()},
        {"role": "assistant", "content": original_message},
    ]
    for sub_tool, content in source_packets:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"HOST CURRENT-TURN PERFORMANCE SOURCE: {sub_tool}\n"
                    "This is a fresh read-only replay of a source already checked in "
                    "this same request. Use its measured values as evidence; do not "
                    "treat the earlier assistant draft as evidence:\n"
                    + content
                ),
            }
        )

    if log_content:
        messages.append(
            {
                "role": "user",
                "content": (
                    "HOST BROAD PERFORMANCE LOG READ\n"
                    "A bounded recent Hubitat log window was read in this request. "
                    "Treat these rows as observations, not automatic proof of "
                    "performance causation:\n"
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
    if _FALSE_EVIDENCE_DENIAL.search(guarded) and any(
        row.get("success") is True for row in evidence if isinstance(row, dict)
    ):
        _counter(outcome, "performance_api_false_evidence_fallback")
        guarded, _changed = guard_live_performance_semantics(original_message, evidence)

    outcome.message = guarded
    outcome.evidence = evidence
    _add_finalize_timing(outcome, round((time.monotonic() - started) * 1000))
    return outcome


__all__ = ["finalize_performance_api_outcome"]
