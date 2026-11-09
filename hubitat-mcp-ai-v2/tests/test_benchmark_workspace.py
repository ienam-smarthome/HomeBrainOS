"""Synthetic privacy and tool-free browser benchmark API tests (no home or cloud)."""
from __future__ import annotations

import asyncio
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import httpx
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from benchmark import (BenchmarkWorkspace, BenchmarkError, CATEGORIES, SCHEMA,
                       _sha, model_answer)
from benchmark_routes import router


PRIVATE = "SYNTHETIC_HOUSEHOLD_PRIVATE_DEVICE_NAME"


def frozen_zip(note=True):
    raw_receipt = [{"call_order": 1, "tool": "hub_get_device_attribute",
                    "arguments": {"deviceId": PRIVATE, "attribute": "switch"},
                    "success": True, "response": json.dumps({
                        "attribute": "switch", "value": "off", "private": PRIVATE,
                    })}]
    base = {"instructions": "Retrospective review. No tools or actions.",
            "recorded_user_question": "Why is " + PRIVATE + " off?",
            "native_tool_receipts": raw_receipt}
    role = {"instructions": base["instructions"],
            "recorded_user_question": base["recorded_user_question"],
            "native_tool_receipts": [dict(raw_receipt[0],
                                         generic_source_role_note="A current read, not causality.")]}
    manifest = {"schema": SCHEMA, "seed": 42, "cases": [{
        "case_id": "case-001", "source_sha256": _sha(raw_receipt),
        "condition_map": {"A": "role_notes", "B": "baseline"},
    }]}
    scores = {"schema": SCHEMA, "categories": list(CATEGORIES), "cases": {
        "case-001": {
            label: {"ratings": {name: None for name in CATEGORIES}, "elapsed_ms": None}
            for label in ("A", "B")
        },
    }}
    result = io.BytesIO()
    with zipfile.ZipFile(result, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("private_manifest.json", json.dumps(manifest))
        archive.writestr("blind_ratings.json", json.dumps(scores))
        archive.writestr("case-001-A.json", json.dumps(role if note else base))
        archive.writestr("case-001-B.json", json.dumps(base))
    return result.getvalue()


class PrivateBenchmarkTests(unittest.TestCase):
    def test_zip_rejects_modified_pairs_and_archive_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            store = BenchmarkWorkspace(Path(root) / "private")
            with self.assertRaises(BenchmarkError):
                store.import_zip(frozen_zip(note=False))
            self.assertFalse(store.available())
            raw = io.BytesIO()
            with zipfile.ZipFile(raw, "w") as archive:
                archive.writestr("../private_manifest.json", "x")
            with self.assertRaises(BenchmarkError):
                store.import_zip(raw.getvalue())
            self.assertFalse((Path(root) / "private_manifest.json").exists())

    def test_private_import_source_and_blind_review_aggregate(self):
        with tempfile.TemporaryDirectory() as root:
            store = BenchmarkWorkspace(Path(root) / "private")
            self.assertEqual(store.import_zip(frozen_zip()), 1)
            self.assertTrue(store.available())
            self.assertEqual(store.summary()["cases"][0]["answered"], False)
            with self.assertRaises(BenchmarkError):
                store.import_zip(frozen_zip())
            info = store.case("case-001")
            self.assertIn(PRIVATE, json.dumps(info["source"]))
            self.assertNotIn("condition_map", json.dumps(info))
            self.assertNotIn("generic_source_role_note", json.dumps(info["source"]))
            self.assertEqual(store.pending(["case-001"]), [
                ("case-001", "A"), ("case-001", "B")])
            store.store_answer("case-001", "A", "Synthetic answer", 120)
            self.assertEqual(store.case("case-001")["answers"], {})
            with self.assertRaises(BenchmarkError):
                store.score("case-001", {"A": {}, "B": {}})
            store.store_answer("case-001", "B", "Another synthetic answer", 100)
            rating = {name: 1 for name in CATEGORIES}
            higher = {name: 2 for name in CATEGORIES}
            store.score("case-001", {"A": higher, "B": rating})
            report = store.report()
            self.assertEqual(report["blind_reviewed_pairs"], 1)
            self.assertEqual(report["condition_effects"]["factual_grounding"]
                             ["role_notes_better"], 1)
            self.assertEqual(report["elapsed_ms_difference_role_notes_minus_baseline"]
                             ["median_difference"], 20)
            self.assertNotIn(PRIVATE, json.dumps(report))
            self.assertNotIn("case-001", json.dumps(report))
            self.assertNotIn("condition_map", json.dumps(report))
            self.assertEqual(store.summary()["cases"][0]["graded"], True)
            store.clear()
            self.assertFalse(store.available())

    def test_score_rejects_boolean_missing_and_invalid_categories(self):
        with tempfile.TemporaryDirectory() as root:
            store = BenchmarkWorkspace(Path(root) / "private")
            store.import_zip(frozen_zip())
            for label in ("A", "B"):
                store.store_answer("case-001", label, "Complete", 50)
            good = {category: 0 for category in CATEGORIES}
            for bad in (True, 3, "unknown", None):
                wrong = dict(good, causal_calibration=bad)
                with self.assertRaises(BenchmarkError):
                    store.score("case-001", {"A": wrong, "B": good})
            store.score("case-001", {"A": dict(good, command_outcome="n/a"),
                                      "B": good})
            self.assertEqual(store.report()["condition_effects"]["command_outcome"]
                             ["rated_pairs"], 0)


class PrivateBenchmarkApiTests(unittest.TestCase):
    def test_routes_require_ui_header_and_explicit_cloud_consent(self):
        async def run():
            with tempfile.TemporaryDirectory() as folder:
                web = FastAPI()
                web.include_router(router)
                web.state.benchmark = BenchmarkWorkspace(Path(folder) / "dataset")
                web.state.benchmark_task = None
                web.state.benchmark_progress = {"running": False, "error": None}
                web.state.configuration_error = None
                web.state.options = {
                    "model_base_url": "https://ollama.com",
                    "model_name": "gemma4:31b-cloud",
                    "model_api_key": "SYNTHETIC_FAKE_TOKEN",
                    "model_timeout_seconds": 15,
                }
                calls = []
                def handle(request):
                    data = json.loads(request.content)
                    calls.append(data)
                    self.assertEqual(request.url.path, "/api/chat")
                    self.assertEqual(data["model"], "gemma4:31b")
                    self.assertEqual(data["options"]["temperature"], 0)
                    self.assertNotIn("tools", data)
                    self.assertNotIn("mcp", data)
                    self.assertIn(PRIVATE, data["messages"][1]["content"])
                    return httpx.Response(200, json={"message": {
                        "role": "assistant", "content": "Synthetic answer with <script>raw</script>",
                    }})
                class StubModel:
                    base_url = "https://ollama.com"
                    model = "gemma4:31b"
                web.state.model = StubModel()
                web.state.model.client = httpx.AsyncClient(
                    transport=httpx.MockTransport(handle))
                t = httpx.ASGITransport(app=web)
                async with httpx.AsyncClient(transport=t, base_url="http://testserver") as client:
                    h = {"X-Homebrain-Request": "1"}
                    self.assertEqual((await client.get("/api/benchmark/status")).status_code, 403)
                    bad = await client.post("/api/benchmark/import", content=b"notzip",
                        headers={**h, "Content-Type": "application/zip"})
                    self.assertEqual(bad.status_code, 400)
                    self.assertEqual((await client.post("/api/benchmark/import", content=frozen_zip(),
                        headers=h)).status_code, 415)
                    ok = await client.post("/api/benchmark/import",
                        content=frozen_zip(), headers={**h, "Content-Type": "application/zip"})
                    self.assertEqual(ok.status_code, 200)
                    self.assertEqual(ok.json()["pairs"], 1)
                    self.assertEqual(len(calls), 0)
                    payload = {"case_ids": ["case-001"], "private_evidence_consent": True,
                               "cloud_transfer_consent": False}
                    denied = await client.post("/api/benchmark/run", json=payload, headers=h)
                    self.assertEqual(denied.status_code, 403)
                    self.assertEqual(len(calls), 0)
                    payload["cloud_transfer_consent"] = True
                    accepted = await client.post("/api/benchmark/run", json=payload, headers=h)
                    self.assertEqual(accepted.status_code, 200)
                    self.assertEqual(accepted.json()["pending"], 2)
                    await web.state.benchmark_task
                    self.assertEqual(len(calls), 2)
                    case = (await client.get("/api/benchmark/case/case-001",headers=h)).json()
                    self.assertTrue(case["both_answered"])
                    self.assertIn("<script>raw</script>", case["answers"]["A"])
                    self.assertNotIn("condition_map", json.dumps(case))
                    original = dict.fromkeys(CATEGORIES, 1)
                    self.assertEqual((await client.post(
                        "/api/benchmark/case/case-001/score",
                        json={"scores":{"A":original,"B":original}},headers=h)).status_code, 200)
                    report = (await client.get("/api/benchmark/report",headers=h)).json()
                    self.assertEqual(report["blind_reviewed_pairs"], 1)
                    self.assertNotIn(PRIVATE, json.dumps(report))
                    self.assertEqual((await client.post(
                        "/api/benchmark/delete",json={"confirm_delete":False},headers=h)).status_code, 400)
                    self.assertEqual((await client.post(
                        "/api/benchmark/delete",json={"confirm_delete":True},headers=h)).status_code, 200)
                    self.assertFalse(web.state.benchmark.available())
                await web.state.model.client.aclose()
        asyncio.run(run())

    def test_model_tool_call_result_is_rejected(self):
        async def run():
            class Stub:
                base_url = "http://localhost:11434"
                model = "synthetic"
            model = Stub()
            model.client = httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"message": {
                    "content": "Attempted tool", "tool_calls": [{"function": {"name":"off"}}],
                }})
            ))
            try:
                with self.assertRaises(BenchmarkError):
                    await model_answer(model, {"instructions":"safe", "recorded_user_question":"test",
                                             "native_tool_receipts":[]}, 5)
            finally:
                await model.client.aclose()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
