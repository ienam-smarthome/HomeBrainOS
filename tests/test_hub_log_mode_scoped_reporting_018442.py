"""Source-scoped native past-log reporting, including upstream default mode.

The 0.18.441 live receipt had two different calls:
(1) mode omitted + time window => upstream default past, zero matches;
(2) explicit past + no time window => 10 recent messages.
Aggregate bounded counts must not be rendered under the recent read too.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from hub_incident_ai import (  # noqa: E402
    guard_unresolved_causal_publication,
    read_only_log_receipt_summary,
)


def log_receipt(*, mode=None, bounded=True, returned=0, matched=0,
                source_total=10639, app_rows=0, device_rows=0,
                success=True):
    params = {"limit": 50 if bounded else 10}
    if mode is not None:
        params["mode"] = mode
    if bounded:
        params.update({
            "since": "2026-11-05T16:20:00Z",
            "until": "2026-11-05T17:00:00Z",
        })
    return {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": success, "mutates": False, "supports_live_claim": True,
        "arguments": {"tool": "hub_get_logs", "args": params},
        "summary": "object fields: mode, total, matched, entries, count",
        "details": {"nativePastLog": {
            "requestDateBounded": bounded,
            "returnedRowsInspected": returned,
            "matchedRowsReported": matched,
            "sourceRowsReported": source_total,
            "timestampedMessageRows": returned,
            "appMessageRowsWithVerifiedSourceId": app_rows,
            "deviceMessageRowsWithVerifiedSourceId": device_rows,
            "hasNextCursor": False, "responseTruncated": False,
        }},
    }


def unverified(evidence):
    return {
        "route": "unified-mcp-agent",
        "request_class": "live-read",
        "message": "System logs were purged due to reboot.",
        "outcome_presentation": {"value": "unresolved"},
        "investigation_coverage": {
            "hypothesisComparisons": [
                {"candidate": "retention cause", "discriminator_verified": False}
            ]
        },
        "evidence": evidence,
    }


def test_actual_018441_two_distinct_log_reads_are_not_cross_attributed():
    bounded_default = log_receipt(
        bounded=True, returned=0, matched=0, source_total=10639
    )
    recent_explicit = log_receipt(
        mode="past", bounded=False, returned=10, matched=10611,
        source_total=10640, device_rows=10
    )
    source = read_only_log_receipt_summary(
        [bounded_default, recent_explicit]
    )
    assert source["mode_reads"]["past"] == {"attempts": 1, "successes": 1}
    assert source["mode_reads"]["generic_bounded"] == {
        "attempts": 1, "successes": 1
    }
    assert source["verified_native_past_pages"] == 1
    assert source["native_past_empty_bounded_pages"] == 1
    assert source["native_past_page_observations"] == [{
        "returnedRowsInspected": 0, "matchedRowsReported": 0,
        "sourceRowsReported": 10639
    }]
    scoped = source["mode_page_observations"]
    assert scoped["past"]["bounded"] == []
    assert scoped["past"]["recent"][0]["timestampedMessageRows"] == 10
    assert scoped["generic_bounded"]["recent"] == []
    assert scoped["generic_bounded"]["bounded"][0]["sourceRowsReported"] == 10639

    response = guard_unresolved_causal_publication(
        unverified([bounded_default, recent_explicit])
    )
    assert response["ai_claim_validation"] == (
        "unverified_historical_retention_cause_withheld"
    )
    answer = response["message"]
    past_line = next(line for line in answer.splitlines()
                     if line.startswith("- Past historical log:"))
    bounded_line = next(line for line in answer.splitlines()
                        if line.startswith("- Past historical log (default mode; bounded):"))
    assert "10 rows" in past_line
    assert "0 matching" not in past_line
    assert "10639" not in past_line
    assert "0 matching messages" in bounded_line
    assert "10639" in bounded_line
    assert "10640" not in bounded_line
    assert answer.count("Source response row count before the time filter: 10639") == 1
    assert "10 device-identified" in answer
    assert "A recent page has already been read" in answer
    assert "using a separate small recent past-log sample" not in answer
    assert "logs were purged due to reboot" not in answer.lower()


def test_explicit_bounded_past_and_default_empty_are_qualified_independently():
    explicit = log_receipt(
        mode="past", bounded=True, returned=2, matched=2,
        app_rows=1, device_rows=1, source_total=200
    )
    implicit = log_receipt(
        bounded=True, returned=0, matched=0, source_total=201
    )
    response = guard_unresolved_causal_publication(
        unverified([explicit, implicit])
    )
    text = response["message"]
    past_line = next(line for line in text.splitlines()
                     if line.startswith("- Past historical log:"))
    default_line = next(line for line in text.splitlines()
                        if line.startswith("- Past historical log (default mode; bounded):"))
    assert "2 timestamped messages observed" in past_line
    assert "1 app-identified" in past_line
    assert "0 matching" not in past_line
    assert "0 matching" in default_line
    assert "201" in default_line and "200" not in default_line
    assert response["causal_read_source_coverage"][
        "verified_bounded_app_message_rows"
    ] == 1


def test_invalid_or_failed_bounded_page_does_not_enrich_mode_scoped_evidence():
    failed = log_receipt(
        bounded=True, source_total=77777, success=False
    )
    unverified_success = log_receipt(bounded=True, source_total=88888)
    unverified_success["supports_live_claim"] = False
    source = read_only_log_receipt_summary([failed, unverified_success])
    assert source["mode_reads"]["generic_bounded"] == {
        "attempts": 2, "successes": 1
    }
    assert source["mode_page_observations"]["generic_bounded"]["bounded"] == []
    assert source["verified_native_past_pages"] == 0
    rendered = guard_unresolved_causal_publication(
        unverified([failed, unverified_success])
    )["message"]
    assert "77777" not in rendered
    assert "88888" not in rendered
    assert "historical content/retention coverage unverified" in rendered
