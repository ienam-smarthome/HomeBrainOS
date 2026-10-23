"""Keep optional whole-hub AI advice inside its bounded audit evidence.

The model can rank hypotheses, not convert missing top-N rows into low load,
or a saturated newest-N log page into proof that an exception never occurred.
This guard repairs a small set of directly unsupported assertion forms.
It does not add observations, infer cross-run continuity, or mutate Hubitat.
"""
from __future__ import annotations

import re

_UNVERIFIED_OFFLINE_TITLE = re.compile(
    r"(?i)\bConfirmed\s+Device\s+Outages?\s*\(Errors?\)"
)
_OFFLINE_AUTOMATION_CERTAINTY = re.compile(
    r"(?i)\b(?:any|all)\s+automations?\s+relying\s+on\s+"
    r"(?:these|those|the)\s+devices?\s+as\s+triggers?\s+or\s+targets?"
    r"\s+will\s+fail\s+to\s+execute\b[^\n]*"
)
_GHOST_JOB_CLAIM = re.compile(
    r"(?i)\b(?:the\s+hub\s+may\s+be\s+wasting\s+resources\s+executing\s+)?"
    r"(?:[\"']?ghost[\"']?\s+scheduled\s+jobs?|"
    r"(?:these|those)\s+disabled\s+apps?\s+(?:still\s+)?execut(?:e|ing)\s+jobs?)"
    r"[^\n]*"
)
_PCT_BUSY_CAUSAL = re.compile(
    r"(?i)\bhigh\s+" + "\x60?" + r"pctBusy" + "\x60?" +
    r"\s+values?\s+increas(?:e|es)\s+the\s+risk\b[^\n]*"
)

_UNVERIFIED_MANUAL_CONTROL = re.compile(
    r"(?i)\b(?:the\s+)?device\s+is\s+currently\s+unavailable\s+for\s+"
    r"automation\s+triggers?\s+or\s+manual\s+control\b[^\n.]*"
)
_UNVERIFIED_HEARTBEAT = re.compile(
    r"(?i)\bthe\s+monitoring\s+mechanism\s+is\s+currently\s+non[- ]functional\b"
)
_CPU_CYCLES_OVERCLAIM = re.compile(
    r"(?i)\b(?:these\s+components?\s+are\s+)?utiliz(?:ing|e)\s+"
    r"a\s+larger\s+fraction\s+of\s+the\s+hub's\s+available\s+"
    r"processing\s+cycles\b[^\n.]*"
)
_UNVERIFIED_CONNECTIVITY_ROOT = re.compile(
    r"(?i)\bBedroom\s+3\s+Mesh\s+\(ID\s+7103\)\s+Connectivity\s+Failure\b"
)

_LOAD_THROTTLE_CLAIM = re.compile(
    r"(?i)\bHubitat'?s?\s+internal\s+load\s+protection\s+is\s+"
    r"actively\s+throttling\s+this\s+app\b[^\n.]*"
)
_OFFLINE_UNREACHABLE_CLAIM = re.compile(
    r"(?i)\bthe\s+device\s+is\s+currently\s+unreachable\s+"
    r"and\s+unable\s+to\s+trigger\s+or\s+receive\s+commands\b[^\n.]*"
)
_AVERAGE_MS_CAUSAL = re.compile(
    r"(?i)\b(?:extremely\s+)?high\s+average\s+execution\s+times?\s+"
    r"for\s+a\s+single\s+app\s+increas(?:e|es)\s+the\s+risk\s+"
    r"of\s+triggering\s+(?:the\s+)?(?:\x60)?LimitExceededException(?:\x60)?"
    r"\s+observed\s+above\b[^\n.]*"
)

_TOPN_NEGATIVE = re.compile(
    r"(?i)\b(?:target apps? (?:are|is) not (?:high[- ]load|major)[^\n]*|"
    r"(?:these|those|the target) apps?\s+are\s+unlikely\s+to\s+be\s+"
    r"(?:the\s+)?(?:primary|major|main)\s+drivers?\b[^\n]*)"
)
_UNBOUNDED_NO_EVIDENCE = re.compile(
    r"(?i)\bthere\s+is\s+no\s+evidence\s+that\b[^\n.]*"
    r"\b(?:caus(?:e|es|ing)|responsible|contribut(?:e|ing))\b[^\n.]*"
)
_NO_ERROR_PRINCIPLE = re.compile(
    r"(?i)\b(?:there\s+is\s+)?no\s+evidence\s+of\b[^\n.]*"
    r"\b(?:rate[- ]limit(?:ing)?|integration\s+failures?|runtime\s+failures?)\b[^\n.]*"
)
_NO_INSTANCES = re.compile(
    r"(?i)\b(?:a\s+review\s+of\s+)?(?:the\s+)?\d+\s+returned\s+log\s+rows\b"
    r"[^\n.]*\bshows?\s+no\s+instances?\s+of\b[^\n.]*"
)
_ONLY_WARNINGS = re.compile(r"(?i)\bthe\s+only\s+recorded\s+warnings?\b[^\n.]*")
_SENSECAP_UNSUPPORTED = re.compile(
    r"(?i)\b(?:high\s+load\s+or\s+transport\s+failures?|"
    r"(?:the\s+)?measured\s+app(?:lication)?\s+load)\b"
    r"[^\n.]*\b(?:expected|explained)\b[^\n.]*"
)
_ABSOLUTE = re.compile(r"(?i)\*\*Certainty:\*\*\s*Absolute\b[^\n]*")
_HIGH_CERTAINTY = re.compile(r"(?i)\*\*Certainty:\*\*\s*High\b[^\n]*")
_SENSECAP_HEAD = re.compile(r"(?i)SenseCap\s+D1\s+load\s+is\s+a\s+known\s+state")
_NO_EXCEPTIONS_HEAD = re.compile(r"(?i)(?<!\w)No\s+(\x60?LimitExceededException\x60?)\s+observed")
_NOT_HIGH_HEAD = re.compile(r"(?i)Target\s+apps?\s+are\s+not\s+high[- ]load\s+contributors?")


def calibrate_audit_ai_advisory(advisory: str, report: str) -> tuple[str, tuple[str, ...]]:
    """Return grounded advisory and repair reasons, using only audit scope metadata."""
    original = str(advisory or "")
    host = str(report or "").casefold()
    if not original:
        return original, ()
    bounded_performance = ("top-ranked sample" in host
                           or "top-20" in host
                           or "20 top-ranked" in host)
    saturated_logs = "log window saturated" in host
    known_unpowered = "sensecap d1" in host and "intentionally" in host and "unpowered" in host
    offline_scope_only = (
        "offline-device evidence" in host
        and "verify upstream telemetry" in host
    )
    heartbeat_cadence_unverified = (
        "lighting automation heartbeat" in host
        and ("old last-activity timestamp alone cannot prove failover is broken" in host
             or "intended heartbeat schedule" in host)
    )
    observed_load_exception = (
        "device status report display" in host
        and "limitexceededexception" in host
        and "app 3977" in host
    )
    unverified_automation_impact = (
        "offline-device evidence" in host
        and "automation configuration and dependency investigation" in host
        and "execution unverified" in host
    )
    unverified_job_ownership = (
        "scheduler-key attribution unverified" in host
        or "0 rows have explicit, source-recognised owner fields" in host
    )
    corrected: list[str] = []
    reasons: set[str] = set()
    section = ""
    in_table = False
    for raw in original.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        newline = raw[len(line):]
        clean = re.sub(r"[*\x60]", "", line).casefold()
        if re.search(r"(?i)\b(?:performance risk|performance)\b", clean) and (
            clean.lstrip().startswith(("**1", "#"))):
            section = "performance"
        elif ("errors:" in clean or "exception" in clean) and clean.lstrip().startswith(("**2", "#")):
            section = "errors"
        elif "sensecap" in clean and clean.lstrip().startswith(("**3", "#")):
            section = "sensecap"
        if line.startswith("### "):
            in_table = "target app summary" in clean
        result = line
        if observed_load_exception and _LOAD_THROTTLE_CLAIM.search(result):
            result = _LOAD_THROTTLE_CLAIM.sub(
                "Hubitat recorded excessive-load exceptions naming this "
                "app; whether it throttled ongoing calls or affected other "
                "apps was not established by this audit",
                result,
            )
            reasons.add("throttling_effect_unverified")
        if offline_scope_only and _OFFLINE_UNREACHABLE_CLAIM.search(result):
            result = _OFFLINE_UNREACHABLE_CLAIM.sub(
                "The device is reported offline with watchdog warnings; "
                "actual command reachability and trigger outcomes were "
                "not independently tested",
                result,
            )
            reasons.add("offline_command_effect_unverified")
        if observed_load_exception and bounded_performance and _AVERAGE_MS_CAUSAL.search(result):
            result = _AVERAGE_MS_CAUSAL.sub(
                "The long averageMs value warrants investigation alongside "
                "independently observed excessive-load errors; the sample "
                "does not prove which operation caused each exception",
                result,
            )
            reasons.add("runtime_exception_causality_unverified")
        if offline_scope_only and _UNVERIFIED_MANUAL_CONTROL.search(result):
            result = _UNVERIFIED_MANUAL_CONTROL.sub(
                "The device is reported offline; this does not independently "
                "verify the outcome of specific commands or automation triggers",
                result,
            )
            reasons.add("offline_manual_control_unverified")
        if offline_scope_only and _UNVERIFIED_CONNECTIVITY_ROOT.search(result):
            result = _UNVERIFIED_CONNECTIVITY_ROOT.sub(
                "Bedroom 3 Mesh (ID 7103) — Reported Offline With Watchdog Warnings",
                result,
            )
            reasons.add("offline_root_cause_unverified")
        if heartbeat_cadence_unverified and _UNVERIFIED_HEARTBEAT.search(result):
            result = _UNVERIFIED_HEARTBEAT.sub(
                "the monitoring mechanism's current function is unverified "
                "without an expected reporting cadence or execution evidence",
                result,
            )
            reasons.add("heartbeat_cadence_unverified")
        if bounded_performance and _CPU_CYCLES_OVERCLAIM.search(result):
            result = _CPU_CYCLES_OVERCLAIM.sub(
                "have higher pctBusy in the returned statistics; this is "
                "not a measured fraction of the hub's CPU processing cycles",
                result,
            )
            reasons.add("pctbusy_cpu_share_unverified")
        if unverified_automation_impact:
            if _UNVERIFIED_OFFLINE_TITLE.search(result):
                result = _UNVERIFIED_OFFLINE_TITLE.sub(
                    "Reported Offline Device States (Not Proven Automation Failures)",
                    result,
                )
                reasons.add("offline_effect_unverified")
            if _OFFLINE_AUTOMATION_CERTAINTY.search(result):
                result = _OFFLINE_AUTOMATION_CERTAINTY.sub(
                    "An automation depending on a currently unavailable device "
                    "may be affected, but this audit did not establish its "
                    "trigger/action dependency or actual failed execution.",
                    result,
                )
                reasons.add("offline_effect_unverified")
        if unverified_job_ownership and _GHOST_JOB_CLAIM.search(result):
            result = _GHOST_JOB_CLAIM.sub(
                "Scheduler-key candidates do not establish that the disabled "
                "apps own or execute jobs; no wasted work was verified.",
                result,
            )
            reasons.add("scheduler_ownership_unverified")
        if bounded_performance and _PCT_BUSY_CAUSAL.search(result):
            result = _PCT_BUSY_CAUSAL.sub(
                "The returned pctBusy values are performance observations; "
                "this sample does not establish hub-wide CPU contention "
                "or future LimitExceededException events.",
                result,
            )
            reasons.add("pctbusy_risk_unverified")
        if bounded_performance:
            if _NOT_HIGH_HEAD.search(result):
                result = _NOT_HIGH_HEAD.sub("Target-app contribution is unverified by this top-ranked sample", result)
                reasons.add("topn_absence")
            if _TOPN_NEGATIVE.search(result):
                result = _TOPN_NEGATIVE.sub(
                    "The returned top-ranked sample does not establish whether these named apps materially contribute to hub load or latency.",
                    result,
                )
                reasons.add("topn_absence")
            if _UNBOUNDED_NO_EVIDENCE.search(result):
                result = _UNBOUNDED_NO_EVIDENCE.sub(
                    "the sampled audit does not establish whether the named apps cause excessive Hubitat load; unreturned performance rows and historical errors remain unchecked",
                    result,
                )
                reasons.add("topn_absence")
        if saturated_logs:
            if _NO_EXCEPTIONS_HEAD.search(result):
                result = _NO_EXCEPTIONS_HEAD.sub(
                    "No \x60LimitExceededException\x60 shown in the bounded log excerpt", result
                )
                reasons.add("saturated_logs")
            if _NO_INSTANCES.search(result):
                result = _NO_INSTANCES.sub(
                    "the 200-row bounded sample does not display a LimitExceededException for the named apps; the saturated page does not exclude displaced earlier errors",
                    result,
                )
                reasons.add("saturated_logs")
            if _ONLY_WARNINGS.search(result):
                result = _ONLY_WARNINGS.sub(
                    "The selected alert summary mentions watchdog and automation-state observations; it is not an exhaustive warning inventory.",
                    result,
                )
                reasons.add("saturated_logs")
            if _NO_ERROR_PRINCIPLE.search(result):
                result = _NO_ERROR_PRINCIPLE.sub(
                    "The bounded excerpt cannot rule out app runtime failures; a Hubitat excessive-load exception is not, by itself, evidence of remote API rate limiting.",
                    result,
                )
                reasons.add("saturated_logs")
            if in_table and "|" in result and re.search(r"\|\s*\*\*No\*\*\s*\|", result, re.I):
                result = re.sub(
                    r"\|\s*\*\*No\*\*\s*\|",
                    "| Not shown in bounded log sample |", result, flags=re.I,
                )
                reasons.add("saturated_logs")
        if known_unpowered:
            if _SENSECAP_HEAD.search(result):
                result = _SENSECAP_HEAD.sub(
                    "SenseCap D1 power state is user-reported; its app load cause remains unverified",
                    result,
                )
                reasons.add("user_reported_not_causal")
            if _SENSECAP_UNSUPPORTED.search(result):
                result = _SENSECAP_UNSUPPORTED.sub(
                    "Transport failures to an intentionally unpowered device may be expected, but this does not explain its measured app load.",
                    result,
                )
                reasons.add("user_reported_not_causal")
            if section == "sensecap" and re.search(r"(?i)\bno\s+test\s+required\b", result):
                result = re.sub(
                    r"(?i)\bno\s+test\s+required\b[^\n]*",
                    "Inspect existing app schedule and sampled errors read-only before attributing measured load to the power-off state.",
                    result,
                )
                reasons.add("user_reported_not_causal")
        if _HIGH_CERTAINTY.search(result) and (
            (section == "performance" and bounded_performance)
            or (section == "errors" and saturated_logs)
        ):
            result = _HIGH_CERTAINTY.sub(
                "**Certainty:** Limited by returned top-ranked statistics and saturated log coverage.",
                result,
            )
            reasons.add("overconfident_certainty")
        if _ABSOLUTE.search(result) and known_unpowered:
            result = _ABSOLUTE.sub(
                "**Certainty:** User-reported power-off state; attribution of app load to that state is unverified.",
                result,
            )
            reasons.add("overconfident_certainty")
        corrected.append(result + newline)
    return "".join(corrected), tuple(sorted(reasons))


__all__ = ["calibrate_audit_ai_advisory"]
