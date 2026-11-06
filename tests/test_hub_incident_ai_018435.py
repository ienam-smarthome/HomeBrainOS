"""Regression: ordinary Ask preserves typed evidence when causal draft is withheld."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from hub_incident_ai import (  # noqa: E402
    guard_unresolved_causal_publication,
    read_only_log_receipt_summary,
)


def receipt(mode, *, success=True, since=None, until=None,
            details=None, supports=True):
    params = {"mode": mode, "limit": 100}
    if since is not None:
        params["since"] = since
    if until is not None:
        params["until"] = until
    row = {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": success, "supports_live_claim": supports,
        "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_get_logs", "args": params},
        "summary": "object fields: mode, count, entries",
    }
    if details is not None:
        row["details"] = details
    return row


def unresolved(message, evidence):
    return {
        "route": "unified-mcp-agent", "request_class": "live-read",
        "message": message, "outcome_presentation": {"value": "unresolved"},
        "investigation_coverage": {"hypothesisComparisons": [
            {"candidate": "a leak", "discriminator_verified": False,
             "source_kind": "app_logs", "hypothesis_verdict": "unverified"},
        ]},
        "evidence": evidence, "confirmation_required": False,
    }


def test_real_1652_ordinary_ask_pattern_keeps_qualified_log_receipts():
    reads = [
        receipt("hubEvents", since="2026-11-05T16:30:00Z",
                until="2026-11-05T17:10:00Z"),
        receipt("past", since="2026-11-05T16:00:00Z",
                until="2026-11-05T16:50:00Z"),
        receipt("apps"),  # The successful unbounded app snapshot is NOT history.
    ]
    result = guard_unresolved_causal_publication(unresolved(
        "The app was responsible for the memory drop and caused the reboot.",
        reads,
    ))
    answer = result["message"]
    assert result["route"] == "unified-mcp-agent"
    assert "was responsible for" not in answer
    assert "authenticated Hubitat events" not in answer.lower()
    assert "Hub Events log: 1/1" in answer
    assert "Past log: 1/1" in answer
    assert "App runtime statistics: 1/1" in answer
    assert "content/retention coverage unverified" in answer
    assert "Read-only next checks" in answer
    assert result["causal_read_source_coverage"]["verified_bounded_app_message_rows"] == 0
    assert result["causal_read_source_coverage"]["complete_historical_app_log_coverage"] is False
    assert result["evidence"] == reads


def test_real_2233_ordinary_ask_mode_success_is_not_historical_app_proof():
    reads = [
        receipt("hubEvents", since="2026-11-05T22:00:00Z",
                until="2026-11-05T23:00:00Z"),
        receipt("past", since="2026-11-05T22:00:00Z",
                until="2026-11-05T23:00:00Z"),
    ]
    result = guard_unresolved_causal_publication(unresolved(
        "The firmware update caused the earlier memory pressure.", reads
    ))
    assert result["ai_claim_validation"] == "unresolved_cause_claim_withheld"
    assert "firmware update caused" not in result["message"].lower()
    modes = result["causal_read_source_coverage"]["mode_reads"]
    assert modes["hubEvents"]["successes"] == 1
    assert modes["past"]["successes"] == 1
    assert modes["apps"]["successes"] == 0
    assert "App-mode log: 1/1" not in result["message"]


def test_verified_bounded_typed_events_survive_unsafe_model_draft():
    source = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "supports_live_claim": True, "mutates": False,
        "arguments": {"args": {
            "since": "2026-11-05T16:30:00Z",
            "until": "2026-11-05T17:10:00Z",
        }},
        "details": {"observedEvents": [
            {"name": "lowMemory", "date": "2026-11-05T16:41:40.105+0000",
             "description": "Hub memory is critically low, rebooting now"},
            {"name": "systemStart", "date": "2026-11-05T16:52:15.774+0000",
             "value": "2.5.3.117"},
            {"name": "update", "date": "2026-11-04T16:25:00Z",
             "description": "out of window and must not appear"},
        ]},
    }
    result = guard_unresolved_causal_publication(unresolved(
        "A particular app caused the critical low memory.", [source]
    ))
    assert "16:41:40 UTC" in result["message"]
    assert "16:52:15 UTC" in result["message"]
    assert result["message"].index("16:41:40 UTC") < result["message"].index("16:52:15 UTC")
    assert "Verified reported restart context" in result["message"]
    assert "explicitly warned that memory was critically low" in result["message"]
    assert "04 Nov" not in result["message"]
    assert "particular app" not in result["message"]


def test_unverified_or_mutating_event_rows_are_never_promoted():
    row = {
        "sub_tool": "hub_list_device_events", "success": True,
        "supports_live_claim": False, "mutates": False,
        "arguments": {"args": {
            "since": "2026-11-05T16:30:00Z",
            "until": "2026-11-05T17:10:00Z",
        }},
        "details": {"observedEvents": [
            {"name": "lowMemory", "date": "2026-11-05T16:41:40Z",
             "description": "Hub memory is critically low, rebooting now"},
        ]},
    }
    for bad in (row, {**row, "supports_live_claim": True, "mutates": True},
                {**row, "supports_live_claim": True, "success": False}):
        answer = guard_unresolved_causal_publication(unresolved(
            "A driver caused the memory leak.", [bad]))["message"]
        assert "16:41:40" not in answer
        assert "explicitly warned" not in answer


def test_app_rows_need_bounded_actual_typed_message_not_just_summary_counts():
    since, until = "2026-11-05T16:00:00Z", "2026-11-05T17:00:00Z"
    good = {"appId": 4151, "date": "2026-11-05T16:25:00Z",
            "message": "PRIVATE MESSAGE BODY"}
    rows = [
        receipt("past", since=since, until=until,
                details={"entries": [
                    good,
                    {"appId": 4151, "date": "2026-11-04T16:25:00Z",
                     "message": "other day"},
                    {"date": "2026-11-05T16:30:00Z", "message": "missing app id"},
                ]}),
        receipt("apps", details={"entries": [good]}),
        receipt("past", since=since, until=until),
    ]
    assessed = read_only_log_receipt_summary(rows)
    assert assessed["verified_bounded_app_message_rows"] == 1
    assert assessed["mode_reads"]["apps"]["successes"] == 1
    assert assessed["mode_reads"]["past"]["successes"] == 2
    assert assessed["mode_reads"]["past"]["successes"] == 1
    assert assessed["complete_historical_app_log_coverage"] is False
    result = guard_unresolved_causal_publication(unresolved(
        "The app caused this event.", rows
    ))
    assert "PRIVATE MESSAGE BODY" not in result["message"]
    assert "PRIVATE MESSAGE BODY" not in str(result["causal_read_source_coverage"])


def test_no_history_mode_contamination_and_no_mutation_to_verified_results():
    generic = receipt(None, since="2026-11-05T16:00:00Z",
                      until="2026-11-05T17:00:00Z")
    failed = receipt("apps", success=False)
    coverage = read_only_log_receipt_summary([generic, failed])
    assert coverage["mode_reads"]["generic_bounded"]["successes"] == 1
    assert coverage["mode_reads"]["apps"]["attempts"] == 1
    assert coverage["mode_reads"]["apps"]["successes"] == 0
    completed = unresolved("Low memory was observed, cause unverified.", [generic])
    assert guard_unresolved_causal_publication(completed) is completed
    completed["message"] = "The app caused this."
    completed["outcome_presentation"] = {"value": "completed"}
    assert guard_unresolved_causal_publication(completed) is completed
