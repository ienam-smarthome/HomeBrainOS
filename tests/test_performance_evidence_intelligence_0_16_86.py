from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_diagnostic_evidence_gate import (  # noqa: E402
    classify_adaptive_diagnostics,
    render_diagnostic_evidence_gate,
)
from performance_diagnostic_format_guard import (  # noqa: E402
    guard_format_independent_performance_diagnostics,
)
from performance_host_plan import select_adaptive_log_targets  # noqa: E402


def _nest_scoped_evidence() -> list[dict]:
    return [
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
                "logCount": 72,
                "logs": [
                    {
                        "date": "2026-10-01 17:04:01.101",
                        "level": "WARN",
                        "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|method runQ of child device Google Nest Hub - [Google Nest Hub] ran for 166,621ms",
                    },
                    {
                        "date": "2026-10-01 17:03:40.754",
                        "level": "WARN",
                        "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|method runQ of child device Google Nest Hub - [Google Nest Hub] ran for 186,138ms",
                    },
                    {
                        "date": "2026-10-01 16:16:26.661",
                        "level": "WARN",
                        "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|method runQ of child device Google Nest Hub - [Google Nest Hub] ran for 401,699ms",
                    },
                    {
                        "date": "2026-10-01 17:01:02.499",
                        "level": "INFO",
                        "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|Google Nest Hub - [Google Nest Hub] volume is 13",
                    },
                ],
                "hostDerivedTiming": {
                    "cadence": [
                        {
                            "source": "Google Nest Hub - [Google Nest Hub]",
                            "sourceRef": "dev|7934",
                            "signal": "volume",
                            "observationCount": 16,
                            "timingKind": "irregular_intervals",
                            "intervalCount": 15,
                            "medianIntervalSeconds": 62.434,
                            "minIntervalSeconds": 0.016,
                            "maxIntervalSeconds": 7287.876,
                            "regularCadence": False,
                        }
                    ]
                },
            },
        }
    ]


def test_comma_formatted_hubitat_runq_warns_are_diagnostic_long_calls() -> None:
    targets = classify_adaptive_diagnostics(_nest_scoped_evidence())
    assert len(targets) == 1
    target = targets[0]
    assert target["scopeId"] == "7934"
    assert target["classification"] == "diagnostic_signal"
    assert target["longCallMs"] == [166621, 186138, 401699]

    gate = render_diagnostic_evidence_gate(_nest_scoped_evidence())
    assert "classification=diagnostic_signal" in gate
    assert "very long call 166621 ms" in gate
    assert "very long call 186138 ms" in gate
    assert "very long call 401699 ms" in gate


def test_plain_integer_long_call_format_remains_supported() -> None:
    evidence = _nest_scoped_evidence()
    evidence[0]["details"]["logs"] = [
        {
            "date": "2026-10-01 17:04:01.101",
            "level": "WARN",
            "message": "dev|7934|Google Nest Hub - [Google Nest Hub]|method runQ completed in 5000ms",
        }
    ]
    evidence[0]["details"]["logCount"] = 1
    target = classify_adaptive_diagnostics(evidence)[0]
    assert target["classification"] == "diagnostic_signal"
    assert target["longCallMs"] == [5000]


def test_format_guard_does_not_turn_real_runq_warns_into_non_diagnostic_evidence() -> None:
    message = """### Diagnostic Hypotheses & Recommendations

**1. Google Nest Hub Resource Usage**
* **Finding:** Scoped logs contain runQ calls lasting over two minutes.
* **Hypothesis:** The target-scoped diagnostic read returned 72 non-diagnostic log observation(s) and did not establish a mechanism for this measured outlier; the mechanism remains unresolved.
"""
    corrected, changed = guard_format_independent_performance_diagnostics(
        message,
        _nest_scoped_evidence(),
    )
    assert changed is True
    assert "72 non-diagnostic" not in corrected
    assert "explicit diagnostic signal(s)" in corrected
    assert "very long call 166621 ms" in corrected
    assert "do not prove the exact implementation mechanism" in corrected


def test_near_threshold_busy_leader_can_beat_isolated_slow_average_app() -> None:
    performance_data = {
        "deviceStats": [],
        "appStats": [
            {
                "id": "4129",
                "name": "SenseCap D1 Settings",
                "pctBusy": 18.8,
                "pctTotal": 0.992,
                "averageMs": 200.0,
            },
            {
                "id": "3919",
                "name": "Isolated Slow Average App",
                "pctBusy": 1.0,
                "pctTotal": 0.1,
                "averageMs": 3000.0,
            },
        ],
    }
    assert select_adaptive_log_targets(performance_data) == [
        {"kind": "app", "id": "4129", "name": "SenseCap D1 Settings"}
    ]


def test_quiet_rows_still_do_not_expand_adaptive_diagnostics() -> None:
    performance_data = {
        "deviceStats": [
            {"id": "1", "name": "Quiet Device", "pctBusy": 5.0, "pctTotal": 0.2, "averageMs": 100.0}
        ],
        "appStats": [
            {"id": "2", "name": "Quiet App", "pctBusy": 7.0, "pctTotal": 0.4, "averageMs": 150.0}
        ],
    }
    assert select_adaptive_log_targets(performance_data) == []


def test_adaptive_target_count_remains_bounded_to_one_device_and_one_app() -> None:
    performance_data = {
        "deviceStats": [
            {"id": "7934", "name": "Google Nest Hub", "pctBusy": 81.2, "pctTotal": 23.747, "averageMs": 1125.28},
            {"id": "7486", "name": "LG webOS TV", "pctBusy": 2.0, "pctTotal": 0.5, "averageMs": 3052.1},
        ],
        "appStats": [
            {"id": "4129", "name": "SenseCap D1 Settings", "pctBusy": 18.8, "pctTotal": 0.992, "averageMs": 200.0},
            {"id": "3919", "name": "Isolated Slow Average App", "pctBusy": 1.0, "pctTotal": 0.1, "averageMs": 3000.0},
        ],
    }
    targets = select_adaptive_log_targets(performance_data)
    assert targets == [
        {"kind": "device", "id": "7934", "name": "Google Nest Hub"},
        {"kind": "app", "id": "4129", "name": "SenseCap D1 Settings"},
    ]
