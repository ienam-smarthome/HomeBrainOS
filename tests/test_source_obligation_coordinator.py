"""General source obligation coalescing with no additional permissions or reads."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))
from source_obligation_coordinator import select_issuing_app_log_obligation
from test_method_command_source_contract import evidence, QUESTION


def test_typed_command_attested_issuer_yields_one_read_only_window():
    result = select_issuing_app_log_obligation(QUESTION, evidence())
    assert result == {
        "kind": "typed-command-app-decision", "tool": "hub_get_logs",
        "args": {
            "appId": "2710", "since": "2026-11-01T22:20:02Z",
            "until": "2026-11-01T22:40:02Z", "limit": 60,
        },
    }


def test_prior_attempted_app_log_even_failed_prevents_retries():
    receipts = evidence()
    plan = select_issuing_app_log_obligation(QUESTION, receipts)
    receipts.append({
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": False,
        "effect": "read",
        "arguments": {"tool": "hub_get_logs", "args": dict(plan["args"])},
    })
    assert select_issuing_app_log_obligation(QUESTION, receipts) is None


def test_unrelated_or_unverified_issuer_never_authorizes_read():
    assert select_issuing_app_log_obligation(
        "What is the thermostat temperature?", evidence()
    ) is None
    rows = evidence()
    rows[0]["details"]["observedEvents"][1]["producedBy"] = {
        "type": "device", "id": "2710",
    }
    assert select_issuing_app_log_obligation(QUESTION, rows) is None
    rows = evidence()
    rows[0]["success"] = False
    assert select_issuing_app_log_obligation(QUESTION, rows) is None


def test_specific_historical_incident_is_preferred_over_generic_app_logs():
    historic = {
        "tool": "hub_get_logs",
        "args": {
            "appId": "9981", "since": "2026-10-01T14:00:00Z",
            "until": "2026-10-01T14:20:00Z", "limit": 100,
        },
        "reason": "recorded app issuer; verified incident window",
        "deviceId": "7012",
    }
    method = {
        "tool": "hub_get_logs",
        "args": {
            "appId": "9981", "since": "2026-10-01T13:50:00Z",
            "until": "2026-10-01T14:10:00Z", "limit": 60,
        },
    }
    with (
        patch("source_obligation_coordinator.pending_provenance_app_log_read",
              return_value=historic) as hp,
        patch("source_obligation_coordinator.pending_command_app_decision_log",
              return_value=method) as mp,
    ):
        selected = select_issuing_app_log_obligation(
            "Investigate this recorded issue at 14:10", [],
        )
    assert selected["kind"] == "incident-command-provenance"
    assert selected["args"] == historic["args"]
    assert hp.call_count == 1 and mp.call_count == 0


def test_hist_empty_falls_back_to_generic_command_source_once():
    with (
        patch("source_obligation_coordinator.pending_provenance_app_log_read",
              return_value=None) as hp,
        patch("source_obligation_coordinator.pending_command_app_decision_log",
              return_value={"tool": "hub_get_logs",
                            "args": {"appId": "7331", "since": "2026-11-01T00:00:00Z",
                                     "until": "2026-11-01T00:20:00Z"}}) as mp,
    ):
        selected = select_issuing_app_log_obligation("Investigate event", [])
    assert selected["kind"] == "typed-command-app-decision"
    assert hp.call_count == 1 and mp.call_count == 1
