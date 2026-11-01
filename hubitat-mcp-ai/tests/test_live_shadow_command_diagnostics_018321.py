"""Stage 8.6 Command Shadow source-coverage diagnostics on mocked evidence.

Diagnostics do not infer source completeness, source-clock validity or absence.
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_commands import read_plan, project_command_shadow  # noqa: E402
from webui import render_page  # noqa: E402


NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
PLAN = read_plan("123", "2026-10-12", NOW)


def result(events=None, *, data=None, failed=False):
    return SimpleNamespace(
        data=({"success": not failed, "events": events}
              if data is None else data),
        is_error=failed,
    )


def compare(*sources):
    return project_command_shadow(
        PLAN,
        list(zip(PLAN["operations"], sources)),
        read_at_utc=NOW.isoformat(),
    )


def row(name, at, *, device="123", value="off"):
    return {
        "name": name, "date": at, "deviceId": device, "value": value,
        "description": "PRIVATE COMMAND LOG",
        "producedBy": {"appId": "556", "name": "PRIVATE AUTOMATION NAME"},
    }


def test_all_successful_empty_upstream_pages_do_not_establish_absence():
    answer = compare(result([]), result([]), result([]))
    assert answer["status"] == "bounded_sources_no_day_matches"
    assert answer["returned_event_count"] == 0
    assert all(x["source_rows"] == 0 for x in answer["read_diagnostics"].values())
    assert "All three upstream pages returned zero" in answer["zero_match_explanation"]
    assert answer["complete_history_proven"] is False
    assert answer["source_clock_authenticated"] is False
    assert answer["causal_attribution_verified"] is False
    assert answer["publisher_approval"] is False


def test_success_without_events_array_is_unusable_not_empty():
    answer = compare(
        result(data={"success": True, "message": "PRIVATE SECRET"}),
        result([]), result([]),
    )
    assert answer["status"] == "partial_or_failed_read"
    assert answer["read_status"]["command-off"] == "unusable_event_payload"
    assert answer["read_diagnostics"]["command-off"]["source_rows"] is None
    assert "PRIVATE SECRET" not in str(answer)


def test_rows_later_than_day_reveal_coverage_limit_not_proven_absence():
    later = "2026-10-28T11:04:00Z"
    answer = compare(
        result([row("command-off", later)]),
        result([]),
        result([row("switch", later)]),
    )
    assert answer["status"] == "bounded_sources_no_day_matches"
    assert answer["read_diagnostics"]["command-off"]["dated_after_day"] == 1
    assert answer["read_diagnostics"]["switch"]["dated_after_day"] == 1
    assert "outside the selected day" in answer["zero_match_explanation"]
    assert not answer["complete_history_proven"]


def test_filter_mismatches_are_exposed_as_counts_without_private_strings():
    answer = compare(
        result([
            row("command-off", "2026-10-11T22:00:00Z"),
            row("command-off", "2026-10-13T02:00:00Z"),
            row("command-off", "not-a-date"),
            row("command-off", "2026-10-12T10:00:00Z", device="999"),
            row("switch", "2026-10-12T10:00:00Z"),
        ]),
        result([]),
        result([
            row("switch", "2026-10-12T12:00:00Z", value="untrusted secret"),
            row("switch", "2026-10-12T13:00:00Z", value="on"),
        ]),
    )
    detail = answer["read_diagnostics"]["command-off"]
    assert detail["source_rows"] == 5
    assert detail["dated_before_day"] == 1
    assert detail["dated_after_day"] == 1
    assert detail["discarded_missing_or_invalid_time"] == 1
    assert detail["discarded_wrong_device"] == 1
    assert detail["discarded_wrong_type"] == 1
    assert answer["read_diagnostics"]["switch"]["discarded_unrecognised_value"] == 1
    assert answer["returned_event_count"] == 1
    assert answer["events"][0]["value"] == "on"
    for forbidden in ("PRIVATE", "999", "untrusted secret", "SECRET"):
        assert forbidden not in str(answer)


def test_full_page_not_treated_as_history_completeness():
    page = [row("command-off", "2026-10-28T11:00:00Z")] * 50
    answer = compare(result(page), result([]), result([]))
    d = answer["read_diagnostics"]["command-off"]
    assert d["source_rows"] == 50
    assert d["page_at_limit"] is True
    assert answer["complete_history_proven"] is False


def test_read_failures_are_distinguished_from_empty_pages():
    answer = compare(result([], failed=True), result([]), result([]))
    assert answer["status"] == "partial_or_failed_read"
    assert answer["read_status"]["command-off"] == "upstream_read_failed"
    assert answer["zero_match_explanation"].startswith("One or more upstream")


def test_phone_explains_no_matching_events_and_bounded_source_page():
    ui = render_page("HomeBrainOS", "0.18.321")
    for phrase in (
        "Source page coverage diagnostics",
        "Why this test returned no evidence:",
        "returned rows",
        "matching day",
        "page at 50-record cap",
        "Visible target-row date range:",
    ):
        assert phrase in ui
