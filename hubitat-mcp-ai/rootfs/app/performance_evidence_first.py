"""Evidence-first synthesis contract and final backstop for broad performance answers.

The performance API already has the normalized current-turn payloads. This module
keeps the model focused on those sources instead of inventing mechanisms or
qualitative thresholds, and provides a small generic backstop for unsupported
language that can still escape model synthesis.
"""

from __future__ import annotations

import re
from typing import Any


_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_MARKDOWN_PREFIX = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+|>\s+))(.*)$", re.S)

_CONDITIONAL_BLOCKING = re.compile(
    r"(?i)\bif\b[^.!?\n]{0,180}\b(?:synchronous|blocking|blocking\s+network\s+calls?)\b"
    r"[^.!?\n]{0,220}\b(?:can|could|may|might)\b[^.!?\n]{0,180}"
    r"\b(?:stutter|delay(?:ed|s|ing)?|lag|stall)\b"
)
_REPORTING_CAUSAL = re.compile(
    r"(?i)\b(?:reporting|reports?|calls?|activity|chatter)\b[^.!?\n]{0,220}"
    r"\b(?:increase|increases|increased|increasing|add|adds|adding|fill|fills|filling|"
    r"slow|slows|slowing)\b[^.!?\n]{0,220}"
    r"\b(?:background\s+overhead|overhead|event\s+logs?|logs?|history\s+lookups?|history)\b"
)
_SUMMARY_OVERREACH = re.compile(
    r"(?i)\bsignificant\s+inefficienc(?:y|ies)\b[^.!?\n]{0,220}"
    r"\b(?:may|might|can|could)\b[^.!?\n]{0,160}\b(?:latency|performance\s+degradation|lag|stutter)\b"
)
_PROCESSING_LOAD_OVERREACH = re.compile(
    r"(?i)\bcontribut(?:e|es|ing)\s+disproportionately\s+to\s+(?:the\s+)?hub(?:'s)?\s+processing\s+load\b"
)
_NO_OPTIMIZATION_NEEDED = re.compile(
    r"(?i)\bno\s+(?:immediate\s+)?need\s+for\s+(?:memory\s+management|database\s+optimi[sz]ation)"
    r"(?:\s+or\s+(?:memory\s+management|database\s+optimi[sz]ation))?\b"
)


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def has_configuration_evidence(evidence: list[dict[str, Any]]) -> bool:
    """Return True only for an actual configuration/implementation read."""

    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is False:
            continue
        kind = str(row.get("evidence_kind") or "").casefold()
        if any(token in kind for token in ("configuration", "preferences", "settings", "code", "implementation")):
            return True
        sub_tool = _sub_tool(row).casefold()
        if not sub_tool or "list" in sub_tool or sub_tool == "hub_get_logs":
            continue
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


def build_performance_synthesis_contract(evidence: list[dict[str, Any]]) -> str:
    """Return the evidence discipline for the one final performance model pass."""

    config_state = (
        "Configuration/implementation evidence is present; only use mechanisms or exact edits that the cited source directly establishes."
        if has_configuration_evidence(evidence)
        else
        "No configuration or implementation source was read in this turn. Recommendations must therefore be inspection-first, not exact setting/code/schedule changes."
    )
    return (
        "HOST PERFORMANCE EVIDENCE-FIRST CONTRACT\n"
        "Synthesize directly from the HOST current-turn sources below. There is no trusted assistant draft in this synthesis context. "
        "Every factual or causal statement must be supportable by one of these current-turn source classes.\n"
        "- METRICS: report numeric values and explicit alert/state fields. An empty/no-alert result supports 'no active alert', not qualitative labels such as healthy, very healthy, normal, safe, stable, excellent, major, severe, or exceptional unless the source itself supplies that classification or a threshold.\n"
        "- PERFORMANCE STATS: execution time, call count, busy percentage, and returned ranking are measurements. They do not by themselves establish synchronous/blocking calls, timeouts, network reachability, hub stutter, delayed automations, background overhead, log growth, history slowdown, or another implementation mechanism. Do not introduce those mechanisms even conditionally as 'if X, it can Y' unless current-turn implementation evidence establishes X.\n"
        "- JOBS: a job list establishes names/timestamps/cadence returned by the tool. It does not establish CPU spikes/load, UI delay, contention, or a benefit from moving/staggering/offsetting jobs.\n"
        "- LOGS: recent log rows are observations. An explicit error message can be reported as that error/failed endpoint operation, but it does not automatically explain longer-window performance statistics.\n"
        "- RECOMMENDATIONS: preserve useful measured facts and recommend the next evidence-gathering/configuration inspection step. Do not say optimisation is unnecessary merely because no alert is active.\n"
        + config_state
        + "\nDo not add an 'Impact' statement that depends on an unobserved mechanism. Do not use dramatic qualitative labels when the source provides only numbers. Separate measured observations from any genuinely evidence-backed interpretation."
    )


def _repair_fragment(text: str) -> str:
    repaired = str(text or "")

    repaired = re.sub(
        r"(?i)\bthe\s+hub\s+is\s+currently\s+stable\s+with\s+healthy\s+core\s+resources\b",
        "No active core-resource health alerts are reported in this turn",
        repaired,
    )
    if _SUMMARY_OVERREACH.search(repaired):
        repaired = _SUMMARY_OVERREACH.sub(
            "measured device-execution and scheduling observations worth investigating; this turn does not establish that they cause user-visible latency",
            repaired,
        )

    repaired = re.sub(
        r"(?i)(High-Latency\s+Device)\s*\(Blocking\s+Risk\)",
        r"\1",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\bmajor\s+outlier\b",
        "measured execution-time outlier",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\bis\s+exceptionally\s+high\b",
        "warrants investigation",
        repaired,
    )
    if _CONDITIONAL_BLOCKING.search(repaired):
        repaired = _CONDITIONAL_BLOCKING.sub(
            "The measured execution time warrants investigation, but this turn did not inspect the implementation and does not establish synchronous blocking, hub stuttering, or delayed automations",
            repaired,
        )

    repaired = re.sub(
        r"(?i)Job\s+Synchronization\s*\([\"“]?Thunder-Claps?[\"”]?\)",
        "Job Scheduling Alignment",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\ba\s+massive\s+volume\s+of\s+jobs\b",
        "many jobs",
        repaired,
    )

    if _PROCESSING_LOAD_OVERREACH.search(repaired):
        repaired = _PROCESSING_LOAD_OVERREACH.sub(
            "have comparatively high returned call counts and busy percentages",
            repaired,
        )
    if _REPORTING_CAUSAL.search(repaired):
        repaired = _REPORTING_CAUSAL.sub(
            "The returned activity is worth reviewing; this turn does not establish material background overhead, log growth, or slower history lookups from that activity",
            repaired,
        )

    repaired = re.sub(
        r"(?i)\bthe\s+hub\s+is\s+otherwise\s+very\s+healthy\b",
        "No active high-load or low-memory alerts are reported in this turn",
        repaired,
    )
    if _NO_OPTIMIZATION_NEEDED.search(repaired):
        repaired = _NO_OPTIMIZATION_NEEDED.sub(
            "the current alerts alone do not establish a need for or against memory/database optimisation",
            repaired,
        )

    return repaired


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _repair_table_row(line: str) -> str:
    indent = line[: len(line) - len(line.lstrip())]
    stripped = line.strip()
    cells = stripped[1:-1].split("|")
    repaired: list[str] = []
    for raw in cells:
        cell = raw.strip()
        repaired.append(cell if _TABLE_SEPARATOR_CELL.fullmatch(cell) else _repair_fragment(cell).strip())
    return indent + "| " + " | ".join(repaired) + " |"


def guard_evidence_first_performance(message: str) -> tuple[str, bool]:
    """Generic last-mile backstop for evidence-first performance language."""

    original = str(message or "")
    if not original:
        return original, False
    lines: list[str] = []
    for line in original.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        core = line[:-1] if newline else line
        if _is_table_row(core):
            repaired = _repair_table_row(core)
        else:
            match = _MARKDOWN_PREFIX.match(core)
            if match:
                repaired = match.group(1) + _repair_fragment(match.group(2))
            else:
                repaired = _repair_fragment(core)
        lines.append(repaired + newline)
    corrected = "".join(lines)
    return corrected, corrected != original


__all__ = [
    "build_performance_synthesis_contract",
    "guard_evidence_first_performance",
    "has_configuration_evidence",
]
