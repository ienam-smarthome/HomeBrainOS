from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_job_analysis import summarize_job_workload, render_job_workload_summary
from performance_api_finalizer import _qualify_job_key_owner_labels


LIVE_JOB_ROWS = [
    {"id": "dev7086Once.heartbeat", "method": "heartbeat", "name": "Fan Switch (Tuya Local)"},
    {"id": "dev7334Once.healthCheck", "method": "healthCheck", "name": "FP2 Livingroom"},
    {"id": "dev7889Recur.autoPoll", "method": "autoPoll", "name": "Eufy Robovac socket"},
    {"id": "dev6910Recur.sessionTick", "method": "sessionTick", "name": "Block Phone"},
    {"id": "dev6983Recur.sessionTick", "method": "sessionTick", "name": "Block Bedroom3 PC"},
    {"id": "dev6982Recur.sessionTick", "method": "sessionTick", "name": "Block Freezer"},
    {"id": "dev7959Recur.autoPoll", "method": "autoPoll", "name": "Kettle"},
]


def test_v016136_live_job_key_formats_are_separate_unverified_candidates():
    snapshot = {"scheduledJobs": {"count": 250, "jobs": LIVE_JOB_ROWS}}
    d = summarize_job_workload(snapshot)
    assert d["reportedJobs"] == 250
    assert d["rowsExamined"] == 7
    assert d["completeRows"] is False
    assert d["ownerIdentifiedRows"] == 0
    assert d["unattributedRows"] == 7
    assert d["keyPatternCandidateRows"] == 7
    assert d["keyPatternCandidateTypes"] == {"device": 7}
    assert d["unknownMethodRows"] == 0
    assert sum(group["jobs"] for group in d["topCandidateOwnerMethods"]) == 7
    assert any(group["candidateOwnerId"] == "6910" and group["method"] == "sessionTick"
               for group in d["topCandidateOwnerMethods"])
    rendered = render_job_workload_summary(d)
    assert "7 of 7 rows contain strict, unverified owner candidates" in rendered
    assert "No authoritative owner IDs" in rendered
    assert "NOT confirmed owners" in rendered
    assert "Only part of the reported job list" in rendered


def test_map_key_with_row_id_unrelated_and_recur_suffix():
    d = summarize_job_workload({"scheduledJobs": {
        "count": 2,
        "dev6910Recur.sessionTick": {"id": "arbitrary-guid", "method": "sessionTick"},
        "app4151Once.refreshCache": {"method": "refreshCache"},
    }})
    assert d["keyPatternCandidateRows"] == 2
    assert d["keyPatternCandidateTypes"] == {"device": 1, "app": 1}
    assert d["ownerIdentifiedRows"] == 0


def test_full_job_key_in_name_field_only_is_exact_candidate():
    d = summarize_job_workload({"scheduledJobs": [{"name": "dev7889Recur.autoPoll"}]})
    assert d["keyPatternCandidateRows"] == 1
    assert d["topCandidateOwnerMethods"][0]["method"] == "autoPoll"


def test_untrusted_names_and_disagreeing_method_cannot_be_owner_candidates():
    d = summarize_job_workload({"scheduledJobs": [
        {"id": "dev1234Recur.sessionTickExtra", "method": "sessionTick"},
        {"id": "dev1234Recur.sessionTick", "method": "differentMethod"},
        {"name": "Device dev1234Recur.sessionTick", "method": "sessionTick"},
        {"id": "dev1234Recur.sessionTickExtra.text", "method": "sessionTick"},
        {"id": "app1234Once.heartbeat.bad"},
    ]})
    # A complete key with a different valid method suffix is a separate key
    # candidate, while conflicts and embedded fragments are rejected.
    assert d["keyPatternCandidateRows"] == 1
    assert d["unattributedRows"] == 5


def test_model_sample_owner_claim_qualified_but_verified_labels_preserved():
    message = (
        "| Job ID / Name | Method | Next run | Owner |\n"
        "| --- | --- | --- | --- |\n"
        "| dev7086Once.heartbeat / Fan Switch | heartbeat | 13:09:50 | Device 7086 |\n"
        "| dev7889Recur.autoPoll / Robovac | autoPoll | 13:10:00 | Device 7889 |\n"
        "| unrelated job | refresh | 13:10:00 | Device 42 |\n"
    )
    digest = {"ownerIdentifiedRows": 0}
    output, changed = _qualify_job_key_owner_labels(message, digest)
    assert changed
    assert "Unverified candidate device 7086" in output
    assert "Unverified candidate device 7889" in output
    assert "| Device 42 |" in output
    assert _qualify_job_key_owner_labels(message, {"ownerIdentifiedRows": 10}) == (message, False)
    assert _qualify_job_key_owner_labels(message, None) == (message, False)
