"""V2 evidence-linked, fluent sequence explanations without freeform causality.

The model proposes *relationships*, not narrative facts. The host checks exact
record identity, same target, chronological ordering and epistemic stages,
then renders a short explanation of what source reads establish and what they
do not. Invalid pairs never reach the response.

This is not device-name/keyword routing and cannot issue hub commands.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .evidence import CaseFile, EvidenceItem
from .synthesis import GroundedAnswer


@dataclass(frozen=True)
class CheckedLink:
    earlier_id: str
    later_id: str
    relation: str
    reason: str = ""

    @property
    def approved(self) -> bool:
        return not self.reason


@dataclass(frozen=True)
class NarrativeAudit:
    approved: tuple[CheckedLink, ...]
    rejected: tuple[CheckedLink, ...]
    used_fallback: bool


def review_links(case: CaseFile, proposed: Any) -> NarrativeAudit:
    """Review up to four model-selected links. Reject unknown source bridges."""
    records = {row.record_id: row for row in case.records}
    if not isinstance(proposed, list) or len(proposed) > 4:
        proposed = []
    accepted: list[CheckedLink] = []
    rejected: list[CheckedLink] = []
    seen: set[tuple[str, str, str]] = set()
    for obj in proposed:
        if not isinstance(obj, dict) or set(obj) != {"earlier_id", "later_id", "relation"}:
            rejected.append(CheckedLink("", "", "", "invalid_link_shape"))
            continue
        before_id = obj.get("earlier_id")
        after_id = obj.get("later_id")
        relation = obj.get("relation")
        if any(not isinstance(x, str) for x in (before_id, after_id, relation)):
            rejected.append(CheckedLink("", "", "", "invalid_link_values"))
            continue
        a = records.get(before_id)
        b = records.get(after_id)
        link = CheckedLink(before_id, after_id, relation)
        reason = ""
        if a is None or b is None:
            reason = "unknown_record_reference"
        elif not a.target_id or a.target_id != b.target_id:
            reason = "unverified_same_target"
        elif not a.timestamp_utc < b.timestamp_utc:
            reason = "invalid_utc_chronology"
        elif relation == "later_command":
            if a.stage != "command_issued" or b.stage != "command_issued":
                reason = "command_relation_stage_mismatch"
        elif relation == "later_report":
            if a.stage != "command_issued" or b.stage != "state_reported":
                reason = "report_relation_stage_mismatch"
        else:
            reason = "unsupported_link_relation"
        signature = (before_id, after_id, relation)
        if not reason and signature in seen:
            reason = "duplicate_link"
        if reason:
            rejected.append(replace(link, reason=reason))
            continue
        seen.add(signature)
        accepted.append(link)

    return NarrativeAudit(tuple(accepted), tuple(rejected), False)


def _automatic_links(case: CaseFile) -> tuple[CheckedLink, ...]:
    """Deterministic evidence fallback, not model/rule/word routing."""
    observed = [r for r in case.records if r.stage == "command_issued" and r.target_id]
    candidate = []
    # Adjacent issued commands on the SAME target are useful chronological
    # relationships; this infers no causality or execution.
    for before, after in zip(observed, observed[1:]):
        if before.target_id == after.target_id and before.timestamp_utc < after.timestamp_utc:
            candidate.append(CheckedLink(before.record_id, after.record_id, "later_command"))
    return tuple(candidate[-3:])


def _event_reference(row: EvidenceItem) -> str:
    source = f"source {row.producer_id}" if row.producer_id else "issuer unverified"
    value = f" ({row.value})" if row.value is not None else ""
    return f"{row.action}{value} at {row.timestamp_original} by {source} [{row.record_id}]"


def render_evidence_narrative(
    case: CaseFile, answer: GroundedAnswer, proposed_links: Any,
) -> tuple[GroundedAnswer, NarrativeAudit]:
    """Add a concise, conservative interpretation ahead of immutable evidence.

    A chronological link is NOT proof of causality; a later state report is
    NOT independent proof that an earlier command physically took effect.
    """
    audit = review_links(case, proposed_links)
    links = audit.approved
    fallback = not links
    if fallback:
        links = _automatic_links(case)
    audit = replace(audit, used_fallback=fallback)
    lookup = {r.record_id: r for r in case.records}
    intro = [
        "What the records show: ",
    ]
    if links:
        for link in links[:3]:
            before, after = lookup[link.earlier_id], lookup[link.later_id]
            if link.relation == "later_command":
                intro.append(
                    f"An issued {_event_reference(before)} was followed by an "
                    f"issued {_event_reference(after)}. This establishes the "
                    "order of commands, not that either changed the device state."
                )
            else:
                intro.append(
                    f"After the issued {_event_reference(before)}, the source "
                    f"reported {_event_reference(after)}. This is a later "
                    "state report, not independent physical confirmation of "
                    "the earlier command."
                )
    elif case.records:
        intro.append("Source observations exist, but no safe cross-record "
                     "sequence could be established.")
    else:
        intro.append("No time-stamped source observation was recovered.")

    if not any(c.source_complete is True for c in case.coverage):
        intro.append(
            "The returned history is not independently proven complete; "
            "missing transitions cannot establish what did not happen."
        )
    intro.append("The available sources do not independently establish a root cause.")

    issues = list(answer.validation_issues)
    if audit.rejected:
        issues.append("unsupported_narrative_link")
    if audit.used_fallback:
        issues.append("narrative_link_fallback")
    return replace(
        answer,
        text="\n\n".join(intro) + "\n\n" + answer.text,
        validation_issues=tuple(dict.fromkeys(issues)),
    ), audit


__all__ = ["CheckedLink", "NarrativeAudit", "review_links", "render_evidence_narrative"]
