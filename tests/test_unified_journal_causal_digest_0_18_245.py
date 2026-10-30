"""v0.18.245: replay the real 30 Oct Historical Journal 17+23 source case.

Prevents HomeBrain's final answer from reverting to 60+ raw technical rows
after recovering the actual switch transitions. Accurate cause and provenance
are preserved: no unsupported external-ON initiation and no reception-time
elevation into a verified source clock.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from test_group_journal_recovery_0_18_244 import (
    Journal, Recorder, archived, EXPLICIT,
)
from test_unified_incident_causal_consistency_0_18_243 import (
    actual_partial_receipts, WRONG_LIVE,
)
from unified_incident_digest import (
    source_incident_digest, _dedupe_archive, _source_rows,
)
from unified_incident_synthesis import (
    reconcile_ledger_if_needed, verified_incident_ledger,
)
from unified_investigation_bridge import (
    collect_unified_evidence, reconcile_unified_investigation_answer,
)


SOURCE = {
    "7818": [
        ("off", "02:18:15.850"),
        ("on", "02:52:44.099"),
        ("off", "03:04:18.218"),
        ("on", "03:40:21.668"),
        ("off", "03:46:05.928"),
        ("on", "07:12:33.514"),
    ],
    "7821": [
        ("off", "02:18:16.833"),
        ("on", "02:52:45.141"),
        ("off", "03:04:18.278"),
        ("on", "03:40:22.678"),
        ("off", "03:46:06.059"),
        ("on", "07:12:34.589"),
    ],
    "7807": [
        ("on", "02:13:30.399"),
        ("off", "02:15:13.073"),
        ("on", "03:03:31.727"),
        ("off", "03:04:17.212"),
        ("on", "07:27:48.079"),
    ],
}


def fixture_receipts():
    source_receipts = actual_partial_receipts()
    # Original live invocation returned app commands, but no in-window
    # source-reported switch rows in any of the three device pages.
    for receipt in source_receipts:
        if receipt.get("sub_tool") == "hub_list_device_events":
            args = receipt.get("arguments", {}).get("args", {})
            if args.get("deviceId") == "7807":
                receipt["details"]["observedEvents"] = [
                    row for row in receipt["details"]["observedEvents"]
                    if row["name"] != "switch"
                ]
    archive = Recorder()
    journal_events = {}
    for ident, events in SOURCE.items():
        rows = [
            archived(ident, value, "2026-10-30T" + when + "+00:00")
            for value, when in events
        ]
        # A second journal stream observes the same state 1.25s later:
        # it cannot be counted as a second physical switch transition.
        rows.extend(
            archived(ident, value,
                     "2026-10-30T" + (
                         __import__("datetime").datetime.fromisoformat(
                             "2026-10-30T" + when + "+00:00"
                         ) + __import__("datetime").timedelta(seconds=1.25)
                     ).strftime("%H:%M:%S.%f")[:-3] + "+00:00",
                     "collector-received")
            for value, when in events
        )
        journal_events[ident] = rows
    # Six collector-only observations: reception time is not guaranteed
    # to be the actual light state transition timestamp.
    journal_events["7818"] += [
        archived("7818", "on", "2026-10-30T02:10:01.060+00:00", "collector-received"),
        archived("7818", "off", "2026-10-30T02:10:33.782+00:00", "collector-received"),
        archived("7818", "on", "2026-10-30T02:13:19.265+00:00", "collector-received"),
    ]
    journal_events["7821"] += [
        archived("7821", "on", "2026-10-30T02:10:01.798+00:00", "collector-received"),
        archived("7821", "off", "2026-10-30T02:10:34.710+00:00", "collector-received"),
        archived("7821", "on", "2026-10-30T02:13:20.296+00:00", "collector-received"),
    ]
    # Represent archive receipts rather than using the HTTP endpoint. The
    # original model never receives invented source event IDs or permissions.
    from datetime import datetime, timezone
    for ident, observations in journal_events.items():
        converted = [
            {
                "device_id": ident, "attribute": "switch",
                "value": item["value"], "date": item["observed_at"],
                "timestamp_basis": item["timestamp_basis"],
                "source": item["source"],
            }
            for item in observations
        ]
        archive.record(
            "homebrain_evidence_journal",
            {"device_id": ident, "attribute": "switch"},
            success=True, elapsed_ms=1, mutates=False, effect="read",
            evidence_kind="group_archived_switch_history",
            supports_live_claim=True, summary="bounded archived switch observations",
            details={"deviceId": ident, "observations": converted,
                     "gapCount": 2, "coverageComplete": False,
                     "truncated": False},
        )
    return source_receipts + archive.receipts()


def test_real_17_source_23_collector_live_replay():
    rows = fixture_receipts()
    facts = collect_unified_evidence(rows, EXPLICIT)
    assert facts["journal_source_observations"] == 17
    assert facts["journal_collector_observations"] == 23
    source, collector, live = _source_rows(facts)
    clean, unmatched, paired = _dedupe_archive(source, collector)
    assert len(clean) == 17
    assert paired == 17
    assert len(unmatched) == 6

    fixed, changed = reconcile_unified_investigation_answer(WRONG_LIVE, rows, EXPLICIT)
    assert changed
    assert len(fixed) < 6200  # prior raw ledger was ~9k and overwhelmed explanation
    assert fixed.count("### Reconstructed source-timed sequence") == 1
    assert fixed.count("| 02:18:15 |") == 1
    assert "| 02:52:44 | Bathroom Lights 1 and 2 | ON |" in fixed
    assert "| 03:04:17 | All three lights | OFF |" in fixed
    assert "app 1568" in fixed
    assert "| 03:46:05 | Bathroom Lights 1 and 2 | OFF |" in fixed
    assert "app 1569" in fixed
    assert "| 07:12:33 | Bathroom Lights 1 and 2 | ON |" in fixed
    assert "| 07:27:48 | Shower Light | ON |" in fixed
    assert "ON reported before app 4013 adjusted brightness" in fixed
    assert "ON reported before app 4014 adjusted brightness" in fixed
    assert "School Run" not in fixed  # no source mode observation in fixture
    assert "02:10:01" in fixed and "collector-only" in fixed
    assert "The initiating ON controller is unverified" in fixed
    assert "no OFF commands" not in fixed
    assert "activations were driven by location mode changes" not in fixed
    assert "source timestamp" not in fixed or "collector" in fixed


def test_collector_only_is_not_promoted_to_precise_source_history():
    rows = fixture_receipts()
    for rec in rows:
        if rec.get("evidence_kind") == "group_archived_switch_history":
            rec["details"]["observations"] = [
                e for e in rec["details"]["observations"]
                if e["timestamp_basis"] != "source"
            ]
    facts = collect_unified_evidence(rows, EXPLICIT)
    assert facts["journal_source_observations"] == 0
    assert source_incident_digest(facts) is None
    result, _ = reconcile_unified_investigation_answer(WRONG_LIVE, rows, EXPLICIT)
    assert "### Verified incident ledger" in result


def test_source_only_one_device_preserves_raw_fallback():
    rows = fixture_receipts()
    for rec in rows:
        if rec.get("evidence_kind") == "group_archived_switch_history":
            if rec.get("arguments", {}).get("device_id") != "7807":
                rec["details"]["observations"] = []
    facts = collect_unified_evidence(rows, EXPLICIT)
    assert source_incident_digest(facts) is None


def test_school_run_mode_reapplies_brightness_after_source_reported_on():
    rows = fixture_receipts()
    facts = collect_unified_evidence(rows, EXPLICIT)
    response = source_incident_digest(facts)
    assert response
    assert "School Run at 07:15:01" in response
    assert "already reported ON at 07:12:33" in response
    assert "mode-time setLevel was not that initial ON" in response
