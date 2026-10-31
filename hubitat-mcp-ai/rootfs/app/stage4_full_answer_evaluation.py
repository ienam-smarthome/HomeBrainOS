"""Stage 4G: offline, model-authored FULL investigation explanation evaluation.

This is not a publisher. It asks a separately injected local model to
author concise natural prose with host-owned evidence IDs, checks source
references and their exact typed witness projection, and sends the resulting
sentence *unchanged* to two independent reviewer calls.

The reviewer verdict is not independent truth. Source-fact coverage is not
answer correctness. No model-produced prose is returned or published. All
cases are constructed; no HomeBrain/HA/Hubitat device or MCP calls.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Mapping, Sequence

from stage4_narrative_contract import validate_stage4_model_draft
from stage4_semantic_sufficiency import (
    build_stage4_semantic_review_request, _review_votes,
)

_SECTION_NAMES = frozenset(("summary", "evidence", "limitations", "next_checks"))
_MAX_SENTENCES = 3
_MAX_TEXT = 360
_MAX_FACT_IDS = 2
_MAX_CASES = 4


def stage4g_authoring_prompt() -> str:
    """General answer guidance, no prefilled text or an example verdict."""
    return (
        "You are writing a short, natural-language investigation explanation "
        "for a user based only on the supplied host-issued evidence facts. "
        "Explain what the evidence *shows* in a useful sentence, then any "
        "material limitation. Distinguish command from observed state or "
        "physical effect, source clock from collector time, immediate "
        "command issuer from upstream trigger, and incomplete records from "
        "complete absence. Do NOT invent causes, events, devices, timing, "
        "commands, physical acknowledgement or missing source data. "
        "Write one to three clear and distinct sentences total. "
        "Use the exact host fact IDs that support each sentence; cite at "
        "least one fact per sentence, at most two. The text must be your own "
        "natural wording, not copied from the prompt or an example. "
        "Reply strictly as homebrain-stage4g-authored-proposal.v1 JSON with "
        "one sections entry, a name, and sentences of text and fact_ids. "
        "Do not include typed factual claims or create source fact IDs. "
        "The host will resolve cited fact IDs to source records; reviewers "
        "will independently assess every full sentence against those facts. "
        "No explanation is approved for publication in this evaluation."
    )


def stage4g_source_to_case(
    *,
    case_id: str, domain: str, question: str,
    packet: Mapping[str, Any], required_fact_ids: Sequence[str],
) -> dict[str, Any]:
    """Construct synthetic host-scoped question + independent coverage labels."""
    if (not isinstance(case_id, str) or not 1 <= len(case_id) <= 40
            or not all(x.islower() or x.isdigit() or x in "_-" for x in case_id)
            or not isinstance(domain, str) or domain not in (
                "lighting", "heating", "ventilation", "history")
            or not isinstance(question, str) or not 1 <= len(question) <= 240
            or not isinstance(packet, Mapping)
            or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"
            or packet.get("shadow_only") is not True
            or packet.get("is_publisher_input_not_publication") is not True
            or not isinstance(packet.get("facts"), list)
            or not 1 <= len(packet["facts"]) <= 8
            or not isinstance(required_fact_ids, (list, tuple))
            or not 1 <= len(required_fact_ids) <= 3
            or len(set(required_fact_ids)) != len(required_fact_ids)):
        raise ValueError("invalid synthetic case")
    refs = {f.get("fact_id") for f in packet["facts"] if isinstance(f, Mapping)}
    if any(not isinstance(fid, str) or fid not in refs for fid in required_fact_ids):
        raise ValueError("independent expected IDs not in scoped source packet")
    return {
        "case_id": case_id,
        "domain": domain,
        "question": question,
        "packet": dict(packet),
        "required_fact_ids": list(required_fact_ids),
    }


def _typed_claim(fact: Mapping[str, Any]) -> dict[str, Any]:
    """Host projection of source fact, *not* an assertion made by the model."""
    if fact["kind"] == "coverage_limit":
        keys = ("fact_id", "kind", "entity_id", "source", "gap_count",
                "truncated", "complete")
    else:
        keys = ("fact_id", "kind", "entity_id", "attribute", "value",
                "clock_basis", "time_utc", "issuer_app_id", "physical_ack_verified")
    return {key: fact[key] for key in keys}


def validate_stage4g_proposal(
    proposal: Any, packet: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Reject invalid/ambiguous model output; never fix author text or IDs."""
    if (not isinstance(proposal, Mapping)
            or set(proposal) != {"schema", "sections"}
            or proposal.get("schema") != "homebrain-stage4g-authored-proposal.v1"
            or not isinstance(proposal.get("sections"), list)
            or len(proposal["sections"]) != 1):
        return None
    section = proposal["sections"][0]
    if (not isinstance(section, Mapping)
            or set(section) != {"name", "sentences"}
            or section.get("name") not in _SECTION_NAMES
            or not isinstance(section.get("sentences"), list)
            or not 1 <= len(section["sentences"]) <= _MAX_SENTENCES):
        return None
    facts = {f["fact_id"]: f for f in packet["facts"]
             if isinstance(f, Mapping) and isinstance(f.get("fact_id"), str)}
    sentences = []
    for row in section["sentences"]:
        if (not isinstance(row, Mapping)
                or set(row) != {"text", "fact_ids"}
                or not isinstance(row.get("text"), str)
                or not 1 <= len(row["text"].strip()) <= _MAX_TEXT
                or "\x00" in row["text"]
                or not isinstance(row.get("fact_ids"), list)
                or not 1 <= len(row["fact_ids"]) <= _MAX_FACT_IDS
                or len(row["fact_ids"]) != len(set(str(v) for v in row["fact_ids"]))):
            return None
        ids = row["fact_ids"]
        if any(not isinstance(fid, str) or fid not in facts for fid in ids):
            return None
        sentences.append({
            "text": row["text"], "citations": list(ids),
            "claims": [_typed_claim(facts[fid]) for fid in ids],
        })
    # Resolve model-selected IDs to host facts. These typed projections
    # are source checks, NOT semantic assertions by the author.
    draft = {
        "schema": "homebrain-stage4-draft.v1",
        "sections": [{"name": section["name"], "sentences": sentences}],
    }
    if not validate_stage4_model_draft(draft, packet)["structured_claims_valid"]:
        return None
    return draft


def evaluate_stage4g_authored_answers(
    cases: Sequence[Mapping[str, Any]],
    *,
    author_model: str,
    reviewer_models: Sequence[str],
    invoke: Callable[[str, Mapping[str, Any]], Any],
) -> dict[str, Any]:
    """Actual local invocation is supplied by explicit caller; output aggregates only."""
    if (not isinstance(cases, (list, tuple)) or len(cases) != _MAX_CASES
            or author_model != "qwen2.5:3b"
            or tuple(reviewer_models) != ("qwen2.5:3b", "llama3.2:3b")
            or not callable(invoke)):
        raise ValueError("Stage 4G only supports its bounded synthetic model experiment")
    seen = set()
    for case in cases:
        if not isinstance(case, Mapping) or set(case) != {
            "case_id", "domain", "question", "packet", "required_fact_ids"
        }:
            raise ValueError("invalid synthetic case envelope")
        checked = stage4g_source_to_case(**case)
        if checked["case_id"] in seen:
            raise ValueError("duplicated benchmark case")
        seen.add(checked["case_id"])

    totals: Counter[str] = Counter()
    cited_expected = 0
    expected_total = sum(len(c["required_fact_ids"]) for c in cases)
    used: Counter[str] = Counter()
    for case in cases:
        totals["author_calls_attempted"] += 1
        try:
            raw = invoke(author_model, {
                "task": "author",
                "schema": "homebrain-stage4g-author-request.v1",
                "instructions": stage4g_authoring_prompt(),
                "question": case["question"],
                "packet": case["packet"],
            })
        except Exception:
            totals["author_invocation_errors"] += 1
            continue
        totals["author_model_responses_received"] += 1
        try:
            draft = validate_stage4g_proposal(raw, case["packet"])
        except (ValueError, TypeError, KeyError, AttributeError):
            draft = None
        if draft is None:
            totals["author_invalid_proposals"] += 1
            continue
        totals["author_source_valid_proposals"] += 1
        sentences = draft["sections"][0]["sentences"]
        totals["authored_sentences"] += len(sentences)
        citation_ids = {fid for row in sentences for fid in row["citations"]}
        cited_expected += len(citation_ids & set(case["required_fact_ids"]))
        # Naturalness is not reliably measured by word count, but a
        # nonempty sentence is not an empty/templated answer either.
        totals["authored_words"] += sum(len(row["text"].split()) for row in sentences)

        request = build_stage4_semantic_review_request(draft, case["packet"])
        if not request["ready"]:
            totals["review_request_invalid"] += 1
            continue
        case_complete = True
        for sentence in request["sentences"]:
            # A reviewer receives ONE independently scoped sentence. The
            # Stage 4E schema explicitly permits only s001, so reindex the
            # isolated review ID; the author text and cited facts stay exact.
            isolated = {**sentence, "sentence_id": "s001"}
            expected = {"s001": frozenset(sentence["cited_fact_ids"])}
            votes = []
            for model in reviewer_models:
                totals["review_calls_attempted"] += 1
                try:
                    reply = invoke(model, {
                        "task": "review",
                        "schema": "homebrain-stage4g-reviewer-request.v1",
                        "sentences": [isolated],
                        "source_facts_may_be_truncated": bool(
                            case["packet"].get("facts_omitted")
                            or case["packet"].get("receipts_omitted")),
                    })
                    totals["review_responses_received"] += 1
                    vote, error = _review_votes(reply, expected)
                except Exception:
                    totals["review_invocation_errors"] += 1
                    vote, error = None, "model-error"
                if error:
                    totals["invalid_reviewer_responses"] += 1
                    case_complete = False
                    votes.append(None)
                else:
                    votes.append(vote[sentence["sentence_id"]])
                    used[model] += 1
            if None not in votes:
                totals["sentences_with_two_valid_reviews"] += 1
                if votes[0] != votes[1]:
                    totals["reviewer_disagreement_sentences"] += 1
                elif votes[0] == "entailed":
                    totals["both_reviewers_propose_supported"] += 1
                else:
                    totals["both_reviewers_withhold"] += 1
        if case_complete:
            totals["cases_with_complete_reviews"] += 1

    return {
        "schema": "homebrain-stage4g-authored-investigation-evaluation.v1",
        "case_count": len(cases),
        "expected_source_fact_count": expected_total,
        "independent_expected_facts_cited": cited_expected,
        "independent_source_fact_coverage": (
            round(cited_expected / expected_total, 4)
            if expected_total else None),
        "author_calls_attempted": totals["author_calls_attempted"],
        "author_model_responses_received": totals["author_model_responses_received"],
        "author_invocation_errors": totals["author_invocation_errors"],
        "author_invalid_proposals": totals["author_invalid_proposals"],
        "author_source_valid_proposals": totals["author_source_valid_proposals"],
        "authored_sentences": totals["authored_sentences"],
        "authored_words": totals["authored_words"],
        "review_calls_attempted": totals["review_calls_attempted"],
        "review_responses_received": totals["review_responses_received"],
        "review_invocation_errors": totals["review_invocation_errors"],
        "invalid_reviewer_responses": totals["invalid_reviewer_responses"],
        "sentences_with_two_valid_reviews": totals["sentences_with_two_valid_reviews"],
        "cases_with_complete_reviews": totals["cases_with_complete_reviews"],
        "reviewer_disagreement_sentences": totals["reviewer_disagreement_sentences"],
        "both_reviewers_propose_supported": totals["both_reviewers_propose_supported"],
        "both_reviewers_withhold": totals["both_reviewers_withhold"],
        "independent_fact_coverage_is_not_prose_truth": True,
        "host_projected_typed_claims_not_model_attestations": True,
        "model_reviewer_verdicts_are_not_independent_truth": True,
        "generated_prose_has_no_independent_sentence_oracle": True,
        "human_quality_or_naturalness_measured": False,
        "actual_homebrain_investigation_tested": False,
        "publication_authorised": False,
        "production_answer_changed": False,
        "real_household_data_processed": False,
    }


__all__ = [
    "stage4g_authoring_prompt", "stage4g_source_to_case",
    "validate_stage4g_proposal", "evaluate_stage4g_authored_answers",
]
