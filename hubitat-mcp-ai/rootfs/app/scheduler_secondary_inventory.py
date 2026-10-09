"""Bounded second-source identity probe for context-absent scheduler candidates.

A second MCP tool route can establish additional entity *presence*, never
scheduler ownership or deletion. Strictly no attributes, commands, or writes.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

_MAX_PAGES = 4
_PAGE_SIZE = 100
_TIME_BUDGET = 4.5
_FIELDS = ["id", "name", "label"]


def _id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return ""
    item = str(value).strip()
    return str(int(item)) if item.isascii() and item.isdecimal() and int(item) > 0 else ""


def _page(data: Any) -> dict[str, Any] | None:
    current = data
    for _ in range(4):
        if isinstance(current, list):
            return {"devices": current}
        if not isinstance(current, dict):
            return None
        if isinstance(current.get("devices"), list):
            return current
        current = next(
            (current.get(k) for k in ("result", "data", "output", "content")
             if isinstance(current.get(k), (dict, list))), None
        )
    return None


def context_absent_candidates(candidate_ids: list[Any], context: Any) -> set[str]:
    if not isinstance(context, dict) or not isinstance(context.get("devices"), list):
        return set()
    listed = {
        _id(row.get("id", row.get("deviceId")))
        for row in context["devices"] if isinstance(row, dict)
    }
    return {_id(x) for x in candidate_ids} - listed - {""}


async def probe_secondary_device_inventory(
    executor: Any,
    candidate_ids: list[Any],
    context: Any,
    *,
    budget_seconds: float = _TIME_BUDGET,
    page_size: int = _PAGE_SIZE,
    max_pages: int = _MAX_PAGES,
) -> dict[str, Any] | None:
    """Probe only when the live context had real IDs that need corroboration.

    At most four projected identity pages, total deadline 4.5 seconds.
    Unverified absence remains 'unresolved' even when a page appears complete.
    Caller must have already validated context structural completeness.
    """

    missing = context_absent_candidates(candidate_ids, context)
    if not missing:
        return None

    page_size = min(100, max(1, int(page_size)))
    max_pages = min(4, max(1, int(max_pages)))
    budget_seconds = min(4.5, max(0.01, float(budget_seconds)))
    started = time.monotonic()
    offset = 0
    total: int | None = None
    seen: dict[str, str] = {}
    duplicate = False
    page_count = 0
    complete = False
    status = "partial"

    for _ in range(max_pages):
        remaining = budget_seconds - (time.monotonic() - started)
        if remaining <= 0:
            status = "timed_out"
            break
        arguments = {
            "tool": "hub_list_devices",
            "args": {"detailed": False, "fields": list(_FIELDS),
                     "limit": page_size, "offset": offset},
        }
        read_started = time.monotonic()
        success = False
        page: dict[str, Any] | None = None
        try:
            response = await asyncio.wait_for(
                executor.execute(
                    "hub_read_devices", arguments, supports_live_claim=True,
                    evidence_kind="host_planned_scheduler_secondary_inventory",
                    record_evidence=False,
                ),
                timeout=remaining,
            )
            if bool(getattr(response, "success", False)):
                value = getattr(getattr(response, "result", None), "data", None)
                page = _page(value)
                success = page is not None
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            status = "timed_out"
        except Exception:
            status = "unavailable"

        recorder = getattr(executor, "evidence", None)
        if callable(getattr(recorder, "record", None)):
            recorder.record(
                "hub_read_devices", arguments, success=success,
                elapsed_ms=round((time.monotonic() - read_started) * 1000),
                summary=("Secondary identity page read succeeded" if success
                         else "Secondary identity page unavailable"),
                supports_live_claim=success,
                evidence_kind="host_planned_scheduler_secondary_inventory",
                mutates=False, effect="read",
            )
        if not success or page is None:
            if status == "partial":
                status = "unavailable" if not page_count else "partial"
            break

        page_count += 1
        rows = page["devices"]
        if not all(isinstance(x, dict) for x in rows):
            status = "partial"
            break
        for row in rows:
            identifier = _id(row.get("id", row.get("deviceId")))
            if not identifier or identifier in seen:
                duplicate = True
                continue
            seen[identifier] = " ".join(
                str(row.get("label") or row.get("name") or "").split()
            )[:80]

        reported = page.get("total", page.get("totalDevices"))
        try:
            if reported is not None and not isinstance(reported, bool):
                parsed = int(reported)
                if parsed < 0 or (total is not None and parsed != total):
                    duplicate = True
                else:
                    total = parsed
        except (ValueError, TypeError):
            pass

        has_more = page.get("hasMore")
        # Completeness must have explicit pagination confirmation and stable
        # cardinality: absent IDs are still scoped to this MCP tool route.
        if has_more is False:
            complete = (not duplicate and total is not None
                        and len(seen) == total)
            break
        if has_more is not True:
            complete = (not duplicate and total is not None
                        and len(seen) == total and page_count == 1)
            break
        next_offset = page.get("nextOffset")
        try:
            proposed = int(next_offset)
        except (TypeError, ValueError):
            break
        if proposed <= offset or proposed > offset + page_size:
            break
        offset = proposed

    matches = sorted(missing.intersection(seen), key=int)
    unresolved = missing.difference(seen)
    return {
        "status": ("complete" if complete else
                   "partial" if page_count else status),
        "source": "hub_read_devices/hub_list_devices",
        "pageCount": page_count,
        "rowsReturned": len(seen),
        "reportedTotal": total,
        "boundedSeconds": budget_seconds,
        "elapsedMs": round((time.monotonic() - started) * 1000),
        "candidateIdsAbsentFromContext": len(missing),
        "foundInSecondarySource": len(matches),
        "unresolvedCandidateIds": len(unresolved),
        "presentExamples": [
            {"id": identifier, "name": seen[identifier]} for identifier in matches[:6]
        ],
        "unresolvedExamples": sorted(unresolved, key=int)[:5],
        "ownershipVerified": False,
        "hubWideCensusVerified": False,
    }


__all__ = ["context_absent_candidates", "probe_secondary_device_inventory"]
