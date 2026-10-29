"""Conservative independent validation of model-authored general explanations.

The model may author *how to explain* a source case, but the host checks
the subject, returned numeric facts, exact reported status attributes,
unsupported causal terms, vocabulary and safe read-only next checks before
publishing any of its words. No extra read/write operation is authorised.

This is NOT arbitrary semantic entailment: accepted text uses a deliberately
small source-scoped language. Unsupported or nonconforming output is rejected
in full and the existing host-attested answer is retained.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .native_source_adapters import safe_string

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d+(?![A-Za-z0-9])")
_ASSIGN = re.compile(
    r"\b(healthStatus|networkStatus|deviceHealth|mqttStatus)"
    r"\s*=\s*([A-Za-z]+)", re.I)
_UNSAFE = re.compile(
    r"(?i)(?:https?://|www\.|[<>]|[\x00-\x1f]|"
    r"\b(?:token|password|credential|secret|apikey|execute|sudo|"
    r"install|uninstall|write|disable|enable|delete|reboot|restart|"
    r"caused|causes|root.cause|definitely|certainly|guaranteed|"
    r"broken|dead|crashed|overheating|unreachable|fixed|resolved|"
    r"failure.is|has.failed|must.replace|power.cut|not.responding)\b)"
)
# Neutral words cannot claim a new status, time, actor, physical failure or
# automation execution. Names and exact statuses are added from source case.
_CONNECTIVES = set("""
the a an and or but is are was were be been being it its this that these those
there here from to of for in on at by with without as than so when where
which who why how what if then because while though despite due only may might
could should would can cannot not do does did has have had reported reports
report reporting source sources source-reported state status statuses reading
readings independent independently observed observation observations
log logs warning warnings error errors warn row rows returned sampled sample
samples count counts repeated recurring recurrence currently current recent
historical during earlier later period window windows since last known unknown
activity connection connectivity device devices app apps automation system
hub hubitat telemetry evidence verified unverified uncertain uncertainty
suspected possible potential plausible concern concerns issue issues reason
reasons finding findings priority attention check checking worth important
first next separate consistent inconsistent conflicting mismatch between
indicates indicate show shows showing suggests suggest rather confirms confirm
confirmed proof proves prove alone together alongside also another additionally
anomalous unusual more less many several same different distinct one two three
observations matching match identity independently recorded source-linked
isn't aren't doesn't didn't hasn't haven't can't won't
healthstatus networkstatus devicehealth mqttstatus lastseen dataageseconds
online offline stale connected disconnected true false warn error
""".replace("-", " ").split())
_ALLOWED_RECOMMENDATION = re.compile(
    r"(?i)^(?:check|verify|inspect|confirm|review|compare|test|investigate|"
    r"examine|look at)\b")
_FORBID_CHECK = re.compile(
    r"(?i)\b(?:turn|switch|set|change|create|delete|disable|enable|restart|"
    r"reboot|block|unblock|reset|power.off|shut.down|write|send|"
    r"deploy|install|uninstall|force)\b")
_SPACES = re.compile(r"\s+")


def _parsed(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str) or len(value) > 7500:
        return None
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _validate_explanation(text: Any, case: Mapping[str, Any]) -> str | None:
    if (not isinstance(text, str) or len(text) > 265
            or len(text) < 18 or _UNSAFE.search(text)):
        return None
    prose = _SPACES.sub(" ", text).strip()
    if not prose or prose.count(".") > 2:
        return None
    name = str(case.get("name") or "")
    ident = str(case.get("source_id") or "")
    if not name or not ident or (
        name.casefold() not in prose.casefold()
        and not re.search(r"(?<!\d)"+re.escape(ident)+r"(?!\d)", prose)):
        return None
    status = case.get("status")
    status = status if isinstance(status, Mapping) else {}
    for match in _ASSIGN.finditer(prose):
        field, state = match.group(1), match.group(2)
        actual = next((v for k, v in status.items()
                       if k.casefold() == field.casefold()), None)
        if str(actual or "").casefold() != state.casefold():
            return None
    # Never take unqualified "is offline" as physical proof: source status
    # words must remain attached to exact source-reported field names.
    if re.search(
            r"(?i)\b(?:is|was|are|went|stayed)\s+"
            r"(?:online|offline|stale|connected|disconnected)\b", prose):
        return None
    levels = {str(level).upper()
              for level in case.get("warning_levels", [])}
    for word in ("WARN", "ERROR"):
        if re.search(r"\b"+word+r"\b", prose, flags=re.I) and word not in levels:
            return None
    numbers = set(_NUMBER.findall(prose))
    allowable_numbers = {ident, str(case.get("warning_rows_in_returned_sample") or "")}
    allowable_numbers.update(_NUMBER.findall(name))
    if not numbers.issubset(allowable_numbers):
        return None
    warnings = int(case.get("warning_rows_in_returned_sample") or 0)
    has_evidence = False
    if warnings and str(warnings) in numbers and re.search(
            r"(?i)\b(?:warn|error|warnings|errors|log|logs|rows)\b", prose):
        has_evidence = True
    if any(re.search(r"(?i)\b"+re.escape(k)+r"\s*=\s*"
                     +re.escape(str(v))+r"\b", prose)
           for k, v in status.items() if k in (
               "healthStatus", "networkStatus", "deviceHealth", "mqttStatus")):
        has_evidence = True
    if not has_evidence:
        return None
    allowed = _CONNECTIVES | {w.casefold() for w in _WORD.findall(name)}
    allowed.update({w.casefold() for w in _WORD.findall(ident)})
    allowed.update({w.casefold() for k, v in status.items()
                    for w in _WORD.findall(k + " " + str(v))})
    if any(w.casefold() not in allowed for w in _WORD.findall(prose)):
        return None
    return safe_string(prose, 265)


def _validate_next_check(value: Any) -> str | None:
    if not isinstance(value, str) or not (15 <= len(value) <= 155):
        return None
    clean = _SPACES.sub(" ", value).strip()
    # A diagnostic question is a recommendation, not proof that a particular
    # physical state is already true; no model action is ever executed.
    if (_UNSAFE.search(clean) or _FORBID_CHECK.search(clean)
            or not _ALLOWED_RECOMMENDATION.match(clean)
            or _NUMBER.search(clean)
            or re.search(r"(?i)\b(?:is|was|were|has|have)\b", clean)):
        return None
    return safe_string(clean, 155)


def verify_model_explanation(
    proposal: Any,
    cases: Sequence[Mapping[str, Any]],
    *,
    max_findings: int = 3,
) -> dict[str, Any]:
    """Fail closed on any unsupported segment; no partial model prose leaks."""
    obj = _parsed(proposal)
    if obj is None or set(obj) != {"findings"}:
        return {"accepted": False, "reason": "invalid_proposal"}
    findings = obj.get("findings")
    if not isinstance(findings, list) or not (1 <= len(findings) <= max_findings):
        return {"accepted": False, "reason": "invalid_findings"}
    source = {str(c.get("source_id")): c for c in cases
              if isinstance(c, Mapping) and c.get("source_id")}
    assembled = []
    seen = set()
    ordered_ids = []
    for row in findings:
        if not isinstance(row, Mapping) or set(row) != {
            "source_id", "explanation", "next_check"}:
            return {"accepted": False, "reason": "invalid_segment_shape"}
        ident = row.get("source_id")
        if not isinstance(ident, str) or ident not in source or ident in seen:
            return {"accepted": False, "reason": "unverified_subject"}
        case = source[ident]
        explanation = _validate_explanation(row.get("explanation"), case)
        next_check = _validate_next_check(row.get("next_check"))
        if explanation is None or next_check is None:
            return {"accepted": False, "reason": "unsupported_language"}
        seen.add(ident)
        ordered_ids.append(ident)
        evidence = case.get("evidence_reads", [])
        if (not isinstance(evidence, list) or not evidence
                or any(type(n) is not int for n in evidence)):
            return {"accepted": False, "reason": "unverified_read_references"}
        refs = ", ".join("#" + str(n) for n in evidence)
        assembled.append(
            f"{len(assembled)+1}. {explanation} (Read {refs})\n"
            f"   **Next check:** {next_check}"
        )
    return {
        "accepted": True,
        "reason": "source_scoped_factual_validation",
        "text": "**Evidence-checked explanation**\n\n"
                + "\n\n".join(assembled)
                + "\n\n**Limits:** This is an evidence-based triage, not "
                  "verification of physical connectivity, execution or a "
                  "root cause. The returned log window may be incomplete.",
        "verified_subject_ids": ordered_ids,
    }


def narrative_followup_eligible(
    planning_model_ms: int, planning_model_calls: int, seconds_left: float,
) -> bool:
    """Do not add a short model call after consistently slow planning calls.

    All inputs are measured durations, never a question-specific word or
    device rule. A previously verified in-loop draft always wins separately.
    """
    if (type(planning_model_ms) is not int or planning_model_ms < 0
            or type(planning_model_calls) is not int
            or planning_model_calls < 1
            or type(seconds_left) not in (int, float)
            or not (8.0 <= seconds_left < 181.0)):
        return False
    return planning_model_ms / planning_model_calls <= 3000


__all__ = ["verify_model_explanation", "narrative_followup_eligible"]
