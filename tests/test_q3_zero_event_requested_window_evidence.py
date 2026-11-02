"""Replay real zero-event source *shape* across generic device types.

This is a synthetic contract replay, not a model response or a live read. A
successful empty event page is evidence only for the returned bounded page,
not proof of zero physical activity, commands, or state changes elsewhere.
"""
from __future__ import annotations

from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from requested_event_window_evidence import render_requested_event_window_evidence

QUERY = (
    "Inspect Lounge Lamp over the last 20 minutes, ending at the hub current "
    "time. Count ON/OFF events; distinguish commands from state reports."
)


def empty_history(*, attribute="switch", source_count=0, analysis_count=0,
                  label="Lounge Lamp", at="2026-11-02T12:53:56.502226+00:00"):
    # Exact same receipt field shape as a successful no-event device-history
    # read: observedEvents is ABSENT, never inferred from a missing key alone.
    return {
        "tool": "homebrain_device_history", "timestamp": at,
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "deterministic_device_event_history",
        "arguments": {"attribute": attribute, "hours_back": 1,
                      "name": label},
        "details": {
            "label": label,
            "attribute": attribute,
            "hoursBack": 1,
            "timeWindow": None,
            "sourceEventCount": source_count,
            "analysisEventCount": analysis_count,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
        }
    }


def test_exact_zero_history_receipt_without_events_generates_window_packet():
    packet = render_requested_event_window_evidence(QUERY, [empty_history()])
    assert packet is not None
    assert "2026-11-02T12:33:56.502226+00:00" in packet
    assert "2026-11-02T12:53:56.502226+00:00" in packet
    assert "Returned switch events WITHIN the requested window: 0" in packet
    assert "Returned events BEFORE the requested window: 0" in packet
    assert "Source history integrity was NOT independently verified" in packet
    assert "not proof of no real detection" in packet
    assert "does NOT prove no automation command was sent elsewhere" in packet


def test_zero_event_motion_history_is_supported_not_device_specific():
    receipt = empty_history(attribute="motion", label="Utility Motion")
    packet = render_requested_event_window_evidence(
        "Show Utility Motion events during the past 30 minutes", [receipt]
    )
    assert "Returned motion events WITHIN the requested window: 0" in packet


def test_missing_and_nonzero_count_in_absent_events_cannot_mean_zero():
    bad = empty_history()
    bad["details"].pop("sourceEventCount")
    assert render_requested_event_window_evidence(QUERY, [bad]) is None
    for sc, ac in ((1, 1), (1, 0), (0, 1), (False, 0), (0, "0")):
        assert render_requested_event_window_evidence(
            QUERY, [empty_history(source_count=sc, analysis_count=ac)]
        ) is None


def test_redacted_empty_list_but_nonzero_source_does_not_mean_zero():
    data = empty_history(source_count=1, analysis_count=1)
    data["details"]["observedEvents"] = []
    assert render_requested_event_window_evidence(QUERY, [data]) is None


def test_explicit_empty_list_and_zero_counts_are_valid():
    data = empty_history()
    data["details"]["observedEvents"] = []
    packet = render_requested_event_window_evidence(QUERY, [data])
    assert "Returned switch events WITHIN the requested window: 0" in packet


def test_failure_mutation_unverified_source_and_unknown_attribute_denied():
    receipt = empty_history()
    for change in (
        {"success": False},
        {"effect": "write"},
        {"evidence_kind": "tool_result"},
    ):
        assert render_requested_event_window_evidence(
            QUERY, [{**receipt, **change}]
        ) is None
    assert render_requested_event_window_evidence(
        QUERY, [empty_history(attribute="privateCredential")]
    ) is None


def test_two_different_targets_must_not_be_joined():
    assert render_requested_event_window_evidence(
        QUERY, [empty_history(), empty_history(label="Other Sensor")]
    ) is None


def test_final_synthesis_packet_counter_exists_without_more_model_rounds():
    final = (APP / "final_answer_coordinator.py").read_text()
    assert 'increment_active_metric("requested_event_window_packet")' in final
    assert "rolling_evidence = render_requested_event_window_evidence(" in final
    assert final.index("rolling_evidence = render_requested_event_window_evidence(") < (
        final.index("response = await self._chat(final_messages, [])")
    )
