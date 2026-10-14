"""Source-based completeness contracts. All fixture calls are read-only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] /
           "hubitat-mcp-ai" / "rootfs" / "app")
)

from general_evidence_completion import (  # noqa: E402
    EVIDENCE_KINDS, assess_task_source_coverage,
)
from general_task_engine import GeneralTaskPlan  # noqa: E402


def receipt(tool, *, arguments=None, sub_tool=None, success=True, effect="read"):
    return {
        "tool": tool, "sub_tool": sub_tool,
        "arguments": arguments or {},
        "success": success, "effect": effect, "mutates": False,
    }


def test_telemetry_needs_distinct_sources_beyond_room_listing():
    needed = ("device_state", "device_history", "device_logs")
    sources = [
        receipt("hub_read_rooms", sub_tool="hub_get_room", arguments={
            "tool": "hub_get_room", "args": {"room": "Bedroom 3"},
        }),
    ]
    coverage = assess_task_source_coverage(needed, sources)
    assert coverage.missing == needed
    assert coverage.checked == ()
    assert not coverage.sources_checked
    assert "not checked" in coverage.retry_instruction()
    sources.extend([
        receipt("hub_read_devices", sub_tool="hub_get_device",
                arguments={"tool": "hub_get_device",
                           "args": {"deviceId": "7103"}}),
        receipt("hub_read_devices", sub_tool="hub_list_device_events",
                arguments={"tool": "hub_list_device_events",
                           "args": {"deviceId": "7103"}}),
        receipt("hub_manage_logs", sub_tool="hub_get_logs",
                arguments={"tool": "hub_get_logs",
                           "args": {"deviceId": "7103", "limit": 100}}),
    ])
    coverage = assess_task_source_coverage(needed, sources)
    assert coverage.sources_checked
    assert coverage.missing == ()
    assert coverage.checked == needed
    assert "not establish" in coverage.to_dict()["note"]


def test_catalog_discovery_identity_and_failed_reads_are_not_device_evidence():
    sources = [
        receipt("hub_search_tools", arguments={"query": "device health"}),
        receipt("homebrain_resolve_device", arguments={"name": "Bedroom 3 Mesh"}),
        receipt("hub_read_devices", sub_tool="hub_list_devices",
                arguments={"tool": "hub_list_devices", "args": {
                    "labelFilter": "Bedroom 3 Mesh",
                    "detailed": False,
                }}),
        receipt("hub_read_devices", sub_tool="hub_get_device",
                success=False, arguments={"tool": "hub_get_device",
                                          "args": {"deviceId": "7103"}}),
    ]
    assert assess_task_source_coverage(
        ("device_state", "device_history"), sources,
    ).missing == ("device_state", "device_history")


def test_broad_logs_and_nested_invalid_device_log_envelopes_do_not_count():
    sources = [
        receipt("hub_read_diagnostics", sub_tool="hub_get_logs",
                arguments={"tool": "hub_get_logs",
                           "args": {"level": "warn"}}),
        receipt("hub_manage_logs", sub_tool="hub_get_logs",
                arguments={"tool": "hub_get_logs", "args": {
                    "args": {"deviceId": "7103"},
                    "tool": "hub_get_logs",
                }}),
    ]
    assert assess_task_source_coverage(("device_logs",), sources).missing == (
        "device_logs",
    )


def test_read_source_receipt_can_be_checked_even_with_zero_log_rows():
    sources = [receipt("hub_read_diagnostics", sub_tool="hub_get_logs",
                       arguments={"tool": "hub_get_logs",
                                  "args": {"appId": "4019", "limit": 50}})]
    result = assess_task_source_coverage(("app_logs",), sources)
    assert result.sources_checked
    assert "historic" in result.to_dict()["note"]


def test_mutations_cannot_satisfy_read_source_requirements():
    r = receipt("hub_get_device", arguments={"deviceId": "1"})
    r["effect"] = "sensitive_write"
    assert assess_task_source_coverage(("device_state",), [r]).missing


def test_model_required_evidence_kind_is_validated():
    raw = {
        "version": "1", "domain": "diagnostics", "operation": "investigate",
        "objective": "Diagnose room telemetry",
        "skills": ["diagnostics"], "capabilityQueries": ["device events"],
        "evidenceGoals": ["Determine freshness"],
        "requiredEvidenceKinds": ["device_state", "device_history",
                                  "delete_everything", "device_state"],
    }
    plan = GeneralTaskPlan.from_model(json.dumps(raw))
    assert plan is not None
    assert plan.required_evidence_kinds == ("device_state", "device_history")
    assert set(plan.required_evidence_kinds) <= EVIDENCE_KINDS
