"""Fictional-only checks for the offline review-pass comparison ledger."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "evaluation" / "review_pass_pairs.py"
spec = importlib.util.spec_from_file_location("review_pass_pairs", TARGET)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReviewPairsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "evidence.json").write_text('{"fictional":true}')
        (self.root / "a.json").write_text('{"answer":"unknown"}')
        (self.root / "b.json").write_text('{"answer":"unproved"}')
        self.digest = module._fingerprint(self.root, "evidence.json")

    def payload(self):
        arms = []
        for label, mode, answer, score in (
            ("A", "single_answer", "a.json", 1),
            ("B", "source_review_and_audit", "b.json", 2)):
            arms.append({"label": label, "mode": mode, "answer_file": answer,
                         "evidence_sha256": self.digest, "elapsed_ms": 100,
                         "model_rounds": 2, "unexpected_write": False,
                         "scores": {"factual_grounding": score,
                                    "source_completeness": 1,
                                    "causal_calibration": 0,
                                    "usefulness": 1}})
        return {"schema": module.SCHEMA,
                "cases": [{"id": "synthetic-01", "read_only": True,
                           "model": "fixture", "frozen_evidence_file": "evidence.json",
                           "arms": arms}]}

    def test_paired_delta_and_no_private_answer_text(self):
        out = module.validate(self.payload(), self.root)
        self.assertEqual(out["cases"][0]["delta_B_minus_A"], 1)
        self.assertNotIn("unproved", json.dumps(out))
        self.assertNotIn("unknown", json.dumps(out))

    def test_rejects_mismatched_evidence(self):
        raw = self.payload()
        raw["cases"][0]["arms"][1]["evidence_sha256"] = "0" * 64
        with self.assertRaises(module.ReviewError):
            module.validate(raw, self.root)

    def test_rejects_writes(self):
        raw = self.payload()
        raw["cases"][0]["arms"][0]["unexpected_write"] = True
        with self.assertRaises(module.ReviewError):
            module.validate(raw, self.root)

    def test_rejects_path_escape(self):
        raw = self.payload()
        raw["cases"][0]["arms"][0]["answer_file"] = "../outside.json"
        with self.assertRaises(module.ReviewError):
            module.validate(raw, self.root)

    def test_rejects_noncomparable_score_denominators(self):
        raw = self.payload()
        raw["cases"][0]["arms"][1]["scores"]["causal_calibration"] = None
        with self.assertRaises(module.ReviewError):
            module.validate(raw, self.root)

if __name__ == "__main__":
    unittest.main()
