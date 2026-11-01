"""Q1: only fixed, anonymised evidence can be replayed and compared."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from answer_quality_fixed_packets import (
    PACKET_SCHEMA, RUN_SCHEMA, ScorecardInputError,
    build_fixed_packets, canonical_digest, main, pair_metadata,
    validate_run_manifest,
)


def run(packet, *, build="a" * 40, model="gemma4:31b", answer="b" * 64):
    return {
        "case_id": packet["case_id"],
        "packet_sha256": packet["packet_sha256"],
        "answer_sha256": answer,
        "model": model,
        "provider": "ollama-cloud",
        "build_sha": build,
        "attempt_index": 1,
        "elapsed_ms": 23456,
    }


def manifest(*runs):
    return {"schema": RUN_SCHEMA, "runs": list(runs)}


def test_exact_curated_inventory_yields_only_model_visible_frozen_packet():
    packets = build_fixed_packets()
    assert len(packets) == 18
    assert len({p["case_id"] for p in packets}) == 18
    assert any(p["case_id"] == "aq_network_broker_vs_device_health" for p in packets)
    assert any(p["case_id"] == "aq_early_heating_off_resume" for p in packets)
    for packet in packets:
        assert packet["schema"] == PACKET_SCHEMA
        assert set(packet) == {
            "schema", "case_id", "question", "available_evidence",
            "tool_policy", "packet_sha256",
        }
        assert packet["tool_policy"] == "offline-evidence-only-no-tools"
        assert packet["packet_sha256"] == canonical_digest(
            {k: v for k, v in packet.items() if k != "packet_sha256"}
        )
    text = json.dumps(packets)
    assert '"required_findings"' not in text
    assert '"forbidden_claims"' not in text
    assert '"review_status"' not in text
    assert '"reference_type"' not in text


def test_packet_hash_changes_when_prompt_or_evidence_changes():
    p = build_fixed_packets()[0]
    original = {k: v for k, v in p.items() if k != "packet_sha256"}
    changed = {**original, "question": original["question"] + " altered"}
    assert canonical_digest(changed) != p["packet_sha256"]
    changed = {**original, "available_evidence": original["available_evidence"] + ["new source"]}
    assert canonical_digest(changed) != p["packet_sha256"]


def test_export_cli_selection_emits_json_lines_not_grading_keys(tmp_path):
    out = tmp_path / "model-packets.jsonl"
    assert main(["export", "--case-id", "aq_app_logs_empty", "--output", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    packet = json.loads(lines[0])
    assert packet["case_id"] == "aq_app_logs_empty"
    assert "required_findings" not in out.read_text(encoding="utf-8")


def test_unknown_selected_packet_fails():
    with pytest.raises(ScorecardInputError, match="Unknown curated case"):
        main(["export", "--case-id", "invented_case"])


def test_same_packet_comparison_is_metadata_only_not_factual_score():
    p = build_fixed_packets()[0]
    result = pair_metadata(
        manifest(run(p)), manifest(run(p, build="c" * 40, model="other-model", answer="d" * 64)),
        build_fixed_packets(),
    )
    assert result["paired_cases"] == 1
    assert result["paired_case_ids"] == [p["case_id"]]
    assert result["quality_measurement_status"] == "not_measured"
    assert result["comparison_status"] == "metadata_pairs_ready_for_independent_review"
    assert "grounded_conclusions_pct" not in result
    assert "first_attempt_useful_pct" not in result
    assert "answer" not in json.dumps(result)


def test_no_pair_and_missing_case_are_not_measured():
    p, q = build_fixed_packets()[:2]
    result = pair_metadata(manifest(run(p)), manifest(run(q)), build_fixed_packets())
    assert result["paired_cases"] == 0
    assert result["comparison_status"] == "not_measured"
    assert result["baseline_only_case_ids"] == [p["case_id"]]
    assert result["candidate_only_case_ids"] == [q["case_id"]]
    assert pair_metadata(manifest(), manifest(), build_fixed_packets())["quality_measurement_status"] == "not_measured"


@pytest.mark.parametrize("field,value", [
    ("packet_sha256", "0" * 64),
    ("answer_sha256", "not-a-hash"),
    ("build_sha", "v0.18.330"),
    ("model", "Private model\nSECRET-ANSWER"),
    ("provider", ["ollama-cloud"]),
    ("provider", "SECRET-PRIVATE-NAME"),
    ("attempt_index", 2),
    ("attempt_index", 1.0),
    ("attempt_index", True),
    ("elapsed_ms", -12),
    ("elapsed_ms", float("nan")),
    ("elapsed_ms", False),
])
def test_invalid_or_nonfirst_metadata_fails_closed(field, value):
    p = build_fixed_packets()[0]
    item = run(p)
    item[field] = value
    with pytest.raises(ScorecardInputError):
        validate_run_manifest(manifest(item), build_fixed_packets())


def test_raw_answer_private_log_fields_never_accepted_for_comparison():
    p = build_fixed_packets()[0]
    item = run(p)
    item["message"] = "SECRET-HOUSEHOLD-TIMELINE"
    with pytest.raises(ScorecardInputError, match="metadata-only"):
        pair_metadata(manifest(item), manifest(), build_fixed_packets())


def test_duplicate_model_runs_do_not_count_as_two_attempts():
    p = build_fixed_packets()[0]
    with pytest.raises(ScorecardInputError, match="Duplicate run"):
        validate_run_manifest(manifest(run(p), run(p)), build_fixed_packets())


def test_manifest_change_to_live_or_ungraded_input_is_rejected(tmp_path):
    source = json.loads((ROOT / "tests/fixtures/answer_quality_cases_v1.json").read_text())
    source["cases"][0]["read_only"] = False
    file = tmp_path / "bad-manifest.json"
    file.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ScorecardInputError, match="read-only"):
        build_fixed_packets(file)
    source["cases"][0]["read_only"] = True
    source["cases"][0]["required_findings"] = []
    file.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ScorecardInputError, match="reviewer rubric"):
        build_fixed_packets(file)


def test_cli_comparison_with_empty_manifests_is_explicitly_unmeasured(tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    output = tmp_path / "result.json"
    before.write_text(json.dumps(manifest()), encoding="utf-8")
    after.write_text(json.dumps(manifest()), encoding="utf-8")
    assert main([
        "compare", "--baseline", str(before), "--candidate", str(after),
        "--output", str(output),
    ]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["paired_cases"] == 0
    assert report["quality_measurement_status"] == "not_measured"
