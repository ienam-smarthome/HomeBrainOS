"""Q1 source-saturated telemetry answer and Groovy app ID scope safeguards.

Use synthetic Hubitat receipts only; no network/MCP/driver/device writes.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai/rootfs/app"
sys.path.insert(0, str(ROOT))

from telemetry_completion_policy import (  # noqa: E402
    ready_for_bounded_telemetry_answer,
    ready_after_bounded_telemetry_read,
)
from evidence_source_scope import source_app_scope_error  # noqa: E402


QUESTION = "Why does Sample Socket report MQTT connected when its health is offline?"


def scoped_history(*, target="7103", label="Sample Socket",
                   status="offline", mqtt="connected",
                   age="162325", lastseen="Mon Oct 12 01:30:01 BST 2026"):
    rows = [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "timestamp": "2026-11-04T15:16:40.747838+00:00",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": label}},
            "summary": "1 targeted device candidates",
            "details": {"reportedDeviceState": {
                "deviceId": target, "label": label,
                "observedAt": "2026-11-04T15:16:40.747647+00:00",
                "reportedAttributes": {
                    "healthStatus": status,
                    "mqttStatus": mqtt,
                    "lastSeen": lastseen,
                    "dataAgeSeconds": age,
                },
                "source": "targeted-hubitat-device-state",
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False, "effect": "read",
            "timestamp": "2026-11-04T15:16:45.871294+00:00",
            "arguments": {
                "tool": "hub_list_device_events",
                "args": {"deviceId": target, "hoursBack": 24, "limit": 20},
            },
            "summary": f"2 device events for '{label}'",
        },
        {
            "tool": "homebrain_device_history",
            "success": True, "mutates": False, "effect": "read",
            "timestamp": "2026-11-04T15:16:45.873768+00:00",
            "details": {
                "label": label, "hoursBack": 24,
                "observedEvents": [
                    {
                        "name": "deviceHealth", "value": "unknown",
                        "date": "2026-11-04T15:14:36.322+0000",
                        "producedBy": {
                            "id": target, "type": "device", "label": label,
                        },
                    },
                    {
                        "name": "mqttStatus", "value": "connected",
                        "date": "2026-11-03T18:04:42.850+0000",
                        "producedBy": {
                            "id": target, "type": "device", "label": label,
                        },
                    },
                ],
                "observedEventsTruncated": False,
                "analysisEventCount": 2,
                "sourceEventCount": 2,
                "historySourceIntegrityVerified": False,
            },
        },
    ]
    return rows


def logs(target="7103"):
    return {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "mutates": False, "effect": "read",
        "arguments": {
            "tool": "hub_get_logs", "args": {
                "deviceId": target, "limit": 100, "since": "24h",
            },
        },
        "summary": "object fields: mode, total, matched, entries",
    }


def test_contrasting_offline_and_mqtt_clock_conflict_allows_bounded_answer():
    rows = [*scoped_history(), logs()]
    assert ready_for_bounded_telemetry_answer(
        QUESTION, rows, domain="device_telemetry",
    ) is True


def test_no_history_or_scoped_logs_or_known_target_must_not_early_stop():
    all_rows = [*scoped_history(), logs()]
    for rows in (
        all_rows[:1],
        all_rows[:3],
        [*all_rows[:2], logs()],
        [*scoped_history(target="702"), logs("702")],
    ):
        assert ready_for_bounded_telemetry_answer(
            QUESTION, rows, domain="device_telemetry",
        ) is False


def test_no_early_stop_with_matching_or_absent_clock_evidence():
    for attrs in (
        {"age": str(566 * 3600)},
        {"age": "no data"},
        {"status": "healthy"},
        {"mqtt": "disconnected"},
    ):
        rows = [*scoped_history(**attrs), logs()]
        assert ready_for_bounded_telemetry_answer(
            QUESTION, rows, domain="device_telemetry",
        ) is False


def test_no_scope_leak_into_other_domains_or_explicit_whole_home():
    rows = [*scoped_history(), logs()]
    assert not ready_for_bounded_telemetry_answer(
        QUESTION, rows, domain="existing_rule_verification"
    )
    assert not ready_for_bounded_telemetry_answer(
        "Compare MQTT connectivity across all devices in the hub.",
        rows, domain="device_telemetry",
    )


def test_optional_failed_source_does_not_force_further_model_rounds():
    prior = scoped_history()
    after = [*prior, logs(), {
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "success": False, "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_get_app_config",
                      "args": {"appId": "9999"}},
    }]
    assert ready_after_bounded_telemetry_read(
        QUESTION, after, domain="device_telemetry",
        receipt_count_before_round=len(prior),
        had_tool_actions=True, round_has_mutation=False,
        round_tool_failure=True,
    ) is True


def test_no_new_good_read_no_saturation_even_after_source_errors():
    rows = [*scoped_history(), logs()]
    assert not ready_after_bounded_telemetry_read(
        QUESTION, rows, domain="device_telemetry",
        receipt_count_before_round=len(rows),
        had_tool_actions=True, round_has_mutation=False,
        round_tool_failure=True,
    )
    assert not ready_after_bounded_telemetry_read(
        QUESTION, rows, domain="device_telemetry",
        receipt_count_before_round=len(rows) - 1,
        had_tool_actions=True, round_has_mutation=True,
        round_tool_failure=False,
    )


def test_device_id_cannot_be_passed_as_groovy_app_id():
    evidence = scoped_history()
    args = {"appId": "7103", "symbols": ["healthStatus"]}
    msg = source_app_scope_error(
        "homebrain_read_groovy_source", args, evidence, QUESTION
    )
    assert msg and "device ID" in msg and "app" in msg


def test_device_id_cannot_be_used_as_app_config_target():
    args = {"tool": "hub_get_app_config",
            "args": {"appId": "7103", "includeSettings": False}}
    msg = source_app_scope_error(
        "hub_read_apps_code", args, scoped_history(), QUESTION
    )
    assert msg and "device ID" in msg


def test_verified_dependent_app_link_can_legitimately_share_number():
    evidence = scoped_history()
    evidence.append({
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_list_device_dependents",
        "success": True, "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_list_device_dependents",
                      "args": {"deviceId": "7103"}},
        "details": {
            "verifiedDeviceTargetLinks": True,
            "appsUsing": [{"appId": "7103"}],
        },
    })
    assert source_app_scope_error(
        "hub_read_apps_code",
        {"tool": "hub_get_app_config",
         "args": {"appId": "7103"}},
        evidence, QUESTION,
    ) is None


def test_distinct_app_id_is_not_blocked_by_device_id_collision_guard():
    rows = scoped_history()
    assert source_app_scope_error(
        "hub_read_apps_code",
        {"tool": "hub_get_app_config", "args": {"appId": "4012"}},
        rows, QUESTION,
    ) is None
    assert source_app_scope_error(
        "homebrain_read_groovy_source",
        {"appId": "4012"}, rows, QUESTION,
    ) is None


def test_not_yet_resolved_scope_does_not_block_regular_app_reads():
    assert source_app_scope_error(
        "hub_read_apps_code",
        {"tool": "hub_get_app_config", "args": {"appId": "7103"}},
        [], QUESTION,
    ) is None
