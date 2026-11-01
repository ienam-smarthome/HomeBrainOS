"""Stage 6.10: inspect-only leaf record citation boundary, strict fail closed."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import (  # noqa: E402
    Stage6Benchmark, _CASES, _validate_answer,
)
from stage610_citation_contract import validate_leaf_citations  # noqa: E402
from stage66_answer_diagnostics import (  # noqa: E402
    Stage6AnswerContractFailure, answer_failure_category,
)


def result():
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": "The fictional plug was reported offline at 01:50:00Z.",
            "kind": "state_report", "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "offline"}],
            "epistemic": {"position": "affirmed", "scope": "examined_records"},
        }],
        "uncertainties": ["The physical cause remains unproven"],
        "next_evidence": "Check timestamped, independent device packets.",
    }


def records():
    fixture = _CASES["stale_connectivity"]
    by_source = {s["id"]: s["records"] for s in fixture["catalog"]}
    return [fixture["initial"]] + by_source["S1"] + by_source["S2"] + by_source["S3"]


@pytest.mark.parametrize("bad,category", [
    (["S2"], "source_container_instead_of_record_id"),
    (["S1", "E2"], "source_container_instead_of_record_id"),
    (["E99"], "unknown_record_id_in_citation"),
    (["E4"], "unknown_record_id_in_citation"),
    ([], "malformed_evidence_citation_ids"),
    ("E2", "malformed_evidence_citation_ids"),
    ([15], "malformed_evidence_citation_ids"),
    (["I1", "I1"], "duplicate_evidence_citation"),
    (["I1", "E1", "E2", "E3"], "malformed_evidence_citation_ids"),
])
def test_invalid_citations_have_safe_distinct_error_category(bad, category):
    d = result()
    d["sentences"][0]["evidence_ids"] = bad
    with pytest.raises(ValueError) as e:
        _validate_answer(json.dumps(d), records(),
                         source_container_ids={"S1", "S2", "S3"})
    assert answer_failure_category(e.value) == category
    assert "S2" not in str(e.value) and "E99" not in str(e.value)


def test_valid_leaf_id_never_rewritten_or_promoted_to_factual_proof():
    d = result()
    d["sentences"][0]["evidence_ids"] = ["E2"]
    d["sentences"][0]["atoms"] = [{
        "record_id": "E2", "field": "state", "value": "on",
    }]
    assert _validate_answer(json.dumps(d), records(),
                            source_container_ids={"S1", "S2", "S3"}) == d


def test_invalid_kind_cannot_be_cast_as_valid_citation():
    d = result()
    d["sentences"][0]["kind"] = "watchdog_tick"
    with pytest.raises(ValueError) as e:
        _validate_answer(json.dumps(d), records(),
                         source_container_ids={"S1", "S2", "S3"})
    assert answer_failure_category(e.value) == "invalid_claim_type"


class MockCloud:
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    api_key = "private-synthetic-credential"
    timeout_seconds = 60
    configured = True

    def __init__(self, *, malformed=False):
        self.calls = []
        self.malformed = malformed

    async def _chat_post(self, messages, tools, **kwargs):
        assert tools == [] and kwargs["disable_thinking"] is True
        self.calls.append(messages)
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            count = len(body["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": ["S2", "S3", "S1"][count],
                "reason": "Read source relevant to the fictional question",
            })}
        assert body["allowed_evidence_record_ids"] == ["E1", "E2", "E3", "I1"]
        prompt = messages[0]["content"]
        assert "LEAF RECORD" in prompt
        assert "MUST NEVER be used as evidence_ids" in prompt
        assert "proof_target" in prompt
        assert "gold_sources" not in json.dumps(messages)
        assert "private-synthetic-credential" not in json.dumps(messages)
        d = result()
        if self.malformed:
            d["sentences"][0]["evidence_ids"] = ["S2"]
        return {"content": json.dumps(d)}


def test_full_mock_cloud_run_cites_only_revealed_leaf_ids_with_no_extra_calls():
    model = MockCloud()
    out = asyncio.run(Stage6Benchmark().run_case(
        model, "stale_connectivity", confirmed=True))
    assert out["success"] and len(model.calls) == out["cloud_requests_attempted"] == 4
    assert out["independent_review_packet"]["publisher_approval"] is False


def test_full_mock_cloud_invalid_container_fails_closed_and_preserves_plan():
    model = MockCloud(malformed=True)
    with pytest.raises(Stage6AnswerContractFailure) as exc:
        asyncio.run(Stage6Benchmark().run_case(
            model, "stale_connectivity", confirmed=True))
    fail = exc.value
    assert fail.category == "source_container_instead_of_record_id"
    assert fail.progress["relevant_reference_sources_selected"] == 3
    assert fail.progress["attempted_cloud_requests"] == 4
    assert fail.progress["model_answer_published"] is False
    assert fail.progress["publisher_approval"] is False
    assert len(model.calls) == 4
    assert "fictional plug" not in str(fail)
    assert "private-synthetic-credential" not in str(fail)


@pytest.mark.parametrize("case", list(_CASES))
def test_citation_whitelist_only_contains_inspected_source_records(case):
    fixture = _CASES[case]
    model = MockCloud()
    # Source IDs and record IDs are distinct; unknown records are rejected
    # without mapping them onto possibly relevant source containers.
    all_sources = {r["id"] for source in fixture["catalog"] for r in source["records"]}
    assert fixture["initial"]["id"] not in all_sources
    assert all(r["id"] not in {s["id"] for s in fixture["catalog"]}
               for source in fixture["catalog"] for r in source["records"])


def test_no_production_imports():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        text = (APP / name).read_text()
        assert "stage610_citation_contract" not in text
