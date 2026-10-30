"""V2 whole-hub question regression: no fake device resolution or Hubitat writes."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.semantic_plan import (
    SemanticPlan, parse_semantic_plan, inventory_profile,
)
from investigation_v2.system_diagnostics import format_system_diagnostics

TOKEN = "v2-diagnostic-test-token-123456789"
DEVICES = [{"id": "7103", "label": "Bedroom 3 Mesh"},
           {"id": "7828", "label": "Livingroom Light 2"}]


def _objective(mode="diagnostics", scope="all", **more):
    result = {"mode": mode, "scope": scope, "device_name": None,
              "room": None, "attribute": None, "operator": "none",
              "value": None, "aggregation": "list", "limit": 10}
    result.update(more)
    return result


def _source_snapshot(log_available=True):
    return {
        "status": "attention", "checked_at": "2026-10-28T14:30:00+00:00",
        "attention_count": 2, "severity_counts": {"critical": 0, "warning": 2},
        "thresholds": {"log_hours": 24},
        "sections": {
            "devices": {"total": 203},
            "automations": {"total": 165},
            "logs": {"available": log_available, "entries_checked": 80,
                     "checked_hours": 24},
        },
        "issues": [
            {"severity": "warning", "domain": "devices",
             "title": "Bedroom 3 Mesh", "detail": "No recent data"},
            {"severity": "warning", "domain": "logs",
             "title": "SenseCap D1 Settings",
             "detail": "HTTP 408 timeout reported by application"},
        ],
    }


def test_system_diagnostic_objective_is_model_selected_but_scope_limited():
    profile = inventory_profile(DEVICES)
    plan = parse_semantic_plan(_objective(), profile)
    assert plan.mode == "diagnostics"
    assert plan.scope == "all"
    assert plan.device_name is None
    for invalid in (
        _objective(scope="named", device_name="Bedroom 3 Mesh"),
        _objective(scope="all", room="Bedroom 3"),
        _objective(scope="all", operator="eq", value="error"),
        _objective(scope="all", attribute="switch"),
    ):
        with pytest.raises(ValueError):
            parse_semantic_plan(invalid, profile)


def test_issues_presented_with_bounded_sample_and_redacted_urls():
    snapshot = _source_snapshot()
    snapshot["issues"][1]["detail"] += " at http://192.168.1.1/?token=abc"
    result = format_system_diagnostics(snapshot)
    assert result["answer_mode"] == "semantic_system_diagnostics"
    assert "Bedroom 3 Mesh" in result["answer"]["text"]
    assert "SenseCap D1 Settings" in result["answer"]["text"]
    assert "bounded sample of 80" in result["answer"]["text"]
    assert "[URL redacted]" in result["answer"]["text"]
    assert "token=abc" not in result["answer"]["text"]
    assert result["system_audit"]["log_coverage_complete"] is False
    assert result["resolved_devices"] == []
    assert result["answer"]["root_cause_verified"] is False


def test_failed_log_gateway_is_reported_not_converted_to_no_errors():
    result = format_system_diagnostics(_source_snapshot(False))
    assert result["system_audit"]["log_available"] is False
    assert "log_source_unavailable" in result["answer"]["validation_issues"]
    assert "no assertion about the absence of errors" in result["answer"]["text"]

