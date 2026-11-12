"""Local, privacy-preserving metadata inspector for fictional stage snapshots."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "inspect_answer_stages.py"
spec = importlib.util.spec_from_file_location("inspect_answer_stages", TOOL)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class InspectorTests(unittest.TestCase):
    def test_returns_counts_and_does_not_export_private_prose(self):
        raw = {
            "ui_version": "2.0.0-alpha.58",
            "model": "fixture",
            "response": {
                "source_review_invoked": True,
                "final_claim_audit_invoked": True,
                "final_claim_audit_status": "completed",
                "rounds": 6,
                "tool_calls": [{"success": True}],
                "answer_stage_trace": [
                    {"stage": "pre_source_review", "answer": "PRIVATE-DRAFT-A",
                     "after_model_round": 2, "tool_receipts_seen": 0,
                     "successful_tool_receipts_seen": 0,
                     "failed_tool_receipts_seen": 0},
                    {"stage": "pre_final_audit", "answer": "PRIVATE-DRAFT-B",
                     "after_model_round": 5, "tool_receipts_seen": 1,
                     "successful_tool_receipts_seen": 1,
                     "failed_tool_receipts_seen": 0},
                    {"stage": "post_final_audit", "answer": "PRIVATE-DRAFT-C",
                     "after_model_round": 6, "tool_receipts_seen": 1,
                     "successful_tool_receipts_seen": 1,
                     "failed_tool_receipts_seen": 0},
                ],
            },
        }
        import json
        report = module.stage_summary(raw)
        self.assertEqual(report["model_rounds"], 6)
        self.assertEqual([x["additional_tool_receipts_since_prior"]
                          for x in report["stages"]], [None, 1, 0])
        self.assertEqual([x["answer_changed_since_prior"]
                          for x in report["stages"]], [None, True, True])
        self.assertNotIn("PRIVATE-DRAFT", json.dumps(report))
        self.assertNotIn("PRIVATE-DRAFT", str(report))

    def test_older_version_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError, "alpha.58"):
            module.stage_summary({"response": {"answer": "private"}})


if __name__ == "__main__":
    unittest.main()
