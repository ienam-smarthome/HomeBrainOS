"""Focused fail-closed repairs for broad live performance synthesis.

These guards cover wording exposed by the 0.16.63/0.16.64 live proofs. They
preserve measured facts while preventing scheduler/job observations, qualitative
database labels, hypotheses, and backup alerts from being promoted beyond
current-turn evidence.
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
    r"(?i)\b(?:sessionTick|scheduled\s+jobs?|recurring\s+(?:jobs?|tasks?)|"
    r"scheduler|job\s+volume)\b"
)
_SCHEDULER_OUTCOME = re.compile(
    r"(?i)\b(?:increase|increases|increased|increasing|cause|causes|caused|causing|"
    r"create|creates|created|creating|lead\s+to|leads\s+to|result\s+in|results\s+in)\b"
    r"[^.!?\n]{0,180}\b(?:baseline\s+)?(?:cpu\s+)?(?:load|overhead|performance\s+drag)\b"
)
_SCHEDULER_TUNING = re.compile(
    r"(?i)\b(?:increase|decrease|raise|lower|lengthen|shorten|adjust|change|set)\b"
    r"[^.!?\n]{0,160}\b(?:sessionTick|scheduler|scheduled\s+job|job|tick)\b"
    r"[^.!?\n]{0,100}\b(?:interval|cadence|frequency)\b"
)
_DATABASE_MB = re.compile(r"(?i)\b(?:database\s*(?:is|:|at)?\s*)?(\d+(?:\.\d+)?)\s*MB\b")
_DATABASE_QUALITATIVE = re.compile(
    r"(?i)\b(?:database|db)\b[^.!?\n]{0,220}\b(?:small|lean|large|bloated)\b|"
    r"\b(?:small|lean|large|bloated)\b[^.!?\n]{0,220}\b(?:database|db)\b"
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


def _guard_sentence(sentence: str, *, has_configuration: bool) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)

    # A 'Hypothesis' heading is not permission to state a mechanism as likely.
    if _ASSERTIVE_HYPOTHESIS.search(comparable) and _MECHANISM.search(comparable):
        return (
            "**Possible hypothesis:** an implementation or connectivity mechanism could contribute to the "
            "observed latency, but the current evidence does not establish which mechanism is responsible."
        )

    # A job list proves jobs/cadence, not CPU attribution.
    if _SCHEDULER_SUBJECT.search(comparable) and _SCHEDULER_OUTCOME.search(comparable):
        return (
            "The scheduled-job activity is worth reviewing; the current job evidence does not establish "
            "material CPU load, hub overhead, or performance drag."
        )

    # Directional scheduler tuning is still a configuration prescription.
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

    # Report the DB measurement without inventing a qualitative threshold or causal conclusion.
    if _DATABASE_LABEL_ONLY.search(comparable):
        return (
            "**Database:** use the measured numeric size below; this turn did not establish a "
            "threshold for calling the database small, lean, large, or bloated."
        )
    if _DATABASE_QUALITATIVE.search(comparable) or _DATABASE_PERF_INFERENCE.search(comparable):
        mb = _DATABASE_MB.search(comparable)
        if mb:
            return (
                f"**Database:** {mb.group(1)} MB. No evidence in this run attributes the identified "
                "performance outliers to database size."
            )
        return (
            "**Database:** the current evidence does not establish a qualitative size threshold or "
            "performance impact from database size alone."
        )

    # NETWORK_BACKUP_FAILED is an alert, not evidence of imminent data loss.
    if _BACKUP_ALERT.search(comparable) and _BACKUP_ALARM.search(comparable):
        return (
            "`NETWORK_BACKUP_FAILED` is active. Check the configured backup destination, credentials/permissions, "
            "and available storage; the current evidence does not establish imminent data loss or whether another "
            "backup method is succeeding."
        )

    # Follow-up sentences/table rows can carry alarm language without repeating the alert token.
    if _BACKUP_ALARM.search(comparable) and re.search(r"(?i)\b(?:backup|backups|data\s+loss)\b", comparable):
        return (
            "Check the active network-backup failure and its destination/settings. The current evidence does not "
            "establish imminent data loss or whether another backup method is succeeding."
        )

    return sentence


def guard_live_performance_semantics(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Localize the live performance failure shapes while preserving the rest."""

    original = str(message or "")
    if not original:
        return original, False

    has_configuration = _has_configuration_evidence(evidence)
    pieces = re.split(r"(?<=[.!?])(\s+)", original)
    for index in range(0, len(pieces), 2):
        if pieces[index]:
            pieces[index] = _guard_sentence(
                pieces[index],
                has_configuration=has_configuration,
            )
    corrected = "".join(pieces)
    return corrected, corrected != original


__all__ = ["guard_live_performance_semantics"]