"""Stage 6.1: source semantics, exact value atoms, and auditable early STOP.

These are deterministic, mock-only tests. They do not establish full semantic
support of authored natural language, and never request real cloud inference.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import (  # noqa: E402
    _CASES, _validate_answer, _audit, Stage6Benchmark,
)
from webui import render_page  # noqa: E402


def _answer(*sentences):
    return {
        "schema": "homebrain-stage6-answer.v2",
        "sentences": list(sentences),
        "uncertainties": ["Physical light actuation was not verified"],
        "next_evidence": "Examine the missing app brightness command history",
    }


def _sentence(text, kind, evidence_ids, atoms):
    return {"text": text, "kind": kind, "evidence_ids": evidence_ids,
            "atoms": atoms}


def _atom(rec, field, value):
    return {"record_id": rec, "field": field, "value": value}


def _clock_records():
    case = _CASES["clock_conflict"]
    return [case["initial"]] + [src["records"][0] for src in case["catalog"]
                                if src["id"] in {"S2", "S3"}]


def test_user_reported_e2_e3_are_value_correct_but_not_independent_telemetry():
    case = _CASES["clock_conflict"]
    text = _answer(
        _sentence("Device-source telemetry reports ON at 20:02:09Z.",
                  "device_telemetry", ["E3"],
                  [_atom("E3", "state", "on"), _atom("E3", "source_time", "20:02:09Z")]),
        _sentence("Device-source telemetry reports OFF at 20:01:10Z.",
                  "device_telemetry", ["E2"],
                  [_atom("E2", "state", "off"), _atom("E2", "source_time", "20:01:10Z")]),
    )
    assert _validate_answer(json.dumps(text), _clock_records()) == text
    result = _audit(case, ["S2", "S3"], text)
    assert result["source_type_mismatches"] == 2
    assert result["unmatched_source_types_other"] == 0
    assert result["source_value_atoms_verified"] == 4
    assert result["source_value_atoms_mismatched"] == 0
    assert result["unsupported_typed_sentence_citations"] == 2
    assert result["high_risk_unsupported_sentences"] == 0
    assert result["premature_stop_missing_relevant_sources"]
    assert result["missing_expected_finding_types"] == ["command_record", "state_report", "time_order_conflict"]
    assert all(not row["typed_source_supported"] and row["source_type_mismatch"]
               for row in result["sentence_citation_checks"])
    assert all(not row["factual_prose_verified"]
               for row in result["sentence_citation_checks"])
    assert not result["prose_semantics_fully_verified"]
    assert not result["publisher_approval"]


def test_exact_value_atom_detects_wrong_time_separately_from_valid_source_type():
    case = _CASES["clock_conflict"]
    draft = _answer(_sentence(
        "The ON report is recorded at 20:09:09, which is not the actual source time.",
        "state_report", ["E3"],
        [_atom("E3", "state", "on"), _atom("E3", "source_time", "20:09:09Z")],
    ))
    result = _audit(case, ["S3"], draft)
    assert result["source_type_mismatches"] == 0
    assert result["source_value_atoms_verified"] == 1
    assert result["source_value_atoms_mismatched"] == 1
    assert result["sentence_citation_checks"][0]["typed_source_supported"]
    assert not result["sentence_citation_checks"][0]["factual_prose_verified"]


def test_state_report_with_source_clock_is_still_state_report_not_physical_proof():
    case = _CASES["clock_conflict"]
    draft = _answer(_sentence(
        "The light was reported off at its device-source time.",
        "state_report", ["E2"],
        [_atom("E2", "state", "off"), _atom("E2", "source_time", "20:01:10Z")],
    ))
    result = _audit(case, ["S2"], draft)
    assert result["typed_source_supported_sentences"] == 1
    assert result["source_type_mismatches"] == 0
    assert result["source_value_atoms_verified"] == 2
    assert not result["prose_semantics_fully_verified"]


@pytest.mark.parametrize("fault", [
    "unknown_atom_record", "unknown_atom_field", "mismatched_atom_reference",
    "duplicate_atoms", "non_array_atoms", "excessive_atoms", "object_value", "extra_sentence_key",
])
def test_v2_source_atom_contract_is_strict_and_no_guessing(fault):
    row = _sentence(
        "The source reported the fictional light on at 20:02:09.",
        "state_report", ["E3"],
        [_atom("E3", "state", "on")],
    )
    if fault == "unknown_atom_record":
        row["atoms"][0]["record_id"] = "E999"
    elif fault == "unknown_atom_field":
        row["atoms"][0]["field"] = "private_token"
    elif fault == "mismatched_atom_reference":
        row["atoms"][0]["record_id"] = "E2"
    elif fault == "duplicate_atoms":
        row["atoms"] *= 2
    elif fault == "non_array_atoms":
        row["atoms"] = {}
    elif fault == "excessive_atoms":
        row["atoms"] *= 5
    elif fault == "object_value":
        row["atoms"][0]["value"] = {"injection": "ignored"}
    elif fault == "extra_sentence_key":
        row["secret"] = "should reject"
    with pytest.raises(ValueError):
        _validate_answer(json.dumps(_answer(row)), _clock_records())


def test_host_does_not_prove_physical_outcome_even_with_matching_model_atom():
    case = _CASES["clock_conflict"]
    draft = _answer(_sentence(
        "The physical lamp was definitely on.",
        "physical_confirmation", ["E3"],
        [_atom("E3", "state", "on")],
    ))
    result = _audit(case, ["S3"], draft)
    assert result["source_value_atoms_verified"] == 1
    assert result["high_risk_unsupported_sentences"] == 1
    assert result["unsupported_typed_sentence_citations"] == 1
    assert result["publisher_approval"] is False


def test_legacy_answer_v1_remains_readable_but_prose_stays_unverified():
    case = _CASES["clock_conflict"]
    draft = {"schema": "homebrain-stage6-answer.v1",
             "sentences": [{"text": "The light was reported on.", "kind": "state_report",
                            "evidence_ids": ["I1"]}],
             "uncertainties": ["Physical state is not independently confirmed"],
             "next_evidence": "Examine the command app records"}
    _validate_answer(json.dumps(draft), [case["initial"]])
    report = _audit(case, [], draft)
    assert report["source_value_atoms_verified"] == 0
    assert report["source_value_atoms_mismatched"] == 0
    assert not report["prose_semantics_fully_verified"]


class StopEarlyCloud:
    def __init__(self):
        self.api_key = "fake-not-logged"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.timeout_seconds = 60
        self.calls = []
        self.picked = ["S2", "S3"]

    @property
    def configured(self):
        return True

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        assert not tools and kwargs["disable_thinking"] is True
        assert self.api_key not in json.dumps(messages)
        assert "gold_sources" not in json.dumps(messages)
        question = json.loads(messages[1]["content"])
        if "remaining_source_titles" in question:
            seen = [row["source_id"] for row in question["sources_already_examined"]]
            if len(seen) == 2:
                return {"content": json.dumps({
                    "schema": "homebrain-stage6-next.v1",
                    "action": "stop", "source_id": None,
                    "reason": "The clock conflict is clear; no need to check command history",
                })}
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": self.picked[len(seen)],
                "reason": "Read device state timeline",
            })}
        return {"content": json.dumps(_answer(
            _sentence("The device-source OFF report predates ON.",
                      "state_report", ["E2"],
                      [_atom("E2", "state", "off"), _atom("E2", "source_time", "20:01:10Z")]),
            _sentence("The later ON report has a device-source clock.",
                      "state_report", ["E3"],
                      [_atom("E3", "state", "on"), _atom("E3", "source_time", "20:02:09Z")]),
        ))}


def test_premature_stop_remains_a_detectable_failure_no_oracle_leakage():
    model = StopEarlyCloud()
    result = asyncio.run(Stage6Benchmark().run_case(
        model, "clock_conflict", confirmed=True))
    assert result["cloud_requests_attempted"] == 4
    assert result["requested_source_reads"] == 2
    assert result["stop_reason"] == "model_stopped"
    assert result["stop_left_host_reference_sources_unexamined"]
    assert result["premature_stop_missing_relevant_sources"]
    assert "command history" in result["model_stop_justification"]
    assert result["relevant_source_recall"] == "2/3"
    assert result["source_value_atoms_verified"] == 4
    assert result["missing_expected_finding_types"] == ["command_record", "time_order_conflict"]
    for messages, _, _ in model.calls:
        model_input = json.dumps(messages)
        assert "required_types" not in model_input
        assert "gold_sources" not in model_input
    assert not result["publisher_approval"]


def test_model_planning_prompt_demands_check_for_unread_material_sources():
    source = (APP / "stage6_adaptive_benchmark.py").read_text()
    assert "Before STOP" in source
    assert "UNREAD" in source
    assert "Do not stop simply because two plausible" in source
    assert "only a" not in source or "fictional" in source


def test_stage61_dashboard_separates_types_from_values_and_stop_reason():
    html = render_page("HomeBrain", "0.18.296")
    for phrase in ("Source-type mismatches", "Cited source-value atoms",
                   "Source label mismatch (not a proven false fact)",
                   "Exact source-value checks", "model_stop_justification",
                   "not automatically a false fact"):
        assert phrase in html


def test_production_publisher_still_does_not_load_stage61():
    for filename in ("mcp_agent_orchestrator.py", "tool_executor.py",
                     "causal_claim_publication.py", "final_answer_coordinator.py"):
        src = (APP / filename).read_text()
        assert "stage6_adaptive_benchmark" not in src
