"""Offline source-reuse contract: only equivalent native location pages.

The original fan trace contained both a successful native location page and
a later local wrapper request for the same 48h/20-event page. This synthetic
replay checks *read selection*, not model accuracy or latency on live systems.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))
from source_read_reuse_policy import duplicate_location_projection_reason


def native(*, hours=48, limit=20, success=True, scoped=False):
    args = {"hoursBack": hours, "limit": limit}
    if scoped:
        args["deviceId"] = "9911"
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": success, "mutates": False, "effect": "read",
        "evidence_kind": "authoritative_location_event_history",
        "arguments": {"tool": "hub_list_device_events", "args": args},
        "summary": "20 location events",
    }


def reason(rows, args=None, *, tool="homebrain_location_events"):
    return duplicate_location_projection_reason(
        "Investigate why a scheduled automation changed state.",
        rows, tool, args or {"hours_back": 48},
    )


def test_native_location_page_is_reused_for_equivalent_local_wrapper():
    assert reason([native()]) == "native-location-page-already-read"
    assert reason([native()], {"hours_back": 24, "limit": 10})
    assert reason([native()], {"hours_back": 48, "limit": 20})
    # A generic device read and one app log must still be possible.
    assert reason([native()], tool="homebrain_device_history") is None
    assert reason([native()], tool="hub_read_diagnostics") is None


def test_no_prior_or_failed_or_device_scoped_source_must_not_suppress():
    assert reason([]) is None
    assert reason([native(success=False)]) is None
    assert reason([native(scoped=True)]) is None
    assert reason([{**native(), "mutates": True}]) is None
    assert reason([{**native(), "effect": "write"}]) is None
    assert reason([native(hours=24)]) is None
    assert reason([native(limit=10)]) is None
    assert reason([native()], {"hours_back": 72}) is None
    assert reason([native()], {"hours_back": 48, "limit": 25}) is None


def test_filter_and_missing_window_are_not_assumed_equivalent():
    assert reason([native()], {"hours_back": 48, "attribute": "mode"}) is None
    assert reason([native()], {"hours_back": 48, "cursor": "next"}) is None
    assert reason([native()], {"hours_back": 0}) is None
    assert reason([native()], {"hours_back": "not-a-window"}) is None
    assert reason([native()], {"limit": 20}) is None
    assert reason([native()], {"hours_back": True}) is None


def test_native_attribute_or_pagination_is_a_distinct_source():
    base = native()
    for key, value in (
        ("attribute", "mode"), ("filter", {"name": "mode"}),
        ("cursor", "page2"), ("since", "2026-11-01T22:00:00Z"),
    ):
        row = native()
        row["arguments"]["args"][key] = value
        assert reason([row]) is None
    # Other source classes must never substitute for native location history.
    base["tool"] = "homebrain_device_history"
    assert reason([base]) is None
