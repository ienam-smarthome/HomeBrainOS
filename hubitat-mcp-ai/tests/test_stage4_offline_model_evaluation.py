"""Stage 4C: real-model-capable OFFLINE runner, with fake transports in CI.

These checks DO NOT run real LLMs. No misleading genuine reviewer accuracy
claims can be inferred from constructed response fixtures.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
from urllib.error import HTTPError

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "rootfs" / "app"))
sys.path.insert(0, str(PACKAGE / "tools"))

from stage4_offline_model_evaluation import run_stage4c_offline_model_evaluation
from stage4c_local_model_eval import LoopbackOllama, _constructed_cases, main


class MockModel:
    def __init__(self, cases):
        self.calls = []
        self.expected = {}
        for case in cases:
            sent = case["draft"]["sections"][0]["sentences"][0]["text"]
            self.expected[sent] = (
                "entailed" if case["oracle"][0] == "entailed" else "insufficient"
            )

    def __call__(self, model, request):
        self.calls.append((model, deepcopy(request)))
        assert "oracle" not in json.dumps(request)
        assert "trace_origin" not in json.dumps(request)
        assert "case_id" not in json.dumps(request)
        if request["task"] == "review":
            return {
                "schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [
                    {
                        "sentence_id": sentence["sentence_id"],
                        "verdict": self.expected.get(sentence["text"], "insufficient"),
                        "supporting_fact_ids": (
                            list(sentence["cited_fact_ids"])
                            if self.expected.get(sentence["text"]) == "entailed" else []
                        ),
                    }
                    for sentence in request["sentences"]
                ],
            }
        raise AssertionError("unexpected author")


def test_eight_domain_reference_cases_validate_only_when_model_is_actually_invoked():
    cases = _constructed_cases()
    before = deepcopy(cases)
    stub = MockModel(cases)
    result = run_stage4c_offline_model_evaluation(
        cases, reviewer_models=("reviewer-one:3b", "reviewer-two:4b"),
        invoke=stub,
    )
    assert result["case_count"] == 8
    assert result["model_invocations_attempted"] == 16
    assert len(stub.calls) == 16
    assert result["completed_review_sets"] == 8
    assert result["reference_scored_cases"] == 8
    assert result["reference_scored_sentences"] == 8
    assert result["reference_unsupported_sentences"] == 4
    assert result["false_accept_count"] == 0
    assert result["false_reject_count"] == 0
    assert result["false_accept_rate"] == 0.0
    assert result["false_reject_rate"] == 0.0
    assert result["safe_to_publish"] is False
    assert result["semantic_ground_truth_independently_verified"] is False
    assert result["live_homebrain_evaluation_performed"] is False
    assert cases == before


def test_a_wrong_but_agreeing_pair_is_measured_as_false_acceptance():
    cases = _constructed_cases()
    stub = MockModel(cases)
    original = stub.__call__
    def wrong(model, request):
        resp = original(model, request)
        if request["sentences"][0]["text"] == (
            "The boiler fired and every radiator valve opened."):
            resp["assessments"][0]["verdict"] = "entailed"
            resp["assessments"][0]["supporting_fact_ids"] = (
                list(request["sentences"][0]["cited_fact_ids"]))
        return resp
    report = run_stage4c_offline_model_evaluation(
        cases, reviewer_models=("reviewer-one", "reviewer-two"),
        invoke=wrong,
    )
    assert report["false_accept_count"] == 1
    assert report["false_accept_rate"] == 0.25
    assert report["safe_to_publish"] is False


def test_wrong_rejection_is_counted_separately_from_false_acceptance():
    cases = _constructed_cases()
    stub = MockModel(cases)
    def wrong(model, request):
        response = stub(model, request)
        if request["sentences"][0]["text"] == (
            "The source recorded a brightness command."):
            response["assessments"][0]["verdict"] = "insufficient"
            response["assessments"][0]["supporting_fact_ids"] = []
        return response
    score = run_stage4c_offline_model_evaluation(
        cases, reviewer_models=("a", "b"), invoke=wrong)
    assert score["false_accept_count"] == 0
    assert score["false_reject_count"] == 1
    assert score["false_reject_rate"] == 0.25


def test_generated_answer_requires_new_independent_oracle_and_never_inherits_labels():
    case = _constructed_cases()[0]
    expected = deepcopy(case["draft"])
    case.pop("draft")
    case.pop("oracle")
    seen = []
    def author_and_review(model, request):
        seen.append((model, deepcopy(request)))
        if request["task"] == "author":
            assert "packet" in request
            return deepcopy(expected)
        assert request["task"] == "review"
        return {
            "schema": "homebrain-stage4b-semantic-review.v1",
            "assessments": [
                {"sentence_id": row["sentence_id"], "verdict": "entailed",
                 "supporting_fact_ids": list(row["cited_fact_ids"])}
                for row in request["sentences"]
            ],
        }
    result = run_stage4c_offline_model_evaluation(
        [case], author_model="author",
        reviewer_models=("reviewer-1", "reviewer-2"), invoke=author_and_review)
    assert len(seen) == 3
    assert [model for model, _ in seen] == ["author", "reviewer-1", "reviewer-2"]
    assert result["author_invocations_attempted"] == 1
    assert result["author_responses_received"] == 1
    assert result["reference_scored_cases"] == 0
    assert result["reference_scored_sentences"] == 0
    assert result["false_accept_rate"] is None
    assert result["generated_or_unlabelled_sentences_unscored"] == 1
    assert result["reviewer_concordant_entailed_sentences"] == 1
    assert result["author_or_reviewer_model_quality_proven"] is False


def test_reference_labels_cannot_be_supplied_for_newly_authored_draft():
    case = _constructed_cases()[0]
    case.pop("draft")
    with pytest.raises(ValueError, match="pre-labelled oracle"):
        run_stage4c_offline_model_evaluation(
            [case], author_model="writer",
            reviewer_models=("reviewer-a", "reviewer-b"),
            invoke=lambda *_: {},
        )


def test_bad_author_output_cannot_trigger_reviewers_or_publish():
    case = _constructed_cases()[0]
    case.pop("draft")
    case.pop("oracle")
    calls = []
    def wrong(model, request):
        calls.append(model)
        return {"schema": "improperly-authored"}
    report = run_stage4c_offline_model_evaluation(
        [case], author_model="writer", reviewer_models=("reviewer-a", "reviewer-b"),
        invoke=wrong)
    assert calls == ["writer"]
    assert report["typed_drafts_invalid"] == 1
    assert report["review_calls_attempted"] == 0
    assert report["completed_review_sets"] == 0
    assert report["safe_to_publish"] is False


def test_invalid_or_failed_review_cannot_be_recorded_as_success():
    cases = _constructed_cases()[:1]
    def invalid(model, request):
        if model == "reviewer-2":
            raise RuntimeError("PRIVATE-HOUSEHOLD-EXCEPTION-CONTENT")
        return {"schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": []}
    report = run_stage4c_offline_model_evaluation(
        cases, reviewer_models=("reviewer-1", "reviewer-2"), invoke=invalid)
    assert report["completed_review_sets"] == 0
    assert report["invalid_or_incomplete_review_sets"] == 1
    assert report["reference_scored_cases"] == 0
    assert report["false_accept_rate"] is None
    assert "PRIVATE-HOUSEHOLD" not in json.dumps(report)


@pytest.mark.parametrize("models,author", [
    (("same", "same"), None),
    (("qwen3:4b-cloud", "local"), None),
    (("http://remote", "local"), None),
    (("review-a", "review-b"), "review-a"),
    (("review-a", "review-b"), "qwen3:4b-cloud"),
])
def test_local_model_separation_fail_closed(models, author):
    with pytest.raises(ValueError):
        run_stage4c_offline_model_evaluation(
            [_constructed_cases()[0]], reviewer_models=models,
            author_model=author, invoke=lambda *_: {},
        )


def test_case_bounds_and_owner_supplied_provenance_are_not_authentication():
    cases = _constructed_cases()
    cases[0]["trace_origin"] = "owner-labelled-redacted"
    result = run_stage4c_offline_model_evaluation(
        cases[:1], reviewer_models=("a", "b"), invoke=MockModel(cases))
    assert result["semantic_ground_truth_independently_verified"] is False
    assert result["reference_labels_user_supplied_not_authenticated"]
    with pytest.raises(ValueError, match="bounded"):
        run_stage4c_offline_model_evaluation(
            cases * 2, reviewer_models=("a", "b"), invoke=lambda *_: {},
        )
    cases = _constructed_cases()
    cases[0]["trace_origin"] = "independently-certified-real"
    with pytest.raises(ValueError, match="unlabelled"):
        run_stage4c_offline_model_evaluation(
            cases[:1], reviewer_models=("a", "b"), invoke=lambda *_: {},
        )


def test_different_reviewers_cannot_reuse_a_hidden_oracle_or_share_an_answer():
    cases = _constructed_cases()[:1]
    invocations = []
    def stub(model, request):
        invocations.append((model, deepcopy(request)))
        return {"schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [
                    {"sentence_id": r["sentence_id"], "verdict": "entailed",
                     "supporting_fact_ids": list(r["cited_fact_ids"])}
                    for r in request["sentences"]
                ]}
    run_stage4c_offline_model_evaluation(
        cases, reviewer_models=("independent-a", "independent-b"), invoke=stub)
    assert [m for m, _ in invocations] == ["independent-a", "independent-b"]
    assert invocations[0][1] == invocations[1][1]
    assert "assessments" not in json.dumps(invocations[1][1])
    assert "oracle" not in json.dumps(invocations)


def test_demo_inputs_are_synthetic_and_never_include_live_names():
    examples = _constructed_cases()
    assert len(examples) == 8
    assert all(c["trace_origin"] == "constructed-fixture" for c in examples)
    assert {c["domain"] for c in examples} == {
        "lighting", "heating", "ventilation", "history"}
    assert "Bedroom 1" not in json.dumps(examples)
    assert "192.168." not in json.dumps(examples)


def test_cli_without_both_flags_never_opens_private_file(tmp_path):
    missing = tmp_path / "private-sensitive-secret.json"
    run = subprocess.run([
        sys.executable, str(PACKAGE / "tools" / "stage4c_local_model_eval.py"),
        "--input", str(missing),
        "--reviewer-1", "a", "--reviewer-2", "b",
    ], capture_output=True, text=True, check=False)
    assert run.returncode == 2
    assert not run.stdout
    assert "flags required" in run.stderr
    assert "sensitive-secret" not in run.stderr


def test_loopback_client_rejects_model_cloud_and_invalid_port_without_network():
    with pytest.raises(ValueError):
        LoopbackOllama(port=0)
    cli = LoopbackOllama()
    assert cli._url == "http://127.0.0.1:11434/api/chat"
    assert type(cli._opener).__name__ == "OpenerDirector"
    with pytest.raises(ValueError, match="model"):
        cli("qwen:4b-cloud", {"task": "review"})


def test_cli_local_transport_uses_json_and_rejects_redirects(monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self, limit):
            return json.dumps({"message": {"content": json.dumps({
                "schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": []})}}).encode()
    class Opener:
        def open(self, req, timeout):
            assert req.full_url == "http://127.0.0.1:11434/api/chat"
            body = json.loads(req.data)
            assert body["model"] == "local-review:3b"
            assert body["stream"] is False and body["format"] == "json"
            assert body["options"]["temperature"] == 0
            return Response()
    cli = LoopbackOllama()
    cli._opener = Opener()
    answer = cli("local-review:3b", {
        "task": "review", "instructions": "Return JSON.",
        "sentences": [], "source_facts_may_be_truncated": False,
    })
    assert answer["schema"] == "homebrain-stage4b-semantic-review.v1"
    assert cli.succeeded == 1


def test_cli_demo_with_mocked_local_model_prints_only_private_aggregates(monkeypatch, capsys):
    examples = _constructed_cases()
    class Stub:
        def __init__(self, **kwargs):
            self.original = MockModel(examples)
        def __call__(self, *args):
            return self.original(*args)
    monkeypatch.setattr("stage4c_local_model_eval.LoopbackOllama", Stub)
    status = main([
        "--demo-constructed", "--reviewer-1", "a", "--reviewer-2", "b",
        "--enable-local-inference", "--ack-local-data-processing",
    ])
    captured = capsys.readouterr()
    assert status == 0
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["reference_scored_cases"] == 8
    assert report["false_accept_count"] == 0
    assert "Synthetic Controller" not in captured.out
    assert "contact" not in captured.out
    assert '"101"' not in captured.out


def test_cli_failure_does_not_log_exceptions_or_private_data(monkeypatch, capsys):
    class Stub:
        def __init__(self, **kwargs): pass
        def __call__(self, *args):
            raise RuntimeError("SECRET-SENSOR-LOCATION-and-authentication")
    monkeypatch.setattr("stage4c_local_model_eval.LoopbackOllama", Stub)
    status = main([
        "--demo-constructed", "--reviewer-1", "a", "--reviewer-2", "b",
        "--enable-local-inference", "--ack-local-data-processing",
    ])
    captured = capsys.readouterr()
    assert status == 2 and captured.out == ""
    assert "SECRET-SENSOR-LOCATION" not in captured.err


def test_active_agent_and_publisher_do_not_import_stage4c_code():
    root = PACKAGE / "rootfs" / "app"
    for filename in ("mcp_agent_orchestrator.py", "final_answer_coordinator.py",
                     "causal_claim_publication.py", "app.py"):
        assert "stage4_offline_model_evaluation" not in (root / filename).read_text()
