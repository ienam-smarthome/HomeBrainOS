from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_job_analysis import summarize_job_workload
from scheduler_report_sanitizer import sanitize_scheduler_overview


def _digest():
    return summarize_job_workload({"scheduledJobs": {
        "count": 5,
        "jobs": [
            {"id": "dev1089Recur.poll1", "handler": "poll1"},
            {"id": "app1418Once.timeHandler", "handler": "timeHandler"},
            {"handler": "sendEventReminder"},
            {"handler": "sendEventReminder"},
            {"handler": "sendEventReminder"},
        ]
    }})


def _log_receipts():
    return [{
        "sub_tool": "hub_get_logs", "success": True,
        "details": {"hostDerivedTiming": {"cadence": [
            {"source": "Halo3000x socket power", "sourceRef": "dev|5383",
             "signal": "ActivePower", "timingKind": "regular_cadence",
             "medianIntervalSeconds": 9.999, "observationCount": 19},
            {"source": "Halo3000x socket power", "sourceRef": "dev|5383",
             "signal": "CumulativeEnergyImported", "timingKind": "regular_cadence",
             "medianIntervalSeconds": 59.995, "observationCount": 3},
            {"source": "Octopus Live Meter", "sourceRef": "dev|7433",
             "signal": "power", "timingKind": "observed_gap",
             "medianIntervalSeconds": 60, "observationCount": 2},
        ]}},
    }]


def test_model_primary_table_is_replaced_by_complete_host_counts_without_duplication():
    model = (
        "### Scheduled Job Analysis\n\n"
        "| Owner Type | Owner/Candidate ID | Method/Handler | Job Count | Source |\n"
        "| --- | --- | --- | ---: | --- |\n"
        "| Device | Candidate (Various) | sessionTick | 29 | hub_get_jobs |\n"
        "| App | 1418 (Mode Manager) | timeHandler | 200 | hub_get_jobs |\n"
        "\n### Performance Overlap\n\nThis remains model-authored context.\n"
    )
    message, replaced, cadence = sanitize_scheduler_overview(
        model, _digest(), _log_receipts()
    )
    assert replaced is True
    assert cadence is False
    assert "sendEventReminder | 3 |" in message
    assert "sessionTick | 29" not in message
    assert "timeHandler | 200" not in message
    assert "No authoritative owner IDs were available" in message
    assert message.count("### Scheduled-job workload breakdown") == 1
    assert "This remains model-authored context." in message


def test_bad_model_cadence_table_is_replaced_by_labelled_log_observations():
    model = (
        "### Observed High-Frequency Activity\n\n"
        "| Device/App | Signal | Observed Cadence |\n"
        "| --- | --- | --- |\n"
        "Regular cadence; median interval 9.999 seconds.\n"
        "Regular cadence; median interval 59.995 seconds.\n"
        "| Octopus Live Meter | power | ~60 seconds |\n"
        "\n### Performance Overlap\n\nSaved.\n"
    )
    message, job_replaced, cadence_replaced = sanitize_scheduler_overview(
        model, _digest(), _log_receipts()
    )
    assert job_replaced is False
    assert cadence_replaced is True
    assert "Observed device log cadences (read-only)" in message
    assert "Halo3000x socket power (dev/5383)" in message.replace("|", "/")
    assert "| ActivePower | 9.999 s | 19 | hub_get_logs |" in message
    assert "| CumulativeEnergyImported | 59.995 s | 3 | hub_get_logs |" in message
    assert "Octopus Live Meter | power | ~60 seconds" not in message
    assert "not** measurements of scheduled-job execution" in message
    assert "Saved." in message


def test_unrecognized_model_structure_is_preserved_and_no_unsourced_cadence_generated():
    model = "### Advice\nDo not change anything without verification."
    message, replaced, cadence = sanitize_scheduler_overview(model, _digest(), [])
    assert message == model
    assert not replaced and not cadence

    original = "### Observed High-Frequency Activity\nNo log data.\n"
    message, _job, cadence = sanitize_scheduler_overview(original, _digest(), [])
    assert cadence
    assert "No sufficiently repeated, source-labelled log series" in message
    assert "No log data." not in message
