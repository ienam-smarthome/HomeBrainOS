"""Focused fail-closed repairs for broad live performance synthesis.

These guards cover wording exposed by the 0.16.63-0.16.72 live proofs. They
preserve measured facts while preventing scheduler/job observations, qualitative
database labels, implementation mechanisms, and recommendations from being
promoted beyond current-turn evidence. Repairs are Markdown-aware so tables,
bullets, and headings retain their structure.
"""

from __future__ import annotations

import re
from typing import Any


_ASSERTIVE_HYPOTHESIS = re.compile(
    r"(?i)\b(?:likely|probably)\s+(?:caused\s+by|due\s+to)\b"
)
_MECHANISM = re.compile(
    r"(?i)\b(?:driver|integration|network|timeout|api|poll(?:ing)?|retry|retries|"
    r"reconnect|blocking|thread|unreachable|asleep|offline)\b"
)
_SCHEDULER_SUBJECT = re.compile(
    r"(?i)\b(?:sessionTick|scheduled\s+jobs?|recurring\s+(?:jobs?|tasks?)|jobs?|"
    r"scheduler|job\s+volume|synchroni[sz](?:ed|ation))\b"
)
_SCHEDULER_OUTCOME = re.compile(
    r"(?i)\b(?:increase|increases|increased|increasing|cause|causes|caused|causing|"
    r"create|creates|created|creating|lead\s+to|leads\s+to|result\s+in|results\s+in)\b"
    r"[^.!?\n]{0,220}\b(?:baseline\s+|momentary\s+)?(?:cpu\s+)?(?:load|spikes?|overhead|performance\s+drag)\b"
)
_SCHEDULER_USER_IMPACT = re.compile(
    r"(?i)\b(?:cpu\s+spikes?|load|overhead)\b[^.!?\n]{0,180}"
    r"\b(?:ui\s+stutter(?:ing)?|stutter(?:ing)?|delayed\s+automation|automation\s+delays?|lag)\b"
)
_SCHEDULER_EXECUTION_CAUSAL = re.compile(
    r"(?i)\bexecuting\s+this\s+many\s+(?:jobs?|tasks?)\b[^.!?\n]{0,180}"
    r"\b(?:create|creates|created|creating|cause|causes|caused|causing)\s+"
    r"(?:momentary\s+)?cpu\s+spikes?\b"
)
_SCHEDULER_TUNING = re.compile(
    r"(?i)\b(?:increase|decrease|raise|lower|lengthen|shorten|adjust|change|set)\b"
    r"[^.!?\n]{0,160}\b(?:sessionTick|scheduler|scheduled\s+job|job|tick)\b"
    r"[^.!?\n]{0,100}\b(?:interval|cadence|frequency)\b"
)
_SCHEDULER_STAGGER = re.compile(
    r"(?i)\bstagger\b[^.!?\n]{0,180}\b(?:jobs?|sessionTick|start\s+times?|execution)\b|"
    r"\b(?:jobs?|sessionTick|start\s+times?|execution)\b[^.!?\n]{0,180}\bstagger\b"
)
_DATABASE_MB = re.compile(r"(?i)\b(?:database\s*(?:is|:|at|measured\s+at)?\s*)?(\d+(?:\.\d+)?)\s*MB\b")
_DATABASE_QUALITATIVE = re.compile(
    r"(?i)\b(?:database|db)\b[^.!?\n]{0,220}\b(?:small|lean|large|bloated)\b|"
    r"\b(?:small|lean|large|bloated)\b[^.!?\n]{0,220}\b(?:database|db)\b"
)
_DATABASE_NORMAL_LIMIT = re.compile(
    r"(?i)\b(?:well\s+)?within\s+(?:the\s+)?(?:normal|healthy)\s+(?:limits?|range)\b|"
    r"\b(?:normal|healthy)\s+(?:limits?|range)\b"
)
_DATABASE_LABEL_ONLY = re.compile(
    r"(?i)^\s*(?:[-*| ]+)?(?:#{1,6}\s*)?(?:database|db)\s*:\s*"
    r"(?:\*\*)?(?:small|lean|large|bloated)(?:\*\*)?\s*[|.]*\s*$"
)
_DATABASE_PERF_INFERENCE = re.compile(
    r"(?i)\b(?:unlikely|not\s+likely)\b[^.!?\n]{0,120}\b(?:performance|drag|slow|latency|load)\b"
)
_BACKUP_ALERT = re.compile(r"(?i)NETWORK_BACKUP_FAILED|network\s+backup\s+failure")
_BACKUP_ALARM = re.compile(
    r"(?i)\b(?:most\s+urgent|urgent|immediately|prevent\s+data\s+loss|"
    r"ensure\s+your\s+configuration\s+is\s+being\s+saved)\b"
)
_NOT_BOTTLENECK = re.compile(r"(?i)\b(?:is|are)\s+not\s+(?:currently\s+)?(?:a\s+)?bottleneck\b")
_HIGHLY_EFFICIENT = re.compile(r"(?i)\bhighly\s+efficient\b")
_BLOCKING_THREAD_CLAIM = re.compile(
    r"(?i)\b(?:block(?:ing)?\s+(?:hub\s+)?threads?|thread\s+blocking|"
    r"blocking\s+(?:device\s+calls?|behaviou?rs?)|stall\s+other\s+hub\s+operations?)\b"
)
_LATENCY_MECHANISM_SUGGESTION = re.compile(
    r"(?i)\b(?:execution\s+time|latency|delay|seconds?)\b[^.!?\n]{0,180}"
    r"\bsuggests?\b[^.!?\n]{0,180}"
    r"\b(?:tim(?:e|ing)\s*out|struggl(?:e|ing)\s+to\s+reach|unreachable|offline)\b"
)
_PRIMARY_CAUSE = re.compile(r"(?i)\b(?:primary|main)\s+cause\b")
_ACTIVITY_OVERHEAD = re.compile(
    r"(?i)\b(?:add(?:ing|s)?|create(?:s|d|ing)?)\s+"
    r"(?:constant\s+)?(?:background\s+)?overhead\b"
)
_ZWAVE_REPAIR = re.compile(r"(?i)\b(?:run|perform|start)\s+(?:a\s+)?z[- ]?wave\s+repair\b")
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_MARKDOWN_PREFIX = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+|>\s+))(.*)$", re.S)


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def _has_configuration_evidence(evidence: list[dict[str, Any]]) -> bool:
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


def _has_zwave_diagnostic_evidence(evidence: list[dict[str, Any]]) -> bool:
    """Require Z-Wave-specific diagnostic detail before prescribing repair."""

    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is False:
            continue
        kind = str(row.get("evidence_kind") or "").casefold()
        sub_tool = _sub_tool(row).casefold()
        combined = f"{kind} {sub_tool}"
        if "zwave" not in combined and "z-wave" not in combined:
            continue
        if any(
            token in combined
            for token in (
                "node",
                "route",
                "detail",
                "diagnostic",
                "topology",
                "mesh",
                "repair_status",
            )
        ):
            return True
    return False


def _measured_activity_replacement(sentence: str) -> str:
    calls = re.search(r"(?i)\b([\d,]+\s+calls?)\b", sentence)
    avg = re.search(r"(?i)\b(\d+(?:\.\d+)?\s*ms)\b", sentence)
    prefix = sentence.split(":", 1)[0].strip() if ":" in sentence else "This component"
    facts: list[str] = []
    if calls:
        facts.append(calls.group(1))
    if avg:
        facts.append(f"{avg.group(1)} average execution time")
    measured = " and ".join(facts) if facts else "the measured activity"
    return (
        f"{prefix}: {measured}; this turn does not establish either a performance problem "
        "or a qualitative efficiency/bottleneck conclusion from that activity alone."
    )


def _database_replacement(comparable: str) -> str:
    mb = _DATABASE_MB.search(comparable)
    if mb:
        return (
            f"**Database:** {mb.group(1)} MB. The current turn does not establish a normal-size threshold, "
            "a healthy-size threshold, or performance impact from database size alone."
        )
    return (
        "**Database:** the current evidence does not establish a qualitative size threshold or "
        "performance impact from database size alone."
    )


def _guard_sentence(
    sentence: str,
    *,
    has_configuration: bool,
    has_zwave_diagnostics: bool,
) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)

    if _ASSERTIVE_HYPOTHESIS.search(comparable) and _MECHANISM.search(comparable):
        return (
            "**Possible hypothesis:** an implementation or connectivity mechanism could contribute to the "
            "observed latency, but the current evidence does not establish which mechanism is responsible."
        )

    if _LATENCY_MECHANISM_SUGGESTION.search(comparable):
        return (
            "The measured latency warrants investigation. Check connectivity, driver settings, and relevant "
            "logs to determine the mechanism; this turn does not establish whether a network timeout, device "
            "availability, driver behaviour, or another mechanism is responsible."
        )

    if _BLOCKING_THREAD_CLAIM.search(comparable):
        avg = re.search(r"(?i)\b(\d+(?:[,.]\d+)?\s*ms)\b", comparable)
        suffix = f" The measured execution time is {avg.group(1)}." if avg else ""
        return (
            "The measured execution time warrants investigation, but this turn does not establish thread "
            "blocking, stalled hub operations, or a blocking implementation mechanism."
            + suffix
        )

    if _SCHEDULER_EXECUTION_CAUSAL.search(comparable):
        return (
            "The scheduled-job alignment is worth reviewing; the current job evidence does not establish "
            "material CPU load, a CPU spike, UI stuttering, delayed automations, hub overhead, or performance drag."
        )

    if _SCHEDULER_SUBJECT.search(comparable) and (
        _SCHEDULER_OUTCOME.search(comparable) or _SCHEDULER_USER_IMPACT.search(comparable)
    ):
        return (
            "The scheduled-job alignment is worth reviewing; the current job evidence does not establish "
            "material CPU load, a CPU spike, UI stuttering, delayed automations, hub overhead, or performance drag."
        )

    if not has_configuration and _SCHEDULER_STAGGER.search(comparable):
        return (
            "Inspect the app responsible for the scheduled jobs before changing their alignment; the current "
            "job evidence does not establish that staggering is configurable, necessary, or behaviour-preserving."
        )

    if (
        not has_configuration
        and _SCHEDULER_SUBJECT.search(comparable)
        and _SCHEDULER_TUNING.search(comparable)
    ):
        return (
            "Inspect the cited scheduler/app configuration first. The measured job count or cadence can "
            "justify review, but this turn did not establish whether the interval is configurable or whether "
            "changing it would preserve required behaviour."
        )

    if _DATABASE_LABEL_ONLY.search(comparable):
        return (
            "**Database:** use the measured numeric size below; this turn did not establish a "
            "threshold for calling the database small, lean, large, or bloated."
        )
    if (
        _DATABASE_QUALITATIVE.search(comparable)
        or _DATABASE_PERF_INFERENCE.search(comparable)
        or ("database" in comparable.casefold() and _DATABASE_NORMAL_LIMIT.search(comparable))
    ):
        return _database_replacement(comparable)

    if _BACKUP_ALERT.search(comparable) and _BACKUP_ALARM.search(comparable):
        return (
            "`NETWORK_BACKUP_FAILED` is active. Check the configured backup destination, credentials/permissions, "
            "and available storage; the current evidence does not establish imminent data loss or whether another "
            "backup method is succeeding."
        )

    if _BACKUP_ALARM.search(comparable) and re.search(r"(?i)\b(?:backup|backups|data\s+loss)\b", comparable):
        return (
            "Check the active network-backup failure and its destination/settings. The current evidence does not "
            "establish imminent data loss or whether another backup method is succeeding."
        )

    if _NOT_BOTTLENECK.search(comparable) or _HIGHLY_EFFICIENT.search(comparable):
        return _measured_activity_replacement(sentence)

    if _ACTIVITY_OVERHEAD.search(comparable):
        return (
            "The frequent reporting is a measured activity worth reviewing; this turn does not establish that it "
            "adds material hub overhead or causes a performance problem."
        )

    if _PRIMARY_CAUSE.search(comparable) and any(
        token in comparable.casefold() for token in ("blocking", "latency", "delay", "performance")
    ):
        return (
            "The measured latency is worth investigating, but this turn does not establish it as the primary "
            "cause of thread blocking or another hub performance symptom."
        )

    if _ZWAVE_REPAIR.search(comparable) and not has_zwave_diagnostics:
        return (
            "Inspect Z-Wave diagnostics for failed/dead nodes, route quality, and other mesh evidence before "
            "deciding whether a repair is appropriate; `zwHealthy:false` alone does not establish that a repair "
            "is required."
        )

    return sentence


def _neutralize_causal_headings(text: str) -> str:
    text = re.sub(
        r"(?i)(#{1,6}\s*(?:⚠️\s*)?)Performance\s+Bottlenecks\b",
        r"\1Performance Outliers",
        text,
    )
    text = re.sub(
        r"(?i)(#{1,6}\s*(?:⚠️\s*)?)Critical\s+Performance\s+Issues\b",
        r"\1Performance Observations",
        text,
    )
    text = re.sub(
        r"(?i)(High-Latency\s+Devices)\s*\([^)]*Blocking[^)]*\)",
        r"\1",
        text,
    )
    text = re.sub(
        r"(?i)(Job\s+Volume)\s*&\s*(?:CPU|Scheduling)\s+Overhead",
        r"\1 & Scheduling",
        text,
    )
    text = re.sub(
        r"(?i)(\*\*Recurring)\s+Overhead(?::\*\*|\*\*:)",
        r"\1 Jobs:**",
        text,
    )
    text = re.sub(
        r"(?i)\*\*(\d+\.\s*)?Scheduling\s+[\"“]?Thunder-Claps?[\"”]?\s*\(Job\s+Synchronization\)\*\*",
        lambda match: f"**{match.group(1) or ''}Job Scheduling Alignment**",
        text,
    )
    text = re.sub(
        r"(?i)\*\*(\d+\.\s*)?Blocking\s+Device\s+Execution(?:\s*\([^)]*\))?\*\*",
        lambda match: f"**{match.group(1) or ''}High-Latency Device Execution**",
        text,
    )
    text = re.sub(
        r"(?i)\*\*(\d+\.\s*)?High-Frequency\s+Reporting\s*&\s*Overhead\*\*",
        lambda match: f"**{match.group(1) or ''}High-Activity Reporting**",
        text,
    )
    text = re.sub(
        r"(?i)\*\*(\d+\.\s*)?Stability\s*&\s*Connectivity\s+Issues\s*\(from\s+Logs\)\*\*",
        lambda match: f"**{match.group(1) or ''}Recent Connectivity/Error Observations (from Logs)**",
        text,
    )
    return text


def _neutralize_exact_overreach(text: str) -> str:
    text = re.sub(
        r"(?i)\bsignificant\s+bottlenecks\s+caused\s+by\s+blocking\s+device\s+calls\s+and\s+synchroni[sz]ed\s+scheduling\b",
        "measured device-latency and scheduling-alignment outliers worth investigating; this turn does not establish either as a proven performance cause",
        text,
    )
    text = re.sub(
        r"(?i)\boutliers\s+that\s+are\s+impacting\s+efficiency\b",
        "outliers worth investigating; this turn does not establish an overall efficiency impact",
        text,
    )
    text = re.sub(
        r"(?i)\bThere\s+is\s+a\s+severe\s+synchronization\s+of\s+scheduled\s+jobs\b",
        "Many scheduled jobs share the same scheduled timestamp",
        text,
    )
    text = re.sub(
        r"(?i)average\s+execution\s+times\s+that\s+can\s+block\s+(?:hub\s+)?threads",
        "average execution times that warrant investigation; the current evidence does not establish thread blocking",
        text,
    )
    text = re.sub(
        r"(?i)This\s+synchronization\s+can\s+cause\s+momentary\s+CPU\s+spikes\.",
        "This synchronized schedule is worth reviewing; the current job evidence does not establish a momentary CPU spike.",
        text,
    )
    text = re.sub(
        r"(?i)Stagger\s+the\s+start\s+times\s+of\s+these\s+recurring\s+jobs\s+to\s+avoid\s+the\s+simultaneous\s+execution\s+spike\s+at\s+the\s+top\s+of\s+the\s+minute\.",
        "Inspect the app responsible for these recurring jobs before changing their alignment; this turn does not establish that staggering is configurable, necessary, or behaviour-preserving.",
        text,
    )
    text = re.sub(
        r"(?i)\*\*Stagger\s+the\s+[\"“]?Block[\"”]?\s+Ticks\.\*\*",
        'Review the "Block" tick alignment.',
        text,
    )
    text = re.sub(
        r"(?is)\*\*Shift\s+System\s+Tasks\.\*\*\s*Move\s+.+",
        "Inspect the responsible app/system-task configuration before changing scheduled offsets; the current job evidence does not establish that alternate offsets are configurable, necessary, or behaviour-preserving.",
        text,
    )
    text = re.sub(
        r"(?i)The\s+[\"“]?No\s+route\s+to\s+host[\"”]?\s+error\s+indicates\s+a\s+network-level\s+connectivity\s+issue\s+between\s+the\s+hub\s+and\s+the\s+device\.",
        "The `No route to host` error establishes a routing/connectivity failure to the configured endpoint at that moment; this turn does not establish which network component caused it.",
        text,
    )
    return text


def _collapse_duplicate_performance_repair(text: str) -> str:
    text = re.sub(
        r"(?i)this is a measured performance concern,\s*but\s+the current statistics do not establish that it\s*;\s*"
        r"this is a measured performance concern,\s*but\s+the current statistics do not establish that it"
        r"(?=\s+causes?)",
        "this is a measured performance concern, but the current statistics do not establish that it",
        text,
    )
    text = re.sub(
        r"(?i)(?:the current statistics do not establish that\s+(?:this specific activity|it)\s*;\s*)+"
        r"(?=this is a measured performance concern)",
        "",
        text,
    )
    text = re.sub(
        r"(?i)(?:this is a measured performance concern,\s*but\s+)+"
        r"(?=this is a measured performance concern)",
        "",
        text,
    )
    text = re.sub(
        r"(?i)(?:this is a measured performance concern, but the current statistics do not establish that it\s*;\s*)+"
        r"(?=this is a measured performance concern)",
        "",
        text,
    )
    return text


def _repair_prose(
    text: str,
    *,
    has_configuration: bool,
    has_zwave_diagnostics: bool,
) -> str:
    """Repair one prose fragment without crossing a Markdown boundary."""

    if not text:
        return text
    prepared = _neutralize_exact_overreach(_neutralize_causal_headings(text))
    prefix = ""
    body = prepared
    match = _MARKDOWN_PREFIX.match(prepared)
    if match:
        prefix, body = match.groups()

    pieces = re.split(r"(?<=[.!?])(\s+)", body)
    for index in range(0, len(pieces), 2):
        if pieces[index]:
            pieces[index] = _guard_sentence(
                pieces[index],
                has_configuration=has_configuration,
                has_zwave_diagnostics=has_zwave_diagnostics,
            )
    return prefix + "".join(pieces)


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _repair_table_row(
    line: str,
    *,
    has_configuration: bool,
    has_zwave_diagnostics: bool,
) -> str:
    """Repair each Markdown table cell independently and preserve every column."""

    indent = line[: len(line) - len(line.lstrip())]
    stripped = line.strip()
    raw_cells = stripped[1:-1].split("|")
    repaired: list[str] = []
    for raw in raw_cells:
        cell = raw.strip()
        if _TABLE_SEPARATOR_CELL.fullmatch(cell):
            repaired.append(cell)
            continue
        repaired.append(
            _repair_prose(
                cell,
                has_configuration=has_configuration,
                has_zwave_diagnostics=has_zwave_diagnostics,
            ).strip()
        )
    return indent + "| " + " | ".join(repaired) + " |"


def guard_live_performance_semantics(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Localize performance repairs while preserving Markdown structure."""

    original = str(message or "")
    if not original:
        return original, False

    has_configuration = _has_configuration_evidence(evidence)
    has_zwave_diagnostics = _has_zwave_diagnostic_evidence(evidence)
    lines = original.splitlines(keepends=True)
    repaired_lines: list[str] = []
    for line in lines:
        newline = "\n" if line.endswith("\n") else ""
        core = line[:-1] if newline else line
        if _is_table_row(core):
            repaired = _repair_table_row(
                core,
                has_configuration=has_configuration,
                has_zwave_diagnostics=has_zwave_diagnostics,
            )
        else:
            repaired = _repair_prose(
                core,
                has_configuration=has_configuration,
                has_zwave_diagnostics=has_zwave_diagnostics,
            )
        repaired_lines.append(repaired + newline)

    corrected = _collapse_duplicate_performance_repair("".join(repaired_lines))
    return corrected, corrected != original


__all__ = ["guard_live_performance_semantics"]
