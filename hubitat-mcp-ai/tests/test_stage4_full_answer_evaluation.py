"""Stage 4G: mocked model calls to test real-model runner safety, NOT accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from stage4g_github_authored_answers import (
    _synthetic_author_cases, _author_schema, Stage4GAuthorOllama,
    evaluate_stage4g_authored_answers, summary_markdown, main,
)
from stage4_full_answer_evaluation import (
    stage4g_authoring_prompt, validate_stage4g_proposal,
)


class FakeModels:
    def __init__(self):
        self.calls = []

    def __call__(self, model, job):
        self.calls.append((model, deepcopy(job)))
        if job["task"] == "author":
            assert model == "qwen2.5:3b"
            assert "required_fact_ids" not in json.dumps(job)
            assert "oracle" not in json.dumps(job)
            packet = job["packet"]
            # One self-written sentence per scoped canonical source fact.
            rows = [{
                "text": (
                    "The cited record reports a source observation or command; "
                    "this does not prove an unobserved physical action."
                ),
                "fact_ids": [f["fact_id"]],
            } for f in packet["facts"]]
            return {
                "schema": "homebrain-stage4g-authored-proposal.v1",
                "sections": [{"name": "summary", "sentences": rows}],
            }
        if job["task"] == "review":
            assert model in ("qwen2.5:3b", "llama3.2:3b")
            assert "required_fact_ids" not in json.dumps(job)
            assert "oracle" not in json.dumps(job)
            assert len(job["sentences"]) == 1
            row = job["sentences"][0]
            # Any original s002/s003 author sentence is renumbered for the
            # isolated Stage 4E reviewer schema without changing source/text.
            assert row["sentence_id"] == "s001"
            return {
                "schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [{
                    "sentence_id": row["sentence_id"], "verdict": "entailed",
                    "supporting_fact_ids": list(row["cited_fact_ids"]),
                }],
            }
        raise AssertionError("not a valid test task")


def _run(cases, fake):
    return evaluate_stage4g_authored_answers(
        cases, author_model="qwen2.5:3b",
        reviewer_models=("qwen2.5:3b", "llama3.2:3b"),
        invoke=fake,
    )


def test_four_constructed_domains_have_relevant_independent_coverage_targets():
    cases = _synthetic_author_cases()
    assert [c["domain"] for c in cases] == [
        "lighting", "heating", "ventilation", "history"]
    assert len(cases[-1]["required_fact_ids"]) == 2
    assert sum(len(x["required_fact_ids"]) for x in cases) == 5
    assert all(x["packet"]["shadow_only"] for x in cases)
    assert all(x["packet"]["source_history_complete"] is False for x in cases)
    assert "Bedroom 1" not in json.dumps(cases)


def test_full_answer_generation_measures_host_fact_coverage_without_publishing():
    cases = _synthetic_author_cases()
    original = deepcopy(cases)
    fake = FakeModels()
    output = _run(cases, fake)
    assert cases == original
    assert output["author_calls_attempted"] == 4
    assert output["author_model_responses_received"] == 4
    assert output["author_source_valid_proposals"] == 4
    assert output["expected_source_fact_count"] == 5
    assert output["independent_expected_facts_cited"] == 5
    assert output["independent_source_fact_coverage"] == 1.0
    assert output["authored_sentences"] == 5
    assert output["review_calls_attempted"] == 10
    assert output["sentences_with_two_valid_reviews"] == 5
    assert output["cases_with_complete_reviews"] == 4
    assert len(fake.calls) == 14
    assert output["publication_authorised"] is False
    assert output["generated_prose_has_no_independent_sentence_oracle"] is True
    assert output["human_quality_or_naturalness_measured"] is False
    assert output["actual_homebrain_investigation_tested"] is False


def test_host_projects_exact_claims_but_model_did_not_author_them():
    case = _synthetic_author_cases()[0]
    fact = case["packet"]["facts"][0]
    response = {
        "schema": "homebrain-stage4g-authored-proposal.v1",
        "sections": [{
            "name": "summary",
            "sentences": [{"text": "The evidence records a brightness command.",
                           "fact_ids": [fact["fact_id"]]}],
        }],
    }
    draft = validate_stage4g_proposal(response, case["packet"])
    assert draft is not None
    claim = draft["sections"][0]["sentences"][0]["claims"][0]
    for field in ("entity_id", "value", "time_utc", "issuer_app_id"):
        assert claim[field] == fact[field]
    assert "claims" not in json.dumps(response)


def test_unsupported_causal_prose_with_valid_citation_is_not_attested():
    case = _synthetic_author_cases()[1]
    fact = case["packet"]["facts"][0]
    draft = validate_stage4g_proposal({
        "schema": "homebrain-stage4g-authored-proposal.v1",
        "sections": [{"name": "summary", "sentences": [{
            "text": "Every radiator valve definitely physically opened.",
            "fact_ids": [fact["fact_id"]],
        }]}],
    }, case["packet"])
    # Source-ID correctness cannot prove this sentence or physical ACK.
    assert draft is not None
    assert draft["sections"][0]["sentences"][0]["text"].startswith("Every")
    out = _run(_synthetic_author_cases(), FakeModels())
    assert not out["publication_authorised"]
    assert out["independent_fact_coverage_is_not_prose_truth"]


@pytest.mark.parametrize("tamper", [
    lambda p: p.update({"schema": "untrusted"}),
    lambda p: p["sections"][0]["sentences"][0].update({"fact_ids": ["f999"]}),
    lambda p: p["sections"][0]["sentences"][0].update({"text": ""}),
    lambda p: p["sections"][0]["sentences"][0].update({"extra": True}),
    lambda p: p["sections"].append({"name": "evidence", "sentences": []}),
])
def test_invalid_author_output_rejected_instead_of_silently_rewritten(tamper):
    case = _synthetic_author_cases()[0]
    f = case["packet"]["facts"][0]
    proposal = {
        "schema": "homebrain-stage4g-authored-proposal.v1",
        "sections": [{"name": "summary", "sentences": [
            {"text": "A command is recorded.", "fact_ids": [f["fact_id"]]}
        ]}],
    }
    tamper(proposal)
    assert validate_stage4g_proposal(proposal, case["packet"]) is None


def test_invalid_model_proposals_do_not_trigger_any_review():
    calls = []
    def bad(model, request):
        calls.append(request["task"])
        return {"schema": "invalid"}
    out = _run(_synthetic_author_cases(), bad)
    assert calls == ["author"] * 4
    assert out["author_invalid_proposals"] == 4
    assert out["review_calls_attempted"] == 0
    assert out["independent_source_fact_coverage"] == 0.0
    assert out["publication_authorised"] is False


def test_missing_and_malformed_review_votes_fail_closed():
    fake = FakeModels()
    def bad(model, job):
        if job["task"] == "review" and model == "llama3.2:3b":
            return {"schema": "bad"}
        return fake(model, job)
    out = _run(_synthetic_author_cases(), bad)
    assert out["author_source_valid_proposals"] == 4
    assert out["cases_with_complete_reviews"] == 0
    assert out["invalid_reviewer_responses"] == 5
    assert out["sentences_with_two_valid_reviews"] == 0
    assert out["publication_authorised"] is False


def test_different_reviewer_verdicts_report_disagreements_without_winner():
    fake = FakeModels()
    def disagree(model, job):
        if job["task"] == "review" and model == "llama3.2:3b":
            row = job["sentences"][0]
            return {
                "schema": "homebrain-stage4b-semantic-review.v1",
                "assessments": [{"sentence_id": row["sentence_id"],
                                 "verdict": "insufficient",
                                 "supporting_fact_ids": []}],
            }
        return fake(model, job)
    out = _run(_synthetic_author_cases(), disagree)
    assert out["reviewer_disagreement_sentences"] == 5
    assert out["both_reviewers_propose_supported"] == 0
    assert out["publication_authorised"] is False


def test_independent_fact_coverage_is_not_sent_to_any_model():
    fake = FakeModels()
    _run(_synthetic_author_cases(), fake)
    for model, request in fake.calls:
        s = json.dumps(request)
        for forbidden in ("required_fact_ids", "coverage_oracle",
                          "reference_scored_sentences", "gold_label"):
            assert forbidden not in s


def test_host_author_schema_does_not_embed_example_answer_or_prechoose_text():
    case = _synthetic_author_cases()[0]
    schema = _author_schema(case["packet"])
    assert schema["properties"]["schema"]["const"] == (
        "homebrain-stage4g-authored-proposal.v1")
    row = schema["properties"]["sections"]["items"]["properties"]["sentences"]["items"]
    assert row["properties"]["fact_ids"]["items"]["enum"] == [
        case["packet"]["facts"][0]["fact_id"]]
    assert row["properties"]["text"]["type"] == "string"
    assert "default" not in json.dumps(schema)
    assert "Do NOT invent causes" in stage4g_authoring_prompt()


def test_actual_author_transport_is_local_and_uses_source_bound_json_schema():
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self, limit):
            return json.dumps({"message": {"content": json.dumps({
                "schema": "homebrain-stage4g-authored-proposal.v1",
                "sections": [{"name": "summary", "sentences": [
                    {"text": "The source records a command.", "fact_ids": ["f001"]}
                ]}],
            })}}).encode()
    class Open:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/chat"
            body = json.loads(request.data)
            assert body["model"] == "qwen2.5:3b"
            assert body["stream"] is False
            assert body["format"]["properties"]["sections"]["minItems"] == 1
            assert "required_fact_ids" not in body["messages"][1]["content"]
            return Response()
    client = Stage4GAuthorOllama()
    client._opener = Open()
    case = _synthetic_author_cases()[0]
    x = client("qwen2.5:3b", {
        "task": "author", "instructions": stage4g_authoring_prompt(),
        "question": case["question"], "packet": case["packet"],
    })
    assert x["schema"] == "homebrain-stage4g-authored-proposal.v1"
    assert client.attempted == client.succeeded == 1


def test_only_private_aggregates_leave_runner():
    report = _run(_synthetic_author_cases(), FakeModels())
    output = json.dumps(report) + summary_markdown(report)
    for private in ("The source", "The cited record", "Synthetic Controller",
                    "2026-01-01", '"101"', "fact_id", "f001",
                    "question", "case_id", "source_event"):
        assert private not in output
    assert "Stage 4G" in output


def test_cli_consent_and_github_only(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert main([]) == 2
    assert "consent" in capsys.readouterr().err
    assert main(["--ack-github-synthetic-local-inference"]) == 2
    assert "loopback GitHub-only" in capsys.readouterr().err


def test_cli_fake_models_print_only_aggregate_summary(monkeypatch, tmp_path, capsys):
    class Models:
        def __init__(self, **kwargs):
            self.fake = FakeModels()
            self.author = type("A", (), {"attempted": 4})()
            self.reviewer = type("R", (), {"attempted": 10})()
        def __call__(self, model, req): return self.fake(model, req)
        @property
        def requests_attempted(self): return 14
    monkeypatch.setattr("stage4g_github_authored_answers.Stage4GLocalModels", Models)
    for name, value in (("GITHUB_ACTIONS", "true"), ("OLLAMA_NO_CLOUD", "1"),
                        ("OLLAMA_HOST", "127.0.0.1:11434"),
                        ("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))):
        monkeypatch.setenv(name, value)
    assert main(["--ack-github-synthetic-local-inference"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["authored_sentences"] == 5
    assert (tmp_path / "summary.md").is_file()


def test_workflow_is_readonly_and_no_active_publisher_import():
    path = ROOT.parent / ".github/workflows/stage4g-authored-answer-evaluation.yml"
    wf = path.read_text()
    assert "permissions:\n  contents: read" in wf
    assert "persist-credentials: false" in wf
    assert "OLLAMA_NO_CLOUD: '1'" in wf
    assert "OLLAMA_HOST: '127.0.0.1:11434'" in wf
    assert "pull_request_target" not in wf
    assert "upload-artifact@" not in wf
    assert "${{ secrets." not in wf
    for name in ("mcp_agent_orchestrator.py", "final_answer_coordinator.py",
                 "causal_claim_publication.py", "app.py"):
        assert "stage4_full_answer_evaluation" not in (
            ROOT / "rootfs" / "app" / name).read_text()
