"""Offline fixed-source pair benchmark: synthetic and privacy-only tests.

No network, model, hub, user data, external apps or actual device commands.
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "tools" / "fixed_source_benchmark.py"
spec = importlib.util.spec_from_file_location("v2_fixed_source_benchmark", FILE)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def mcp(body):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(body)}]})


def example(*, previous=0, action=True):
    device = "SYNTHETIC-PRIVATE-DEVICE-123"
    calls = [
        {
            "name": "hub_list_devices",
            "arguments": {"labelFilter": "SYNTHETIC-PRIVATE-NAME"},
            "success": True,
            "response": mcp({"devices": [{
                "id": device, "label": "SYNTHETIC-PRIVATE-NAME",
                "currentStates": {"switch": "off"}}]}),
        },
    ]
    if action:
        calls += [
            {"name": "hub_call_device_command",
             "arguments": {"deviceId": device, "command": "on"},
             "success": True,
             "response": mcp({"success": True, "command": "on",
                              "state": {"switch": {"value": "off"}}})},
            {"name": "hub_get_device_attribute",
             "arguments": {"deviceId": device, "attribute": "switch"},
             "success": True,
             "response": mcp({"attribute": "switch", "value": "on"})},
        ]
    else:
        calls += [
            {"name": "hub_list_device_events",
             "arguments": {"deviceId": device, "limit": 1},
             "success": True, "response": mcp({"device": device, "events": [{
                 "name": "switch", "value": "off", "date": "2020-01-01T01:00:00Z"
             }]})},
            {"name": "hub_get_logs",
             "arguments": {"mode": "past", "limit": 1},
             "success": True, "response": mcp({"mode": "past", "matched": 99,
                                                "entries": [{"message": "PRIVATE-ERROR-NEVER-REVEAL"}]})},
        ]
    return {
        "ui_version": "2.0.0-alpha.18",
        "model": "synthetic-private-model",
        "request_id": "PRIVATE-REQUEST-NEVER-REVEAL",
        "question": "Change SYNTHETIC-PRIVATE-DEVICE-123 to on"
                    if action else "Why did SYNTHETIC-PRIVATE-DEVICE-123 switch off?",
        "client_elapsed_ms": 9000,
        "response": {
            "answer": "ORIGINAL-PRIVATE-ANSWER-DO-NOT-SHOW",
            "rounds": 4,
            "prior_receipts_used": previous,
            "prior_sources_indexed": previous,
            "tool_calls": calls,
        },
    }


class FixedSourceBenchmarkTests(unittest.TestCase):
    def make_export(self, directory, name, data):
        path = directory / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_pair_fixes_all_native_responses_and_blinds_conditions(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            case = self.make_export(home, "fixture", example())
            output = home / "private-output"
            summary = bench.prepare([case], output, 42)
            self.assertEqual(summary["created_case_pairs"], 1)
            self.assertEqual(summary["model_calls_executed"], 0)
            self.assertEqual(summary["live_actions_executed"], 0)
            a = json.loads((output / "case-001-A.json").read_text())
            b = json.loads((output / "case-001-B.json").read_text())
            private = json.loads((output / "private_manifest.json").read_text())
            self.assertTrue(bench._check_pair(
                a if private["cases"][0]["condition_map"]["A"] == "baseline" else b,
                b if private["cases"][0]["condition_map"]["A"] == "baseline" else a,
                private["cases"][0]["source_sha256"],
            ))
            self.assertNotIn("ORIGINAL-PRIVATE-ANSWER-DO-NOT-SHOW",
                             (output / "case-001-A.json").read_text())
            self.assertEqual(a["recorded_user_question"], b["recorded_user_question"])
            self.assertEqual(a["instructions"], b["instructions"])
            self.assertEqual(len(a["native_tool_receipts"]), 3)
            self.assertEqual(len(b["native_tool_receipts"]), 3)
            self.assertFalse(any("condition_map" in c for c in (a, b)))
            self.assertEqual(
                sum("generic_source_role_note" in x for x in a["native_tool_receipts"])
                + sum("generic_source_role_note" in x for x in b["native_tool_receipts"]),
                3,
            )
            self.assertNotIn("SYNTHETIC-PRIVATE", json.dumps(summary))
            if os.name == "posix":
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertEqual((output / "case-001-A.json").stat().st_mode & 0o777,
                                 0o600)

    def test_prior_session_excluded_and_balanced_source_assignment(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            cases = [self.make_export(home, f"case{i}",
                       example(action=i % 2 == 0)) for i in range(6)]
            prior = self.make_export(home, "prior", example(previous=3))
            output = home / "private"
            summary = bench.prepare(cases + [prior], output, 100)
            self.assertEqual(summary["created_case_pairs"], 6)
            self.assertEqual(summary["skipped_prior_context"], 1)
            private = json.loads((output / "private_manifest.json").read_text())
            count = sum(c["condition_map"]["A"] == "baseline" for c in private["cases"])
            self.assertEqual(count, 3)
            self.assertEqual(set(c["condition_map"]["B"] for c in private["cases"]),
                             {"baseline", "role_notes"})
            with self.assertRaises(ValueError):
                bench.prepare(cases, output, 100)

    def test_source_role_annotations_are_general_and_not_source_leaks(self):
        led = bench._receipt_ledger(example(action=False))
        a = [{**c, "generic_source_role_note": bench._source_role(c)} for c in led]
        self.assertIn("current-state snapshots", a[0]["generic_source_role_note"])
        self.assertIn("Discrete returned event rows", a[1]["generic_source_role_note"])
        self.assertIn("bounded log response", a[2]["generic_source_role_note"])
        for c in a:
            note = c["generic_source_role_note"]
            self.assertNotIn("SYNTHETIC-PRIVATE", note)
            self.assertNotIn("PRIVATE-ERROR", note)
        self.assertEqual(bench._strip_note(a), led)

    def test_report_requires_two_answers_and_blind_human_ratings(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            inp = self.make_export(home, "source", example())
            folder = home / "private"
            bench.prepare([inp], folder, 42)
            report0 = bench.report(folder, home / "empty-report.json")
            self.assertEqual(report0["blind_reviewed_pairs"], 0)
            self.assertEqual(report0["missing_pair_answers"], 1)
            for label in ("A", "B"):
                (folder / "answers" / f"case-001-{label}.txt").write_text(
                    f"Blind review answer {label}, not auto scored", encoding="utf-8")
            report1 = bench.report(folder, home / "unrated-report.json")
            self.assertEqual(report1["blind_reviewed_pairs"], 0)
            self.assertEqual(report1["missing_pair_ratings"], 1)
            ratings_file = folder / "blind_ratings.json"
            ratings = json.loads(ratings_file.read_text())
            for label in ("A", "B"):
                ratings["cases"]["case-001"][label]["ratings"] = {
                    k: 1 for k in bench.RUBRIC
                }
                ratings["cases"]["case-001"][label]["elapsed_ms"] = 1111
            mapping = json.loads((folder / "private_manifest.json").read_text())
            enhanced_label = next(
                label for label, kind in mapping["cases"][0]["condition_map"].items()
                if kind == "role_notes"
            )
            ratings["cases"]["case-001"][enhanced_label]["ratings"]["factual_grounding"] = 2
            ratings_file.write_text(json.dumps(ratings))
            scored = bench.report(folder, home / "scored-report.json")
            self.assertEqual(scored["blind_reviewed_pairs"], 1)
            grounding = scored["condition_effects"]["factual_grounding"]
            self.assertEqual(grounding["mean_role_notes_minus_baseline"], 1)
            self.assertEqual(grounding["role_notes_better"], 1)
            self.assertEqual(scored["elapsed_ms_difference_role_notes_minus_baseline"]
                             ["median_difference"], 0)
            report_text = json.dumps(scored)
            for private in ("SYNTHETIC-PRIVATE", "PRIVATE-REQUEST",
                            "ORIGINAL-PRIVATE", "2020-01", "hub_call_device_command"):
                self.assertNotIn(private, report_text)

    def test_tampered_native_receipt_fails_before_scoring(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            inp = self.make_export(home, "fixture", example())
            folder = home / "private"
            bench.prepare([inp], folder, 42)
            payload_path = folder / "case-001-B.json"
            payload = json.loads(payload_path.read_text())
            payload["native_tool_receipts"][0]["success"] = False
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "integrity"):
                bench.report(folder, home / "tampered-report.json")

    def test_output_inside_repository_is_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            inp = self.make_export(Path(scratch), "fixture", example())
            with self.assertRaisesRegex(ValueError, "OUTSIDE"):
                bench.prepare([inp], ROOT / "unsafe-private-output", 42)

    def test_source_with_no_prior_but_archived_receipt_is_excluded(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            source = example()
            source["response"]["tool_calls"].append({
                "name": "homebrain_read_prior_evidence",
                "result_kind": "prior_evidence_read",
                "success": True,
                "response": "{}",
            })
            inp = self.make_export(home, "prior-hidden", source)
            with self.assertRaises(ValueError):
                bench.prepare([inp], home / "private", 42)

    def test_report_rejects_invalid_ratings_and_preserves_no_model_claim(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            inp = self.make_export(home, "source", example())
            folder = home / "private"
            bench.prepare([inp], folder, 43)
            for label in ("A", "B"):
                (folder / "answers" / f"case-001-{label}.txt").write_text(
                    "OFFLINE ANSWER", encoding="utf-8")
            ratings_path = folder / "blind_ratings.json"
            ratings = json.loads(ratings_path.read_text())
            for label in ("A", "B"):
                ratings["cases"]["case-001"][label]["ratings"] = {
                    k: 1 for k in bench.RUBRIC
                }
            ratings["cases"]["case-001"]["B"]["ratings"]["factual_grounding"] = True
            ratings_path.write_text(json.dumps(ratings))
            report = bench.report(folder, home / "not-scored.json")
            self.assertEqual(report["blind_reviewed_pairs"], 0)
            self.assertEqual(report["missing_pair_ratings"], 1)
            self.assertEqual(report["model_calls_executed_by_this_tool"], 0)


if __name__ == "__main__":
    unittest.main()
