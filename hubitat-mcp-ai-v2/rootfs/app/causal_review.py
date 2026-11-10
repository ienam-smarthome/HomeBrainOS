"""Private, reviewer-attested causal evidence checks for prospective A/B only.

No Hubitat, model, or network connection. The original native receipts and
human claim quotations stay in the in-memory case file. Public aggregates
contain counts only; tool arguments, source values, and claim text never leave
this module through an aggregate response.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

COVERAGE_STATES = ("sufficient", "partial", "unavailable", "not_verified")
VERDICTS = ("supported", "unsupported", "unverified")
MAX_CAUSE_CLAIMS = 20


class CausalReviewError(ValueError):
    pass


def _reads(arm: dict) -> dict[tuple[str, str], Counter[str]]:
    """Read-only receipt multiset, preserving repeated calls and exact payloads.

    Invocation equality only means same (name, arguments). Payload equality
    only means returned JSON/text is identical after JSON whitespace
    normalization. Neither proves an authoritative, complete, fresh source.
    """
    out: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    result = arm.get("result") if isinstance(arm, dict) else None
    receipts = result.get("tool_calls", []) if isinstance(result, dict) else []
    if not isinstance(receipts, list):
        return out
    for row in receipts:
        if (not isinstance(row, dict) or row.get("result_kind") != "tool_result"
                or row.get("success") is not True
                or not isinstance(row.get("name"), str)
                or not isinstance(row.get("arguments"), dict)
                or not isinstance(row.get("response"), str)):
            continue
        invocation = (row["name"], json.dumps(
            row["arguments"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ))
        raw = row["response"]
        try:
            normalized = json.dumps(
                json.loads(raw), sort_keys=True, ensure_ascii=False,
                separators=(",", ":")
            )
        except (ValueError, TypeError):
            normalized = raw
        out[invocation][normalized] += 1
    return out


def source_parity(arms: dict) -> dict:
    """Symmetric, label-preserving comparison; no private content or hashes."""
    a = _reads(arms.get("A", {}))
    b = _reads(arms.get("B", {}))
    n_a = sum(sum(c.values()) for c in a.values())
    n_b = sum(sum(c.values()) for c in b.values())
    shared = sum(min(sum(a[key].values()), sum(b[key].values()))
                 for key in a.keys() & b.keys())
    exact = sum(sum(min(c, b[key].get(raw, 0)) for raw, c in a[key].items())
                for key in a.keys() & b.keys())
    return {
        "successful_tool_results_A": n_a,
        "successful_tool_results_B": n_b,
        "same_name_and_arguments": shared,
        "exactly_matching_response_payloads": exact,
        "same_call_different_response": shared - exact,
        "only_A_read_invocations": n_a - shared,
        "only_B_read_invocations": n_b - shared,
        "identical_read_receipt_multisets": n_a == n_b == exact,
        "interpretation": (
            "Exact comparison of returned successful tool receipts, not "
            "independent proof of matched time windows, source truth, or "
            "complete investigation coverage."
        ),
    }


def validate_causal_review(review: dict, arms: dict, ratings: dict) -> dict:
    """Require genuine manual source-check receipts and claim-by-claim verdicts.

    An empty claim list is valid: the model may correctly refuse to infer a
    cause. For causal-study questions, the 0/1/2 causal-calibration rating is
    still mandatory; it must not be silently excluded as n/a.
    """
    if not isinstance(review, dict) or set(review) != {"A", "B"}:
        raise CausalReviewError("Provide a causal evidence review for BOTH A and B")
    validated = {}
    for label in ("A", "B"):
        item = review[label]
        if (not isinstance(item, dict)
                or set(item) != {
                    "receipts_inspected", "all_definite_cause_claims_reviewed",
                    "source_coverage", "claims"
                }):
            raise CausalReviewError(
                f"{label}: confirm source review, coverage and definite causal claims"
            )
        if (item["receipts_inspected"] is not True
                or item["all_definite_cause_claims_reviewed"] is not True):
            raise CausalReviewError(
                f"{label}: read the original tool receipts and review every "
                "definite causal claim before scoring"
            )
        if item["source_coverage"] not in COVERAGE_STATES:
            raise CausalReviewError(f"{label}: source coverage was not classified")
        claims = item["claims"]
        if not isinstance(claims, list) or len(claims) > MAX_CAUSE_CLAIMS:
            raise CausalReviewError(
                f"{label}: provide up to {MAX_CAUSE_CLAIMS} reviewed causal claims"
            )
        result = arms.get(label, {}).get("result", {})
        receipts = result.get("tool_calls", []) if isinstance(result, dict) else []
        if not isinstance(receipts, list):
            receipts = []
        seen = set()
        safe_claims = []
        unsupported = 0
        for claim in claims:
            if (not isinstance(claim, dict)
                    or set(claim) != {"text", "verdict", "receipt_indices"}):
                raise CausalReviewError(
                    f"{label}: each causal claim needs exact text, verdict and receipt indices"
                )
            note = claim["text"]
            verdict = claim["verdict"]
            refs = claim["receipt_indices"]
            if (not isinstance(note, str) or not 5 <= len(note.strip()) <= 400
                    or verdict not in VERDICTS
                    or not isinstance(refs, list) or len(refs) > 20
                    or any(type(index) is not int or index < 0 or index >= len(receipts)
                           for index in refs)
                    or len(refs) != len(set(refs))):
                raise CausalReviewError(f"{label}: invalid claim, verdict or receipt index")
            if (verdict == "supported" and not any(
                isinstance(receipts[index], dict)
                and receipts[index].get("result_kind") == "tool_result"
                and receipts[index].get("success") is True
                for index in refs
            )):
                raise CausalReviewError(
                    f"{label}: a supported definite cause must cite a successful "
                    "original MCP tool receipt"
                )
            normalized = note.strip()
            if normalized in seen:
                raise CausalReviewError(f"{label}: duplicate claim")
            seen.add(normalized)
            unsupported += int(verdict == "unsupported")
            safe_claims.append({
                "text": normalized, "verdict": verdict,
                "receipt_indices": list(refs)
            })
        if unsupported and ratings[label]["causal_calibration"] == 2:
            raise CausalReviewError(
                f"{label}: a full causal-calibration score contradicts "
                "an unsupported definite cause claim"
            )
        validated[label] = {
            "receipts_inspected": True,
            "all_definite_cause_claims_reviewed": True,
            "source_coverage": item["source_coverage"],
            "claims": safe_claims,
            "independently_verified": False,
        }
    return validated


def aggregate_causal_review(cases: dict, private_conditions: dict,
                            revealed: bool) -> dict:
    """Never expose private claim prose, receipt references or case identities."""
    totals = {
        condition: {
            "arms_reviewed": 0, "definite_cause_claims_reviewed": 0,
            "definite_causes_supported": 0,
            "definite_causes_unsupported": 0,
            "definite_causes_unverified": 0,
            "answers_with_unsupported_definite_cause": 0,
            "source_coverage": {coverage: 0 for coverage in COVERAGE_STATES},
        }
        for condition in ("baseline", "candidate")
    }
    if revealed:
        for case_id, case in cases.items():
            if not isinstance(case.get("causal_review"), dict):
                continue
            for label in ("A", "B"):
                condition = private_conditions[case_id][label]
                review = case["causal_review"][label]
                row = totals[condition]
                row["arms_reviewed"] += 1
                row["source_coverage"][review["source_coverage"]] += 1
                claims = review["claims"]
                row["definite_cause_claims_reviewed"] += len(claims)
                row["answers_with_unsupported_definite_cause"] += int(
                    any(c["verdict"] == "unsupported" for c in claims)
                )
                for claim in claims:
                    row[f"definite_causes_{claim['verdict']}"] += 1
    return {
        "results": totals if revealed else None,
        "manual_source_and_claim_review": True,
        "independent_claim_truth_verified": False,
        "empty_claim_list_means_no_definite_claims_identified": True,
        "interpretation": (
            "Manually inspected model cause assertions, their original "
            "receipts, and discriminating source coverage. No automatic "
            "proof of the asserted causes or complete hub event retention."
        ),
    }
