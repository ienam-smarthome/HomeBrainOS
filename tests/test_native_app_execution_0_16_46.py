from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_native_logs import (  # noqa: E402
    correlate_native_log_boundaries,
    native_log_app_execution_sufficient,
    native_log_causal_provenance_sufficient,
    render_strong_native_provenance_answer,
)


def subject_evidence() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": "Microwave (MQTT)",
            "attribute": "switch",
            "room": "Appliances",
            "temporalAnalysis": {
                "intervalCount": 0,
                "observedIntervals": [],
                "unboundedActiveInterval": True,
                "openActiveInterval": True,
                "openActiveStart": "2026-09-25T19:51:24.133+0100",
                "openActiveStartNatural": "7:51 pm on Friday 25 September 2026",
            },
            "boundaryEvents": [{
                "name": "switch",
                "value": "on",
                "date": "2026-09-25T19:51:24.133+0100",
                "isStateChange": True,
            }],
        },
    }


def log_evidence() -> dict:
    return {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "evidence_kind": "authoritative_native_log_history",
        "details": {
            "logs": [
                {
                    "date": "2026-09-25 19:51:24.135",
                    "level": "INFO",
                    "message": (
                        "dev|7124|Microwave (MQTT)|Microwave (MQTT): Switch → on"
                    ),
                },
                {
                    "date": "2026-09-25 19:51:24.044",
                    "level": "INFO",
                    "message": (
                        "app|3090|Appliance: Microwave ON/OFF|"
                        "Action: On: Microwave (MQTT)"
                    ),
                },
                {
                    "date": "2026-09-25 19:51:24.034",
                    "level": "INFO",
                    "message": (
                        "app|3090|Appliance: Microwave ON/OFF|"
                        "Triggered: Microwave Door contact reported *changed*"
                    ),
                },
                {
                    "date": "2026-09-25 19:51:24.021",
                    "level": "INFO",
                    "message": (
                        "app|3090|Appliance: Microwave ON/OFF|"
                        "Event: Microwave Door contact closed"
                    ),
                },
            ]
        },
    }


def test_rule_machine_action_is_direct_app_execution_provenance() -> None:
    rows = correlate_native_log_boundaries([subject_evidence(), log_evidence()])

    assert len(rows) == 1
    row = rows[0]
    assert row["boundaryRole"] == "start"
    assert row["command"]["sourceLabel"] == "Appliance: Microwave ON/OFF"
    assert row["command"]["provenanceKind"] == "app-execution"
    assert row["command"]["commandToStateMs"] == 89.0
    assert row["controller"] is None
    assert [item["message"] for item in row["appTriggerContext"]] == [
        "Triggered: Microwave Door contact reported *changed*",
        "Event: Microwave Door contact closed",
    ]
    assert native_log_app_execution_sufficient(rows) is True
    assert native_log_causal_provenance_sufficient(rows) is True


def test_direct_app_execution_renders_without_model_or_configuration_downgrade() -> None:
    answer = render_strong_native_provenance_answer(
        [subject_evidence(), log_evidence()]
    )

    assert answer is not None
    assert "**Cause:** Appliance: Microwave ON/OFF issued ON for Microwave (MQTT)" in answer
    assert "about 89 ms before the device reported ON" in answer
    assert "**Trigger chain:**" in answer
    assert "Microwave Door contact closed" in answer
    assert "Triggered: Microwave Door contact reported *changed*" in answer
    assert "direct app execution logging" in answer
    assert "configuration" in answer


def test_unrelated_app_action_does_not_match_subject() -> None:
    evidence = log_evidence()
    evidence["details"]["logs"][1]["message"] = (
        "app|3090|Appliance: Microwave ON/OFF|Action: On: Kettle"
    )
    rows = correlate_native_log_boundaries([subject_evidence(), evidence])

    assert rows == []
