"""An explicit historical OFF must never inherit the latest OFF provenance.

Uses multiple OFF states on the same day so a newest-first result cannot pass.
"""
from __future__ import annotations
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from causal_command_provenance import (
    boundary_producer_transition_kind, boundary_producer_transition_match,
    boundary_producer_transition_sufficient, correlate_boundary_producers,
)
from causal_transition_provenance import focal_closed_transition
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_metrics import RequestMetrics
from test_independent_transition_provenance_0_17_15 import _records


OLD = "2026-10-12T08:18:23.830+0100"
NEW = "2026-10-12T15:58:11.531+0100"
QUESTION = (
    "Investigate thoroughly why Example Room Light switched OFF at 08:18:23 "
    "on 12 October 2026. Read-only."
)


def rows_with_later_off():
    rows = copy.deepcopy(_records())
    history = rows[0]["details"]
    history["temporalAnalysis"]["observedIntervals"].append({
        "start": "2026-10-12T15:46:25.448+0100",
        "end": NEW, "durationSeconds": 706,
    })
    history["boundaryEvents"].insert(0, {
        "name": "switch", "value": "off", "date": NEW, "type": "physical",
        "producedBy": {"label": "Another Bridge", "id": "200", "type": "device"},
    })
    return rows


def test_exact_boundary_producer_overrides_newest_off():
    rows = rows_with_later_off()
    matches = correlate_boundary_producers(rows)
    assert boundary_producer_transition_match(matches, "off")["stateBoundary"].startswith("2026-10-12T15:58:11")
    focused = focal_closed_transition(rows, QUESTION, resolved_device_id="7840")
    assert focused and focused["end"] == OLD
    selected = boundary_producer_transition_match(
        matches, "off", requested_boundary=focused["end"],
    )
    assert selected["stateBoundary"].startswith("2026-10-12T08:18:23")
    assert selected["producer"]["id"] == "7790"
    assert boundary_producer_transition_kind(
        matches, "off", requested_boundary=OLD,
    ) == "reporting_source"
    assert boundary_producer_transition_sufficient(
        matches, "off", requested_boundary=OLD,
    )


def test_ambiguous_or_nonexistent_explicit_boundary_fails_closed():
    rows = rows_with_later_off()
    matches = correlate_boundary_producers(rows)
    assert boundary_producer_transition_match(
        matches, "off", requested_boundary="2026-10-12T08:18:24+01:00",
    ) is None
    assert not boundary_producer_transition_sufficient(
        matches, "off", requested_boundary="2026-10-12T08:18:24+01:00",
    )
    assert focal_closed_transition(
        rows, "Why did Example Room Light switch off at 08:19:23 on 12 October?"
    ) is None


class _MCP:
    async def get_device_identities(self):
        return [{
            "id": "7840", "name": "Example Room Light",
            "label": "Example Room Light", "room": "Example Room",
            "capabilities": ["Switch"], "attributes": {"switch": "off"},
            "commands": ["on", "off"],
        }]


class _Executor:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, *args, **kwargs):
        return SimpleNamespace(
            success=True, content="observed state history",
            result=SimpleNamespace(data=self.rows[0]["details"]),
        )


class _Evidence:
    def __init__(self, rows):
        self.rows = rows

    def receipts(self):
        return self.rows


class _Catalog:
    def declared_tool(self, name):
        return object()


@pytest.mark.asyncio
async def test_prefetch_passes_user_selected_old_off_to_secondary_retrieval():
    rows = rows_with_later_off()
    received = []
    async def no_extra_off(**kwargs):
        pass
    async def secondary(**kwargs):
        received.append(kwargs["boundary_match"])
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
    assert len(received) == 1
    assert received[0]["stateBoundary"].startswith("2026-10-12T08:18:23")


@pytest.mark.asyncio
async def test_missing_requested_off_never_substitutes_newest():
    rows = rows_with_later_off()
    received = []
    async def no_extra_off(**kwargs):
        pass
    async def secondary(**kwargs):
        received.append(kwargs)
    host = SimpleNamespace(
        causal_subject_prefetch_enabled=True, mcp=_MCP(),
        executor=_Executor(rows), evidence=_Evidence(rows),
        _collect_focal_off_provenance=no_extra_off,
        _collect_reporting_source_secondary_correlation=secondary,
    )
    query = "Investigate why Example Room Light switched OFF at 08:19:23 on 12 October 2026. Read-only."
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        messages = []
        result = await UnifiedMCPAgent._prefetch_explicit_causal_subject(
            host, query, catalog=_Catalog(), completed_calls=set(),
            messages=messages,
        )
    finally:
        metrics.reset(token)
    assert result[0] == "partial"
    assert received == []
    assert any("Do not substitute a newer OFF event" in str(m.get("content")) for m in messages)
