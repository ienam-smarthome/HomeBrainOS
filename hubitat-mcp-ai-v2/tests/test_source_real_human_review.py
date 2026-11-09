"""Unseen/source-real acceptance review is explicitly human graded, never inferred.

Tests use invented local export strings only; no model, device or web calls.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "tools" / "first_answer_audit.py"
SPEC = importlib.util.spec_from_file_location("source_real_audit_test", FILE)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def technical_export(question="SENSITIVE-FIXTURE-QUESTION"):
    return {
        "ui_version": "2.0.0-alpha.26",
        "model": "SENSITIVE-FIXTURE-MODEL",
        "question": question,
        "client_elapsed_ms": 1000,
        "response": {"success": True, "answer": "SENSITIVE-FIXTURE-ANSWER",
                     "rounds": 2, "tool_calls": []},
    }


def review(index, **updates):
    row = {
        "export_index": index, "first_attempt": True, "source_kind": "real",
        "factual_claims_reviewed": 5, "supported_factual_claims": 4,
        "definitive_causal_claims_reviewed": 2,
        "unsupported_definitive_causal_claims": 1,
        "useful_first_answer": False,
        "relevant_sources_sufficient": True,
    }
    row.update(updates)
    return row


def assessments(*rows):
    return {"schema": audit.HUMAN_REVIEW_SCHEMA, "reviews": list(rows)}


class SourceRealHumanReviewTests(unittest.TestCase):
    def test_no_review_is_not_measured_even_if_tools_and_model_succeed(self):
        result = audit.summarize([audit.audit_export(technical_export())])
        self.assertEqual(result["quality_status"], "not_measured")
        self.assertIsNone(result["grounded_claim_rate"])
        self.assertIsNone(result["unsupported_definitive_causal_claim_count"])

    def test_human_attested_rates_use_real_claim_denominators(self):
        records = [audit.audit_export(technical_export(str(i))) for i in range(2)]
        result = audit.summarize(records, human_reviews=assessments(
            review(0), review(1, factual_claims_reviewed=3,
                              supported_factual_claims=3,
                              definitive_causal_claims_reviewed=0,
                              unsupported_definitive_causal_claims=0,
                              useful_first_answer=True,
                              relevant_sources_sufficient=False),
        ))
        self.assertEqual(result["quality_status"], "human_attested_complete")
        self.assertEqual(result["reviewed_source_real_first_answers"], 2)
        self.assertEqual(result["factual_claims_reviewed"], 8)
        self.assertEqual(result["supported_factual_claims"], 7)
        self.assertEqual(result["grounded_claim_rate"], 0.875)
        self.assertEqual(result["definitive_causal_claims_reviewed"], 2)
        self.assertEqual(result["unsupported_definitive_causal_claim_count"], 1)
        self.assertEqual(result["useful_first_answer_rate"], 0.5)
        self.assertEqual(result["relevant_source_sufficiency_rate"], 0.5)
        self.assertEqual(result["reviewer_independence"], "not_verified")

    def test_partial_unknown_and_nonreal_reviews_cannot_inflate_quality(self):
        records = [audit.audit_export(technical_export(str(i))) for i in range(3)]
        result = audit.summarize(records, human_reviews=assessments(
            review(0, factual_claims_reviewed=0, supported_factual_claims=0,
                   definitive_causal_claims_reviewed=0,
                   unsupported_definitive_causal_claims=0,
                   useful_first_answer=None, relevant_sources_sufficient=None),
            review(1, source_kind="synthetic",
                   factual_claims_reviewed=100, supported_factual_claims=100,
                   useful_first_answer=True),
        ))
        self.assertEqual(result["quality_status"], "human_attested_partial")
        self.assertEqual(result["reviewed_source_real_first_answers"], 1)
        self.assertEqual(result["excluded_nonreal_or_nonfirst_attempt_reviews"], 1)
        self.assertEqual(result["unreviewed_export_samples"], 1)
        self.assertIsNone(result["grounded_claim_rate"])
        self.assertIsNone(result["unsupported_definitive_causal_claim_count"])
        self.assertIsNone(result["useful_first_answer_rate"])
        self.assertIsNone(result["relevant_source_sufficiency_rate"])

    def test_no_real_first_attempt_is_not_measured(self):
        records = [audit.audit_export(technical_export())]
        result = audit.summarize(records, human_reviews=assessments(
            review(0, first_attempt=False),
        ))
        self.assertEqual(result["quality_status"], "not_measured")
        self.assertEqual(result["reviewed_source_real_first_answers"], 0)
        self.assertIsNone(result["grounded_claim_rate"])

    def test_reject_malformed_and_duplicate_ratings(self):
        records = [audit.audit_export(technical_export(str(i))) for i in range(2)]
        invalid = [
            assessments(review(0), review(0)),
            assessments(review(-1)),
            assessments(review(2)),
            assessments(review(True)),
            assessments(review(0, factual_claims_reviewed=1)),
            assessments(review(0, unsupported_definitive_causal_claims=3)),
            assessments(review(0, useful_first_answer="yes")),
            assessments(review(0, source_kind="guess")),
            assessments(review(0, first_attempt=1)),
            assessments({**review(0), "private_note": "SENSITIVE-FIXTURE"}),
            {"schema": "other", "reviews": [review(0)]},
            {"schema": audit.HUMAN_REVIEW_SCHEMA, "reviews": {}},
        ]
        for body in invalid:
            with self.subTest(body=str(body)[:80]):
                with self.assertRaises(audit.AuditInputError):
                    audit.summarize(records, human_reviews=body)

    def test_private_review_and_export_text_never_printed(self):
        with tempfile.TemporaryDirectory() as folder:
            export = Path(folder) / "private-export.json"
            review_file = Path(folder) / "private-review.json"
            export.write_text(json.dumps(technical_export()), encoding="utf-8")
            review_file.write_text(json.dumps(assessments(review(0))), encoding="utf-8")
            command = [sys.executable, str(FILE), str(export),
                       "--reviews", str(review_file)]
            run = subprocess.run(command, capture_output=True, text=True,
                                 timeout=15, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["quality_status"], "human_attested_complete")
            self.assertEqual(payload["grounded_claim_rate"], 0.8)
            self.assertNotIn("SENSITIVE-FIXTURE", run.stdout)
            self.assertNotIn(str(export), run.stdout)
            self.assertNotIn(str(review_file), run.stdout)
            # Invalid sensitive review details must not reach stderr either.
            review_file.write_text(json.dumps(assessments(
                {**review(0), "SENSITIVE-FIXTURE": "secret"})), encoding="utf-8")
            bad = subprocess.run(command, capture_output=True, text=True,
                                 timeout=15, check=False)
            self.assertNotEqual(bad.returncode, 0)
            self.assertNotIn("SENSITIVE-FIXTURE", bad.stderr)


if __name__ == "__main__":
    unittest.main()
