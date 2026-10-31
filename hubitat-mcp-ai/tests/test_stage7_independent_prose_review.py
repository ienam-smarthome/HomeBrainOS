"""Stage 7: frozen synthetic evidence corpus for independent prose review.

The reviewer compares ALL authored sentences with all static source records,
including unexamined sources, without trusting the model's own evidence atoms.
No real Hubitat/HA data, inference calls, automatic second model or publisher.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, _validate_answer, _audit, Stage6Benchmark,
)
from stage7_review_packet import build_review_packet  # noqa: E402
from webui import render_page  # noqa: E402


def _draft(text="The fictional lamp was reported on.", *, kind="state_report"):
    return {
        "schema": "homebrain-stage6-answer.v2",
        "sentences": [{
            "text": text, "kind": kind, "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "on"}],
        }],
        "uncertainties": ["Physical actuator response is not independently verified"],
        "next_evidence": "Inspect the independent actuator acknowledgement",
    }


@pytest.mark.parametrize("scenario,selected", [
    ("clock_conflict", ["S2", "S3"]),
    ("competing_commands", ["S1", "S2"]),
    ("stale_connectivity", ["S1", "S2"]),
])
def test_full_original_source_corpus_freezes_after_model_choice(scenario, selected):
    case = _CASES[scenario]
    draft = _draft()
    draft["sentences"][0]["text"] = "Fictional device reports a state."
    packet = build_review_packet(scenario, case, selected, draft)
    assert packet["schema"] == "homebrain-stage7-review.v1"
    assert len(packet["source_records"]) == len(case["catalog"]) + 1
    assert {r["source_id"] for r in packet["source_records"]} == {
        "INITIAL", *(src["id"] for src in case["catalog"])
    }
    assert {r["source_id"] for r in packet["source_records"]
            if r["was_selected_by_model"]} == {"INITIAL", *selected}
    assert all(r["records"] for r in packet["source_records"])
    assert packet["author_sentences"][0]["text"] == draft["sentences"][0]["text"]
    assert packet["gold_reference_labels_included"] is False
    assert packet["prose_fully_verified"] is False
    assert packet["publisher_approval"] is False
    assert packet["independent_human_review_required"] is True
    assert len(packet["review_packet_id"]) == 16
    assert packet == build_review_packet(scenario, case, selected, draft)
    assert "gold_sources" not in json.dumps(packet)
    assert "required_types" not in json.dumps(packet)
    assert "192.168.1." not in json.dumps(packet)


def test_unexamined_command_history_remains_available_to_reviewer():
    c = _CASES["clock_conflict"]
    packet = build_review_packet("clock_conflict", c, ["S2", "S3"], _draft())
    missing = next(s for s in packet["source_records"] if s["source_id"] == "S1")
    assert missing["was_selected_by_model"] is False
    assert missing["records"][0]["command"] == "setLevel"
    assert missing["records"][0]["issuer"] == "Fictional Lighting Routine"
    assert packet["source_records"][0]["records"][0]["state"] == "on"


def test_typically_correct_atom_does_not_verify_misleading_natural_sentence():
    # Regression for the exact weakness observed after 6.5:
    # typed source and matching atom may be correct while prose invents
    # independent physical activation. Independent reviewer must detect it.
    case = _CASES["clock_conflict"]
    draft = _draft("The actual physical lamp definitely turned on because of motion.")
    _validate_answer(json.dumps(draft), [case["initial"]])
    audit = _audit(case, [], draft)
    assert audit["typed_source_supported_sentences"] == 1
    assert audit["source_value_atoms_verified"] == 1
    assert audit["source_value_atoms_mismatched"] == 0
    assert audit["sentences_with_unverified_free_prose"] == 1
    assert audit["prose_semantics_fully_verified"] is False
    packet = build_review_packet("clock_conflict", case, [], draft)
    assert "definitely" in packet["author_sentences"][0]["text"]
    assert packet["author_sentences"][0]["human_factual_verdict"] == "not_reviewed"
    assert "unsupported" in packet["reviewer_rubric"]["per_sentence"]


def test_review_packet_excludes_unknown_fields_from_source_and_never_exposes_golds():
    case = {**_CASES["clock_conflict"]}
    case["initial"] = {**case["initial"],
                       "api_key": "SECRET-NO-EXPOSE",
                       "access_token": "SECRET-NO-EXPOSE"}
    sources = []
    for item in case["catalog"]:
        copy = {**item, "records": [
            {**r, "password": "SECRET-NO-EXPOSE"}
            for r in item["records"]
        ]}
        sources.append(copy)
    case["catalog"] = sources
    packet = build_review_packet("clock_conflict", case, ["S1"], _draft())
    assert "SECRET-NO-EXPOSE" not in json.dumps(packet)
    assert "gold_sources" not in json.dumps(packet)
    assert packet["publisher_approval"] is False


@pytest.mark.parametrize("choices", [["S999"], ["S1", "S1"], ["S1"] * 4])
def test_unknown_duplicate_or_excessive_source_selection_rejected(choices):
    with pytest.raises(ValueError):
        build_review_packet("clock_conflict", _CASES["clock_conflict"], choices, _draft())


class FictionalCloud:
    def __init__(self):
        self.base_url = "https://ollama.com"
        self.api_key = "never-print-provider-key"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert tools == []
        assert self.api_key not in json.dumps(messages)
        p = json.loads(messages[1]["content"])
        if "remaining_source_titles" in p:
            count = len(p["sources_already_examined"])
            choice = ["S1", "S2", "S3"][count]
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1",
                "action": "read", "source_id": choice,
                "reason": "Gather independent fictional source records",
            })}
        return {"content": json.dumps(_draft())}


def test_successful_stage6_attaches_review_packet_without_extra_cloud_calls():
    model = FictionalCloud()
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "clock_conflict", confirmed=True))
    packet = result["independent_review_packet"]
    assert result["success"]
    assert len(model.calls) == 4
    assert packet["case_id"] == "clock_conflict"
    assert packet["publisher_approval"] is False
    assert packet["gold_reference_labels_included"] is False
    assert len(packet["source_records"]) == len(_CASES["clock_conflict"]["catalog"]) + 1
    assert packet["author_sentences"][0]["text"] == _draft()["sentences"][0]["text"]
    assert "never-print-provider-key" not in json.dumps(result)


def test_mobile_review_is_human_authored_and_export_is_explicit_only():
    html = render_page("HomeBrainOS", "0.18.302")
    for target in (
        "Stage 7 · Independently review every sentence",
        "Full source packet (including unread fictional records)",
        "Sentence '+sentence.number",
        "Copy independent review packet",
        "independently_reviewed_by_human",
        "Not reviewed",
        "Partially supported",
        "Important omissions",
        "Overconfident causation",
        "data.independent_review_packet",
        "automatic_semantic_certification:false",
    ):
        assert target in html
    assert "copy.onclick=()=>{" in html


def test_stage7_not_imported_into_production_publisher_or_mcp_agent():
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage7_review_packet" not in (APP / filename).read_text()
