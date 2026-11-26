from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_test_sheet  # noqa: E402


class Scoreboard(unittest.TestCase):
    def test_row_summarises_timing_tokens_and_failures(self):
        result = {"success": True, "rounds": 3, "answer": "Two lights\nare on.",
                  "tool_calls": [{"success": True}, {"success": False}],
                  "model_round_metrics": [{"prompt_eval_count": 100}, {"prompt_eval_count": 900}]}
        row = run_test_sheet.scoreboard_row(1, "Which lights are on?", result, 4.26)
        self.assertEqual(row["peak_prompt_tokens"], 900)
        self.assertEqual(row["failed_calls"], 1)
        self.assertEqual(row["answer_head"], "Two lights are on.")
        self.assertEqual(row["wall_s"], 4.3)

    def test_sheet_is_the_fixed_set_of_read_questions(self):
        self.assertEqual([n for n, _ in run_test_sheet.SHEET], [1, 3, 4, 5, 6, 7])
        for _, question in run_test_sheet.SHEET:
            self.assertFalse(question.lower().startswith(("turn ", "block ", "unblock ", "disable ")))


if __name__ == "__main__":
    unittest.main()
