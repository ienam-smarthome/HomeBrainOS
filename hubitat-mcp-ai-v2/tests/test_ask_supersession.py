"""Fresh Ask/Speak supersession with real FastAPI route/gate, fictional devices.

No live model, Hubitat, browser microphone, credentials or private receipts.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

import app as runtime
from interaction import Interaction
from mcp import MCPError


UI_HEADERS = {"X-Homebrain-Request": "1"}


class FakeNativeModel:
    def __init__(self):
        self.submissions = []
        self.started = []
        self.prepare_flags = []
        self.writes_started = asyncio.Event()

    async def answer(self, question, history, mcp, deadline, before_call=None,
                     **kwargs):
        self.started.append(question)
        self.prepare_flags.append(bool(kwargs.get('prepare_action', False)))
        if question == "OLD pending approval":
            await before_call(
                "hub_call_device_command",
                {"deviceId": "FICTIONAL-1", "command": "on"},
                "Fictional lamp test only",
            )
            self.submissions.append("OLD")
            return {"success": True, "answer": "OLD command done",
                    "tool_calls": [], "elapsed_ms": 5}
        if question == "OLD in-flight write":
            owner = getattr(before_call, "__self__", None)
            await before_call(
                "hub_call_device_command",
                {"deviceId": "FICTIONAL-1", "command": "off"},
                "Fictional lamp test only",
            )
            owner.note_native_write_submission()
            self.writes_started.set()
            await asyncio.sleep(600)
            return {"success": False, "answer": "Late unknown",
                    "tool_calls": []}
        return {"success": True, "answer": "NEW answered independently",
                "tool_calls": [], "elapsed_ms": 1}


class SupersessionHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        state = runtime.app.state
        self.original = {
            name: (name in state._state, state._state.get(name))
            for name in ("configuration_error", "mcp", "model", "options",
                         "ask_lock", "interactions", "ask_tasks")
        }
        state.configuration_error = None
        state.mcp = object()
        self.model = FakeNativeModel()
        state.model = self.model
        state.options = {"investigation_timeout_seconds": 300}
        state.ask_lock = asyncio.Lock()
        state.interactions = {}
        state.ask_tasks = {}
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=runtime.app),
            base_url="http://testserver"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        state = runtime.app.state
        for key, (present, value) in self.original.items():
            if present:
                state._state[key] = value
            else:
                state._state.pop(key, None)

    async def test_prepare_action_preserves_user_intent(self):
        original = "Turn off fictional reading lamp"
        response = await self.client.post("/api/ask", headers=UI_HEADERS, json={
            "request_id": str(uuid4()), "question": original,
            "history": [], "prepare_action": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.model.started[-1], original)
        self.assertIs(self.model.prepare_flags[-1], True)

    async def start_old(self, question):
        rid = str(uuid4())
        task = asyncio.create_task(self.client.post(
            "/api/ask", headers=UI_HEADERS, json={
                "request_id": rid, "question": question,
                "history": [], "conversation_id": None,
            }
        ))
        for _ in range(100):
            if rid in runtime.app.state.interactions:
                if (runtime.app.state.interactions[rid].pending
                        or question == "OLD in-flight write"
                        and self.model.writes_started.is_set()):
                    break
            await asyncio.sleep(0.01)
        self.assertIn(rid, runtime.app.state.interactions)
        return rid, task

    async def test_new_ask_bypasses_old_approval_after_server_cancel(self):
        rid, old = await self.start_old("OLD pending approval")
        old_gate = runtime.app.state.interactions[rid]
        pending = old_gate.pending
        self.assertIsNotNone(pending)
        self.assertFalse(self.model.submissions)
        self.assertEqual(old_gate.status()["phase"]["kind"], "awaiting_approval")
        self.assertEqual(old_gate.status()["pending"]["id"], pending["id"])
        denied = await self.client.post(f"/api/activity/{rid}/cancel")
        self.assertEqual(denied.status_code, 403)
        result = await self.client.post(
            f"/api/activity/{rid}/cancel", headers=UI_HEADERS)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["cancelled"])
        self.assertFalse(result.json()["native_write_outcome_unknown"])
        self.assertTrue(old_gate.status()["cancelled"])
        self.assertIsNone(old_gate.pending)
        with self.assertRaises(ValueError):
            old_gate.decide(pending["id"], True)
        second = await asyncio.wait_for(self.client.post(
            "/api/ask", headers=UI_HEADERS, json={
                "request_id": str(uuid4()),
                "question": "NEW fresh speak", "conversation_id": None,
                "history": [],
            }
        ), timeout=2.0)
        self.assertEqual(second.status_code, 200)
        self.assertIn("NEW answered independently", second.json()["answer"])
        self.assertNotIn("OLD", self.model.submissions)
        self.assertFalse(runtime.app.state.ask_lock.locked())
        await asyncio.gather(old, return_exceptions=True)

    async def test_inflight_write_cancellation_reports_unknown_and_no_retry(self):
        rid, old = await self.start_old("OLD in-flight write")
        gate = runtime.app.state.interactions[rid]
        self.assertIsNotNone(gate.pending)
        gate.decide(gate.pending["id"], True)
        await asyncio.wait_for(self.model.writes_started.wait(), timeout=2)
        self.assertTrue(self.model.writes_started.is_set())
        outcome = await self.client.post(
            f"/api/activity/{rid}/cancel", headers=UI_HEADERS)
        self.assertTrue(outcome.json()["cancelled"])
        self.assertTrue(outcome.json()["native_write_outcome_unknown"])
        second = await asyncio.wait_for(self.client.post(
            "/api/ask", headers=UI_HEADERS, json={
                "request_id": str(uuid4()), "question": "NEW read only",
                "conversation_id": None, "history": []
            }
        ), timeout=2)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.model.submissions, [])
        await asyncio.gather(old, return_exceptions=True)

    async def test_cancelling_nonexistent_request_does_not_claim_action(self):
        result = await self.client.post(
            f"/api/activity/{uuid4()}/cancel", headers=UI_HEADERS)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["cancelled"])
        self.assertEqual(result.json()["reason"], "request_not_active")

    async def test_interaction_rejects_native_calls_after_invalidation(self):
        gate = Interaction(require_native_write_approval=True)
        gate.invalidate()
        with self.assertRaises(MCPError):
            await gate.before_call(
                "hub_call_device_command",
                {"deviceId": "FAKE-1", "command": "on"},
                "Fictional only"
            )
        with self.assertRaises(MCPError):
            gate.note_native_write_submission()


class SourceUiFreshChatTests(unittest.TestCase):
    def test_v2_new_ask_speak_both_replace_busy_request(self):
        html = (Path(__file__).resolve().parents[1] /
                "rootfs" / "app" / "ui.html").read_text(encoding="utf-8")
        for source in (
            'id="cancelAsk"', "async function invalidateActiveAsk(requestId)",
            "async function cancelCurrentAsk()", "async function newConversation()",
            "const previousRequest=activeRequest",
            "await invalidateActiveAsk(previousRequest)",
            "resetFreshAskConversation();",
            "conversationId=newRequestId();",
            "history:[]", "const token=++askGeneration",
            "if(activeRequest!==requestId||token!==askGeneration)return;",
            "if(shouldSend&&byId('question').value.trim()){",
            "const ready=!!q.value.trim();",
            "Awaiting approval:",
            "if(phase==='model')",
            "if(activeAskController)activeAskController.abort()",
        ):
            self.assertIn(source, html, source)
        self.assertNotIn("if(!q||activeRequest)return", html)
        self.assertNotIn("Finish the current request before speaking", html)
        self.assertNotIn("if(byId('send').disabled)return;", html)
        self.assertNotIn("question:q,history:messages.slice(-12)", html)


if __name__ == "__main__":
    unittest.main()
