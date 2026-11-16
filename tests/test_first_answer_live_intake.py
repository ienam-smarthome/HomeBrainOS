"""Source-real intake contracts: no automatic grades or silent case matching.

All records and tool results are fictional; these tests never contact a
model, Home Assistant, Hubitat, GitHub or the user's original private data.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from answer_quality_scorecard import (  # noqa: E402
    ScorecardInputError, build_scorecard, load_catalog,
)
from first_answer_live_intake import (  # noqa: E402
    IntakeError, _catalog_prompts, _read_private_capture, main,
    prepare_one, prepare_many,
)


def fake_capture(case_id="causal_light2_off"):
    live, _ = _catalog_prompts()
    task = next(t for t in live.values() if t["key"] == case_id)
    inner = {
        "device": "Fixture lamp",
        "events": [
            {"name": "switch", "value": "off",
             "date": "2031-01-01T12:01:00Z",
             "producedBy": {"name": "Fixture bridge"}},
        ],
        "count": 1,
    }
    native = json.dumps({"content": [{"type": "text", "text": json.dumps(inner)}]})
    doc = {
        "ui_version": "2.0.0-alpha.133",
        "model": "fixture-model",
        "question": task["prompt"],
        "client_elapsed_ms": 2600,
        "response": {
            "rounds": 3, "prior_receipts_used": 0,
            "prior_sources_indexed": 0,
            "answer": "Reported OFF. Historical cause not independently established.",
            "tool_calls": [{
                "name": "hub_list_device_events", "success": True,
                "arguments": {"deviceId": "FICT-01", "limit": 20},
                "response": native,
            }],
        },
    }
    return doc


def raw(doc):
    return json.dumps(doc, sort_keys=True).encode("utf-8")


def test_exact_frozen_live_case_creates_ungraded_review_and_source_limited_metrics():
    doc = fake_capture()
    before = deepcopy(doc)
    result = prepare_many([(raw(doc), doc)], build_sha="a" * 40)
    meta = result["intake_metadata"][0]
    item = result["reviews"][0]
    assert result["scorecard_ready"] is False
    assert result["quality_status"] == "not_measured"
    assert meta["case_id"] == "causal_light2_off"
    assert meta["source_summary"]["successful_attempts"] == 1
    assert meta["source_summary"]["event_rows_returned_total"] == 1
    assert meta["source_summary"]["source_windows_complete"] == "not_established"
    assert meta["source_summary"]["controller_or_physical_cause_verified"] == "human_review_required"
    assert item["case_id"] == "causal_light2_off"
    assert item["build_sha"] == "a" * 40
    assert item["metrics"] == {"latency_seconds": 2.6, "tool_calls": 1}
    assert item["review"]["grounding"] is None
    assert item["review"]["unsupported_definitive_causal_claims"] is None
    assert item["reviewer"] is None
    assert item["evidence_reference"] == "sha256:" + hashlib.sha256(raw(doc)).hexdigest()
    assert doc == before
    # The existing scorer refuses to call an unreviewed template a result.
    with pytest.raises(ScorecardInputError):
        build_scorecard(result, load_catalog())


def test_no_raw_evidence_appears_in_draft_even_with_sensitive_fixture_text():
    doc = fake_capture()
    doc["response"]["answer"] = "PRIVATE DEVICE SERIAL FICT-01"
    doc["response"]["tool_calls"][0]["arguments"]["token"] = "PRIVATE-SECRET"
    result = prepare_many([(raw(doc), doc)])
    output = json.dumps(result)
    assert "PRIVATE DEVICE SERIAL" not in output
    assert "PRIVATE-SECRET" not in output
    assert "FICT-01" not in output
    assert doc["question"] not in output
    assert result["reviews"][0]["build_sha"] is None
    assert result["intake_metadata"][0]["first_attempt"].startswith("reported_zero")


@pytest.mark.parametrize("field", ["prior_receipts_used", "prior_sources_indexed"])
def test_contaminated_context_fails_closed(field):
    doc = fake_capture()
    doc["response"][field] = 2
    with pytest.raises(IntakeError, match="earlier conversation"):
        prepare_one(doc, raw(doc))


def test_read_only_intake_rejects_possible_writes_and_untrusted_tool_classes():
    for name in ("hub_call_device_command", "hub_manage_rule",
                 "unknown_tool", "homebrain_read_prior_evidence"):
        doc = fake_capture()
        doc["response"]["tool_calls"].append({
            "name": name, "success": True, "response": {},
        })
        with pytest.raises(IntakeError, match="write|unknown tool"):
            prepare_one(doc, raw(doc))
    doc = fake_capture()
    doc["response"]["tool_calls"][0]["read_only"] = False
    with pytest.raises(IntakeError):
        prepare_one(doc, raw(doc))


def test_curated_packet_prompt_cannot_be_mistaken_for_matching_live_sources():
    _, curated = _catalog_prompts()
    doc = fake_capture()
    doc["question"] = next(iter(curated))
    with pytest.raises(IntakeError, match="curated offline"):
        prepare_one(doc, raw(doc))


def test_modified_prompt_does_not_silently_take_closest_case():
    doc = fake_capture()
    doc["question"] += " Please check every input."
    with pytest.raises(IntakeError, match="exactly match"):
        prepare_one(doc, raw(doc))


def test_existing_write_case_must_only_use_mocked_executor():
    live, _ = _catalog_prompts()
    write_task = next(t for t in live.values() if t["read_only"] is False)
    doc = fake_capture()
    doc["question"] = write_task["prompt"]
    with pytest.raises(IntakeError, match="mocked executor"):
        prepare_one(doc, raw(doc))


def test_duplicate_case_model_build_does_not_allow_cherry_picking():
    a, b = fake_capture(), fake_capture()
    b["response"]["answer"] = "Second successful attempt after first failed"
    with pytest.raises(IntakeError, match="Duplicate"):
        prepare_many([(raw(a), a), (raw(b), b)], build_sha="a" * 40)


def test_two_distinct_cases_keep_independent_private_references():
    a, b = fake_capture(), fake_capture("status_named_dimmer")
    report = prepare_many([(raw(a), a), (raw(b), b)])
    assert len(report["reviews"]) == 2
    assert len({x["case_id"] for x in report["reviews"]}) == 2
    assert len({x["evidence_reference"] for x in report["reviews"]}) == 2


def test_output_file_private_create_only_and_no_raw_stdout(capsys, tmp_path):
    source = tmp_path / "original-private-export.json"
    source.write_bytes(raw(fake_capture()))
    destination = tmp_path / "private-review-drafts.json"
    assert main([str(source), "--output", str(destination)]) == 0
    assert (destination.stat().st_mode & 0o777) == 0o600
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report["scorecard_ready"] is False
    printed = capsys.readouterr().out
    assert "UNGRADED" in printed
    assert "Fixture" not in printed
    assert "FICT-01" not in destination.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        main([str(source), "--output", str(destination)])
    doc = json.loads(source.read_text(encoding="utf-8"))
    assert _read_private_capture(source)[1] == doc


def test_bad_sha_not_backfilled_from_version():
    doc = fake_capture()
    with pytest.raises(IntakeError, match="40 hexadecimal"):
        prepare_many([(raw(doc), doc)], build_sha="alpha.133")
