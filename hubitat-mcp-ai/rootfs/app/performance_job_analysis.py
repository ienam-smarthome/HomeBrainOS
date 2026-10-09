"""Bounded, provenance-preserving analysis of Hubitat scheduled-job snapshots.

Each scheduled row is a queued/scheduled entry, not an observed execution or
a CPU-consumption measurement. Missing ownership/method fields stay unknown.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any

_LIST_FIELDS = ("jobs", "entries", "items", "scheduledJobs", "schedules", "jobList", "jobEntries")
_TOTAL_FIELDS = ("count", "total", "totalCount", "scheduledJobCount")
_OWNER_FIELDS = (("appId", "app"), ("deviceId", "device"))
_METHOD_FIELDS = ("handlerMethod", "methodName", "method", "handler", "callback", "handlerName")
_NEXT_FIELDS = ("nextRun", "nextRunTime", "nextScheduledRun", "nextExecution", "nextRunAt")
_JOB_KEY_FIELDS = ("jobId", "jobKey", "scheduleId", "scheduleKey", "id")
# This is a *candidate*, not a verified ownership relationship. Hubitat
# scheduler keys such as dev7334Once encode a plausible parent identifier.
# Never interpret arbitrary device display names as owner IDs.
_JOB_KEY_CANDIDATE = re.compile(
    r"^(app|dev)([1-9][0-9]{0,8})(Once|Recur)"
    r"(?:\.([A-Za-z][A-Za-z0-9_$]{0,99}))?$", re.I
)



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
    possible_rows = [value for key, value in section.items()
                     if key not in _TOTAL_FIELDS and isinstance(value, dict)]
    if possible_rows and len(possible_rows) == len(
        [key for key in section if key not in _TOTAL_FIELDS]
    ):
        # Preserve the scheduler's map key (it may be the only place the
        # encoded parent reference survives), but do not change source rows.
        return [
            {**value, "__schedulerMapKey": str(key)}
            for key, value in section.items()
            if key not in _TOTAL_FIELDS and isinstance(value, dict)
        ]
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
    candidate_groups: Counter[tuple[str, str, str]] = Counter()
    candidate_key_examples: list[str] = []
    candidate_rows = 0
    candidate_types: Counter[str] = Counter()
    candidate_methods: Counter[tuple[str, str]] = Counter()
    candidate_owner_totals: Counter[tuple[str, str]] = Counter()
    methods: Counter[str] = Counter()
    no_candidate_methods: Counter[str] = Counter()
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
        # Decode only an exact, narrowly recognized scheduler-key pattern.
        # This is explicitly NOT a verified owner from the row. A separate
        # app/device inventory is needed to establish that relationship.
        candidate_kind = ""
        candidate_id = ""
        if not owner_id:
            job_keys = [
                str(row[key]).strip()
                for key in (*_JOB_KEY_FIELDS, "jobName")
                if isinstance(row.get(key), (str, int))
                and str(row[key]).strip()
            ]
            # A numeric/GUID row ID may coexist with an encoded schedule-map
            # key; do not lose the latter simply because 'id' is populated.
            job_keys.append(str(row.get("__schedulerMapKey") or ""))
            match = next(
                (candidate for key in job_keys
                 if (candidate := _JOB_KEY_CANDIDATE.fullmatch(key))),
                None,
            )
            if match:
                job_key = match.group(0)
                key_method = match.group(4) or ""
                row_method = _pick(row, _METHOD_FIELDS)
                # A disagreement between independent method fields is not
                # sufficient to resolve ownership: report it as unknown.
                if not key_method or not row_method or key_method.casefold() == row_method.casefold():
                    candidate_kind = "app" if match.group(1).casefold() == "app" else "device"
                    candidate_id = match.group(2)
                    candidate_rows += 1
                    candidate_types[candidate_kind] += 1
                    if len(candidate_key_examples) < 3:
                        candidate_key_examples.append(job_key)
            unattributed += 1
        method = _pick(row, _METHOD_FIELDS)
        if not method:
            if candidate_id and match and match.group(4):
                method = match.group(4)[:100]
            else:
                unknown_method += 1
                method = "unknown method"
        methods[method] += 1
        if not owner_id and not candidate_id:
            no_candidate_methods[method] += 1
        groups[(owner_type or "unknown", owner_id or "unknown", method)] += 1
        if candidate_id:
            candidate_groups[(candidate_kind, candidate_id, method)] += 1
            candidate_methods[(candidate_kind, method)] += 1
            candidate_owner_totals[(candidate_kind, candidate_id)] += 1
        next_run = _pick(row, _NEXT_FIELDS)
        if next_run:
            next_runs[next_run] += 1

    grouped = [
        {"ownerType": key[0], "ownerId": key[1], "method": key[2], "jobs": count}
        for key, count in sorted(groups.items(), key=lambda it: (-it[1], it[0]))
        if key[1] != "unknown"
    ][:max_groups]
    inferred_groups = [
        {"ownerType": key[0], "candidateOwnerId": key[1],
         "method": key[2], "jobs": count, "attribution": "scheduler-key-pattern"}
        for key, count in sorted(
            candidate_groups.items(), key=lambda item: (-item[1], item[0])
        )
    ][:max_groups]
    # The globally capped list can contain only tied app entries. Rank the
    # types independently from the *full* grouped set to represent both.
    def _top_kind_methods(kind: str) -> list[dict[str, Any]]:
        return [
            {"ownerType": key[0], "candidateOwnerId": key[1],
             "method": key[2], "jobs": value,
             "attribution": "scheduler-key-pattern"}
            for key, value in sorted(
                ((key, value) for key, value in candidate_groups.items()
                 if key[0] == kind),
                key=lambda item: (-item[1], item[0]),
            )[:max_groups]
        ]

    def _top_kind_owners(kind: str) -> list[dict[str, Any]]:
        return [
            {"candidateOwnerId": key[1], "jobs": count}
            for key, count in sorted(
                ((key, count) for key, count in candidate_owner_totals.items()
                 if key[0] == kind),
                key=lambda item: (-item[1], item[0]),
            )[:max_groups]
        ]

    observed_count = len(rows)
    reported = total if total is not None else observed_count
    return {
        "status": "parsed",
        "reportedJobs": reported,
        "rowsExamined": observed_count,
        "completeRows": total is None or total == observed_count,
        "ownerIdentifiedRows": observed_count - unattributed,
        "unattributedRows": unattributed,
        "keyPatternCandidateRows": candidate_rows,
        "keyPatternCandidateExamples": candidate_key_examples,
        "keyPatternCandidateTypes": dict(candidate_types),
        "rowsWithoutOwnerCandidate": unattributed - candidate_rows,
        "topNoCandidateMethods": [
            {"method": method, "jobs": count}
            for method, count in no_candidate_methods.most_common(8)
        ],
        "keyPatternUniqueOwners": {
            kind: sum(1 for key in candidate_owner_totals if key[0] == kind)
            for kind in ("device", "app")
        },
        "topCandidateDeviceMethods": _top_kind_methods("device"),
        "topCandidateAppMethods": _top_kind_methods("app"),
        "topCandidateDeviceOwners": _top_kind_owners("device"),
        "topCandidateAppOwners": _top_kind_owners("app"),
        # Full distinct identity sets are host-only. The model packet strips
        # them; they exist to validate candidate IDs in one bounded inventory
        # cross-check without guessing from the truncated top tables.
        "candidateIdsByType": {
            kind: sorted(
                {key[1] for key in candidate_owner_totals if key[0] == kind},
                key=lambda identifier: int(identifier),
            )
            for kind in ("device", "app")
        },
        "topCandidateMethodsByType": {
            kind: [
                {"method": key[1], "jobs": count}
                for key, count in sorted(
                    ((key, count) for key, count in candidate_methods.items()
                     if key[0] == kind),
                    key=lambda item: (-item[1], item[0]),
                )[:6]
            ]
            for kind in ("device", "app")
        },
        "topCandidateOwnerMethods": inferred_groups,
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
    candidate_count = int(summary.get("keyPatternCandidateRows") or 0)
    without_candidate = int(summary.get(
        "rowsWithoutOwnerCandidate",
        max(0, int(summary.get("unattributedRows") or 0) - candidate_count),
    ))
    if candidate_count:
        breakdown = summary.get("keyPatternCandidateTypes") or {}
        lines.append(
            f"Of {examined} rows: {owner_rows} confirmed from explicit IDs; "
            f"{candidate_count} unverified scheduler-key owner candidates "
            f"(device: {breakdown.get('device', 0)}, "
            f"app: {breakdown.get('app', 0)}); "
            f"{without_candidate} have no owner candidate."
        )

        lines.extend([
            "",
            "**Scheduler-key owner candidates — not verified**",
            "A matching device/app prefix is not proof that the referenced "
            "entity owns or executes the scheduled task. Validate IDs and "
            "dependencies before recommending modifications.",
        ])
        for kind in ("device", "app"):
            records = summary.get(
                "topCandidateDeviceMethods" if kind == "device"
                else "topCandidateAppMethods"
            )
            if records is None:
                records = [
                    item for item in (summary.get("topCandidateOwnerMethods") or [])
                    if item.get("ownerType") == kind
                ]
            unique = (summary.get("keyPatternUniqueOwners") or {}).get(kind)
            lines.append(
                f"**{kind.capitalize()} candidate jobs:** "
                f"{breakdown.get(kind, 0)}"
                + (f" across {unique} distinct candidate IDs" if unique is not None else "")
            )
            if not records:
                lines.append("No individually attributable candidate records available.")
                continue
            lines.extend([
                "| Candidate ID | Handler | Scheduled entries |",
                "| --- | --- | ---: |",
            ])
            for record in records:
                lines.append(
                    f"| {record['candidateOwnerId']} | "
                    f"{str(record['method']).replace('|', '/')} | "
                    f"{record['jobs']} |"
                )
            lines.append("")
        lines.append(
            "These two candidate tables are separately ranked and show only "
            "the most frequent owner/method combinations, not all matched rows."
        )

    unassigned_methods = summary.get("topNoCandidateMethods") or []
    if unassigned_methods:
        lines.extend([
            "",
            "**Scheduled entries with no owner candidate, grouped by handler**",
            "| Handler | Entries with no candidate |",
            "| --- | ---: |",
        ])
        for item in unassigned_methods[:8]:
            lines.append(
                f"| {str(item['method']).replace('|', '/')} | {item['jobs']} |"
            )
        lines.append(
            "These entries lack an ID usable for entity cross-checking. "
            "Method names alone cannot identify an owning app or device."
        )

    methods = summary.get("topMethods") or []
    if methods:
        lines.extend([
            "",
            "**Scheduled entries by handler (where identified)**",
            "| Handler | Entries |",
            "| --- | ---: |",
        ])
        for item in methods[:8]:
            lines.append(
                f"| {str(item['method']).replace('|', '/')} | {item['jobs']} |"
            )
    clusters = summary.get("sameNextRunGroups") or []
    if clusters:
        lines.append(
            "Shared next-run timestamps were observed (largest group "
            f"{clusters[0]['jobs']} entries), but these do not prove "
            "simultaneous execution or CPU contention."
        )
    lines.append("These are scheduled entries, not measured executed calls or verified CPU savings.")
    return "\n".join(lines)
