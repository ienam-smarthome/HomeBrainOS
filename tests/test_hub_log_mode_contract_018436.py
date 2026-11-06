"""MCP log temporal contract: avoid invalid scoped stats/actions requests.

Upstream hub_get_logs modes `apps` / `devices` are runtime statistics, not historic
app/device messages. Time bounds are permitted only in `past` / event modes.
Synthetic tests do not claim anything about actual Hubitat retention.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

import mcp_agent_orchestrator as orchestrator  # noqa: E402

SINCE = "2026-11-05T16:00:00Z"
UNTIL = "2026-11-05T17:00:00Z"


def gateway(mode, **kwargs):
    return {"tool": "hub_get_logs", "args": {"mode": mode, **kwargs}}


def test_reject_historical_date_filters_for_all_nontemporal_tabs():
    for mode in ("apps", "devices", "hubActions", "scheduledJobs",
                 "runningJobs", "mcp", "status"):
        args = gateway(mode, since=SINCE, until=UNTIL, limit=100)
        reason = orchestrator._log_mode_window_rejection(
            "hub_read_diagnostics", args
        )
        assert reason is not None
        assert "do not accept since/until" in reason
        assert "mode='past'" in reason
        if mode in ("apps", "devices"):
            assert "current runtime statistics" in reason


def test_historical_past_and_hub_events_remain_allowed():
    for mode in ("past", "hubEvents", "locationEvents"):
        assert orchestrator._log_mode_window_rejection(
            "hub_read_diagnostics",
            gateway(mode, since=SINCE, until=UNTIL)
        ) is None
    assert orchestrator._log_mode_window_rejection(
        "hub_get_logs", {"mode": "past", "appId": "4151",
                         "since": SINCE, "until": UNTIL}
    ) is None
    assert orchestrator._log_mode_window_rejection(
        "hub_get_logs", {"mode": ["past", "apps"],
                         "since": SINCE, "until": UNTIL}
    ) is not None


def test_current_runtime_tabs_remain_available_without_time_filter():
    for mode in ("apps", "devices", "hubActions"):
        assert orchestrator._log_mode_window_rejection(
            "hub_read_diagnostics", gateway(mode, limit=20)
        ) is None
    assert orchestrator._log_mode_window_rejection(
        "hub_read_devices", {"tool": "hub_list_device_events",
                             "args": {"since": SINCE, "until": UNTIL}}
    ) is None


def test_causal_window_normalization_only_targets_temporal_tabs(monkeypatch):
    monkeypatch.setattr(orchestrator, "causal_log_windows", lambda *_a, **_k: [
        {"since": SINCE, "until": UNTIL}
    ])
    monkeypatch.setattr(
        orchestrator, "explicitly_focused_event_rows", lambda *_a, **_k: []
    )

    for mode in ("apps", "devices", "hubActions", "scheduledJobs"):
        args = gateway(mode)
        actual = orchestrator._normalize_causal_log_call(
            "hub_read_diagnostics", args, [], original_user="Why did the hub restart?"
        )
        assert actual == args  # Host cannot inject invalid since/until.
    for mode in ("past", "hubEvents", "locationEvents"):
        actual = orchestrator._normalize_causal_log_call(
            "hub_read_diagnostics", gateway(mode), [],
            original_user="Why did the hub restart?"
        )
        assert actual["args"]["since"] == SINCE
        assert actual["args"]["until"] == UNTIL
    direct = orchestrator._normalize_causal_log_call(
        "hub_get_logs", {"mode": "past"}, [],
        original_user="Why did the hub restart?"
    )
    assert direct["since"] == SINCE and direct["until"] == UNTIL


def test_unknown_future_mode_uses_live_mcp_contract():
    # Do not hardcode a denial for newly added or renamed upstream modes.
    assert orchestrator._log_mode_window_rejection(
        "hub_read_diagnostics",
        gateway("hypotheticalNewMode", since=SINCE, until=UNTIL)
    ) is None
