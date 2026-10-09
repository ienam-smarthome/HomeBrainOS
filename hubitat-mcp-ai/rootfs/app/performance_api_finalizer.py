from __future__ import annotations

import json
import re
import time
from contextvars import ContextVar
from functools import wraps
from typing import Any

from final_answer_coordinator import FinalAnswerCoordinator
from performance_live_semantic_guard import guard_live_performance_semantics
from synthesis_validator import consume_performance_repair_issues
from tool_executor import ToolExecutor

_PERFORMANCE_TOOL = "hub_get_performance_stats"
_METRICS_TOOL = "hub_get_metrics"
_JOBS_TOOL = "hub_get_jobs"
_LOG_TOOL = "hub_get_logs"
_LOG_ARGS = {"since": "30m", "limit": 100}
_CAPTURED_TOOLS = {
    _METRICS_TOOL,
    _PERFORMANCE_TOOL,
    _JOBS_TOOL,
    _LOG_TOOL,
}
_REPAIR_REASON_COUNTERS = {
    "performance_log_causality": "performance_api_repair_log_causality",
    "performance_live_semantics": "performance_api_repair_live_semantics",
    "performance_evidence_first": "performance_api_repair_evidence_first",
    "performance_log_observation": "performance_api_repair_log_observation",
}
# 0.16.72: the old 12k-per-item / 32k FIFO packet could evict the metrics
# payload simply because metrics was normally captured first. Keep the packet
# bounded while reserving enough space for every performance source so later
# jobs/log payloads cannot silently remove current memory/temperature/database.
_CAPTURE_LIMITS = {
    _METRICS_TOOL: 7500,
    _PERFORMANCE_TOOL: 11500,
    _JOBS_TOOL: 7500,
    _LOG_TOOL: 4500,
}
_MAX_PACKET_CHARS = 32000
_PACKET: ContextVar[tuple[tuple[str, str], ...]] = ContextVar(
    "performance_api_synthesis_packet",
    default=(),
)
_FALSE_EVIDENCE_DENIAL = re.compile(
    r"(?:no\s+mcp\s+tools?\s+(?:were\s+)?executed|"
    r"no\s+(?:current-turn\s+)?(?:mcp\s+)?evidence|"
    r"available\s+evidence.*does\s+not\s+establish\s+any\s+facts)",
    re.I | re.S,
)
_METRIC_DENIAL_LINE = re.compile(
    r"(?im)^.*(?:available\s+evidence|current\s+evidence|this\s+turn).{0,100}"
    r"does\s+not\s+establish.{0,120}(?:current\s+)?memory(?:\s+usage)?.{0,120}"
    r"(?:internal\s+)?temperature.{0,120}database\s+size.*$"
)
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def _capture_sub_tool(name: str, arguments: dict[str, Any]) -> str:
    leaf = str(arguments.get("tool") or "").strip()
    return leaf or str(name or "").strip()


def _packet_chars(rows: list[tuple[str, str]]) -> int:
    return sum(len(name) + len(value) for name, value in rows)


def _append_packet(sub_tool: str, content: str) -> None:
    if sub_tool not in _CAPTURED_TOOLS:
        return
    text = str(content or "").strip()
    if not text:
        return
    text = text[: _CAPTURE_LIMITS[sub_tool]]
    rows = [row for row in _PACKET.get() if row[0] != sub_tool]
    rows.append((sub_tool, text))

    # The fixed source budgets fit below the packet ceiling. This defensive
    # trim keeps every source present even if names/budgets change later; it
    # never drops a whole source as the 0.16.69-0.16.71 FIFO implementation did.
    overflow = _packet_chars(rows) - _MAX_PACKET_CHARS
    if overflow > 0:
        preferred = (_LOG_TOOL, _JOBS_TOOL, _PERFORMANCE_TOOL, _METRICS_TOOL)
        mutable = list(rows)
        for source in preferred:
            if overflow <= 0:
                break
            for index, (name, value) in enumerate(mutable):
                if name != source:
                    continue
                removable = max(0, len(value) - 512)
                cut = min(removable, overflow)
                if cut:
                    mutable[index] = (name, value[: len(value) - cut])
                    overflow -= cut
                break
        rows = mutable

    _PACKET.set(tuple(rows))


def _consume_packet() -> list[tuple[str, str]]:
    rows = list(_PACKET.get())
    _PACKET.set(())
    return rows


def _install_tool_executor_capture() -> None:
    """Capture the exact normalized provider payloads already read this request."""

    current = ToolExecutor.execute
    if getattr(current, "_homebrain_performance_packet_capture", False):
        return

    @wraps(current)
    async def wrapped(
        self: ToolExecutor,
        name: str,
        arguments: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ):
        execution = await current(self, name, arguments, *args, **kwargs)
        if getattr(execution, "success", False):
            execution_arguments = getattr(execution, "arguments", None)
            safe_arguments = (
                dict(execution_arguments)
                if isinstance(execution_arguments, dict)
                else dict(arguments or {})
            )
            _append_packet(
                _capture_sub_tool(name, safe_arguments),
                str(getattr(execution, "content", "") or ""),
            )
        return execution

    setattr(wrapped, "_homebrain_performance_packet_capture", True)
    ToolExecutor.execute = wrapped


_install_tool_executor_capture()


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


def _set_timing(outcome: Any, name: str, elapsed_ms: int) -> None:
    metrics = getattr(outcome, "metrics", None)
    if not isinstance(metrics, dict):
        return
    timings = metrics.setdefault("timings_ms", {})
    if isinstance(timings, dict):
        timings[name] = int(elapsed_ms)


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


def _append_log_receipt(
    evidence: list[dict[str, Any]],
    *,
    gateway: str,
    arguments: dict[str, Any],
    elapsed_ms: int,
    success: bool,
    summary: str,
) -> None:
    evidence.append(
        {
            "tool": gateway,
            "sub_tool": _LOG_TOOL,
            "timestamp": None,
            "elapsed_ms": elapsed_ms,
            "success": success,
            "supports_live_claim": success,
            "evidence_kind": "performance_api_recent_logs",
            "mutates": False,
            "effect": "read",
            "arguments": arguments,
            "summary": summary,
        }
    )


def _packet_map(rows: list[tuple[str, str]]) -> dict[str, str]:
    packet: dict[str, str] = {}
    for sub_tool, content in rows:
        name = str(sub_tool or "").strip()
        text = str(content or "").strip()
        if name and text:
            packet[name] = text
    return packet


def _latest_assistant_content(messages: list[dict[str, Any]], fallback: str) -> str:
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = str(message.get("content") or "").strip()
        if content:
            return content
    return fallback


def _has_configuration_evidence(evidence: list[dict[str, Any]]) -> bool:
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is False:
            continue
        kind = str(row.get("evidence_kind") or "").casefold()
        if any(token in kind for token in ("configuration", "preferences", "settings", "code", "implementation")):
            return True
        sub_tool = _sub_tool(row).casefold()
        if any(
            token in sub_tool
            for token in (
                "get_rule",
                "rule_detail",
                "get_app",
                "app_code",
                "driver_code",
                "get_driver",
                "device_config",
                "device_preferences",
                "get_preferences",
                "get_settings",
                "read_settings",
            )
        ):
            return True
    return False


def _repair_01672_fragment(text: str, *, has_configuration: bool) -> str:
    """Repair exact semantic gaps exposed by the 0.16.71 live proof."""

    repaired = str(text or "")
    repaired = re.sub(
        r"(?i)the\s+following\s+performance\s+bottlenecks\s+have\s+been\s+identified",
        "the following performance observations and outliers were identified",
        repaired,
    )
    repaired = re.sub(
        r"(?i)Critical\s+Performance\s+Issues",
        "Performance Observations",
        repaired,
    )
    repaired = re.sub(
        r"(?i)There\s+is\s+a\s+severe\s+synchronization\s+of\s+scheduled\s+tasks",
        "Many scheduled tasks share the same scheduled timestamp",
        repaired,
    )
    repaired = re.sub(
        r"(?i)scheduled\s+to\s+execute\s+(over\s+\d+\s+jobs?)\s+simultaneously",
        r"has \1 scheduled for the same second",
        repaired,
    )
    repaired = re.sub(
        r"(?i)The\s+logs\s+indicate\s+an\s+efficiency\s+issue\s+with",
        "The logs show repeated activity from",
        repaired,
    )
    repaired = re.sub(
        r"(?i)constant\s+reporting\s+adds\s+to\s+the\s+background\s+load",
        "frequent reporting is an observed activity; this turn does not establish material background load from it",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\*\*Stagger\s+the\s+[\"“]?Block[\"”]?\s+Ticks?\.\*\*",
        '**Review the "Block" tick alignment.**',
        repaired,
    )
    repaired = re.sub(
        r"(?i)\*\*Shift\s+System\s+Tasks\.\*\*",
        "**Review system-task timing.**",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\*\*Top-of-Hour\s+Jobs\*\*",
        "**Scheduled Job Cluster**",
        repaired,
    )

    if not has_configuration:
        repaired = re.sub(
            r"(?i)The\s+high\s+volume\s+of\s+`?sessionTick`?\s+jobs\s+at\s+`?:00`?\s+seconds\s+should\s+be\s+offset\.",
            "The `sessionTick` jobs share a common scheduled second; inspect the responsible app before changing their alignment because this turn does not establish that offsetting is configurable, necessary, or behaviour-preserving.",
            repaired,
        )
        repaired = re.sub(
            r"(?i)Move\s+the\s+14:30:00\s+cluster.*?to\s+different\s+offsets.*?flatten\s+the\s+load\s+curve\.",
            "Inspect the responsible app/system-task configuration before changing this cluster's timing; this turn does not establish that alternate offsets are configurable, necessary, or behaviour-preserving.",
            repaired,
        )
    return repaired


def _repair_01672_surface(message: str, evidence: list[dict[str, Any]]) -> str:
    """Apply 0.16.72 wording repairs without crossing Markdown table cells."""

    has_configuration = _has_configuration_evidence(evidence)
    repaired_lines: list[str] = []
    for line in str(message or "").splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        core = line[:-1] if newline else line
        stripped = core.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            indent = core[: len(core) - len(core.lstrip())]
            cells = stripped[1:-1].split("|")
            repaired_cells: list[str] = []
            for raw in cells:
                cell = raw.strip()
                if _TABLE_SEPARATOR_CELL.fullmatch(cell):
                    repaired_cells.append(cell)
                else:
                    repaired_cells.append(
                        _repair_01672_fragment(
                            cell,
                            has_configuration=has_configuration,
                        ).strip()
                    )
            core = indent + "| " + " | ".join(repaired_cells) + " |"
        else:
            core = _repair_01672_fragment(
                core,
                has_configuration=has_configuration,
            )
        repaired_lines.append(core + newline)
    return "".join(repaired_lines)


def _decode_payload(content: str) -> Any:
    try:
        payload = json.loads(str(content or ""))
    except Exception:
        return None
    if isinstance(payload, dict) and "result" in payload:
        return payload.get("result")
    return payload


def _find_metric_value(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] not in (None, ""):
                return value[key]
        for child in value.values():
            found = _find_metric_value(child, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value[:20]:
            found = _find_metric_value(child, keys)
            if found not in (None, ""):
                return found
    return None


def _format_metric_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _metric_fact_sentence(metrics_content: str) -> str:
    payload = _decode_payload(metrics_content)
    if payload is None:
        return ""
    free_memory = _find_metric_value(
        payload,
        ("freeMemoryMB", "free_memory_mb", "memoryFreeMB"),
    )
    temperature = _find_metric_value(
        payload,
        ("temperatureC", "internalTemperatureC", "hubTemperatureC"),
    )
    database = _find_metric_value(
        payload,
        ("databaseSizeMB", "databaseMB", "dbSizeMB"),
    )
    facts: list[str] = []
    if free_memory not in (None, ""):
        facts.append(f"free memory {_format_metric_number(free_memory)} MB")
    if temperature not in (None, ""):
        facts.append(f"internal temperature {_format_metric_number(temperature)}°C")
    if database not in (None, ""):
        facts.append(f"database {_format_metric_number(database)} MB")
    if not facts:
        return ""
    return "**Current metrics:** " + "; ".join(facts) + "."


def _repair_metric_denial(
    message: str,
    *,
    metrics_content: str,
    metrics_succeeded: bool,
) -> tuple[str, bool]:
    if not metrics_succeeded:
        return message, False
    match = _METRIC_DENIAL_LINE.search(str(message or ""))
    if match is None:
        return message, False
    replacement = _metric_fact_sentence(metrics_content)
    if not replacement:
        replacement = (
            "**Metrics context:** `hub_get_metrics` succeeded in this turn, but its detailed values were not "
            "retained for final synthesis. This is a synthesis-context limitation, not evidence that memory, "
            "temperature, or database metrics were unavailable from the hub."
        )
    repaired = _METRIC_DENIAL_LINE.sub(replacement, str(message or ""), count=1)
    return repaired, repaired != message


def _normalize_recommendation_table(message: str) -> tuple[str, bool]:
    """Keep guard-generated prose between table rows from breaking Markdown.

    Semantic guards sometimes replace an unsupported row-level claim with a
    standalone sentence. This is valuable uncertainty, but Markdown ends the
    table at that sentence and renders the remaining data rows as plain text.
    Move *only interleaved* non-row material after the table, explicitly
    detached from any particular target; do not drop diagnostic caveats.
    """
    original = str(message or "")
    lines = original.splitlines(keepends=True)
    header_at: int | None = None
    for index, line in enumerate(lines):
        low = line.casefold()
        if line.lstrip().startswith("|") and "| priority" in low and (
            "| target" in low or "| app" in low or "| device" in low
        ):
            header_at = index
            break
    if header_at is None or header_at + 1 >= len(lines):
        return original, False
    separator = lines[header_at + 1].strip()
    if not (separator.startswith("|") and separator.endswith("|") and
            re.match(r"^\|\s*:?-{3,}", separator)):
        return original, False
    expected_columns = lines[header_at].count("|")
    ending = header_at + 2
    while ending < len(lines) and not re.match(r"^\s*#{1,6}\s+", lines[ending]):
        ending += 1
    table_indices = [
        idx for idx in range(header_at + 2, ending)
        if lines[idx].strip().startswith("|")
        and lines[idx].strip().endswith("|")
        and lines[idx].count("|") == expected_columns
    ]
    if len(table_indices) < 2:
        return original, False
    last_row = table_indices[-1]
    table_rows = []
    displaced_notes = []
    for idx in range(header_at + 2, last_row + 1):
        if idx in table_indices:
            table_rows.append(lines[idx])
        elif lines[idx].strip():
            displaced_notes.append(lines[idx].strip())
    if not displaced_notes:
        return original, False
    notes = [
        "\n**Additional qualifications (not tied to individual table rows):**\n",
        *[f"- {note}\n" for note in displaced_notes],
    ]
    repaired = (
        lines[:header_at + 2]
        + table_rows
        + ["\n"]
        + notes
        + lines[last_row + 1:]
    )
    return "".join(repaired), True


def _repair_unattributed_performance_recommendations(
    message: str, evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Keep an observed signal's timing out of an anonymous remediation step.

    A semantic guard may faithfully correct cadence numbers but accidentally
    leave a numbered 'Device Reporting' recommendation with no named source
    or actual inspection action. Source-link the measured timing when uniquely
    identified by the host timing evidence, else mark the source unresolved.
    """
    text = str(message or "")
    facts: list[dict[str, Any]] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is False:
            continue
        details = receipt.get("details") or {}
        if not isinstance(details, dict):
            continue
        timing = details.get("hostDerivedTiming") or {}
        if isinstance(timing, dict) and isinstance(timing.get("cadence"), list):
            facts.extend(row for row in timing["cadence"] if isinstance(row, dict))
    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        observation = match.group("observation").strip()
        nums = re.search(r"\bmedian(?:\s+interval)?\s+(\d+(?:\.\d+)?)\s+seconds?\b", observation, re.I)
        matches: list[dict[str, Any]] = []
        if nums:
            observed = float(nums.group(1))
            for fact in facts:
                try:
                    recorded = float(fact.get("medianIntervalSeconds"))
                except (ValueError, TypeError):
                    continue
                if abs(recorded - observed) <= max(.2, observed * .02):
                    matches.append(fact)
        unique = {
            (str(row.get("sourceRef") or ""), str(row.get("signal") or "")): row
            for row in matches
        }
        if len(unique) == 1:
            fact = next(iter(unique.values()))
            source = str(fact.get("source") or "device").strip()
            ref = str(fact.get("sourceRef") or "")
            identifier = ref.split("|", 1)[1] if "|" in ref else ""
            signal = str(fact.get("signal") or "reporting").strip()
            subject = f"{source} (ID {identifier}), {signal}" if identifier else f"{source}, {signal}"
            return (
                f"{prefix}**Device reporting:** Inspect {subject} and its "
                "configured report threshold/interval and dependencies before "
                "considering a change. Recorded timing: " + observation
            )
        return (
            f"{prefix}**Device reporting:** Identify the exact device and signal "
            "from a targeted read before changing reporting settings. "
            "Unattributed sampled timing: " + observation
        )

    rule = re.compile(
        r"(?im)^(?P<prefix>\s*\d+[.)]\s+)(?:\*{0,2})?"
        r"Device Reporting(?:\*{0,2})?\s*:\s*"
        r"(?P<observation>(?:Irregular observed intervals|"
        r"Regular observed intervals|Observed intervals)[^\n]*)$"
    )
    corrected = rule.sub(replace, text)
    # A failed admin lookup in a server log establishes a request failure,
    # not a persistent reference retained in the server's configuration.
    if not _has_configuration_evidence(evidence):
        old = re.compile(
            r"(?im)^(?P<prefix>\s*\d+[.)]\s+)"
            r"(?:\*{0,2})?MCP Rule Server(?:\*{0,2})?\s*:\s*"
            r"Inspect (?:the )?configuration of (?:the )?MCP Rule Server "
            r"to determine if it is referencing (?P<objects>[^\n.]+)\."
        )
        corrected = old.sub(
            lambda match: (
                f"{match.group('prefix')}**MCP Rule Server:** Trace the caller "
                "and arguments of the failed app-config and validation requests "
                "before concluding that the server retains obsolete app "
                "references. The logged errors alone do not explain its "
                "performance share."
            ),
            corrected,
        )
    return corrected, corrected != text


async def finalize_performance_api_outcome(
    agent: Any,
    mcp: Any,
    outcome: Any,
    user_prompt: str,
) -> Any:
    """Finalize measured performance answers on the actual `/api/ask` path.

    Reuse the normalized, privacy-redacted ToolExecutor payloads from the original
    reasoning turn rather than re-reading metrics/performance/jobs at the API
    boundary. Only the mandatory bounded recent-log read is added when the original
    turn did not already obtain one.

    0.16.70 made this path single-provider-pass. 0.16.72 preserves every bounded
    source class in that private packet and adds context-aware fail-closed repairs
    for the exact semantic/metrics contradictions exposed by the 0.16.71 live proof.
    """

    captured = _packet_map(_consume_packet())
    evidence = [
        dict(row)
        for row in (getattr(outcome, "evidence", None) or [])
        if isinstance(row, dict)
    ]
    if not _successful(evidence, _PERFORMANCE_TOOL):
        return outcome

    started = time.monotonic()
    original_message = str(getattr(outcome, "message", "") or "")
    if captured:
        _counter(outcome, "performance_api_packet_sources", len(captured))
    if captured.get(_METRICS_TOOL):
        _counter(outcome, "performance_api_metrics_payload_reused")
    elif _successful(evidence, _METRICS_TOOL):
        _counter(outcome, "performance_api_metrics_payload_missing")

    # Prefer the compact evidence-log details when they are already available;
    # fall back to the bounded private packet otherwise.
    log_content = _existing_log_content(evidence) or captured.get(_LOG_TOOL, "")
    log_attempts = 0

    if not _successful(evidence, _LOG_TOOL):
        _counter(outcome, "broad_performance_log_api_attempt")
        for gateway in ("hub_manage_logs", "hub_read_diagnostics"):
            log_attempts += 1
            call_started = time.monotonic()
            arguments = {"tool": _LOG_TOOL, "args": dict(_LOG_ARGS)}
            try:
                result = await mcp.call_tool(gateway, arguments)
                success = bool(agent._tool_succeeded(result))
                _append_log_receipt(
                    evidence,
                    gateway=gateway,
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
                _append_log_receipt(
                    evidence,
                    gateway=gateway,
                    arguments=arguments,
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

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": str(user_prompt).strip()},
        {"role": "assistant", "content": original_message},
    ]

    for sub_tool in (_METRICS_TOOL, _PERFORMANCE_TOOL, _JOBS_TOOL):
        content = captured.get(sub_tool)
        if not content:
            if sub_tool == _METRICS_TOOL and _successful(evidence, _METRICS_TOOL):
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "HOST CURRENT-TURN METRICS STATUS\n"
                            "hub_get_metrics succeeded in this request, but its detailed private payload was not "
                            "retained. Do not claim the metrics tool was not executed or that the hub lacks those "
                            "metrics; state the synthesis-context limitation if the values are needed."
                        ),
                    }
                )
            continue
        extra = ""
        if sub_tool == _METRICS_TOOL:
            extra = (
                " Memory, internal-temperature, database-size, and health fields in this source are current-turn "
                "evidence. If those fields are present, do not state that those metrics are unavailable."
            )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"HOST CURRENT-TURN PERFORMANCE SOURCE: {sub_tool}\n"
                    "This is the normalized, privacy-redacted payload already read by "
                    "the original tool turn. Use its measured values as current-turn "
                    "evidence; do not treat the earlier assistant draft as evidence."
                    + extra
                    + "\n"
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

    provider_rounds = 0
    first_synthesis = ""

    async def single_pass_chat(
        chat_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        nonlocal provider_rounds, first_synthesis
        if provider_rounds:
            _counter(outcome, "performance_api_deterministic_repair")
            return {
                "content": first_synthesis
                or _latest_assistant_content(chat_messages, original_message)
            }

        model_started = time.monotonic()
        response = await agent._chat(chat_messages, tools)
        _set_timing(
            outcome,
            "performance_api_model",
            round((time.monotonic() - model_started) * 1000),
        )
        provider_rounds = 1
        first_synthesis = str(response.get("content") or "").strip()
        return response

    coordinator = FinalAnswerCoordinator(single_pass_chat, lambda: evidence)
    message = await coordinator.answer(messages)
    if provider_rounds:
        _counter(outcome, "model_rounds", provider_rounds)

    # Validation runs inside the request-coordinator child task, while the API
    # presenter runs in its parent task. ContextVar state does not flow back from
    # child to parent, so copy the fixed-vocabulary repair reasons into the
    # serializable outcome metrics before returning from this task.
    for issue in consume_performance_repair_issues():
        counter = _REPAIR_REASON_COUNTERS.get(issue)
        if counter:
            _counter(outcome, counter)

    guarded, _changed = guard_live_performance_semantics(message, evidence)
    guarded = _repair_01672_surface(guarded, evidence)
    guarded, metric_denial_changed = _repair_metric_denial(
        guarded,
        metrics_content=captured.get(_METRICS_TOOL, ""),
        metrics_succeeded=_successful(evidence, _METRICS_TOOL),
    )
    if metric_denial_changed:
        _counter(outcome, "performance_api_metric_denial_repair")

    if _FALSE_EVIDENCE_DENIAL.search(guarded) and any(
        row.get("success") is True for row in evidence if isinstance(row, dict)
    ):
        _counter(outcome, "performance_api_false_evidence_fallback")
        guarded, _changed = guard_live_performance_semantics(original_message, evidence)
        guarded = _repair_01672_surface(guarded, evidence)
        guarded, metric_denial_changed = _repair_metric_denial(
            guarded,
            metrics_content=captured.get(_METRICS_TOOL, ""),
            metrics_succeeded=_successful(evidence, _METRICS_TOOL),
        )
        if metric_denial_changed:
            _counter(outcome, "performance_api_metric_denial_repair")

    guarded, table_repaired = _normalize_recommendation_table(guarded)
    if table_repaired:
        _counter(outcome, "performance_api_markdown_table_repaired")

    guarded, recommendation_repaired = _repair_unattributed_performance_recommendations(
        guarded, evidence
    )
    if recommendation_repaired:
        _counter(outcome, "performance_api_recommendation_attribution_repaired")

    outcome.message = guarded
    outcome.evidence = evidence
    _set_timing(
        outcome,
        "performance_api_finalize",
        round((time.monotonic() - started) * 1000),
    )
    return outcome


__all__ = ["finalize_performance_api_outcome"]
