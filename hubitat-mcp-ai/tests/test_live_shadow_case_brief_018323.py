"""Stage 8.8: evidence-first historical summaries from safe, bounded archive data."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_journal import project_shadow_history  # noqa: E402
from live_shadow_case_brief import summarize_bounded_archive  # noqa: E402
from webui import render_page  # noqa: E402

START = "2026-02-02T00:00:00+00:00"
END = "2026-03-02T00:00:00+00:00"
SOURCE = "2026-02-12T00:30:01+00:00"
RECEIPT = "2026-03-01T11:44:28+00:00"


def archive_row(attribute="switch", value="off", origin="hubitat-mcp-state",
                source_time=SOURCE):
    return {
        "stream": "events", "device_id": "123", "app_id": "",
        "attribute": attribute, "value": value, "source": origin,
        "source_time": source_time, "observed_at": SOURCE,
        "received_at": RECEIPT, "timestamp_basis": "source",
        "display_name": "PRIVATE APP NAME", "message": "Bearer SECRET",
    }


def summary(rows, gaps=None):
    projection = project_shadow_history(
        "123", {"events": rows, "gaps": gaps or [], "offset": 0, "has_more": False},
        window_start=START, window_end=END, read_at=END,
    )
    return projection, summarize_bounded_archive(projection)


def test_six_delayed_native_state_rows_have_direct_no_cause_summary():
    p, brief = summary([archive_row() for _ in range(6)])
    assert p["archived_native_state_readthrough_count"] == 6
    assert p["archived_native_command_count"] == 0
    assert brief["status"] == "bounded_evidence_summary"
    output = " ".join(brief["findings"])
    assert "6 reported states and 0 native-history command records" in output
    assert "latest declared source-time state" in output
    assert "6 state observations were recovered" in output
    assert "No app-identifiable native command records appear" in output
    assert "6 returned observations have declared source timestamps" in output
    assert "does not establish which automation caused" in brief["conclusion"]
    assert "instead of repeating the same empty historical query" in brief["next_evidence"]
    assert brief["historical_cause_established"] is False
    assert brief["physical_outcome_verified"] is False
    assert brief["source_clock_authenticated"] is False
    assert brief["history_complete"] is False
    assert brief["production_publisher_approved"] is False
    assert brief["cloud_requests"] == brief["additional_reads"] == brief["device_commands"] == 0
    for secret in ("PRIVATE APP NAME", "SECRET", "Bearer"):
        assert secret not in str(brief)


def test_archived_command_app_identification_not_causal_promotion():
    p, brief = summary([
        archive_row("command-off", "", "hubitat-mcp-command:app:456"),
        archive_row("switch", "off", "hubitat-mcp-state"),
    ])
    assert p["archived_native_command_count"] == 1
    assert "1 archived command records identify 1 distinct" in " ".join(brief["findings"])
    assert brief["historical_cause_established"] is False
    assert brief["physical_outcome_verified"] is False
    assert "app ID 456" not in str(brief)  # Only aggregate count in narrative


def test_empty_page_not_negative_fact_or_completeness():
    p, brief = summary([])
    assert "0 reported states and 0" in " ".join(brief["findings"])
    assert "does not prove no command was issued" in " ".join(brief["findings"])
    assert not brief["history_complete"]
    assert not brief["historical_cause_established"]


def test_page_cap_or_collection_gap_never_certifies_old_history():
    p, brief = summary(
        [archive_row() for _ in range(50)],
        gaps=[{"stream": "events", "started_at": "2026-03-01T10:00:00+00:00",
               "ended_at": "2026-03-01T10:00:10+00:00", "reason": "SECRET"}],
    )
    assert "may be truncated" in " ".join(brief["findings"])
    assert "1 collector gap" in " ".join(brief["findings"])
    assert not brief["history_complete"]
    assert "SECRET" not in str(brief)


def test_invalid_archive_result_is_not_reported_as_a_success():
    brief=summarize_bounded_archive({
        "schema": "homebrain-live-shadow-journal.v1",
        "status": "blocked_archive_shape",
        "events": [],
    })
    assert brief["status"] == "insufficient_archive_source"
    assert brief["historical_cause_established"] is False
    assert "did not return a usable evidence page" in " ".join(brief["findings"])


def test_phone_displays_evidence_first_before_raw_metrics():
    ui=render_page("HomeBrainOS","0.18.323")
    first=ui.index("Investigation brief · local archive only")
    second=ui.index("--- Detailed source and timing audit ---")
    assert first < second
    assert "Next useful evidence:" in ui
    assert "Archive history complete: NO · physical execution verified: NO" in ui
    assert "data.case_brief" in ui


def test_publisher_and_cloud_routing_not_wired_to_summary():
    for path in ("mcp_agent_orchestrator.py","causal_claim_publication.py",
                 "tool_executor.py","final_answer_coordinator.py"):
        assert "live_shadow_case_brief" not in (APP/path).read_text()
