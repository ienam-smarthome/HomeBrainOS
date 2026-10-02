from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from agent_prompt_policy import build_system_prompt
from health_audit_service import _device_findings

NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)
OLD = "2026-09-30T20:00:00+00:00"


def _find(devices):
    return _device_findings(devices, low_battery_threshold=20, now=NOW)


def test_age_only_temperature_device_is_neutral_not_stale_or_offline():
    section, issues = _find([
        {
            "id": "1",
            "label": "Quiet temperature sensor",
            "capabilities": ["TemperatureMeasurement"],
            "attributes": {"temperature": 21.2, "lastActivity": OLD},
        }
    ])

    assert section["no_recent_activity_count"] == 1
    assert section["expected_update_overdue_count"] == 0
    assert section["offline_count"] == 0
    assert not [
        item
        for item in issues
        if item["category"] in {"device-stale", "device-long-stale", "device-offline"}
    ]


def test_virtual_flag_contact_and_remote_are_quiet_not_failed():
    devices = [
        {
            "id": "v",
            "label": "Backup Hub Active",
            "attributes": {"switch": "off", "lastActivity": OLD},
        },
        {
            "id": "c",
            "label": "Front Door Contact",
            "capabilities": ["ContactSensor"],
            "attributes": {"contact": "closed", "lastActivity": OLD},
        },
        {
            "id": "r",
            "label": "Ikea remote",
            "capabilities": ["PushableButton"],
            "attributes": {"lastActivity": OLD},
        },
    ]

    section, issues = _find(devices)
    assert section["no_recent_activity_count"] == 3
    assert section["offline_count"] == 0
    assert not [item for item in issues if item["category"].startswith("device-stale")]


def test_direct_offline_evidence_remains_actionable():
    section, issues = _find([
        {
            "id": "2",
            "label": "Offline plug",
            "attributes": {"healthStatus": "offline", "lastActivity": OLD},
        }
    ])

    assert section["offline_count"] == 1
    assert any(item["category"] == "device-offline" for item in issues)


def test_explicit_freshness_contract_can_be_overdue():
    section, issues = _find([
        {
            "id": "3",
            "label": "Contract sensor",
            "attributes": {
                "temperature": 20.0,
                "lastActivity": OLD,
                "expectedUpdateSeconds": 3600,
            },
        }
    ])

    assert section["expected_update_overdue_count"] == 1
    assert any(item["category"] == "device-update-overdue" for item in issues)


def test_old_cached_on_state_is_unconfirmed_not_live_truth():
    section, issues = _find([
        {
            "id": "4",
            "label": "Old TV",
            "attributes": {"switch": "on", "lastActivity": OLD},
        }
    ])

    assert section["unconfirmed_cached_state_count"] == 1
    assert section["unconfirmed_cached_state"][0]["live_status_confirmed"] is False
    assert not [item for item in issues if item["category"] == "device-offline"]


def test_timestamp_cluster_is_observation_not_interruption_issue():
    devices = [
        {
            "id": str(index),
            "label": f"MQTT {index}",
            "driverName": "MQTT",
            "attributes": {
                "power": index,
                "lastActivity": f"2026-09-30T20:0{index}:00+00:00",
            },
        }
        for index in range(3)
    ]

    section, issues = _find(devices)
    assert section["activity_cluster_count"] == 1
    assert section["activity_clusters"][0]["common_failure_proven"] is False
    assert not [item for item in issues if item["category"] == "device-stale-cluster"]


def test_prompt_forbids_promoting_old_activity_into_failure():
    prompt = build_system_prompt(
        "Device manifest omitted or unavailable.",
        now=NOW,
    )

    assert "DEVICE FRESHNESS SEMANTICS" in prompt
    assert "proves only that no recent activity was observed" in prompt
    assert "do NOT establish a reporting cadence" in prompt
    assert "live status cannot be confirmed" in prompt
    assert "Do not infer a shared integration" in prompt
