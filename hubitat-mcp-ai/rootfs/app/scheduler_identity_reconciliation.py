"""Read-only reconciliation of scheduler-key *candidates* with installed IDs.

An appNNNN scheduler key is a tentative attribution, even if NNNN matches
an installed app. Neither the matching identity nor a disabled configuration
state proves callback ownership, execution, or an automation error.
"""
from __future__ import annotations

import re
from typing import Any


_VALID = {"active", "disabled", "paused", "broken", "unknown"}


def _safe(value: Any) -> str:
    value = re.sub(r"[\r\n|<>{}\[\]*\x60]", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()[:90]


def _ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        str(identifier) for identifier in value[:1000]
        if str(identifier).isdigit()
    }


def reconcile_scheduler_candidates(
    job_summary: dict[str, Any] | None,
    automation_section: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return bounded, positive ID overlaps, never inferred ownership."""
    if not isinstance(job_summary, dict) or job_summary.get("status") != "parsed":
        return {"status": "unavailable", "reason": "scheduler source not parsed"}
    if not isinstance(automation_section, dict):
        return {"status": "unavailable", "reason": "automation identity index absent"}
    rows = automation_section.get("inventory_identities")
    if not isinstance(rows, list):
        return {"status": "unavailable", "reason": "automation identity index absent"}
    indexed: dict[str, dict[str, str]] = {}
    for row in rows[:500]:
        if not isinstance(row, dict):
            continue
        identity = str(row.get("id") or "")
        if not identity.isdigit():
            continue
        status = str(row.get("status") or "unknown").lower()
        indexed[identity] = {
            "id": identity,
            "name": _safe(row.get("name") or "Unnamed automation"),
            "type": _safe(row.get("type") or "app"),
            "status": status if status in _VALID else "unknown",
        }
    kinds = job_summary.get("candidateIdsByType")
    candidate_ids = _ids(kinds.get("app")) if isinstance(kinds, dict) else set()
    matches = sorted(candidate_ids & set(indexed), key=int)
    missing = sorted(candidate_ids - set(indexed), key=int)
    # No scheduler candidate IDs is NOT evidence that there are no jobs.
    # Snapshot may also contain anonymous IDs; never claim a complete set.
    status_counts = {
        status: sum(indexed[item]["status"] == status for item in matches)
        for status in sorted(_VALID)
    }
    disabled_candidates = [
        indexed[identity] for identity in matches
        if indexed[identity]["status"] == "disabled"
    ]
    top_candidates = sorted(
        disabled_candidates, key=lambda x: int(x["id"]),
    )[:6]
    total = automation_section.get("total")
    identity_coverage = (
        isinstance(total, int) and len(indexed) == total
    )
    return {
        "status": "checked",
        "attribution": "scheduler-key-pattern only; not verified job ownership",
        "candidateAppIds": len(candidate_ids),
        "matchedAppIds": len(matches),
        "unmatchedAppIds": len(missing),
        "matchedConfigurationStates": status_counts,
        "configurationDisabledCandidateIds": len(disabled_candidates),
        "configurationDisabledCandidateExamples": top_candidates,
        "identityIndexComplete": identity_coverage,
        "noCandidateIds": not bool(candidate_ids),
        "notVerified": [
            "which app owns each scheduler row",
            "whether a callback is active or executed",
            "disabled-app scheduling behavior",
            "overlapping triggers, actions and device dependencies",
        ],
    }


def render_scheduler_candidate_reconciliation(
    analysis: dict[str, Any] | None,
) -> str:
    lines = ["### Scheduler candidates versus installed automations"]
    if not isinstance(analysis, dict) or analysis.get("status") != "checked":
        return "\n".join(lines + [
            "- Not checked: a parsed scheduler and current installed-app identity "
            "index were both required. No ownership conclusion is possible.",
        ])
    if analysis.get("noCandidateIds"):
        return "\n".join(lines + [
            "- No scheduler-key-pattern app IDs were returned. This does not "
            "mean the hub has no scheduled jobs or disabled-app callbacks.",
            "- Owner attribution remains unverified.",
        ])
    lines.append(
        f"- {analysis['candidateAppIds']} distinct **candidate app IDs** "
        f"were encoded in scheduler keys; {analysis['matchedAppIds']} "
        "also occur in the installed-app identity index "
        f"({analysis['unmatchedAppIds']} did not match)."
    )
    if not analysis.get("identityIndexComplete"):
        lines.append(
            "- The installed identity index is partial or includes entries without "
            "stable IDs. An unmatched candidate is not proof of a missing app."
        )
    disabled = analysis.get("configurationDisabledCandidateIds") or 0
    lines.append(
        f"- {disabled} matched candidate ID(s) correspond to automations "
        "**reported disabled in configuration**. This is a lead, not proof "
        "that a disabled app still owns or executes scheduled work."
    )
    for candidate in (analysis.get("configurationDisabledCandidateExamples") or [])[:6]:
        lines.append(
            f"  - {_safe(candidate.get('name'))} (app "
            f"{_safe(candidate.get('id'))}) — configuration status disabled; "
            "scheduler-key attribution unverified."
        )
    lines.append(
        "- **Next read-only verification:** inspect the actual installed app's "
        "scheduled-job owner metadata, configuration and callback registration. "
        "Compare triggers/actions and shared target device IDs before claiming "
        "rule overlap, or proposing to pause, merge or delete automations."
    )
    return "\n".join(lines)


__all__ = [
    "reconcile_scheduler_candidates",
    "render_scheduler_candidate_reconciliation",
]
