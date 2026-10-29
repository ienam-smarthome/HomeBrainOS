"""Independent answer relevance guard for unresolved model-requested subjects.

This does NOT infer a subject from keywords, route tools, manufacture
device identities, or assert a fact about the user's actual devices. A model
can choose to resolve an explicit entity/group through authoritative live
identity; if it fails to fetch any source-verified target state, a broad
health snapshot cannot be substituted as an answer about that target.
Full read coverage stays in the technical report.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any

from .native_source_adapters import safe_string


def subject_relevance_limit(
    lookups: Sequence[Mapping[str, Any]],
    witnesses: Sequence[Mapping[str, Any]],
    *,
    focus_ids: Sequence[str] = (),
    failures: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any] | None:
    """Ground *non-coverage*, never decide the intent or the right answer.

    A successful device read counts only when the returned device ID agrees
    with independently verified read arguments. Do not promote an unscoped
    hub-info/health/log observation to a named device's current status.
    """
    if focus_ids or not lookups:
        return None
    latest = next((
        row for row in reversed(lookups)
        if isinstance(row, Mapping) and row.get("status") in (
            "not_found", "ambiguous", "identity_unavailable",
            "candidate_group", "candidate_group_too_large")
    ), None)
    if latest is None:
        return None
    # Another successful resolution, with independently verified live
    # target-scoped reads, must not be suppressed by an earlier failed alias.
    if any(row.get("status") == "unique"
           for row in lookups if isinstance(row, Mapping)):
        return None
    label = safe_string(latest.get("query"), 100)
    if not label:
        return None
    status = str(latest.get("status"))
    ids = [
        str(x) for x in latest.get("candidate_ids", [])
        if type(x) in (str, int) and str(x).isdecimal()
    ]
    attested_reads: set[str] = set()
    for witness in witnesses:
        if (not isinstance(witness, Mapping)
                or witness.get("operation") != "hub_get_device"):
            continue
        filters = witness.get("read_filters")
        result = witness.get("source_data")
        if not isinstance(filters, Mapping) or not isinstance(result, Mapping):
            continue
        requested = filters.get("deviceId")
        returned = result.get("id")
        if (type(requested) in (str, int)
                and type(returned) in (str, int)
                and str(returned) == str(requested)
                and str(returned).isdecimal()):
            attested_reads.add(str(returned))
    if status == "candidate_group" and ids and set(ids).issubset(attested_reads):
        return None
    if status == "candidate_group" and ids:
        verified = sorted(set(ids) & attested_reads)
        reason = "candidate_group_incomplete"
        text = (
            f"**The requested group \"{label}\" was not fully verified.** "
            f"The live device-name lookup returned {len(ids)} possible "
            f"matching devices; {len(verified)} had independently matching "
            "device-detail reads. Name-prefix matches are candidates, "
            "not proof of group membership. I cannot establish a conclusion "
            "about all devices in that group from the returned records."
        )
    else:
        reason = "named_subject_not_verified"
        descriptions = {
            "not_found": "The authoritative name lookup found no exact or "
                         "independently confirmed candidate match.",
            "ambiguous": "The authoritative name lookup found multiple "
                         "conflicting matches, none automatically selected.",
            "identity_unavailable": "The authoritative name lookup was unavailable.",
            "candidate_group_too_large": "The candidate name group exceeded "
                                         "the safe bounded matching limit.",
        }
        text = (
            f"**I could not establish the requested subject \"{label}\".** "
            + descriptions.get(status, "Identity was not verified.")
            + " The returned generic hub logs and device-health records "
              "do not establish the requested devices' current states "
              "or explain their behaviour."
        )
    timed_out = any(
        isinstance(f, Mapping) and f.get("operation") == "hub_list_devices"
        and f.get("code") in ("read_timeout", "operation_prior_timeout")
        for f in failures
    )
    if timed_out:
        text += (
            " A full device-list read also timed out; repeating the same "
            "unbounded read is not evidence of the missing subject."
        )
    text += (
        " No device or automation was changed. Confirm the intended "
        "device names or use a separately verified targeted read."
    )
    return {
        "status": "insufficient_target_relevance",
        "reason": reason,
        "query": label,
        "candidate_count": len(ids),
        "source_verified_candidate_reads": len(set(ids) & attested_reads),
        "generic_evidence_not_answer": True,
        "text": text,
    }


__all__ = ["subject_relevance_limit"]
