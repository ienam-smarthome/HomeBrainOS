"""Evidence-qualified incident reporting even when a model's draft is withheld."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from hub_incident_ai import (  # noqa: E402
    fact_summary, incident_read_only_next_checks, publish_incident_analysis,
)
from hub_incident_trigger_evidence import (  # noqa: E402
    assess_hub_event_trigger, render_hub_event_findings,
)


def snapshot(first="2026-11-05T22:10:46.475+00:00",
             last="2026-11-05T22:40:46.475+00:00",
             focus="2026-11-05T22:25:46.475+00:00",
             memory=220.96):
    return {
        "focus_at": focus, "window_start": first, "window_end": last,
        "recorder": {
            "status": "partial_observations_not_proof_of_cause",
            "sample_count": 59 if memory is not None else 0,
            "failed_samples": 10 if memory is not None else 0,
            "memory_min": ({
                "value": memory, "recorded_at": focus, "basis": "external_probe",
            } if memory is not None else None),
            "cpu_load_max": None,
            "java_free_min": None,
            "startups": [{
                "occurred_at": "2026-11-05T22:33:16.070+00:00",
                "firmware": "2.5.3.118",
                "source": "hub_events_json_systemStart",
            }],
            "incidents": [],
        },
        "journal": {
            "status": "partial_recording", "event_count": 257,
            "app_log_count": 5, "app_log_apps": [
                {"app_id": "4290", "count": 4},
                {"app_id": "4151", "count": 1},
            ],
            "events_truncated": True,
            "gaps": [{"stream": "logs",
                      "started_at": "2026-11-05T22:27:10+00:00",
                      "ended_at": "2026-11-05T22:32:19+00:00"}],
        },
    }


def typed_events(*rows):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "supports_live_claim": True, "mutates": False,
        "details": {"observedEvents": list(rows), "observedEventsTruncated": False},
        "arguments": {"args": {
            "since": "2026-11-05T22:00:00Z",
            "until": "2026-11-05T23:00:00Z",
        }},
    }


def test_22_25_live_pattern_targeted_failure_and_generic_fallback_are_separate():
    original = snapshot()
    receipts = [
        typed_events(
            {"name": "update", "date": "2026-11-05T22:26:02.189+0000",
             "value": "2.5.3.118", "description": "Updated with build: 2.5.3.118"},
            {"name": "systemStart", "date": "2026-11-05T22:33:16.070+0000",
             "value": "2.5.3.118", "description": "System startup with build: 2.5.3.118"},
        ),
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": False, "mutates": False,
         "arguments": {"args": {"mode": "apps",
                                 "since": "2026-11-05T22:10:00Z",
                                 "until": "2026-11-05T22:40:00Z"}}},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "mutates": False,
         "arguments": {"args": {"since": "2026-11-05T22:10:00Z",
                                 "until": "2026-11-05T22:40:00Z",
                                 "limit": 100}}},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "mutates": False,
         "arguments": {"args": {"since": "30m", "limit": 100}}},
    ]
    assessed = assess_hub_event_trigger(original, receipts)
    assert assessed["restart_trigger"] == "firmware_update_recorded_before_startup"
    assert assessed["app_specific_log_attempts"] == 0
    assert assessed["app_runtime_stats_attempts"] == 1
    assert assessed["app_specific_logs"] == "not_verified"
    assert assessed["bounded_generic_log_reads"] == 1
    assert assessed["bounded_generic_log_read_successes"] == 1
    rendered = render_hub_event_findings(assessed)
    assert "App runtime statistics: 0/1" in rendered
    assert "bounded generic log query also succeeded" in rendered
    assert "does not independently verify app-specific" in rendered
    assert "memory reduction are not established" in rendered
    model_draft = (
        "The firmware update was responsible for the earlier 220.96 MB "
        "memory drop. Therefore the update caused the restart."
    )
    answer, validation = publish_incident_analysis(original, model_draft, receipts)
    assert validation == "draft_overclaim_withheld"
    assert model_draft not in answer
    assert "22:26:02 UTC" in answer
    assert "22:33:16 UTC" in answer
    assert "**Read-only next checks" in answer
    assert "past-mode query with appId" in answer
    assert "collection gaps" in answer
    assert "no proof" not in answer.lower() or "not proof" in answer.lower()


def test_16_52_reboot_warning_is_supported_but_its_culprit_is_not():
    case = snapshot(
        first="2026-11-05T16:37:15.774+00:00",
        last="2026-11-05T17:07:15.774+00:00",
        focus="2026-11-05T16:52:15.774+00:00",
        memory=None,
    )
    case["recorder"]["startups"] = [{
        "occurred_at": "2026-11-05T16:52:15.774+00:00",
        "firmware": "2.5.3.117",
        "source": "hub_events_json_systemStart",
    }]
    receipts = [
        typed_events(
            {"name": "lowMemory", "date": "2026-11-05T16:41:40.105+0000",
             "value": "lowMemory", "description":
                 "Hub memory is critically low, rebooting now"},
            {"name": "systemStart", "date": "2026-11-05T16:52:15.774+0000",
             "value": "2.5.3.117", "description":
                 "System startup with build: 2.5.3.117"},
        ),
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": False, "mutates": False,
         "arguments": {"args": {"mode": "apps",
                                 "since": "2026-11-05T16:00:00Z",
                                 "until": "2026-11-05T17:00:00Z"}}},
    ]
    assessment = assess_hub_event_trigger(case, receipts)
    assert assessment["restart_trigger"] == "hub_explicit_critical_low_memory_reboot"
    assert assessment["underlying_memory_cause"] == "unverified"
    assert assessment["bounded_generic_log_read_successes"] == 0
    model = ("A specific driver caused the memory exhaustion and the reboot."
             " The exact driver is certain.")
    answer, validation = publish_incident_analysis(case, model, receipts)
    assert validation == "draft_overclaim_withheld"
    assert model not in answer
    assert "explicitly reported critically low memory" in answer
    assert "which app or process" in answer
    assert "no external resource samples in this window" in answer.lower()
    assert "App-log coverage" in answer
    assert "Underlying memory/resource cause: UNVERIFIED" in answer
    assert "not proof" in fact_summary(case)


def test_missing_model_draft_still_gives_useful_read_only_checks():
    data = snapshot()
    assessment = assess_hub_event_trigger(data, [])
    checks = incident_read_only_next_checks(data, assessment)
    assert "authenticated, time-bounded Hub Events" in checks
    assert "collection gaps" in checks
    answer, status = publish_incident_analysis(data, "", [])
    assert status == "model_empty"
    assert "Read-only next checks" in answer
    assert "No usable AI interpretation" in answer


def test_successful_generic_log_does_not_upgrade_source_to_app_logs():
    case = snapshot()
    receipts = [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "mutates": False,
         "arguments": {"args": {"limit": 100,
                                 "since": "2026-11-05T22:10:00Z",
                                 "until": "2026-11-05T22:40:00Z"}}},
    ]
    a = assess_hub_event_trigger(case, receipts)
    assert a["bounded_generic_log_read_successes"] == 1
    assert a["app_specific_logs"] == "not_verified"
    assert "not independently established historical app-log" in render_hub_event_findings(a)


def test_failed_bounded_log_query_never_counts_as_a_success():
    case = snapshot()
    receipts = [
        {"sub_tool": "hub_get_logs", "success": False, "mutates": False,
         "arguments": {"args": {"since": "2026-11-05T22:10:00Z",
                                 "until": "2026-11-05T22:40:00Z"}}},
    ]
    a = assess_hub_event_trigger(case, receipts)
    assert a["bounded_generic_log_reads"] == 1
    assert a["bounded_generic_log_read_successes"] == 0
    assert a["app_specific_logs"] == "not_verified"


def test_typed_app_specific_log_status_requires_bounded_past_mode():
    case = snapshot()
    correct = {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "mutates": False,
        "arguments": {"args": {"mode": "past", "appId": "4151",
                                "since": "2026-11-05T22:10:00Z",
                                "until": "2026-11-05T22:40:00Z"}},
        "summary": "object fields: mode, total, matched, entries, count",
    }
    assessment = assess_hub_event_trigger(case, [correct])
    assert assessment["app_specific_log_attempts"] == 1
    assert assessment["app_specific_logs"] == "read_succeeded_coverage_unverified"
    assert assessment["app_runtime_stats_attempts"] == 0
    assert "past-log query returned successfully" in render_hub_event_findings(assessment)
    assert "complete historical" in render_hub_event_findings(assessment)
    # Positive API return never verifies matching historical message contents.
    failed = {**correct, "success": False}
    a2 = assess_hub_event_trigger(case, [failed])
    assert a2["app_specific_logs"] == "read_failed"
    assert "past-log query scoped to one app failed" in render_hub_event_findings(a2)
