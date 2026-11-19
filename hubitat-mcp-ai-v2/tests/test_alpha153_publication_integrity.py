"""General first-answer publication regressions from fictional source receipts.

No live MCP, LLM, network access, previous case replay or device writes.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from read_only_receipt_fallback import source_only_partial_answer
from review_answer_preservation import preserve_receipt_anchored_answer
from test_read_only_receipt_fallback import FakeMCP, ScriptedAgent, tool_call, receipt


CONTACT = {
    "source": "device", "device": "Fixture Gate Contact",
    "deviceId": "FX-GATE", "attributeFilter": "contact",
    "events": [
        {"name": "contact", "value": "closed",
         "date": "2030-11-19T08:48:56.707+0000"},
        {"name": "contact", "value": "open",
         "date": "2030-11-19T08:48:50.046+0000"},
        {"name": "contact", "value": "closed",
         "date": "2030-11-19T07:38:20.193+0000"},
    ],
}
ARGS = {"deviceId": "FX-GATE", "attribute": "contact", "hoursBack": 10}
DRAFT = (
    "Fixture Gate Contact: latest OPEN 2030-11-19T08:48:50.046+0000, "
    "latest CLOSED 2030-11-19T08:48:56.707+0000. These are discrete "
    "returned reports, not evidence of continuous history."
)
REVIEW_ONLY = (
    "The internal source review confirms the previous answer included "
    "the newest OPEN and CLOSED samples; no further checks are necessary."
)
WARN = {
    "mode": "past", "count": 6, "matched": 6, "total": 9121,
    "entries": [
        *[{"name": "Fixture Monitor", "level": "WARN",
           "message": "private data not for UI"} for _ in range(4)],
        *[{"name": "Fixture Device", "level": "WARN",
           "message": "private data not for UI"} for _ in range(2)],
    ],
}


class ReviewSelectionTests(unittest.TestCase):
    def test_dated_observations_survive_tool_free_self_review(self):
        original = [receipt("hub_list_device_events", ARGS, CONTACT)]
        chosen, status = preserve_receipt_anchored_answer(
            DRAFT, REVIEW_ONLY, original,
            receipt_count_at_draft=len(original),
        )
        self.assertEqual(chosen, DRAFT)
        self.assertEqual(status, "source_anchored_draft_preserved_no_new_read")

    def test_preserve_never_promotes_unsupported_or_updated_source(self):
        original = [receipt("hub_list_device_events", ARGS, CONTACT)]
        self.assertEqual(preserve_receipt_anchored_answer(
            "Invented timestamp: 2030-11-19T00:00:00+0000.",
            REVIEW_ONLY, original, receipt_count_at_draft=1,
        )[0], REVIEW_ONLY)
        unsafe = DRAFT + " The device remained closed throughout the entire window."
        self.assertEqual(preserve_receipt_anchored_answer(
            unsafe, REVIEW_ONLY, original, receipt_count_at_draft=1,
        )[0], REVIEW_ONLY)
        added = original + [receipt("hub_list_device_events", ARGS, CONTACT)]
        self.assertEqual(preserve_receipt_anchored_answer(
            DRAFT, REVIEW_ONLY, added, receipt_count_at_draft=1,
        )[0], REVIEW_ONLY)

    def test_normal_revision_with_both_source_times_is_not_replaced(self):
        original = [receipt("hub_list_device_events", ARGS, CONTACT)]
        improved = "Corrected: " + DRAFT
        chosen, status = preserve_receipt_anchored_answer(
            DRAFT, improved, original, receipt_count_at_draft=1,
        )
        self.assertEqual(chosen, improved)
        self.assertEqual(status, "source_anchors_partly_retained")


class FictionalContactMCP(FakeMCP):
    def __init__(self):
        super().__init__({"FX-GATE": CONTACT})


class ReviewAgentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_review_cannot_replace_source_anchored_contact_answer(self):
        agent = ScriptedAgent(
            tool_call("hub_list_device_events", ARGS),
            {"content": DRAFT},
            {"content": REVIEW_ONLY},
        )
        mcp = FictionalContactMCP()
        try:
            result = await agent.answer(
                "For Fixture Gate Contact, report newest OPEN/CLOSED with timestamps "
                "in the past ten hours. What does the interval not establish? "
                "Do not change anything.",
                [], mcp, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_answer_integrity_status"],
                         "source_anchored_draft_preserved_no_new_read")
        self.assertIn("08:48:50.046", result["answer"])
        self.assertIn("08:48:56.707", result["answer"])
        self.assertNotIn("internal source review", result["answer"])
        self.assertEqual(len(mcp.calls), 1)
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])


class LogFallbackTests(unittest.TestCase):
    def test_bounded_warn_log_grouping_retains_counts_without_messages(self):
        rows = [receipt(
            "hub_get_logs",
            {"mode": "past", "level": "warn", "since": "3h", "limit": 0},
            WARN,
        )]
        result = source_only_partial_answer(
            "Summarize WARN entries in the past three hours by source.", rows,
        )
        self.assertIn("Fixture Monitor: 4", result)
        self.assertIn("Fixture Device: 2", result)
        self.assertIn("6 entries actually returned", result)
        self.assertIn("Reported matches: 6", result)
        self.assertIn("9121", result)
        self.assertIn("scope is not established", result)
        self.assertNotIn("private data", result)

    def test_no_cross_page_addition_and_bad_names_rejected(self):
        older = receipt("hub_get_logs", {"mode": "past"}, {
            "mode": "past", "entries": [
                {"name": "Fixture Monitor"} for _ in range(2)
            ],
        })
        current = receipt("hub_get_logs", {"mode": "past"}, {
            "mode": "past", "entries": [
                {"name": "token:abc"}, {"name": "<script>"},
                {"name": "Clean Source"},
            ],
        })
        summary = source_only_partial_answer(
            "Summarize returned warnings.", [older, current],
        )
        self.assertIn("Clean Source: 1", summary)
        self.assertIn("2 returned rows had unpublishable source labels", summary)
        self.assertNotIn("Fixture Monitor: 2", summary)
        self.assertNotIn("<script>", summary)


if __name__ == "__main__":
    unittest.main()
