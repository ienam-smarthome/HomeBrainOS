"""Purely offline causal-review and receipt-equivalence regression tests."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_review import (
    CausalReviewError, aggregate_causal_review, source_parity,
    validate_causal_review,
)
from prospective_source_ab import ProspectiveError, ProspectiveWorkspace, CRITERIA


def result(text: str, name="hub_get_device", args=None):
    return {"result": {"tool_calls": [{
        "name": name, "arguments": args or {"device_id": "SIMULATED-1"},
        "success": True, "result_kind": "tool_result",
        "response": json.dumps({"content": [{"type": "text", "text": text}]})
    }]}}


def grade(a=2, b=2):
    return {
        label: {k: value if k == "causal_calibration" else 2 for k in CRITERIA}
        for label, value in (("A", a), ("B", b))
    }


def review(a_claims=None, b_claims=None, coverage="partial"):
    return {
        label: {
            "receipts_inspected": True,
            "all_definite_cause_claims_reviewed": True,
            "source_coverage": coverage,
            "claims": claims or [],
        }
        for label, claims in (("A", a_claims), ("B", b_claims))
    }


def claim(verdict="supported", text="Verified cause statement",
          indices=None):
    return {
        "text": text, "verdict": verdict,
        "receipt_indices": [0] if indices is None else indices,
    }


class ReceiptComparisonTests(unittest.TestCase):
    def test_exact_receipts_have_positive_parity_with_no_private_payload(self):
        arms = {"A": result("PRIVATE-HOUSEHOLD-KEY"),
                "B": result("PRIVATE-HOUSEHOLD-KEY")}
        compared = source_parity(arms)
        self.assertTrue(compared["identical_read_receipt_multisets"])
        self.assertEqual(compared["same_name_and_arguments"], 1)
        self.assertEqual(compared["exactly_matching_response_payloads"], 1)
        self.assertNotIn("PRIVATE-HOUSEHOLD", json.dumps(compared))
        self.assertNotIn("SIMULATED-1", json.dumps(compared))

    def test_same_call_with_different_response_is_not_source_equivalence(self):
        compared = source_parity({
            "A": result("PRIVATE-VALUE-TIME-ONE"),
            "B": result("PRIVATE-VALUE-TIME-TWO"),
        })
        self.assertFalse(compared["identical_read_receipt_multisets"])
        self.assertEqual(compared["same_call_different_response"], 1)
        self.assertEqual(compared["exactly_matching_response_payloads"], 0)

    def test_unmatched_sources_and_empty_read_lists(self):
        compared = source_parity({
            "A": result("one", name="hub_get_device"),
            "B": result("one", name="hub_list_apps"),
        })
        self.assertEqual(compared["only_A_read_invocations"], 1)
        self.assertEqual(compared["only_B_read_invocations"], 1)
        self.assertFalse(compared["identical_read_receipt_multisets"])
        self.assertFalse(source_parity({"A": {}, "B": {}})[
            "identical_read_receipt_multisets"])

    def test_failed_contract_errors_and_catalog_responses_are_not_source_reads(self):
        a = result("ok")
        a["result"]["tool_calls"] += [
            {"name": "hub_get_device", "success": False,
             "result_kind": "contract_error", "response": "PRIVATE-DATA"},
            {"name": "hub_get_device", "success": True,
             "result_kind": "tool_catalog", "response": "PRIVATE-CATALOG"},
        ]
        self.assertEqual(source_parity({"A": a, "B": result("ok")})[
            "successful_tool_results_A"], 1)

    def test_repeated_reads_are_multiset_matched(self):
        a = result("one")
        a["result"]["tool_calls"].append(a["result"]["tool_calls"][0].copy())
        compared = source_parity({"A": a, "B": result("one")})
        self.assertEqual(compared["same_name_and_arguments"], 1)
        self.assertEqual(compared["only_A_read_invocations"], 1)


class ClaimReviewTests(unittest.TestCase):
    def setUp(self):
        self.arms = {"A": result("EVIDENCE-A"), "B": result("EVIDENCE-B")}

    def test_supported_claim_requires_original_successful_receipt(self):
        ratings = grade()
        good = review([claim()], [claim("unverified", "Unproven bridge origin", [])])
        validated = validate_causal_review(good, self.arms, ratings)
        self.assertEqual(validated["A"]["claims"][0]["receipt_indices"], [0])
        self.assertFalse(validated["A"]["independently_verified"])
        with self.assertRaises(CausalReviewError):
            validate_causal_review(
                review([claim(indices=[])], []), self.arms, ratings
            )
        with self.assertRaises(CausalReviewError):
            validate_causal_review(
                review([claim(indices=[9])], []), self.arms, ratings
            )

    def test_rejects_unsupported_definite_claim_given_full_score(self):
        with self.assertRaises(CausalReviewError):
            validate_causal_review(
                review([claim("unsupported", "Unproven exact cause", [])], []),
                self.arms, grade(a=2)
            )
        reviewed = validate_causal_review(
            review([claim("unsupported", "Unproven exact cause", [])], []),
            self.arms, grade(a=1)
        )
        self.assertEqual(reviewed["A"]["claims"][0]["verdict"], "unsupported")

    def test_uncertain_answer_can_be_scored_without_definitive_causal_claims(self):
        result_data = validate_causal_review(
            review([], [], coverage="unavailable"), self.arms, grade()
        )
        self.assertEqual(result_data["B"]["claims"], [])
        self.assertEqual(result_data["B"]["source_coverage"], "unavailable")

    def test_requires_evidence_and_complete_review_attestation(self):
        item = review()
        item["A"]["receipts_inspected"] = False
        with self.assertRaises(CausalReviewError):
            validate_causal_review(item, self.arms, grade())
        item = review()
        item["B"]["all_definite_cause_claims_reviewed"] = False
        with self.assertRaises(CausalReviewError):
            validate_causal_review(item, self.arms, grade())
        item = review()
        item["B"]["source_coverage"] = "UNKNOWN"
        with self.assertRaises(CausalReviewError):
            validate_causal_review(item, self.arms, grade())

    def test_aggregates_never_export_cause_text_or_receipt_names(self):
        entry = {
            "causal_review": validate_causal_review(
                review([claim("unsupported", "PRIVATE causal explanation", [])],
                       [claim("supported", "PRIVATE verified explanation", [0])]),
                self.arms, grade(a=1)
            )
        }
        report = aggregate_causal_review(
            {"private-case-id": entry},
            {"private-case-id": {"A": "baseline", "B": "candidate"}},
            True
        )
        self.assertEqual(report["results"]["baseline"][
            "definite_causes_unsupported"], 1)
        self.assertEqual(report["results"]["candidate"][
            "definite_causes_supported"], 1)
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertNotIn("private-case-id", json.dumps(report))
        self.assertIsNone(aggregate_causal_review(
            {"private-case-id": entry},
            {"private-case-id": {"A": "baseline", "B": "candidate"}},
            False)["results"])


class CausalStudyTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ProspectiveWorkspace()
        self.questions = [
            "Private read-only causal investigation, scenario " + str(i)
            for i in range(4)
        ]

    def test_requires_four_questions_and_prechecked_real_target_attestation(self):
        with self.assertRaises(ProspectiveError):
            self.workspace.prepare(self.questions[:2], causal_mode=True,
                                   target_check_attested=True)
        with self.assertRaises(ProspectiveError):
            self.workspace.prepare(self.questions, causal_mode=True,
                                   target_check_attested=False)
        summary = self.workspace.prepare(
            self.questions, causal_mode=True, target_check_attested=True)
        self.assertEqual(summary["study_mode"], "causal")
        self.assertEqual(summary["cases_prepared"], 4)
        self.assertTrue(summary["target_check_operator_attested"])
        self.assertFalse(summary["target_check_independently_verified"])

    def test_no_causes_is_valid_when_answer_correctly_abstains(self):
        self.workspace.prepare(self.questions, causal_mode=True,
                               target_check_attested=True)
        self.workspace.questions["new-01"]["arms"] = self.arms()
        with self.assertRaises(ProspectiveError):
            self.workspace.rate("new-01", grade(), None)
        self.assertIsNone(self.workspace.questions["new-01"]["ratings"])
        self.workspace.rate("new-01", grade(), review([], [], "unavailable"))
        self.assertFalse(self.workspace.case("new-01")["causal_review"]["A"][
            "independently_verified"])
        self.assertFalse(self.workspace.report()[
            "condition_mapping_revealed"])

    def arms(self):
        return {"A": result("PRIVATE A"), "B": result("PRIVATE B")}

    def test_causal_calibration_must_be_rated_not_n_a(self):
        self.workspace.prepare(self.questions, causal_mode=True,
                               target_check_attested=True)
        self.workspace.questions["new-01"]["arms"] = self.arms()
        scores = grade()
        scores["A"]["causal_calibration"] = "n/a"
        with self.assertRaises(ProspectiveError):
            self.workspace.rate("new-01", scores, review())
        self.assertIsNone(self.workspace.questions["new-01"]["ratings"])

    def test_private_review_and_public_report_are_separated_until_complete(self):
        self.workspace.prepare(self.questions, causal_mode=True,
                               target_check_attested=True)
        for i in range(1, 5):
            key = f"new-{i:02d}"
            self.workspace.questions[key]["arms"] = self.arms()
            self.workspace.private_conditions[key] = (
                {"A": "baseline", "B": "candidate"} if i % 2
                else {"A": "candidate", "B": "baseline"}
            )
            self.workspace.rate(key, grade(1, 2), review(
                [claim("unsupported", "PRIVATE client cause " + str(i), [])],
                [], "partial"
            ))
            if i != 4:
                self.assertIsNone(self.workspace.report()["causal_claim_audit"][
                    "results"])
        report = self.workspace.report()
        self.assertTrue(report["condition_mapping_revealed"])
        self.assertEqual(report["causal_claim_audit"]["results"]["baseline"][
            "definite_causes_unsupported"], 2)
        self.assertFalse(report["causal_claim_truth_independently_verified"])
        self.assertNotIn("PRIVATE client cause", json.dumps(report))
        self.assertNotIn("Private read-only", json.dumps(report))
        self.assertIn("source_parity", report)
        for key in self.workspace.questions:
            self.assertEqual(len(self.workspace.case(key)["causal_review"]), 2)
        self.workspace.delete()
        self.assertEqual(self.workspace.summary()["study_mode"], "general")

    def test_general_mode_accepts_legacy_score_cards_without_claim_audit(self):
        self.workspace.prepare(self.questions[:2])
        self.workspace.questions["new-01"]["arms"] = self.arms()
        self.workspace.rate("new-01", grade())
        self.assertIsNone(self.workspace.questions["new-01"]["causal_review"])
        with self.assertRaises(ProspectiveError):
            self.workspace.rate("new-01", grade(), review())


if __name__ == "__main__":
    unittest.main()
