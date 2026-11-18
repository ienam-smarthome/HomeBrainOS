"""In-add-on acceptance uses frozen prompts and private original receipts."""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

ADDON = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ADDON / "rootfs" / "app"), str(ADDON / "tools")]

from acceptance_routes import router
from source_real_acceptance import ALPHA145_LABEL_FIELDS, ALPHA145_VERSION


class Hub:
    writes_enabled = False

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_get_info", "annotations": {"readOnlyHint": True}},
            {"name": "hub_call_device_command", "annotations": {"readOnlyHint": False}},
        ]

    async def call(self, name, args):
        if name != "hub_get_info":
            raise AssertionError("Unexpected native operation")
        return {"content": [{"type": "text", "text": json.dumps({
            "readEnabled": True,
            "clientAccess": {
                "client": "fixture", "readEnabled": True,
                "writeEnabled": self.writes_enabled,
            },
        })}]}


class Model:
    model = "fictional"
    calls = 0

    async def answer(self, question, history, hub, timeout):
        self.calls += 1
        assert not history
        assert [tool["name"] for tool in await hub.list_tools()] == ["hub_get_info"]
        receipt = await hub.call("hub_get_info", {})
        return {"success": True, "answer": "Fixture state", "tool_calls": [{
            "name": "hub_get_info", "arguments": {}, "success": True,
            "response": json.dumps(receipt), "result_kind": "tool_result",
        }]}


class AcceptanceWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_seal_permission_capture_and_offline_report(self):
        app = FastAPI(version=ALPHA145_VERSION)
        app.include_router(router)
        consent = {"model_and_private_evidence_consent": True}
        state = app.state
        with tempfile.TemporaryDirectory() as directory:
            state.acceptance_directory = Path(directory) / "study"
            state.configuration_error = None
            state.mcp = Hub()
            state.model = Model()
            state.options = {"investigation_timeout_seconds": 60}
            state.ask_lock = asyncio.Lock()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
                headers={"X-Homebrain-Request": "1"},
            ) as client:
                prefix = "/api/acceptance/"
                labels = {key: "Fixture " + key for key in ALPHA145_LABEL_FIELDS}
                setup = await client.post(prefix + "prepare", json={"labels": labels})
                self.assertEqual(setup.status_code, 200, setup.text)
                self.assertEqual(setup.json()["cases_frozen"], 10)
                cases = (await client.get(prefix + "status")).json()["cases"]
                self.assertEqual(len(cases), 10)

                capture_url = prefix + cases[0]["id"] + "/capture"
                state.mcp.writes_enabled = True
                denied = await client.post(capture_url, json=consent)
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(state.model.calls, 0)
                state.mcp.writes_enabled = False
                captured = await client.post(capture_url, json=consent)
                self.assertEqual(captured.status_code, 200, captured.text)
                repeat = await client.post(capture_url, json=consent)
                self.assertEqual(repeat.status_code, 409)

                export = await client.get(prefix + cases[0]["id"] + "/export")
                self.assertEqual(export.json()["question"], cases[0]["question"])
                self.assertEqual(export.json()["ui_version"], ALPHA145_VERSION)
                self.assertEqual(export.headers["cache-control"], "no-store")
                for case in cases[1:]:
                    captured = await client.post(
                        prefix + case["id"] + "/capture", json=consent,
                    )
                    self.assertEqual(captured.status_code, 200, captured.text)
                report = await client.get(prefix + "report")
                self.assertEqual(report.status_code, 200, report.text)
                self.assertEqual(report.json()["capture_workflow"], "in_addon_read_only_catalog")
                self.assertNotIn(cases[0]["question"], report.text)
                self.assertEqual(state.model.calls, 10)
