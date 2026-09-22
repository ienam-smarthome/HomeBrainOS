from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_timeline import causal_log_windows  # noqa: E402
from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from final_answer_coordinator import _synthesis_instruction  # noqa: E402
from mcp_agent_orchestrator import (  # noqa: E402
    _is_broad_device_inventory_call,
    _normalize_causal_log_call,
)


def _dehumidifier_evidence() -> list[dict]:
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": "Dehumidifier 2",
            "room": "Dehumidifier",
            "attribute": "switch",
            "temporalAnalysis": {
                "intervalCount": 1,
                "observedIntervals": [{
                    "start": "2026-09-22T22:07:37.107+0100",
                    "end": "2026-09-22T22:38:13.489+0100",
                    "startNatural": "10:07 pm on Tuesday 22 September 2026",
                    "endNatural": "10:38 pm on Tuesday 22 September 2026",
                    "duration": "31m",
                    "durationSeconds": 1836,
                }],
            },
        },
    }]


def test_causal_log_window_converts_hub_offset_to_utc() -> None:
    windows = causal_log_windows(_dehumidifier_evidence())

    assert windows == [{
        "timelineId": "T1",
        "subjectStart": "2026-09-22T22:07:37.107000+01:00",
        "since": "2026-09-22T21:07:27.107000Z",
        "until": "2026-09-22T21:07:47.107000Z",
    }]


def test_causal_log_call_overrides_model_authored_wrong_utc_window() -> None:
    arguments = {
        "tool": "hub_get_logs",
        "args": {
            "tool": "hub_get_logs",
            "since": "2026-09-22T22:00:00Z",
            "limit": 100,
        },
    }

    normalized = _normalize_causal_log_call(
        "hub_read_diagnostics",
        arguments,
        _dehumidifier_evidence(),
    )

    assert normalized["args"]["since"] == "2026-09-22T21:07:27.107000Z"
    assert normalized["args"]["until"] == "2026-09-22T21:07:47.107000Z"
    assert normalized["args"]["limit"] == 100
    assert normalized["args"]["tool"] == "hub_get_logs"


def test_causal_broad_inventory_guard_blocks_only_unscoped_device_lists() -> None:
    assert _is_broad_device_inventory_call(
        "hub_manage_devices",
        {"tool": "hub_list_devices"},
    ) is True
    assert _is_broad_device_inventory_call(
        "hub_read_devices",
        {"tool": "hub_list_devices", "args": {}},
    ) is True
    assert _is_broad_device_inventory_call(
        "hub_read_devices",
        {
            "tool": "hub_list_devices",
            "args": {"labelFilter": "Dehumidifier 2"},
        },
    ) is False


def test_final_causal_instruction_forbids_configuration_only_trigger_claim() -> None:
    instruction = _synthesis_instruction("Why did Dehumidifier 2 turn on?")

    assert "configuration alone" in instruction
    assert "must never be described as the most likely trigger" in instruction
    assert "execution/log provenance" in instruction


def test_evidence_ledger_marks_app_config_as_navigation_not_execution_proof() -> None:
    evidence = [
        *_dehumidifier_evidence(),
        {
            "tool": "hub_read_apps_code",
            "sub_tool": "hub_get_app_config",
            "success": True,
            "evidence_kind": "tool_result",
            "summary": "Humidity Controller app configuration",
        },
    ]

    ledger = build_current_turn_evidence_ledger(evidence)

    assert ledger is not None
    assert "hub_get_app_config" in ledger
    assert "CONFIGURATION/NAVIGATION ONLY" in ledger
    assert "not execution proof" in ledger
