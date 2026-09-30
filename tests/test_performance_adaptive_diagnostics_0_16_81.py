from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_evidence_first import build_performance_synthesis_contract  # noqa: E402
from performance_host_plan import select_adaptive_log_targets  # noqa: E402


def test_selects_strongest_device_and_app_only() -> None:
    payload = {
        "deviceStats": [
            {
                "id": "7934",
                "name": "Google Nest Hub",
                "pctBusy": 76.6,
                "pctTotal": 24.434,
                "averageMs": 1564.44,
            },
            {
                "id": "7001",
                "name": "LG webOS TV",
                "pctBusy": 2.0,
                "pctTotal": 1.0,
                "averageMs": 2918.24,
            },
        ],
        "appStats": [
            {
                "id": "1471",
                "name": "00 Google Calendar Notifier",
                "pctBusy": 22.7,
                "pctTotal": 1.506,
                "averageMs": 1270.0,
            },
            {
                "id": "999",
                "name": "Device Health Monitor",
                "pctBusy": 1.0,
                "pctTotal": 0.2,
                "averageMs": 4230.0,
            },
        ],
    }

    assert select_adaptive_log_targets(payload) == [
        {"kind": "device", "id": "7934", "name": "Google Nest Hub"},
        {"kind": "app", "id": "1471", "name": "00 Google Calendar Notifier"},
    ]


def test_normal_performance_rows_do_not_trigger_adaptive_reads() -> None:
    payload = {
        "deviceStats": [
            {"id": "1", "name": "A", "pctBusy": 4.0, "pctTotal": 1.0, "averageMs": 90.0}
        ],
        "appStats": [
            {"id": "2", "name": "B", "pctBusy": 8.0, "pctTotal": 2.0, "averageMs": 300.0}
        ],
    }
    assert select_adaptive_log_targets(payload) == []


def test_adaptive_log_rows_reach_evidence_first_contract_as_hypothesis_evidence() -> None:
    evidence = [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {
                "tool": "hub_get_logs",
                "args": {"deviceId": "7934", "since": "6h", "limit": 120},
            },
            "details": {
                "logs": [
                    {
                        "date": "2026-09-30 20:01:00.000",
                        "level": "WARN",
                        "message": "dev|7934|Google Nest Hub|runQ completed in 120001 ms",
                    },
                    {
                        "date": "2026-09-30 20:03:00.000",
                        "level": "WARN",
                        "message": "dev|7934|Google Nest Hub|setVolume completed in 187000 ms",
                    },
                ]
            },
        }
    ]

    contract = build_performance_synthesis_contract(evidence)

    assert "HOST ADAPTIVE DIAGNOSTIC EVIDENCE" in contract
    assert "deviceId=7934" in contract
    assert "runQ completed in 120001 ms" in contract
    assert "setVolume completed in 187000 ms" in contract
    assert "DIAGNOSTIC HYPOTHESIS" in contract
    assert "what remains unproven" in contract
    assert "verification step" in contract


def test_retrieval_thresholds_are_not_described_as_health_thresholds() -> None:
    evidence = [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {
                "tool": "hub_get_logs",
                "args": {"appId": "1471", "since": "6h", "limit": 120},
            },
            "details": {"logs": []},
        }
    ]
    contract = build_performance_synthesis_contract(evidence)
    assert "retrieval-policy thresholds" in contract
    assert "not health/severity labels" in contract
