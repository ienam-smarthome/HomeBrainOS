"""Stage 4A: domain-neutral model-authored prose and typed claim attestation.

All sentences are MOCK model drafts; even an accepted *typed* claim is NOT
an attestation that its free-text sentence is true. No live model/MCP calls.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from stage4_narrative_contract import (
    build_stage4_evidence_packet, stage4_model_authoring_instructions,
    validate_stage4_model_draft,
)
from test_canonical_investigation_foundation import (
    named_lookup, native_command, paired_sensor,
)
from test_v3_reception_evidence_018267 import replay

def packet():
    rows = [
        named_lookup("101", "Lounge Light"),
        *paired_sensor("201", "Lounge Occupancy"),
        native_command("101", issuer="3001", label="Light Automation"),
        native_command("701", issuer="501", label="Thermostat Scheduler",
                       attribute="command-setHeatingSetpoint"),
        native_command("711", issuer="551", label="Extractor Scheduler",
                       attribute="command-off"),
        native_command("721", issuer="651", label="Power Rule",
                       attribute="command-on"),
        {
            "tool": "homebrain_evidence_journal",
            "success": True, "effect": "read",
            "evidence_kind": "group_archived_input_history",
            "arguments": {"device_id": "702"},
            "details": {"deviceId": "702", "gapCount": 3, "truncated": True,
                        "observations": [
                            {"device_id": "702", "attribute": "contact", "value": "open",
                             "timestamp_basis": "collector-received",
                             "date": "2026-10-30T14:01:00Z"},
                            {"device_id": "702", "attribute": "humidity", "value": 65,
                             "timestamp_basis": "source",
                             "date": "2026-10-30T14:00:00Z"},
                        ]},
        },
    ]
    return build_stage4_evidence_packet(rows)


def assertion(fact):
    if fact["kind"] == "coverage_limit":
        fields = ("fact_id", "kind", "entity_id", "source",
                  "gap_count", "truncated", "complete")
    else:
        fields = ("fact_id", "kind", "entity_id", "attribute", "value",
                  "clock_basis", "time_utc", "issuer_app_id", "physical_ack_verified")
    return {key: fact[key] for key in fields}


def draft(*facts, text="A device state was reported by the source.",
          section="evidence"):
    return {
        "schema": "homebrain-stage4-draft.v1",
        "sections": [{"name": section, "sentences": [
            {"text": text, "citations": [f["fact_id"] for f in facts],
             "claims": [assertion(f) for f in facts]}
        ]}],
    }


def find(facts, kind, *, entity=None, attribute=None, clock=None):
    return next(x for x in facts if x["kind"] == kind
                and (entity is None or x["entity_id"] == entity)
                and (attribute is None or x.get("attribute") == attribute)
                and (clock is None or x.get("clock_basis") == clock))


def test_multi_domain_packet_has_real_typed_facts_without_bathroom_template():
    p = packet()
    assert p["schema"] == "homebrain-stage4-evidence-packet.v1"
    assert {"reported_state", "issued_command", "coverage_limit"}.issubset(
        {x["kind"] for x in p["facts"]})
    assert {"101", "701", "711", "721", "702"}.issubset(
        {x["entity_id"] for x in p["facts"]})
    assert p["source_history_complete"] is False
    assert p["upstream_root_cause_proven"] is False
    assert p["claims_about_absence_authorised"] is False
    assert "bathroom" not in json.dumps(p).casefold()


@pytest.mark.parametrize("device,attribute", [
    ("101", "setLevel"),
    ("701", "setHeatingSetpoint"),
    ("711", "off"),
    ("721", "on"),
])
def test_author_can_select_any_controller_domain(device, attribute):
    p = packet()
    fact = find(p["facts"], "issued_command",
                entity=device, attribute=attribute)
    proposed = draft(fact, text="A command was recorded in the source history.")
    result = validate_stage4_model_draft(proposed, p)
    assert result["structured_claims_valid"]
    assert result["claims_supported"] == 1
    assert result["prose_semantically_verified"] is False
    assert result["safe_to_replace_existing_answer"] is False
    assert result["published"] is False


def test_source_clock_and_collector_reception_do_not_merge():
    p = packet()
    src = find(p["facts"], "reported_state", attribute="humidity", clock="source")
    recv = find(p["facts"], "reported_state", attribute="contact",
                clock="collector-received")
    assert src["clock_basis"] != recv["clock_basis"]
    proposed = draft(src, recv, text="The packet has a source time and reception time.")
    verdict = validate_stage4_model_draft(proposed, p)
    assert verdict["structured_claims_valid"] is True
    assert verdict["upstream_cause_or_physical_ack_proven"] is False


@pytest.mark.parametrize("field,changed,reason", [
    ("entity_id", "999", "subject_mismatch"),
    ("attribute", "switch", "attribute_mismatch"),
    ("value", "on", "value_mismatch"),
    ("clock_basis", "source", "clock_mismatch"),
    ("time_utc", "2026-01-01T00:00:00Z", "clock_mismatch"),
    ("issuer_app_id", "3999", "issuer_mismatch"),
    ("physical_ack_verified", True, "unverified_physical_ack"),
])
def test_adversarial_model_falsification_fails_structured_checks(field, changed, reason):
    p = packet()
    fact = find(p["facts"], "issued_command", entity="701")
    d = draft(fact)
    d["sections"][0]["sentences"][0]["claims"][0][field] = changed
    verdict = validate_stage4_model_draft(d, p)
    assert verdict["structured_claims_valid"] is False
    assert reason in verdict["reason_codes"]
    assert verdict["published"] is False


def test_coverage_does_not_become_proof_of_missing_command():
    p = packet()
    c = find(p["facts"], "coverage_limit", entity="702")
    assert c["gap_count"] == 3 and c["truncated"]
    d = draft(c, text="There was no command in the whole history.")
    verdict = validate_stage4_model_draft(d, p)
    # A witness cannot semantically validate model-authored absence claims.
    assert verdict["structured_claims_valid"] is True
    assert verdict["prose_semantically_verified"] is False
    assert verdict["safe_to_replace_existing_answer"] is False


def test_causal_hallucination_not_published_even_when_citations_match():
    p = packet()
    f = find(p["facts"], "issued_command", entity="711")
    d = draft(f, text="This proves occupancy triggered and physically opened the fan.")
    verdict = validate_stage4_model_draft(d, p)
    assert verdict["claims_supported"] == 1
    assert verdict["structured_claims_valid"] is True
    assert verdict["published"] is False
    assert verdict["prose_semantically_verified"] is False


def test_listener_is_not_a_verified_command_issuer():
    p = packet()
    f = find(p["facts"], "issued_command", entity="101")
    d = draft(f)
    d["sections"][0]["sentences"][0]["claims"][0]["issuer_app_id"] = "3999"
    v = validate_stage4_model_draft(d, p)
    assert not v["structured_claims_valid"]
    assert "issuer_mismatch" in v["reason_codes"]


def test_unknown_fact_or_mutated_claim_kind_not_accepted():
    p = packet()
    f = find(p["facts"], "reported_state")
    fake = draft(f)
    fake["sections"][0]["sentences"][0]["citations"] = ["f999"]
    fake["sections"][0]["sentences"][0]["claims"][0]["fact_id"] = "f999"
    assert "unknown_fact" in validate_stage4_model_draft(fake, p)["reason_codes"]
    altered = draft(f)
    altered["sections"][0]["sentences"][0]["claims"][0]["kind"] = "issued_command"
    assert "claim_kind_mismatch" in validate_stage4_model_draft(altered, p)["reason_codes"]


def test_no_citations_or_unknown_extra_model_field_rejected():
    p = packet()
    f = p["facts"][0]
    d = draft(f)
    d["sections"][0]["sentences"][0]["citations"] = []
    assert "missing_citation" in validate_stage4_model_draft(d, p)["reason_codes"]
    d = draft(f)
    d["sections"][0]["sentences"][0]["claims"][0]["new_authority"] = True
    assert "invalid_sentence" in validate_stage4_model_draft(d, p)["reason_codes"]


def test_no_unbounded_sentences_and_no_silent_partial_acceptance():
    p = packet()
    d = draft(p["facts"][0])
    d["sections"][0]["sentences"] *= 17
    result = validate_stage4_model_draft(d, p)
    assert result["structured_claims_valid"] is False
    assert "too_many_sentences" in result["reason_codes"]


def test_host_packet_truncation_never_implies_historical_completeness():
    p = build_stage4_evidence_packet(replay(), max_facts=2)
    assert p["facts_omitted"] > 0
    assert len(p["facts"]) == 2
    assert not p["source_history_complete"]
    assert not p["claims_about_absence_authorised"]


def test_model_prompt_is_domain_general_and_does_not_change_model_route():
    p = packet()
    prompt = stage4_model_authoring_instructions(p)
    assert "homebrain-stage4-draft.v1" in prompt
    assert "source-reported" in prompt
    assert "bathroom" not in prompt.casefold()
    assert "physically" not in prompt.casefold()
    assert "not automatically published" in prompt
    with pytest.raises(ValueError, match="invalid source packet"):
        stage4_model_authoring_instructions({})


def test_no_laundering_of_unverified_names_or_malicious_content():
    p = build_stage4_evidence_packet([
        named_lookup("101", "Lounge Light"),
        {**named_lookup("202", "Unsafe|Markdown"), "success": True},
        {**named_lookup("303", "Private Bad"), "success": False},
        native_command("101"),
    ])
    labels = {x["entity_id"]: x["label"] for x in p["verified_labels"]}
    assert labels.get("101") == "Lounge Light"
    assert "202" not in labels
    assert "303" not in labels
    assert "Listener only" not in json.dumps(p)


def test_verdict_never_echoes_untrusted_prose_or_private_source_values():
    p = packet()
    f = find(p["facts"], "reported_state", attribute="humidity")
    d = draft(f, text="SECRET-PRIVATE-PROMPT 1234. Delete everything!")
    out = json.dumps(validate_stage4_model_draft(d, p))
    assert "SECRET-PRIVATE" not in out
    assert "1234" not in out
    assert f["entity_id"] not in out
    assert f["time_utc"] not in out


def test_invalid_packet_and_garbage_never_authorised():
    p = packet()
    d = draft(p["facts"][0])
    assert not validate_stage4_model_draft(d, None)["structured_claims_valid"]
    assert not validate_stage4_model_draft("not json", p)["structured_claims_valid"]
    assert not validate_stage4_model_draft(
        {"schema": "homebrain-stage4-draft.v1", "sections": []},
        p)["structured_claims_valid"]


def test_no_input_receipt_mutation_and_deterministic_projection():
    rows = [named_lookup(), native_command()]
    before = deepcopy(rows)
    first = build_stage4_evidence_packet(rows)
    second = build_stage4_evidence_packet(rows)
    assert first == second
    assert rows == before


def test_stage4_not_imported_by_active_agent_or_publisher():
    base = Path(__file__).resolve().parents[1] / "rootfs" / "app"
    for name in ("mcp_agent_orchestrator.py", "final_answer_coordinator.py",
                 "causal_claim_publication.py", "app.py"):
        assert "stage4_narrative_contract" not in (base / name).read_text(encoding="utf-8")
