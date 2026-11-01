"""Stage 6.11: exact JSON-array citation guidance and strict regression.

All cases fictional; 4-request Cloud transport mocked; no runtime device APIs.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import _CASES, _validate_answer, Stage6Benchmark  # noqa: E402
from stage66_answer_diagnostics import Stage6AnswerContractFailure  # noqa: E402


def valid_answer():
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": "The initial focal observation is a reported state.",
            "kind": "state_report", "evidence_ids": ["I1"], "atoms": [],
            "epistemic": {"position": "affirmed", "scope": "examined_records"},
        }],
        "uncertainties": ["Physical outcomes cannot be established from the records"],
        "next_evidence": "Check independent device packet and execution evidence.",
    }


@pytest.mark.parametrize("bad_ids", [
    "E2", "E1,E2", [], None, 12, {}, ["E1", "E2", "E3", "I1"],
    [1], [True], [""], ["I1", ""], ["I1", None],
])
def test_malformed_evidence_id_shapes_rejected_without_coercion(bad_ids):
    answer = valid_answer()
    answer["sentences"][0]["evidence_ids"] = bad_ids
    with pytest.raises(ValueError, match="malformed evidence citation identifiers"):
        _validate_answer(json.dumps(answer), [_CASES["stale_connectivity"]["initial"]])


def test_duplicate_ids_still_rejected():
    answer = valid_answer()
    answer["sentences"][0]["evidence_ids"] = ["I1", "I1"]
    with pytest.raises(ValueError, match="duplicate evidence citation"):
        _validate_answer(json.dumps(answer), [_CASES["stale_connectivity"]["initial"]])


def test_one_id_and_three_distinct_ids_are_accepted_when_seen():
    answer = valid_answer()
    fixture = _CASES["stale_connectivity"]
    records = [fixture["initial"]] + [r for s in fixture["catalog"]
                if s["id"] in {"S1", "S2"} for r in s["records"]]
    assert _validate_answer(json.dumps(answer), records) == answer
    answer["sentences"][0]["evidence_ids"] = ["I1", "E1", "E2"]
    assert _validate_answer(json.dumps(answer), records) == answer


def test_source_containers_never_repaired_to_record_ids():
    answer = valid_answer()
    answer["sentences"][0]["evidence_ids"] = ["S2"]
    with pytest.raises(ValueError, match="source container used as evidence citation"):
        _validate_answer(json.dumps(answer), [_CASES["stale_connectivity"]["initial"]],
                         source_container_ids={"S1", "S2", "S3"})


class MockCloud:
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    api_key = "synthetic-private-credential"
    timeout_seconds = 60
    configured = True

    def __init__(self, failure=False):
        self.calls = []
        self.failure = failure

    async def _chat_post(self, messages, tools, **kwargs):
        assert tools == [] and kwargs["disable_thinking"] is True
        self.calls.append(messages)
        message_json = json.dumps(messages)
        assert "synthetic-private-credential" not in message_json
        assert "gold_sources" not in message_json
        body = json.loads(messages[1]["content"])
        if "remaining_source_titles" in body:
            index = len(body["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": ["S2", "S3", "S1"][index],
                "reason": "Read an independent source to address the objective",
            })}
        system = messages[0]["content"]
        assert "evidence_ids MUST be a JSON ARRAY of 1 to 3" in system
        assert "Prefer exactly ONE ID" in system
        assert "use 2-3 only when the sentence relates multiple records" in system
        assert "do not copy it into the incident explanation" in system
        sample = ('{"text":"A source report was recorded.",'
                  '"kind":"state_report","evidence_ids":["I1"],'
                  '"atoms":[],"epistemic":{"position":"affirmed",'
                  '"scope":"examined_records"}}')
        assert sample in system
        assert body["allowed_evidence_record_ids"] == ["E1", "E2", "E3", "I1"]
        response = valid_answer()
        if self.failure:
            response["sentences"][0]["evidence_ids"] = "I1"
        return {"content": json.dumps(response)}


@pytest.mark.parametrize("case", list(_CASES))
def test_all_three_fictional_scenarios_receive_format_instruction_and_keep_four_calls(case):
    cloud = MockCloud()
    output = asyncio.run(Stage6Benchmark().run_case(cloud, case, confirmed=True))
    assert output["success"]
    assert len(cloud.calls) == output["cloud_requests_attempted"] == 4
    assert output["independent_review_packet"]["publisher_approval"] is False


def test_malformed_live_shaped_reply_stays_rejected_without_retry():
    cloud = MockCloud(failure=True)
    with pytest.raises(Stage6AnswerContractFailure) as caught:
        asyncio.run(Stage6Benchmark().run_case(
            cloud, "stale_connectivity", confirmed=True))
    failure = caught.value
    assert failure.category == "malformed_evidence_citation_ids"
    assert failure.progress["selected_source_ids"] == ["S2", "S3", "S1"]
    assert failure.progress["relevant_reference_sources_selected"] == 3
    assert failure.progress["attempted_cloud_requests"] == len(cloud.calls) == 4
    assert failure.progress["model_answer_published"] is False
    assert failure.progress["publisher_approval"] is False
    assert "initial focal observation" not in failure.detail


def test_no_production_publisher_or_real_tool_dependency_changes():
    for filename in ("causal_claim_publication.py",
                     "mcp_agent_orchestrator.py", "tool_executor.py",
                     "final_answer_coordinator.py"):
        assert "stage611" not in (APP / filename).read_text()
