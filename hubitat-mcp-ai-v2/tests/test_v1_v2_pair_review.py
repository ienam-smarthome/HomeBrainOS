"""V1/V2 offline first-answer ledger regressions; no real Hubitat content."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "evaluation" / "v1_v2_pairs.py"
spec = importlib.util.spec_from_file_location("v1_v2_pairs", MODULE)
pairs = importlib.util.module_from_spec(spec)
sys.modules["v1_v2_pairs"] = pairs
spec.loader.exec_module(pairs)


class PairReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="homebrain-fixture-")
        self.root = Path(self.tmp.name)
        (self.root / "v1.json").write_text(json.dumps({
            "private_mock_token": "SECRET_SHOULD_NOT_APPEAR_IN_REPORT",
            "answer": "Synthetic hall lamp is on",
        }), encoding="utf-8")
        (self.root / "v2.json").write_text(json.dumps({
            "private_mock_token": "OTHER_SECRET_SHOULD_NOT_APPEAR",
            "response": {
                "answer": "Synthetic hall lamp is on",
                "tool_calls": [{"name": "hub_list_devices"}],
            },
        }), encoding="utf-8")
        self.q = "What is the currently reported state of the test light? Read only."
        self.report = {
            "supported_facts": ["The returned test value was on"],
            "unsupported_definite_causes": [],
            "unknowns": ["Physical state was not independently observed"],
            "tool_errors": [],
            "missing_sources": [],
        }
        def arm(version, source, at):
            return {
                "installed_version": version,
                "model": "fictional-model",
                "provider": "fictional-provider",
                "captured_at_utc": at,
                "first_answer_capture": source,
                "human_review": self.report,
                "scores": {
                    "factual_grounding": 2,
                    "source_completeness": 1,
                    "causal_calibration": None,
                    "usefulness": 2,
                },
                "unexpected_mutations": [], "tool_attempt_errors": [],
                "elapsed_ms": 1120,
            }
        self.base = {
            "schema": pairs.SCHEMA,
            "cases": [{
                "id": "pair-01",
                "domain": "current_state",
                "question": self.q,
                "read_only": True,
                "arms": {
                    "v1": arm("0.18.459", "v1.json", "2026-11-11T13:00:00+00:00"),
                    "v2": arm("2.0.0-alpha.51", "v2.json", "2026-11-11T13:01:00Z"),
                },
            }],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_manually_rated_pair_and_sealed_report(self):
        info = pairs.validate(self.base, self.root)
        self.assertEqual(info["counts"], {
            "cases": 1, "paired": 1, "fully_rated": 1,
            "read_only_mutation_flags": 0,
        })
        self.assertEqual(info["cases"][0]["capture_delta_seconds"], 60)
        self.assertTrue(info["cases"][0]["live_state_comparable_within_5m"])
        self.assertEqual(info["cases"][0]["arms"]["v1"]["score"]["points"], 5)
        self.assertEqual(info["cases"][0]["arms"]["v1"]["score"]["maximum"], 6)
        self.assertEqual(len(info["cases"][0]["arms"]["v1"]["capture"]["sha256"]), 64)
        result = pairs.render_markdown(info)
        self.assertIn("| pair-01 | current_state | 5/6 | 5/6 | Both | Both |", result)
        self.assertNotIn("SECRET_SHOULD_NOT_APPEAR", result)
        self.assertNotIn("OTHER_SECRET", result)
        self.assertNotIn(self.q, result)
        self.assertNotIn("v1.json", result)
        self.assertNotIn("test light", result)
        self.assertNotIn(str(self.root), result)

    def test_partial_pair_is_pending_not_zero_score(self):
        self.base["cases"][0]["arms"].pop("v1")
        self.base["cases"][0]["arms"]["v2"]["scores"] = None
        info = pairs.validate(self.base, self.root)
        self.assertEqual(info["counts"]["paired"], 0)
        self.assertEqual(info["counts"]["fully_rated"], 0)
        self.assertIn("—", pairs.render_markdown(info))

    def test_different_provider_and_time_are_flagged_not_interpreted(self):
        arm = self.base["cases"][0]["arms"]["v2"]
        arm["provider"] = "different-provider"
        arm["captured_at_utc"] = "2026-11-11T13:30:00+00:00"
        info = pairs.validate(self.base, self.root)
        item = info["cases"][0]
        self.assertFalse(item["same_provider"])
        self.assertFalse(item["live_state_comparable_within_5m"])
        self.assertEqual(item["capture_delta_seconds"], 1800)
        self.assertIn("Different", pairs.render_markdown(info))

    def test_historical_question_requires_actual_valid_window_when_supplied(self):
        case = self.base["cases"][0]
        case["domain"] = "historical_measurement"
        case["window_utc"] = {
            "start": "2026-11-10T20:00:00Z",
            "end": "2026-11-11T08:00:00Z",
        }
        info = pairs.validate(self.base, self.root)
        self.assertTrue(info["cases"][0]["window_recorded"])
        case["window_utc"]["end"] = "2026-11-10T19:00:00Z"
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)

    def test_requires_read_only_and_never_infers_approval(self):
        self.base["cases"][0]["read_only"] = False
        with self.assertRaisesRegex(pairs.PairReviewError, "read-only"):
            pairs.validate(self.base, self.root)

    def test_mutation_flags_not_silently_called_safe(self):
        self.base["cases"][0]["arms"]["v2"]["unexpected_mutations"] = [
            "One test-recorded write attempt"
        ]
        info = pairs.validate(self.base, self.root)
        self.assertEqual(info["counts"]["read_only_mutation_flags"], 1)
        self.assertIn("Reported unexpected mutation flags: **1**",
                      pairs.render_markdown(info))

    def test_rating_requires_all_criteria_and_no_boolean_scores(self):
        score = self.base["cases"][0]["arms"]["v2"]["scores"]
        score["factual_grounding"] = True
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)
        score["factual_grounding"] = 1
        score.pop("usefulness")
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)
        score["usefulness"] = None
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)

    def test_missing_review_categories_rejected(self):
        self.base["cases"][0]["arms"]["v1"]["human_review"].pop("unknowns")
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)

    def test_capture_cannot_escape_private_directory(self):
        self.base["cases"][0]["arms"]["v1"]["first_answer_capture"] = "../other.json"
        with self.assertRaisesRegex(pairs.PairReviewError, "private folder"):
            pairs.validate(self.base, self.root)

    def test_missing_capture_fails_instead_of_assuming_absent_records(self):
        self.base["cases"][0]["arms"]["v1"]["first_answer_capture"] = "missing.json"
        with self.assertRaisesRegex(pairs.PairReviewError, "missing"):
            pairs.validate(self.base, self.root)

    def test_duplicate_pair_ids_rejected(self):
        self.base["cases"].append(self.base["cases"][0].copy())
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)

    def test_na_only_allowed_for_causal_calibration(self):
        self.base["cases"][0]["arms"]["v1"]["scores"]["causal_calibration"] = 1
        info = pairs.validate(self.base, self.root)
        self.assertEqual(info["cases"][0]["arms"]["v1"]["score"]["maximum"], 8)
        self.assertEqual(info["cases"][0]["arms"]["v1"]["score"]["points"], 6)

    def test_unknown_domain_or_invalid_timestamp_rejected(self):
        self.base["cases"][0]["domain"] = "read_and_write"
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)
        self.base["cases"][0]["domain"] = "current_state"
        self.base["cases"][0]["arms"]["v1"]["captured_at_utc"] = "2026-11-11T13:00:00"
        with self.assertRaises(pairs.PairReviewError):
            pairs.validate(self.base, self.root)


if __name__ == "__main__":
    unittest.main()
