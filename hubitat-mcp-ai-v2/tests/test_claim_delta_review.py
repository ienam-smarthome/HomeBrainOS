"""Fictional/manual-only tests for claim-delta validation and mobile UI contract."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evaluation" / "claim_delta_review.py"
spec = importlib.util.spec_from_file_location("claim_delta_review", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    score = {"factual_grounding": 2, "source_completeness": 1,
             "causal_calibration": 1, "usefulness": 2}
    stages = ["single_answer", "source_review", "source_review_and_audit"]
    return {
        "ui_version": "2.0.0-alpha.61",
        "result": {
            "evidence_sha256": "a" * 64, "mcp_calls_executed": 0,
            "hubitat_writes_executed": 0, "model_rounds": 3,
            "stages": [
                {"stage": stage, "answer": "FICTIONAL, not evidence",
                 "cumulative_elapsed_ms": (idx + 1) * 1000}
                for idx, stage in enumerate(stages)
            ],
        },
        "manual_review": {
            "schema": module.SCHEMA, "evidence_sha256": "a" * 64,
            "case_role": "fresh_case",
            "stage_scores": {stage: dict(score) for stage in stages},
            "claim_changes": [
                {"transition": "source_review",
                 "kind": "unsupported_introduced",
                 "claim": "Claiming no fictional reports existed",
                 "receipt_reference": "hub_get_logs source index 0"},
                {"transition": "final_audit",
                 "kind": "unsupported_corrected",
                 "claim": "Corrected the earlier no-report claim",
                 "receipt_reference": "hub_get_logs source index 0"},
            ],
        },
    }


class ClaimDeltaReviewTests(unittest.TestCase):
    def test_human_scores_and_stage_changes(self):
        value = fixture()
        value["manual_review"]["stage_scores"]["single_answer"]["factual_grounding"] = 1
        value["manual_review"]["stage_scores"]["source_review"]["factual_grounding"] = 0
        result = module.validate(value)
        self.assertEqual(result["delta_review_vs_initial"], -1)
        self.assertEqual(result["delta_final_vs_review"], 2)
        self.assertEqual(result["delta_final_vs_initial"], 1)
        self.assertEqual(result["additional_review_ms"], 2000)
        self.assertEqual(result["claim_change_counts"]["source_review"]["unsupported_introduced"], 1)
        self.assertEqual(result["claim_change_counts"]["final_audit"]["unsupported_corrected"], 1)
        self.assertNotIn("FICTIONAL", json.dumps(result))
        self.assertNotIn("Claiming", json.dumps(result))

    def test_no_claim_entries_is_unassessed_not_no_regression(self):
        value = fixture()
        value["manual_review"]["claim_changes"] = []
        result = module.validate(value)
        self.assertIn("not assessed", result["claim_change_completeness"])

    def test_reject_stale_fingerprint_and_unsafe_replay(self):
        value = fixture()
        value["manual_review"]["evidence_sha256"] = "b" * 64
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        value["result"]["mcp_calls_executed"] = 1
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        value["result"]["hubitat_writes_executed"] = 1
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)

    def test_reject_partial_and_mismatched_causal_na(self):
        value = fixture()
        del value["manual_review"]["stage_scores"]["single_answer"]["usefulness"]
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        value["manual_review"]["stage_scores"]["source_review"]["causal_calibration"] = None
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        for scores in value["manual_review"]["stage_scores"].values():
            scores["causal_calibration"] = None
        self.assertEqual(module.validate(value)["max_score"], 6)

    def test_reject_invalid_or_unanchored_claim_change(self):
        value = fixture()
        value["manual_review"]["claim_changes"][0]["receipt_reference"] = ""
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        value["manual_review"]["claim_changes"][0]["kind"] = "automatically_verified"
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        value["manual_review"]["claim_changes"][0]["transition"] = "initial_answer"
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)

    def test_reject_nonmonotonic_times_and_duplicate_stages(self):
        value = fixture()
        value["result"]["stages"][1]["cumulative_elapsed_ms"] = 1
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)
        value = fixture()
        value["result"]["stages"][2]["stage"] = "source_review"
        with self.assertRaises(module.ClaimDeltaError):
            module.validate(value)

    def test_ui_is_session_only_and_explicitly_manually_graded(self):
        ui = (ROOT / "rootfs" / "app" / "ui.html").read_text(encoding="utf-8")
        self.assertIn('const UI_VERSION="2.0.0-alpha.81"', ui)
        for snippet in ("id=\"evalReviewDownload\"", "id=\"evalScoreGrid\"",
                        "id=\"evalOriginalReceipts\"", "evaluationManualReview()",
                        "evaluationDownloadReview()", "unsupported_introduced",
                        "supported_fact_lost", "source_scope_changed",
                        "No rating is inferred", "claim_changes"):
            self.assertIn(snippet, ui)
        self.assertIn("byId('evalReviewDownload').disabled=!outcome?.complete", ui)
        self.assertIn("evaluationDownloadPrivate(reviewed,'PRIVATE-homebrain-v2-reviewed.json')", ui)
        self.assertIn("byId('evalOriginalReceipts').textContent=JSON.stringify(original,null,2)", ui)
        manual=ui[ui.index("function evaluationResetReview()"):ui.index("function reloadInterface()")]
        self.assertNotIn("localStorage.", manual)
        self.assertNotIn("sessionStorage.", manual)
        self.assertIn("const causalSame=cs.every(v=>(v===null)===(cs[0]===null))", manual)


if __name__ == "__main__":
    unittest.main()
