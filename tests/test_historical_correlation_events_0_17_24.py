"""Regression: historical OFF can outlive the newest boundaryEvents subset.

Reproduces the 12 October 2026 HomeBrain 0.17.23 evidence shape:
the requested 08:18 OFF is in temporal intervals and correlationEvents,
but not in the three newest boundaryEvents / observedEvents rows.
No actual Hubitat device is contacted.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from causal_command_provenance import (
    boundary_producer_transition_match, correlate_boundary_producers,
)
from causal_transition_provenance import focal_closed_transition
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_metrics import RequestMetrics
from test_exact_focal_boundary_0_17_23 import (
    _Catalog, _Evidence, _Executor, _MCP,
    OLD, NEW, QUESTION, rows_with_later_off,
)


def truncated_recent_boundary_rows():
    rows = copy.deepcopy(rows_with_later_off())
    details = rows[0]["details"]
    old_off = next(
        row for row in details["boundaryEvents"]
        if row.get("date") == OLD and row.get("value") == "off"
    )
    latest_off = next(
        row for row in details["boundaryEvents"]
        if row.get("date") == NEW and row.get("value") == "off"
    )
    latest_on = {
        "name": "switch", "value": "on",
        "date": "2026-10-12T15:46:25.448+0100",
        "type": "physical",
        "producedBy": {"label": "Another Bridge", "id": "200", "type": "device"},
    }
    midday_off = {
        "name": "switch", "value": "off",
        "date": "2026-10-12T14:54:57.698+0100",
        "type": "physical",
        "producedBy": {"label": "Another Bridge", "id": "200", "type": "device"},
    }
    details["temporalAnalysis"]["observedIntervals"].append({
        "start": "2026-10-12T14:48:29.691+0100",
        "end": midday_off["date"], "durationSeconds": 388,
    })

    # Matches the live trace's failure mode; the older historical event is
    # intentionally absent from the newest-three presentation subsets.
    details["boundaryEvents"] = [latest_off, latest_on, midday_off]
    details["observedEvents"] = [latest_off, latest_on, midday_off]
    details["correlationEvents"] = [
        latest_off, latest_on, midday_off, old_off,
    ]
    return rows


def test_exact_historical_off_uses_correlations_when_recent_boundaries_truncated():
    rows = truncated_recent_boundary_rows()
    details = rows[0]["details"]
    assert all(row["date"] != OLD for row in details["boundaryEvents"])
    assert any(row["date"] == OLD for row in details["correlationEvents"])

    focus = focal_closed_transition(rows, QUESTION, resolved_device_id="7840")
    assert focus and focus["end"] == OLD
    matched = boundary_producer_transition_match(
        correlate_boundary_producers(rows), "off",
        requested_boundary=focus["end"],
    )
    assert matched is not None
    assert matched["stateBoundary"].startswith("2026-10-12T08:18:23")
    assert matched["producer"]["id"] == "7790"
    assert matched["producer"]["type"] == "device"
    # The later OFF still works for broad, untimed investigations.
    newest = boundary_producer_transition_match(
        correlate_boundary_producers(rows), "off",
    )
    assert newest is not None
    assert newest["stateBoundary"].startswith("2026-10-12T15:58:11")


@pytest.mark.asyncio
async def test_actual_prefetch_hands_old_off_to_secondary_when_recent_subset_truncated():
    rows = truncated_recent_boundary_rows()
    captured = []

    async def no_extra_off(**kwargs):
        return None

    async def secondary(**kwargs):
        captured.append(kwargs["boundary_match"])

    host = SimpleNamespace(
        causal_subject_prefetch_enabled=True,
        mcp=_MCP(), executor=_Executor(rows), evidence=_Evidence(rows),
        _collect_focal_off_provenance=no_extra_off,
        _collect_reporting_source_secondary_correlation=secondary,
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await UnifiedMCPAgent._prefetch_explicit_causal_subject(
            host, QUESTION, catalog=_Catalog(),
            completed_calls=set(), messages=[],
        )
    finally:
        metrics.reset(token)

    assert result[0] == "sufficient"
    assert len(captured) == 1
    assert captured[0]["stateBoundary"].startswith("2026-10-12T08:18:23")
    assert captured[0]["producer"]["id"] == "7790"


def test_correlation_fallback_requires_same_subject_observed_interval_and_switch():
    rows = truncated_recent_boundary_rows()
    details = rows[0]["details"]
    # Neither wrong sensor metadata nor an OFF without a subject interval
    # may invent producer attribution at a different timestamp.
    details["correlationEvents"].extend([
        {"name": "motion", "value": "off", "date": OLD,
         "producedBy": {"label": "Unrelated sensor", "id": "999"}},
        {"name": "switch", "value": "off",
         "date": "2026-10-12T13:00:00.000+0100",
         "producedBy": {"label": "Unrelated controller", "id": "998"}},
    ])
    matches = correlate_boundary_producers(rows)
    selected = boundary_producer_transition_match(
        matches, "off", requested_boundary=OLD,
    )
    assert selected is not None and selected["producer"]["id"] == "7790"
    assert boundary_producer_transition_match(
        matches, "off", requested_boundary="2026-10-12T13:00:00+01:00",
    ) is None

    # An unrelated subject's history cannot overwrite the original subject.
    rows.append({
        "tool": "homebrain_device_history", "success": True,
        "details": {
            "label": "Other Room Light",
            "correlationEvents": [{
                "name": "switch", "value": "off", "date": OLD,
                "producedBy": {"label": "Other room bridge", "id": "997"},
            }],
            "boundaryEvents": [],
        },
    })
    selected = boundary_producer_transition_match(
        correlate_boundary_producers(rows), "off", requested_boundary=OLD,
    )
    assert selected is not None and selected["producer"]["id"] == "7790"
