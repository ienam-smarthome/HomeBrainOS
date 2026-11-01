"""Stage 9.0: recent reported-switch chronology is NOT physical cycle proof."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_report_transitions import summarize_reported_transitions  # noqa: E402
from live_shadow_commands import project_command_shadow, read_plan  # noqa: E402
from webui import render_page  # noqa: E402


def sample():
    # Fictional dates/times/device IDs, not a copy of a live household trace.
    pairs = [
        ("12:10:00", "12:10:41"),
        ("12:16:00", "12:16:22"),
        ("12:17:00", "12:17:20"),
        ("12:25:00", "12:25:23"),
        ("12:26:00", "12:26:49"),
    ]
    states = []
    for begin, end in pairs:
        states.append({"kind": "reported_switch_state", "value": "on",
                       "source_reported_time_utc": "2026-02-12T"+begin+"+00:00"})
        states.append({"kind": "reported_switch_state", "value": "off",
                       "source_reported_time_utc": "2026-02-12T"+end+"+00:00"})
    states.append({"kind": "reported_switch_state", "value": "on",
                   "source_reported_time_utc": "2026-02-12T12:32:00+00:00"})
    return {
        "schema": "homebrain-stage85-command-shadow.v1",
        "status": "bounded_source_evidence",
        "events": states,
        "read_status": {"command-off": "successful_bounded_page",
                        "command-on": "successful_bounded_page",
                        "switch": "successful_bounded_page"},
        "read_diagnostics": {"switch": {"page_at_limit": False}},
    }


def test_recent_repeated_reports_are_not_physical_runtimes():
    result = summarize_reported_transitions(sample())
    assert result["status"] == "bounded_report_transition_review"
    assert result["reported_on_count"] == 6
    assert result["reported_off_count"] == 5
    assert len(result["report_intervals"]) == 5
    assert [x["reported_interval_seconds"] for x in result["report_intervals"]] == [
        41.0, 22.0, 20.0, 23.0, 49.0
    ]
    assert result["shortest_interval_seconds"] == 20
    assert result["longest_interval_seconds"] == 49
    assert result["median_interval_seconds"] == 23
    assert result["trailing_on_without_later_off_in_page"]
    assert result["unmatched_or_ambiguous_state_rows"] == 1
    joined = " ".join(result["findings"])
    assert "5 ordered ON-to-OFF pairs" in joined
    assert "does not establish that the device is still ON" in joined
    assert "no recorded commands" in joined
    assert result["physical_cycle_verified"] is False
    assert result["app_causation_verified"] is False
    assert result["complete_history_verified"] is False
    assert result["device_clock_authenticated"] is False
    assert result["production_publisher_approval"] is False
    assert result["additional_cloud_requests"] == result["additional_hubitat_reads"] == 0


def test_unmatched_duplicates_are_not_falsely_paired():
    s = sample()
    s["events"] = [
        {"kind": "reported_switch_state", "value": value,
         "source_reported_time_utc": "2026-02-12T"+stamp+"+00:00"}
        for stamp, value in [
            ("12:00:00","off"), ("12:01:00","on"), ("12:01:01","on"),
            ("12:01:10","off"), ("12:02:00","on"),
            ("12:02:10","off")
        ]
    ]
    r = summarize_reported_transitions(s)
    assert len(r["report_intervals"]) == 1
    assert r["report_intervals"][0]["reported_interval_seconds"] == 10
    assert r["unmatched_or_ambiguous_state_rows"] >= 3
    assert not r["physical_cycle_verified"]


def test_command_records_are_not_correlated_as_cause():
    s=sample()
    s["events"].append({
        "kind": "recorded_command", "command": "off",
        "recorded_issuer_app_id": "556",
        "source_reported_time_utc": "2026-02-12T12:10:40+00:00",
    })
    r = summarize_reported_transitions(s)
    assert r["reported_command_count"] == 1
    assert "temporal proximity alone" in " ".join(r["findings"])
    assert "556" not in str(r)
    assert not r["app_causation_verified"]


def test_no_reports_and_partial_data_preserve_uncertainty():
    s=sample()
    s["events"]=[]
    r=summarize_reported_transitions(s)
    assert r["report_intervals"] == []
    assert r["reported_on_count"] == 0
    assert r["physical_cycle_verified"] is False
    s["status"]="partial_or_failed_read"
    r=summarize_reported_transitions(s)
    assert r["status"]=="partial_source_evidence"
    assert r["report_intervals"]==[]


def test_existing_command_shadow_auto_adds_review_without_more_reads():
    plan=read_plan("123", "2026-02-12",
                   datetime(2026, 2, 13, tzinfo=timezone.utc))
    data={
        "command-off": [],
        "command-on": [],
        "switch": [
            {"name": "switch", "value": "on",
             "date": "2026-02-12T12:00:00Z", "deviceId": "123"},
            {"name": "switch", "value": "off",
             "date": "2026-02-12T12:00:20Z", "deviceId": "123"}
        ],
    }
    r=project_command_shadow(
        plan,
        [(operation,SimpleNamespace(
            data={"success": True, "events": data[operation]},
            is_error=False,
        )) for operation in plan["operations"]],
        read_at_utc="2026-02-13T00:00:00+00:00",
    )
    assert r["transition_review"]["status"] == "bounded_report_transition_review"
    assert len(r["transition_review"]["report_intervals"]) == 1
    assert r["transition_review"]["report_intervals"][0]["reported_interval_seconds"] == 20
    assert r["transition_review"]["additional_hubitat_reads"] == 0


def test_mobile_report_precedes_diagnostic_detail():
    ui=render_page("HomeBrainOS","0.18.324")
    assert "Recent switching investigation · reported events only" in ui
    assert "Reported ON→OFF intervals (not proof of physical runtime)" in ui
    assert ui.index("Recent switching investigation · reported events only") < ui.index(
        "--- Detailed bounded Hubitat history audit ---"
    )
    assert "data.transition_review" in ui


def test_production_publisher_still_isolated():
    for name in ("causal_claim_publication.py","mcp_agent_orchestrator.py",
                 "tool_executor.py","final_answer_coordinator.py"):
        assert "live_shadow_report_transitions" not in (APP/name).read_text()
