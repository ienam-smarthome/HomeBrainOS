from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

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

    def test_sheet_is_the_fixed_set_and_only_question_two_asks_for_a_write(self):
        self.assertEqual([n for n, _ in run_test_sheet.SHEET], [1, 2, 3, 4, 5, 6, 7])
        writes = [n for n, q in run_test_sheet.SHEET
                  if q.lower().startswith(("turn ", "block ", "unblock ", "disable "))]
        self.assertEqual(writes, [2])


class NoWrites(unittest.TestCase):
    def test_every_request_turns_auto_approval_off(self):
        for profile in (None, "full", "plain"):
            body = run_test_sheet.ask_body("Turn on bathroom lights", "r", profile)
            self.assertIs(body["disable_auto_approval"], True)
            self.assertEqual(body.get("loop_profile"), profile)

    def test_an_older_addon_gets_no_questions(self):
        self.assertEqual(run_test_sheet.missing_ask_options({"version": "2.0.0-alpha.209"}),
                         ["loop_profile", "disable_auto_approval"])
        asked = []

        def fake(base, path, body=None, timeout=15):
            asked.append(path)
            return {"version": "2.0.0-alpha.209"}

        with mock.patch.object(run_test_sheet, "http_json", fake):
            self.assertEqual(run_test_sheet.main(["--base-url", "http://addon.test"]), 2)
        self.assertEqual(asked, ["/api/status"])

    def test_each_card_is_declined_once_and_never_approved(self):
        done = threading.Event()
        posted, polls = [], []

        def fake(base, path, body=None, timeout=15):
            if body is not None:
                posted.append(body)
                return {"accepted": True}
            polls.append(path)
            if len(polls) >= 3:
                done.set()
            return {"pending": {"id": "card-1", "name": "hub_call_device_command",
                                "arguments": {"deviceId": "1", "command": "on"}}}

        declined = []
        run_test_sheet.decline_cards("http://addon.test", "r", done, declined,
                                     fetch=fake, interval=0.001)
        self.assertEqual(posted, [{"id": "card-1", "approved": False}])
        self.assertEqual(len(declined), 1)


if __name__ == "__main__":
    unittest.main()
