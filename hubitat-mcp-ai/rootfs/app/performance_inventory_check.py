"""Read-only scheduler-key candidate vs current Hubitat entity inventory.

Entity existence is an independently verified fact. Ownership of a job is NOT:
the id embedded in devNNNRecur/appNNNOnce is only a candidate association.
Do not infer a deleted app or redundant schedule from a partial/missing list.
"""
from __future__ import annotations

from typing import Any

_TOTALS = ("totalOnHub", "totalDevices", "totalCount", "total", "count")


def _rows_and_coverage(data: Any, kind: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    value = data
    for _ in range(4):
        if not isinstance(value, dict):
            break
        if kind in value and isinstance(value[kind], list):
            break
        wrapped = next(
            (value[key] for key in ("result", "data", "output")
             if isinstance(value.get(key), dict)), None
        )
        if wrapped is None:
            break
        value = wrapped
    if not isinstance(value, dict) or not isinstance(value.get(kind), list):
        return [], {"status": "unavailable", "rowsReturned": 0, "complete": False}
    rows = [row for row in value[kind] if isinstance(row, dict)]
    reported = None
    for source in (value, data):
        if not isinstance(source, dict):
            continue
        for key in _TOTALS:
            try:
                raw = source.get(key)
                if isinstance(raw, bool) or raw is None:
                    continue
                number = int(raw)
                if number >= 0:
                    reported = number
                    break
            except (ValueError, TypeError):
                continue
        if reported is not None:
            break
    partial = any(
        value.get(key) is True for key in ("truncated", "partial", "hasMore")
    ) or value.get("nextOffset") not in (None, "", 0) or value.get("idsComplete") is False
    complete = (
        reported is not None and len(rows) == reported and not partial
        and len(rows) == len(value[kind])
    )
    return rows, {
        "status": "available",
        "source": str(value.get("identitySource") or "hub_list_devices")[:80],
        "rowsReturned": len(rows),
        "reportedTotal": reported,
        "complete": complete,
    }


def _safe_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    token = str(value).strip()
    return str(int(token)) if token.isascii() and token.isdecimal() and int(token) > 0 else ""


def _lookup(data: Any, kind: str) -> tuple[dict[str, str], dict[str, Any]]:
    rows, coverage = _rows_and_coverage(data, kind)
    found: dict[str, str] = {}
    conflicts: set[str] = set()
    for row in rows:
        identifier = _safe_id(row.get("id", row.get("appId" if kind == "apps" else "deviceId")))
        if not identifier:
            continue
        name = str(row.get("label") or row.get("name") or row.get("displayName") or "")[:80]
        if identifier in found:
            conflicts.add(identifier)
        else:
            found[identifier] = name
    for identifier in conflicts:
        found.pop(identifier, None)
    coverage["ambiguousIds"] = len(conflicts)
    coverage["usableUniqueIds"] = len(found)
    return found, coverage


def reconcile_scheduler_candidates(
    job_digest: dict[str, Any],
    *,
    apps: Any = None,
    devices: Any = None,
    performance: Any = None,
) -> dict[str, Any]:
    """Compare complete *candidate ID sets*, never only first-page table rows."""
    candidates = job_digest.get("candidateIdsByType") or {}
    perf = performance if isinstance(performance, dict) else {}
    result: dict[str, Any] = {
        "status": "compared",
        "jobRowsExamined": int(job_digest.get("rowsExamined") or 0),
        "keyCandidateJobs": int(job_digest.get("keyPatternCandidateRows") or 0),
        "explicitOwnerJobs": int(job_digest.get("ownerIdentifiedRows") or 0),
        "note": (
            "Existing entities confirm only ID presence, not the entity that "
            "created, owns or executes a scheduled job. Do not infer CPU savings."
        ),
    }
    for kind, inventory, field, stats_field in (
        ("app", apps, "apps", "appStats"),
        ("device", devices, "devices", "deviceStats"),
    ):
        found, coverage = _lookup(inventory, field)
        ids = {_safe_id(raw) for raw in candidates.get(kind, [])}
        ids.discard("")
        present = ids.intersection(found)
        # No inventory read means no ID was checked. Never turn a timeout
        # into a misleading count of missing or unlisted hub devices.
        available = coverage.get("status") == "available"
        unlisted = ids - present if available else set()
        unchecked = ids if not available else set()
        verified_examples = [
            {"id": identifier, "name": found[identifier]}
            for identifier in sorted(present, key=int)[:5]
        ]
        measured = []
        stats = perf.get(stats_field) or []
        if isinstance(stats, list):
            for row in stats:
                if not isinstance(row, dict):
                    continue
                identifier = _safe_id(row.get("id"))
                if identifier not in present:
                    continue
                try:
                    pct_total = float(str(row.get("pctTotal") or "0").strip().rstrip("%"))
                except (TypeError, ValueError):
                    continue
                measured.append({
                    "id": identifier, "name": found[identifier],
                    "pctTotal": pct_total,
                })
        measured.sort(key=lambda row: (-row["pctTotal"], int(row["id"])))
        result[kind] = {
            "candidateIds": len(ids),
            "presentInReturnedInventory": len(present),
            "notListedInReturnedInventory": len(unlisted),
            "notCheckedDueToUnavailableInventory": len(unchecked),
            "inventory": coverage,
            "presentExamples": verified_examples,
            "notListedExamples": sorted(unlisted, key=int)[:5] if coverage.get("complete") else [],
            "topMeasuredOverlaps": measured[:4],
        }
    return result


def render_scheduler_inventory_crosscheck(report: dict[str, Any]) -> str:
    if report.get("status") != "compared":
        return ""
    lines = [
        "### Scheduled-job entity cross-check (read-only)",
        "A matching Hubitat entity ID **confirms that the entity was listed**, "
        "not that it owns, schedules, or executes the job.",
        "| Candidate kind | Unique candidate IDs | Listed entities | Not listed in returned rows | Not checked | Inventory coverage |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for kind in ("device", "app"):
        section = report.get(kind) or {}
        coverage = section.get("inventory") or {}
        status = (
            f"{coverage.get('rowsReturned', 0)}/{coverage.get('reportedTotal')} returned"
            if coverage.get("reportedTotal") is not None else
            f"{coverage.get('rowsReturned', 0)} rows; total unknown"
        )
        if coverage.get("status") != "available":
            status = "read unavailable"
        elif not coverage.get("complete"):
            status += " (partial/unverified completeness)"
        else:
            status += " (complete)"
        lines.append(
            f"| {kind} | {section.get('candidateIds', 0)} | "
            f"{section.get('presentInReturnedInventory', 0)} | "
            f"{section.get('notListedInReturnedInventory', 0)} | "
            f"{section.get('notCheckedDueToUnavailableInventory', 0)} | {status} |"
        )
    for kind in ("device", "app"):
        section = report.get(kind) or {}
        overlaps = section.get("topMeasuredOverlaps") or []
        if overlaps:
            lines.extend([
                f"**{kind.capitalize()} candidates also appearing in the sampled performance ranking:**",
                "| Candidate ID | Listed entity | Measured pctTotal |",
                "| --- | --- | ---: |",
            ])
            for row in overlaps:
                safe_name = str(row["name"]).replace("|", "/").replace("\n", " ")
                lines.append(
                    f"| {row['id']} | {safe_name} | {row['pctTotal']:.3f}% |"
                )
    for kind in ("app", "device"):
        section = report.get(kind) or {}
        examples = section.get("notListedExamples") or []
        if examples:
            lines.append(
                f"**{kind.capitalize()} candidate IDs absent from a complete returned inventory "
                f"(inspect; not proof of stale scheduled jobs):** "
                + ", ".join(str(item) for item in examples) + "."
            )
    lines.append(
        "Not listed does **not** prove a deleted or orphaned entity, especially "
        "when inventory completeness is not verified. A performance overlap "
        "is an investigation lead, not a quantified saving."
    )
    return "\n".join(lines)
