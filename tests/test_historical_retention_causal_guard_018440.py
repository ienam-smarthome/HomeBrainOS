"""Source-real regression: no invented reason for zero-match historical logs.

The live response supplied in v0.18.439 had a verified system-event timeline,
a recent native past-log sample, and a zero-match bounded past page. The model
asserted those missing messages were purged by reboot, without any retention-
causality proof. These tests cannot prove what the hub actually retains.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from hub_incident_ai import (  # noqa: E402
    _unsupported_historical_loss_claim,
    guard_unresolved_causal_publication,
    read_only_log_receipt_summary,
)


def past(*, bounded: bool, count: int, matched: int, raw: int,
         app_count: int = 0, device_count: int = 0, success: bool = True):
    args = {"mode": "past", "limit": 20}
    if bounded:
        args.update({"since": "2026-11-05T16:30:00Z",
                     "until": "2026-11-05T16:53:00Z"})
    return {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": success, "supports_live_claim": True,
        "mutates": False, "effect": "read",
        "arguments": {"tool": "hub_get_logs", "args": args},
        "details": {"nativePastLog": {
            "requestDateBounded": bounded, "returnedRowsInspected": count,
            "timestampedMessageRows": count,
            "appMessageRowsWithVerifiedSourceId": app_count,
            "deviceMessageRowsWithVerifiedSourceId": device_count,
            "matchedRowsReported": matched, "sourceRowsReported": raw,
            "hasNextCursor": False, "responseTruncated": False,
            "completeHistoricalCoverageVerified": False,
        }},
    }


def system_events():
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "supports_live_claim": True, "mutates": False,
        "effect": "read",
        "arguments": {"args": {
            "since": "2026-11-05T16:30:00Z",
            "until": "2026-11-05T16:53:00Z"
        }},
        "details": {"observedEvents": [
            {"name": "systemStart", "date": "2026-11-05T16:52:15.774+0000",
             "description": "System startup with build: 2.5.3.117"},
            {"name": "sunriseSunsetUpdated", "date": "2026-11-05T16:44:20.990+0000",
             "description": None},
            {"name": "lowMemory", "date": "2026-11-05T16:41:40.105+0000",
             "description": "Hub memory is critically low, rebooting now"},
        ]},
    }


def unresolved(message, evidence):
    return {
        "route": "unified-mcp-agent", "request_class": "live-read",
        "message": message,
        "outcome_presentation": {"value": "unresolved"},
        "investigation_coverage": {"hypothesisComparisons": [
            {"candidate": "Logs purged during reboot",
             "discriminator_verified": False,
             "source_kind": "device_logs",
             "hypothesis_verdict": "unverified"}
        ]},
        "evidence": evidence,
        "confirmation_required": False,
    }


def test_actual_v018439_unverified_retention_explanation_is_withheld():
    original = (
        "System Logs: Not Covered. A targeted query returned 0 matched entries.\n"
        "Reason: System logs are volatile and typically purged upon reboot. "
        "The hub's last restart would have cleared the log buffer.\n"
        "Device/location events are preserved. "
        "Retention Status: System logs were purged due to the reboot at 16:41."
    )
    evidence = [
        past(bounded=False, count=20, matched=9054, raw=9082,
             app_count=1, device_count=19),
        past(bounded=True, count=0, matched=0, raw=9085),
        system_events(),
    ]
    result = guard_unresolved_causal_publication(unresolved(original, evidence))
    answer = result["message"]
    assert result["ai_claim_validation"] == "unverified_historical_retention_cause_withheld"
    assert "Historical log-retention cause is unverified" in answer
    assert "0 matching messages in the returned bounded page" in answer
    assert "Source response row count before the time filter: 9085" in answer
    assert "20 rows returned" in answer
    assert "1 app-identified" in answer
    assert "19 device-identified" in answer
    assert "9082" in answer
    assert "oldest retained timestamp" in answer
    assert "16:41:40 UTC" in answer
    assert "16:44:20 UTC" in answer
    assert "16:52:15 UTC" in answer
    assert answer.index("16:41:40 UTC") < answer.index("16:44:20 UTC")
    assert answer.index("16:44:20 UTC") < answer.index("16:52:15 UTC")
    assert "no reboot causality established" in answer
    assert "System logs were purged" not in answer
    assert "would have cleared" not in answer
    assert "all historical logs are absent" not in answer.lower()
    assert "last restart" not in answer.lower()
    assert result["causal_read_source_coverage"][
        "native_past_recent_page_observations"
    ][0]["returnedRowsInspected"] == 20
    assert result["causal_read_source_coverage"][
        "native_past_empty_bounded_pages"
    ] == 1


def test_patterns_cover_confident_retention_loss_both_word_orders():
    assertions = [
        "System logs were purged due to the reboot.",
        "The restart cleared the log buffer.",
        "The firmware update erased old log history.",
        "Old records were removed after the reset.",
        "The reboot has cleared the historical records.",
    ]
    for statement in assertions:
        assert _unsupported_historical_loss_claim(statement), statement


def test_uncertain_historical_claim_does_not_force_rewrite():
    statements = [
        "The reboot may have cleared logs, but that is unverified.",
        "It is possible the restart erased history; this is not proven.",
        "Historical logs may have been purged after an update.",
        "No evidence proves the restart cleared the logs.",
        "Zero messages matched; the retention mechanism is unknown.",
    ]
    for msg in statements:
        assert not _unsupported_historical_loss_claim(msg), msg
        source = unresolved(msg, [past(
            bounded=True, count=0, matched=0, raw=1234)])
        assert guard_unresolved_causal_publication(source) is source


def test_without_unverified_discriminator_or_unresolved_status_no_rewrite():
    sample = [past(bounded=True, count=0, matched=0, raw=1234)]
    qualified = unresolved(
        "The reboot cleared the log buffer.", sample
    )
    qualified["investigation_coverage"]["hypothesisComparisons"][0][
        "discriminator_verified"
    ] = True
    assert guard_unresolved_causal_publication(qualified) is qualified
    qualified["investigation_coverage"]["hypothesisComparisons"][0][
        "discriminator_verified"
    ] = False
    qualified["outcome_presentation"] = {"value": "completed"}
    assert guard_unresolved_causal_publication(qualified) is qualified


def test_failed_read_never_creates_unsupported_recent_sample_or_empty_page():
    evidence = [
        past(bounded=False, count=20, matched=9054, raw=9082,
             app_count=1, device_count=19, success=False),
        past(bounded=True, count=0, matched=0, raw=9085, success=False),
    ]
    result = guard_unresolved_causal_publication(unresolved(
        "Logs were purged due to reboot.", evidence
    ))
    assert "20 rows returned" not in result["message"]
    assert "9085" not in result["message"]
    assert result["ai_claim_validation"] == "unverified_historical_retention_cause_withheld"
    summary = read_only_log_receipt_summary(evidence)
    assert summary["native_past_page_observations"] == []
    assert summary["native_past_recent_page_observations"] == []


def test_recent_sample_cannot_be_converted_to_oldest_retention_proof():
    rows = [past(bounded=False, count=20, matched=9054, raw=9082,
                 app_count=1, device_count=19)]
    result = read_only_log_receipt_summary(rows)
    assert result["verified_bounded_app_message_rows"] == 0
    assert result["returned_timestamped_past_messages"] == 0
    assert result["native_past_recent_page_observations"][0][
        "timestampedMessageRows"
    ] == 20
    assert result["complete_historical_app_log_coverage"] is False


def test_actual_v018440_log_purge_suggestion_and_cleared_buffer_are_withheld():
    # Full paragraphs closely model the source-real public v0.18.440 response.
    draft = (
        "The historical coverage for 5 November 2026 is fragmented.\n"
        "Log Coverage Analysis: A past-log query returned 0 matched entries.\n"
        "Retention Status: The absence of diagnostic logs alongside the "
        "presence of system events suggests a log purge occurred, likely "
        "triggered by the hub reboot observed in the event history.\n"
        "Timeline: lowMemory at 16:41, sunriseSunsetUpdated at 16:44, "
        "systemStart at 16:52.\n"
        "Conclusion: While the diagnostic log buffer for this period has "
        "been cleared, event history records the low-memory reboot warning."
    )
    reads = [
        past(bounded=False, count=20, matched=9838, raw=9866,
             app_count=0, device_count=20),
        past(bounded=True, count=0, matched=0, raw=9867),
        system_events(),
    ]
    assert _unsupported_historical_loss_claim(draft)
    result = guard_unresolved_causal_publication(unresolved(draft, reads))
    answer = result["message"]
    assert result["ai_claim_validation"] == "unverified_historical_retention_cause_withheld"
    assert "log purge occurred" not in answer
    assert "has been cleared" not in answer
    assert "likely triggered" not in answer
    assert "20 rows returned" in answer
    assert "20 device-identified" in answer
    assert "0 matching messages in the returned bounded page" in answer
    assert "9867" in answer
    assert "9838" not in answer or "Recent unbounded" in answer
    assert "16:41:40 UTC" in answer
    assert "16:44:20 UTC" in answer
    assert "16:52:15 UTC" in answer
    assert "no reboot causality established" in answer


def test_loss_assertion_without_explicit_cause_is_still_unverified():
    confident = [
        "The diagnostic log buffer for this period has been cleared.",
        "An automated log purge occurred.",
        "The old history records were deleted.",
        "Messages were erased from the logging history.",
        "The past logs rotated away yesterday.",
        "Logs were removed from the buffer.",
        "The data suggests a log purge occurred, likely after the restart.",
    ]
    for draft in confident:
        assert _unsupported_historical_loss_claim(draft), draft
    no_assertion = [
        "Zero past-log entries matched the requested time range.",
        "The reboot warning and system startup are source observations.",
        "A reboot may have cleared the logs, but this is unverified.",
        "A log purge could have occurred; the cause is unknown.",
        "These logs were not cleared by the investigated operation.",
        "We cannot conclude that logs were purged.",
    ]
    for draft in no_assertion:
        assert not _unsupported_historical_loss_claim(draft), draft


def test_uncorroborated_loss_is_not_rehabilitated_by_same_turn_disclaimer():
    message = (
        "Retention Status: A log purge occurred, likely due to the reboot.\n"
        "Evidence coverage incomplete: an app log read was not verified."
    )
    assert _unsupported_historical_loss_claim(message)


def test_nonretention_investigation_is_not_rewritten_for_source_event():
    question = "The hub announced low memory and started again."
    draft = unresolved(question, [system_events()])
    assert guard_unresolved_causal_publication(draft) is draft
