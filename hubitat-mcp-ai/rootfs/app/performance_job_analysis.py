"""Bounded, provenance-preserving analysis of Hubitat scheduled-job snapshots.

Each scheduled row is a queued/scheduled entry, not an observed execution or
a CPU-consumption measurement. Missing ownership/method fields stay unknown.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

_LIST_FIELDS = ("jobs", "entries", "items", "scheduledJobs", "schedules")
_TOTAL_FIELDS = ("count", "total", "totalCount", "scheduledJobCount")
_OWNER_FIELDS = (("appId", "app"), ("deviceId", "device"))
_METHOD_FIELDS = ("handlerMethod", "methodName", "method", "handler", "callback", "handlerName")
_NEXT_FIELDS = ("nextRun", "nextRunTime", "nextScheduledRun", "nextExecution", "nextRunAt")


def _pick(row: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(name)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()[:100]
    return ""


def _extract_rows(section: Any) -> list[dict[str, Any]] | None:
    if isinstance(section, list):
        return [r for r in section if isinstance(r, dict)]
    if not isinstance(section, dict):
        return None
    for name in _LIST_FIELDS:
        value = section.get(name)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    # Some gateways return deviceJobs / appJobs collections separately.
    collections = []
    for key, value in section.items():
        if key in _TOTAL_FIELDS:
            continue
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            collections.extend(value)
    if collections:
        return collections
    if section and all(isinstance(v, dict) for v in section.values()):
        return list(section.values())
    return None


def summarize_job_workload(payload: Any, *, max_groups: int = 10) -> dict[str, Any]:
    """Analyze exactly the available job rows without inferring missing jobs."""
    data = payload
    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        data = data["result"]
    if not isinstance(data, dict):
        return {"status": "unavailable", "reason": "No structured job payload"}
    section = data.get("scheduledJobs")
    if section is None:
        return {"status": "unavailable", "reason": "Missing scheduledJobs"}
    rows = _extract_rows(section)
    if rows is None:
        return {"status": "unavailable", "reason": "Scheduled jobs not a recognized row collection"}
    total = None
    for source in (section, data):
        if isinstance(source, dict):
            for field in _TOTAL_FIELDS:
                try:
                    proposed = int(source.get(field))
                    if proposed >= 0:
                        total = proposed
                        break
                except (ValueError, TypeError):
                    pass
        if total is not None:
            break

    groups: Counter[tuple[str, str, str]] = Counter()
    methods: Counter[str] = Counter()
    next_runs: Counter[str] = Counter()
    unattributed = 0
    unknown_method = 0
    for row in rows:
        owner_type = ""
        owner_id = ""
        for id_field, kind in _OWNER_FIELDS:
            owner = row.get(id_field)
            if isinstance(owner, (int, str)) and str(owner).strip():
                owner_type, owner_id = kind, str(owner).strip()[:80]
                break
        if not owner_id:
            for key, kind in (("app", "app"), ("device", "device")):
                nested = row.get(key)
                if isinstance(nested, dict) and nested.get("id") is not None:
                    owner_type, owner_id = kind, str(nested["id"])[:80]
                    break
        if not owner_id:
            unattributed += 1
        method = _pick(row, _METHOD_FIELDS)
        if not method:
            unknown_method += 1
            method = "unknown method"
        methods[method] += 1
        groups[(owner_type or "unknown", owner_id or "unknown", method)] += 1
        next_run = _pick(row, _NEXT_FIELDS)
        if next_run:
            next_runs[next_run] += 1

    grouped = [
        {"ownerType": key[0], "ownerId": key[1], "method": key[2], "jobs": count}
        for key, count in sorted(groups.items(), key=lambda it: (-it[1], it[0]))
        if key[1] != "unknown"
    ][:max_groups]
    observed_count = len(rows)
    reported = total if total is not None else observed_count
    return {
        "status": "parsed",
        "reportedJobs": reported,
        "rowsExamined": observed_count,
        "completeRows": total is None or total == observed_count,
        "ownerIdentifiedRows": observed_count - unattributed,
        "unattributedRows": unattributed,
        "unknownMethodRows": unknown_method,
        "topOwnerMethods": grouped,
        "topMethods": [
            {"method": method, "jobs": n} for method, n in methods.most_common(8)
        ],
        "sameNextRunGroups": [
            {"nextRun": when, "jobs": n}
            for when, n in next_runs.most_common(6) if n > 1
        ],
        "caveat": (
            "Scheduled job rows describe queued work, not confirmed execution, "
            "CPU contention, cadence, or potential savings. A shared next-run "
            "time is not evidence of a performance problem."
        ),
    }


def render_job_workload_summary(summary: dict[str, Any]) -> str:
    """Render a short, completely verified table or an honest coverage warning."""
    if summary.get("status") != "parsed":
        return ""
    total = summary.get("reportedJobs", 0)
    examined = summary.get("rowsExamined", 0)
    lines = [
        "### Scheduled-job workload breakdown (read-only)",
        f"Examined {examined} structured scheduled-job rows (reported total {total}).",
    ]
    if summary.get("completeRows") is False:
        lines.append("Only part of the reported job list was returned; do not extrapolate group counts.")
    owner_rows = int(summary.get("ownerIdentifiedRows") or 0)
    if owner_rows:
        lines.append(f"Exact owner IDs were present for {owner_rows} of {examined} rows.")
        top = summary.get("topOwnerMethods") or []
        if top:
            lines += [
                "| Owner type | Owner ID | Handler/method | Scheduled entries |",
                "| --- | --- | --- | ---: |",
            ]
            for record in top:
                lines.append(
                    f"| {record['ownerType']} | {record['ownerId']} | "
                    f"{record['method'].replace('|', '/')} | {record['jobs']} |"
                )
    else:
        lines.append(
            "No authoritative owner IDs were available in these rows; "
            "job ownership cannot yet be ranked."
        )
    lines.append("These are scheduled entries, not measured executed calls or verified CPU savings.")
    return "\n".join(lines)
