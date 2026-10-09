"""Bounded targeted identity probe for context-absent scheduler candidates.

A targeted MCP read can establish additional entity *presence*, never scheduler
ownership or deletion. Strictly no attributes, commands, configuration or writes.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

_TIME_BUDGET = 4.5
_MAX_TARGETS = 6
_MAX_CONCURRENT = 2


def _id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return ""
    item = str(value).strip()
    return str(int(item)) if item.isascii() and item.isdecimal() and int(item) > 0 else ""


def _device(data: Any) -> dict[str, Any] | None:
    current = data
    for _ in range(5):
        if not isinstance(current, dict):
            return None
        identifier = _id(current.get("id", current.get("deviceId")))
        if identifier:
            return current
        current = next(
            (current.get(k) for k in ("device", "result", "data", "output", "content")
             if isinstance(current.get(k), dict)), None
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
    max_targets: int = _MAX_TARGETS,
    max_concurrent: int = _MAX_CONCURRENT,
    **_legacy_options: Any,
) -> dict[str, Any] | None:
    """Target a small sample of context-absent IDs with hub_get_device.

    The v0.16.144 identity-list fallback timed out before returning its first
    page on the live hub. A single-device read is the narrowest available MCP
    operation and avoids enumerating hundreds of devices merely to corroborate
    scheduler-key candidates.

    A successful response counts only when its numeric returned ID equals the
    requested candidate. Failure/not-found/timeout all remain unresolved:
    none is proof that a device was deleted. The total stage has one 4.5-second
    deadline and at most two reads in flight.
    """

    missing = context_absent_candidates(candidate_ids, context)
    if not missing:
        return None

    budget_seconds = min(4.5, max(0.01, float(budget_seconds)))
    max_targets = min(6, max(1, int(max_targets)))
    max_concurrent = min(2, max(1, int(max_concurrent)))
    targets = sorted(missing, key=int)[:max_targets]
    started = time.monotonic()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def read_one(identifier: str) -> tuple[str, dict[str, Any] | None, str]:
        arguments = {"tool": "hub_get_device", "args": {"deviceId": identifier}}
        read_started = time.monotonic()
        success = False
        row: dict[str, Any] | None = None
        status = "unresolved"
        try:
            async with semaphore:
                remaining = budget_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    return identifier, None, "timed_out"
                response = await asyncio.wait_for(
                    executor.execute(
                        "hub_read_devices", arguments, supports_live_claim=True,
                        evidence_kind="host_planned_scheduler_targeted_identity",
                        record_evidence=False,
                    ),
                    timeout=remaining,
                )
            if bool(getattr(response, "success", False)):
                value = getattr(getattr(response, "result", None), "data", None)
                candidate = _device(value)
                if candidate is not None and _id(
                    candidate.get("id", candidate.get("deviceId"))
                ) == identifier:
                    row = candidate
                    success = True
                    status = "present"
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
                summary=("Targeted scheduler candidate identity confirmed"
                         if success else
                         "Targeted scheduler candidate identity unresolved"),
                supports_live_claim=success,
                evidence_kind="host_planned_scheduler_targeted_identity",
                mutates=False, effect="read",
            )
        return identifier, row, status

    tasks = [asyncio.create_task(read_one(identifier)) for identifier in targets]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks), timeout=budget_seconds + 0.05
        )
    except asyncio.TimeoutError:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        results = [
            task.result() for task in tasks
            if task.done() and not task.cancelled() and task.exception() is None
        ]

    by_id = {identifier: (row, status) for identifier, row, status in results}
    present = {
        identifier: row for identifier, (row, status) in by_id.items()
        if status == "present" and row is not None
    }
    timed_out = sum(1 for _identifier, (_row, status) in by_id.items()
                    if status == "timed_out")
    attempted = len(by_id)
    unattempted = len(missing) - attempted
    unresolved = len(missing) - len(present)

    if timed_out:
        stage_status = "timed_out"
    elif attempted < len(targets):
        stage_status = "partial"
    elif present:
        stage_status = "sampled"
    else:
        stage_status = "unresolved"

    return {
        "status": stage_status,
        "source": "hub_read_devices/hub_get_device",
        "probeMode": "targeted-sample",
        "boundedSeconds": budget_seconds,
        "elapsedMs": round((time.monotonic() - started) * 1000),
        "candidateIdsAbsentFromContext": len(missing),
        "targetLimit": max_targets,
        "attemptedCandidateIds": attempted,
        "foundInSecondarySource": len(present),
        "unresolvedCandidateIds": unresolved,
        "unattemptedCandidateIds": unattempted,
        "presentExamples": [
            {
                "id": identifier,
                "name": " ".join(
                    str(row.get("label") or row.get("name") or "").split()
                )[:80],
            }
            for identifier, row in sorted(present.items(), key=lambda item: int(item[0]))
        ],
        "probedExamples": targets,
        "ownershipVerified": False,
        "hubWideCensusVerified": False,
    }


__all__ = ["context_absent_candidates", "probe_secondary_device_inventory"]
