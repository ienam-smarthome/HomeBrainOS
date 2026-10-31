"""Stage 4M: no implicit cloud calls, manual dispatch, private source audits."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "rootfs" / "app"))

from stage4l_ollama_cloud_trial import (  # noqa: E402
    _offline_author, run_constructed_trial, _private_save,
)
from stage4m_private_postgeneration_review import (  # noqa: E402
    _load_private, make_review_template,
    assess_independently_labelled_bundle, main,
)
from stage4_narrative_contract import build_stage4_evidence_packet  # noqa: E402


def _bundle(count=2):
    report, bundles = run_constructed_trial(_offline_author, case_limit=count)
    assert report["cases"]["frozen"] == count
    return {"schema": "homebrain-stage4l-private-bundle.v1", "cases": bundles}


def _labelled(bundle):
    review = make_review_template(bundle)
    for case, entry in zip(bundle["cases"], review["cases"]):
        facts = build_stage4_evidence_packet(case["receipts"])["facts"]
        fact = facts[0]
        prop = "recorded_gap" if fact["kind"] == "coverage_limit" else "recorded_event"
        for row in entry["sentences"]:
            row["reference_atoms"] = [{
                "proposition": prop,
                "fact_ids": [fact["fact_id"]],
                "limit": None,
            }]
            row["clarity_score"] = 4
            row["usefulness_score"] = 3
    return review


def test_exactly_bound_review_can_source_proof_post_hoc_claims():
    bundle = _bundle(2)
    review = _labelled(bundle)
    report = assess_independently_labelled_bundle(bundle, review)
    assert report["constructed_cases"] == 2
    assert report["reviewed_sentences"] == 2
    assert report["host_proven_labelled_claims"] == 2
    assert report["host_unproven_labelled_claims"] == 0
    assert report["mean_reviewer_clarity_score"] == 4
    assert report["mean_reviewer_usefulness_score"] == 3
    assert not report["post_generation_reviewer_independence_authenticated"]
    assert not report["semantic_exhaustiveness_proven"]
    assert not report["publisher_approval"]


def test_annotated_false_physical_outcome_is_not_host_proven():
    bundle = _bundle(1)
    review = _labelled(bundle)
    row = review["cases"][0]["sentences"][0]
    fact_id = row["reference_atoms"][0]["fact_ids"][0]
    row["reference_atoms"].append({
        "proposition": "physical_effect",
        "fact_ids": [fact_id],
        "limit": None,
    })
    report = assess_independently_labelled_bundle(bundle, review)
    assert report["high_risk_labelled_claims"] == 1
    assert report["high_risk_unproven_claims"] == 1
    assert report["host_unproven_labelled_claims"] == 1
    assert "physical_effect" not in json.dumps(report)


@pytest.mark.parametrize("tamper", ["hash", "missing", "unknown_id", "duplicates",
                                    "unrated", "more", "shape"])
def test_incomplete_forged_or_duplicated_labels_fail_closed(tamper):
    bundle = _bundle(2)
    review = _labelled(bundle)
    row = review["cases"][0]["sentences"][0]
    if tamper == "hash":
        review["cases"][0]["packet_sha256"] = "0" * 64
    elif tamper == "missing":
        review["cases"][1]["sentences"].clear()
    elif tamper == "unknown_id":
        row["reference_atoms"][0]["fact_ids"] = ["f999"]
    elif tamper == "duplicates":
        row["reference_atoms"].append(deepcopy(row["reference_atoms"][0]))
    elif tamper == "unrated":
        row["clarity_score"] = None
    elif tamper == "more":
        row["reference_atoms"] = row["reference_atoms"] * 6
    else:
        row["unsafe"] = True
    with pytest.raises((ValueError, TypeError, KeyError)):
        assess_independently_labelled_bundle(bundle, review)


def test_changed_prose_or_source_after_freeze_rejected():
    bundle = _bundle(1)
    review = _labelled(bundle)
    bundle["cases"][0]["draft"]["sections"][0]["sentences"][0]["text"] += " Altered."
    with pytest.raises(ValueError, match="frozen"):
        assess_independently_labelled_bundle(bundle, review)


def test_template_never_autofills_semantic_claims():
    bundle = _bundle(4)
    tpl = make_review_template(bundle)
    assert len(tpl["cases"]) == 4
    assert all(row["reference_atoms"] == [] and row["clarity_score"] is None
               for c in tpl["cases"] for row in c["sentences"])
    with pytest.raises(ValueError, match="incomplete"):
        assess_independently_labelled_bundle(bundle, tpl)


def test_private_cli_and_reports_do_not_publish_raw_prose(tmp_path, capsys):
    bundle = _bundle(1)
    source = tmp_path / "private-bundle.json"
    _private_save(str(source), bundle["cases"])
    template_path = tmp_path / "private-template.json"
    assert main(["--bundle", str(source), "--template", str(template_path)]) == 0
    assert template_path.stat().st_mode & 0o777 == 0o600
    assert "A source record is present" not in capsys.readouterr().out
    review = _labelled(_load_private(str(source)))
    review_path = tmp_path / "private-annotations.json"
    review_path.write_text(json.dumps(review))
    assert main(["--bundle", str(source), "--review", str(review_path)]) == 0
    report = capsys.readouterr().out
    assert "A source record is present" not in report
    assert "Synthetic Controller" not in report
    assert "physical_effect" not in report
    assert json.loads(report)["publisher_approval"] is False
    with pytest.raises(SystemExit) as error:
        main(["--bundle", str(source), "--template", str(template_path)])
    assert error.value.code == 1


def test_github_cloud_workflow_is_manual_explicit_consent_no_artifact():
    workflow = (ROOT.parent / ".github" / "workflows" /
                "stage4m-manual-ollama-cloud.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "\npush:" not in workflow
    assert "\npull_request:" not in workflow
    assert "confirm_billing:" in workflow
    assert "confirm_synthetic_only:" in workflow
    assert "default: false" in workflow
    assert "secrets.OLLAMA_API_KEY" in workflow
    assert "environment: ollama-cloud-evaluation" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "--ack-cloud-billing" in workflow
    assert "--ack-constructed-data-only" in workflow
    assert "--case-limit" in workflow
    assert "upload-artifact" not in workflow
    assert "--private-output" not in workflow
    assert "hubitat-mcp-ai" in workflow


def test_no_stage4m_import_in_active_production_runtime():
    for filename in ("app.py", "mcp_agent_orchestrator.py",
                     "final_answer_coordinator.py", "causal_claim_publication.py"):
        content = (ROOT / "rootfs" / "app" / filename).read_text()
        assert "stage4m_private_postgeneration_review" not in content
