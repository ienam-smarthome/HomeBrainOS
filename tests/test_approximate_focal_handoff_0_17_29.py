"""0.17.29: approximately 17:14:05 must match the unique observed 17:14:04.380.

Fail closed on exact timestamps, unrelated days, and competing nearby OFFs.
No real hub, journal database, devices or network calls are used.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from causal_timeline import explicitly_focused_event_rows
from causal_transition_provenance import focal_closed_transition
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_metrics import RequestMetrics
from test_independent_transition_provenance_0_17_15 import _records
from test_exact_focal_boundary_0_17_23 import (
    _Catalog, _Evidence, _Executor, _MCP,
    OLD, rows_with_later_off,
)


def test_approximate_clock_selects_actual_off_boundary_not_newer_off():
    rows = rows_with_later_off()
    prompt = (
        "Investigate why Example Room Light switched OFF at approximately "
        "08:18:24 on 12 October 2026. Read-only."
    )
    chosen = focal_closed_transition(rows, prompt, resolved_device_id="7840")
    assert chosen is not None
    assert chosen["end"] == OLD
    assert chosen["offStateEvent"]["producedBy"]["id"] == "7790"
    assert len(explicitly_focused_event_rows(rows, prompt)) == 1


def test_exact_seconds_remain_strict_and_outside_tolerance_stays_unresolved():
    rows = rows_with_later_off()
    assert focal_closed_transition(
        rows, "Investigate why Example Room Light switched OFF at "
        "08:18:24 on 12 October 2026", resolved_device_id="7840",
    ) is None
    assert focal_closed_transition(
        rows, "Investigate why Example Room Light switched OFF at "
        "approximately 08:18:27 on 12 October 2026",
        resolved_device_id="7840",
    ) is None


def test_approximate_clock_fails_closed_for_wrong_date_or_competing_events():
    rows = rows_with_later_off()
    assert focal_closed_transition(
        rows, "Why did Example Room Light switch OFF around "
        "08:18:24 on 11 October 2026?", resolved_device_id="7840",
    ) is None
    ambiguous = copy.deepcopy(rows)
    intervals = ambiguous[0]["details"]["temporalAnalysis"]["observedIntervals"]
    intervals.append({
        "start": "2026-10-12T08:18:24.050+0100",
        "end": "2026-10-12T08:18:25.010+0100",
        "durationSeconds": 1,
    })
    assert focal_closed_transition(
        ambiguous, "Why did Example Room Light switch OFF at "
        "approximately 08:18:24 on 12 October 2026?",
        resolved_device_id="7840",
    ) is None


def test_live_bedroom_1_clock_17_14_05_resolves_17_14_04_380():
    rows = _records()
    details = rows[0]["details"]
    interval = details["temporalAnalysis"]["observedIntervals"][-1]
    old_end = interval["end"]
    interval["end"] = "2026-10-12T17:14:04.380+0100"
    interval["start"] = "2026-10-12T17:10:15.452+0100"
    for event in details.get("boundaryEvents") or []:
        if event.get("date") == old_end and event.get("value") == "off":
            event["date"] = interval["end"]
    subject = focal_closed_transition(
        rows,
        "Investigate why Example Room Light switched OFF at "
        "approximately 17:14:05 on 12 October 2026. "
        "Check the Historical Journal first. Read-only.",
        resolved_device_id="7840",
    )
    assert subject is not None
    assert subject["end"] == "2026-10-12T17:14:04.380+0100"
    assert subject["offStateEvent"]["producedBy"]["id"] == "7790"


@pytest.mark.asyncio
async def test_approximate_focal_off_is_handed_to_secondary_sensor_investigation():
    rows = rows_with_later_off()
    selected = []

    async def no_extra_off(**kwargs):
        return None

    async def secondary(**kwargs):
        selected.append(kwargs["boundary_match"])

    host = SimpleNamespace(
        causal_subject_prefetch_enabled=True,
        mcp=_MCP(),
        executor=_Executor(rows),
        evidence=_Evidence(rows),
        _collect_focal_off_provenance=no_extra_off,
        _collect_reporting_source_secondary_correlation=secondary,
    )
    question = (
        "Investigate thoroughly why Example Room Light switched OFF at "
        "approximately 08:18:24 on 12 October 2026. "
        "Check the Historical Journal first; correlate motion and app evidence. "
        "Read-only."
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await UnifiedMCPAgent._prefetch_explicit_causal_subject(
            host, question, catalog=_Catalog(),
            completed_calls=set(), messages=[],
        )
    finally:
        metrics.reset(token)
    assert result[0] == "sufficient"
    assert len(selected) == 1
    assert selected[0]["stateBoundary"] == OLD
    assert selected[0]["producer"]["id"] == "7790"
