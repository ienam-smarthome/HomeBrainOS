"""Proof-linked natural-language *hypothesis* from the native AI.

The model is an interpreter, not an evidence authority. It must name
specific event receipts from the independently scoped, dated MCP read.
The host verifies exact event names/timestamps/read IDs before publishing
a qualified explanation. This is an optional V2-only step; no tool or
write permission is added, and a model's unsupported causal assertion is
never promoted to a verified root cause.

Unlike catalog-fact fallback, the model can express a general causal
hypothesis in natural language. Full semantic entailment of arbitrary
model prose remains unverified, so all such conclusions stay tentative.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import re
from typing import Any

_CONTROL = re.compile(r"[\x00-\x1f\x7f]|[<>]")
_CONFIDENT = re.compile(
    r"(?i)\b(?:definitely|certainly|proven|proved|undeniably|"
    r"confirmed cause|root cause is|must have been)\b"
)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\d)")


def candidate_prompt() -> str:
    return (
        "You are producing a short, evidence-led explanation for the user's "
        "dated Hubitat incident, NOT an audit of tool calls. Return ONLY JSON "
        "of shape: {\"hypothesis\":\"one natural sentence describing the "
        "most plausible mechanism\",\"confidence\":\"possible\","
        "\"supporting_events\":[{\"read\":1,\"name\":\"switch\","
        "\"date\":\"unchanged timestamp from source evidence\"}],"
        "\"next_check\":\"one useful observation that would distinguish "
        "the leading hypothesis from alternatives\"}. "
        "Select at least two DISTINCT attested events listed in "
        "incident_evidence.material_event_examples and copy each exact "
        "read/name/date. Do not cite a tool result that merely mentions "
        "an app name or lists commands from a later date. "
        "The answer may rank a hypothesis as possible, not assert any "
        "unverified physical cause or timer execution as certain. "
        "Do not invent times, sensors, device states, rules, or execution "
        "results missing from the supplied evidence. If you cannot explain "
        "a mechanism from the shown events, return {\"hypothesis\":\"\","
        "\"supporting_events\":[],\"confidence\":\"unknown\","
        "\"next_check\":\"\"}. No tools or other output."
    )


def verify_natural_hypothesis(
    candidate: Any, *, coverage: Mapping[str, Any] | None,
    observed_source_names: Sequence[str] = (),
) -> dict[str, Any]:
    """Exact source anchors for a tentative user-facing explanation.

    It is impossible to infer the truth of arbitrary English from a read ID
    alone. Therefore the host verifies references and rejects numerical
    claims not present in the source, uses possible rather than confirmed,
    and explicitly records that semantic entailment is NOT verified.
    """
    reject = lambda reason: {
        "accepted": False, "reason": reason, "model_prose_published": False,
    }
    if coverage is None or coverage.get("incident_answer_evidence_present") is not True:
        return reject("no_relevant_dated_incident_events")
    if not isinstance(candidate, Mapping):
        if not isinstance(candidate, str) or len(candidate) > 3500:
            return reject("invalid_response_type")
        try:
            candidate = json.loads(candidate)
        except (ValueError, TypeError):
            return reject("invalid_json")
    if not isinstance(candidate, Mapping):
        return reject("invalid_payload")
    hypothesis = candidate.get("hypothesis")
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        return reject("no_model_explanation")
    hypothesis = " ".join(hypothesis.strip().split())
    if (len(hypothesis) > 260 or len(hypothesis) < 20
            or _CONTROL.search(hypothesis) or _CONFIDENT.search(hypothesis)):
        return reject("overconfident_or_unbounded_explanation")
    if candidate.get("confidence") != "possible":
        return reject("unsupported_confidence")
    provided = candidate.get("supporting_events")
    if not isinstance(provided, list) or len(provided) < 2 or len(provided) > 6:
        return reject("missing_independent_event_anchors")
    allowed = {
        (str(event["read"]), str(event["name"]), str(event["date"]))
        for event in coverage.get("material_event_examples", [])
        if isinstance(event, Mapping)
        and type(event.get("read")) is int
        and isinstance(event.get("name"), str)
        and isinstance(event.get("date"), str)
    }
    chosen = []
    for event in provided:
        if not isinstance(event, Mapping) or set(event) != {"read", "name", "date"}:
            return reject("invalid_event_anchor")
        if type(event["read"]) is not int:
            return reject("invalid_read_id")
        key = (str(event["read"]), str(event["name"]), str(event["date"]))
        if key not in allowed:
            return reject("event_not_in_verified_incident_window")
        if key not in chosen:
            chosen.append(key)
    if len(chosen) < 2:
        return reject("duplicate_event_anchor")
    # A cause description with numbers must not invent an app or event ID,
    # duration, level or timestamp not present in either user-provided
    # question, source anchors or independently observed source names.
    reference_text = " ".join(
        [" ".join(map(str, row)) for row in allowed]
        + [str(name) for name in observed_source_names]
    )
    if any(num not in reference_text for num in _NUMBER.findall(hypothesis)):
        return reject("unsupported_numeric_detail")
    next_check = candidate.get("next_check", "")
    if not isinstance(next_check, str):
        return reject("invalid_next_check")
    next_check = " ".join(next_check.strip().split())
    if len(next_check) > 180 or _CONTROL.search(next_check):
        return reject("invalid_next_check")
    statement = "**Possible explanation:** " + hypothesis
    if next_check:
        statement += " **To distinguish the cause:** " + next_check
    return {
        "accepted": True,
        "reason": "source_event_refs_verified_semantic_cause_not_proven",
        "text": statement,
        "supporting_events": [
            {"read": int(r), "name": n, "date": d} for r, n, d in chosen],
        "model_prose_published": True,
        "semantic_entailment_verified": False,
        "root_cause_verified": False,
    }


__all__ = ["candidate_prompt", "verify_natural_hypothesis"]
