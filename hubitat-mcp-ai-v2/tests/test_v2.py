"""Safety and model-led reasoning contract smoke tests for isolated v2."""
import asyncio
import json
import sys
import tempfile
import unittest

import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent, arguments_of, compact_tool_result, model_tools, cpu_load_context
from external_hub_diagnostics import ExternalHubDiagnostics, validate_hub_url
from mcp import MCPError, MCPClient, redact
from interaction import Interaction, needs_confirmation


class ToolSafetyTests(unittest.TestCase):
    def test_live_catalog_pagination_gateway_discovery_and_writes(self):
        calls = []
        generation = [0]
        def reply(request):
            data = json.loads(request.content)
            calls.append(data)
            method = data["method"]
            if method == "initialize":
                result = {"protocolVersion": "2025-03-26", "capabilities": {}}
                return httpx.Response(200, json={"id": data["id"], "result": result},
                                      headers={"Mcp-Session-Id": "test-session"})
            if method == "notifications/initialized":
                return httpx.Response(202)
            self.assertEqual(request.headers["mcp-session-id"], "test-session")
            self.assertEqual(request.headers["mcp-protocol-version"], "2025-03-26")
            if method == "tools/list":
                if generation[0]:
                    result = {"tools": [{"name": "new_server_tool", "inputSchema": {
                        "type": "object", "properties": {}}}]}
                elif not data["params"]:
                    result = {"tools": [{"name": "hub_get_info"},
                                        {"name": "hub_manage_rule_machine"}],
                              "nextCursor": "page2"}
                else:
                    self.assertEqual(data["params"], {"cursor": "page2"})
                    result = {"tools": [{"name": "hub_call_device_command",
                                         "annotations": {"readOnlyHint": False}}]}
            else:
                self.assertEqual(method, "tools/call")
                name = data["params"]["name"]
                if name == "hub_manage_rule_machine" and not data["params"]["arguments"]:
                    result = {"content": [{"type": "text", "text": "live gateway schemas"}]}
                elif name == "hub_manage_rule_machine":
                    result = {"isError": True, "content": [{"type": "text", "text": "Write tools are disabled"}]}
                else:
                    result = {"content": [{"type": "text", "text": '{"password":"private-value"}'}]}
            return httpx.Response(200, json={"id": data["id"], "result": result})
        async def run():
            mcp = MCPClient("http://192.168.1.239/mcp")
            await mcp._client.aclose()
            mcp._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
            try:
                catalog = await mcp.list_tools(refresh=True)
                self.assertEqual([t["name"] for t in catalog],
                                 ["hub_get_info", "hub_manage_rule_machine", "hub_call_device_command"])
                self.assertFalse(catalog[-1]["annotations"]["readOnlyHint"])
                discovery = await mcp.call("hub_manage_rule_machine", {})
                self.assertIn("live gateway schemas", json.dumps(discovery))
                result = await mcp.call("hub_call_device_command", {"deviceId": 1, "command": "on"})
                self.assertNotIn("private-value", json.dumps(result))
                denied = await mcp.call("hub_manage_rule_machine", {
                    "tool": "hub_set_rule", "args": {"operation": "create"}})
                self.assertTrue(denied["isError"])
                before = len(calls)
                with self.assertRaises(MCPError):
                    await mcp.call("invented_tool", {})
                self.assertEqual(len(calls), before)
                generation[0] = 1
                await mcp.list_tools(refresh=True)
                self.assertEqual(list(mcp._tools), ["new_server_tool"])
                with self.assertRaises(MCPError):
                    await mcp.call("hub_call_device_command", {})
            finally:
                await mcp.close()
        asyncio.run(run())

    def test_repeated_catalog_cursor_is_rejected(self):
        def reply(request):
            data = json.loads(request.content)
            return httpx.Response(200, json={"id": data["id"], "result": {
                "tools": [], "nextCursor": "same"}})
        async def run():
            mcp = MCPClient("http://192.168.1.239/mcp")
            mcp._initialized = True
            await mcp._client.aclose()
            mcp._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
            try:
                with self.assertRaises(MCPError):
                    await mcp.list_tools()
            finally:
                await mcp.close()
        asyncio.run(run())

    def test_write_transport_failure_is_not_retried(self):
        count = []
        def reply(request):
            count.append(request)
            raise httpx.ReadTimeout("uncertain outcome")
        async def run():
            mcp = MCPClient("http://192.168.1.239/mcp")
            mcp._initialized = True
            mcp._tools = {"hub_call_device_command": {"name": "hub_call_device_command"}}
            await mcp._client.aclose()
            mcp._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
            try:
                with self.assertRaises(MCPError):
                    await mcp.call("hub_call_device_command", {"deviceId": 1, "command": "on"})
                self.assertEqual(len(count), 1)
            finally:
                await mcp.close()
        asyncio.run(run())

    def test_schemas_not_derived_from_name(self):
        tools = model_tools([{
            "name": "hub_read_devices", "description": "Gateway",
            "inputSchema": {
                "type": "object", "properties": {"tool": {"type": "string"}}
            },
        }])
        self.assertEqual(tools[0]["function"]["parameters"]["properties"],
                         {"tool": {"type": "string"}})

    def test_bad_arguments_are_invalid_not_executed(self):
        self.assertIn("_invalid_arguments", arguments_of({
            "function": {"name": "hub_get_device", "arguments": "{broken"}
        }))

    def test_recorder_validates_lan(self):
        self.assertEqual(validate_hub_url("http://192.168.1.239"),
                         "http://192.168.1.239")
        for bad in ("http://example.com", "https://192.168.1.239",
                    "http://127.0.0.1", "http://192.168.1.239/private"):
            with self.assertRaises(ValueError):
                validate_hub_url(bad)

    def test_redact_token_value_nested_and_text(self):
        item = {"output": [{"api_key": "example-key", "password": "example-password"}],
                "authorization": "Bearer something-secret",
                "plain": "access_token=example-token"}
        result = redact(item)
        self.assertNotIn("example-key", json.dumps(result))
        self.assertNotIn("example-password", json.dumps(result))
        self.assertNotIn("example-token", json.dumps(result))
        self.assertIn("[REDACTED]", json.dumps(result))

    def test_large_result_explicitly_truncated(self):
        result = compact_tool_result({"content": "x" * 1000}, max_chars=40)
        self.assertTrue(json.loads(result)["truncated"])


class AgentContractTests(unittest.TestCase):

    def test_cpu_load_equivalent_uses_configured_cores_and_preserves_receipt(self):
        source = {"content": [{"type": "text", "text": json.dumps({
            "entries": [
                {"timestamp": "11-10 10:53:32", "cpuLoad5min": "0.68"},
                {"timestamp": "11-10 10:58:32", "cpuLoad5min": "0.65"},
            ],
            "summary": {"showing": "2 of 152 (most recent)"},
        })}]}
        original = json.dumps(source, sort_keys=True)
        agent = Agent("http://localhost:11434", "mock", "", 20, cpu_cores=4)
        try:
            visible = agent.present_native_result(source, {})
            self.assertEqual(json.dumps(source, sort_keys=True), original)
            self.assertEqual(visible["content"], source["content"])
            meta = visible["client_cpu_load_context"]
            self.assertEqual(meta["configured_cpu_cores"], 4)
            self.assertEqual(meta["last_returned_sample"]["load_average_5min"], 0.65)
            self.assertEqual(meta["last_returned_sample"]["core_normalised_load_pct"], 16.25)
            self.assertEqual(meta["returned_samples"][0]["core_normalised_load_pct"], 17.0)
            self.assertEqual(meta["source_showing"], "2 of 152 (most recent)")
            self.assertIn("not measured utilisation", meta["metric_label"])
            self.assertEqual(
                cpu_load_context(source, 8)
                ["last_returned_sample"]["core_normalised_load_pct"], 8.12)
        finally:
            asyncio.run(agent.close())

    def test_cpu_load_equivalent_does_not_invent_missing_or_invalid_values(self):
        self.assertIsNone(cpu_load_context({"content": [
            {"type": "text", "text": '{"entries":[{"cpuLoad5min":"nan"},'
                                     '{"cpuLoad5min":null},{"cpuLoad5min":true}]}'}]}, 4))
        self.assertIsNone(cpu_load_context({"content": [
            {"type": "text", "text": '{"state":"off"}'}]}, 4))
        self.assertIsNone(cpu_load_context({"isError": True,
                                             "entries": [{"cpuLoad5min": "0.65"}]}, 4))
        self.assertIsNone(cpu_load_context({"content": None}, 4))
        # Load is a run-queue pressure metric and may legitimately exceed 100%.
        context = cpu_load_context({"entries": [
            {"timestamp": "x", "cpuLoad5min": "5.0"}]}, 4)
        self.assertEqual(context["last_returned_sample"]["core_normalised_load_pct"], 125.0)

    def test_model_selects_real_tools_and_answers_without_preplan(self):
        class FakeMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [{"name": "hub_get_device", "description": "Read device",
                         "inputSchema": {"type": "object", "properties": {
                             "deviceId": {"type": "integer"}}}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                return {"content": [{"type": "text", "text": '{"state":"off"}'}]}
        class FakeAgent(Agent):
            async def round(self, messages, tools, remaining):
                if not any(item.get("role") == "tool" for item in messages):
                    return {"role": "assistant", "content": "",
                            "tool_calls": [{"function": {
                                "name": "hub_get_device", "arguments": {"deviceId": 7828}
                            }}]}
                return {"role": "assistant",
                        "content": "Device 7828 reported off; cause not established."}
        async def run():
            mcp = FakeMCP()
            agent = FakeAgent("http://localhost:11434", "mock", "", 20)
            try:
                answer = await agent.answer("What happened?", [], mcp, 60)
                self.assertTrue(answer["success"])
                self.assertEqual(answer["rounds"], 2)
                self.assertEqual(mcp.calls, [("hub_get_device", {"deviceId": 7828})])
                self.assertEqual(len(answer["tool_calls"]), 1)
                self.assertEqual(answer["tool_calls"][0]["arguments"], {"deviceId": 7828})
                self.assertIn("cause not established", answer["answer"])
                self.assertEqual(json.loads(answer["tool_calls"][0]["response"]),
                                 {"content": [{"type": "text", "text": '{"state":"off"}'}]})
                async def fail_round(messages, tools, remaining):
                    if any(item.get("role") == "tool" for item in messages):
                        raise RuntimeError("Model API returned HTTP 503")
                    return {"tool_calls": [{"function": {
                        "name": "hub_get_device", "arguments": {"deviceId": 7828}}}]}
                agent.round = fail_round
                failed = await agent.answer("What happened?", [], mcp, 60)
                self.assertFalse(failed["success"])
                self.assertEqual(failed["error"], "model")
                self.assertEqual(failed["tool_calls"][0]["response"],
                                 answer["tool_calls"][0]["response"])
            finally:
                await agent.close()
        asyncio.run(run())

    def test_diagnostics_sqlite_is_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ExternalHubDiagnostics(
                enabled=True, hub_url="http://192.168.1.239",
                path=Path(tmp) / "diag.sqlite3",
            )
            recorder._initialize()
            self.assertTrue((Path(tmp) / "diag.sqlite3").exists())
            self.assertEqual(recorder.history(1)["source_sample_count"], 0)


class InteractionTests(unittest.TestCase):
    def test_confirm_flag_requires_explicit_one_use_decision(self):
        self.assertTrue(needs_confirmation({"tool": "hub_reboot", "args": {"confirm": True}}))
        self.assertFalse(needs_confirmation({"confirm": False}))
        self.assertTrue(needs_confirmation({"args": json.dumps({"confirm": True})}))
        self.assertTrue(needs_confirmation({"confirm": "false"}))
        async def run():
            interaction = Interaction()
            task = asyncio.create_task(interaction.before_call(
                "hub_manage_destructive_ops", {"tool": "hub_reboot", "args": {"confirm": True}},
                "Reboot interrupts hub automations."))
            await asyncio.sleep(0)
            pending = interaction.status()["pending"]
            self.assertIsNotNone(pending)
            self.assertFalse(task.done())
            with self.assertRaises(ValueError):
                interaction.decide("wrong-id", True)
            interaction.decide(pending["id"], True)
            with self.assertRaises(ValueError):
                interaction.decide(pending["id"], True)
            await task
            self.assertIsNone(interaction.pending)
            denied = asyncio.create_task(interaction.before_call(
                "hub_manage_destructive_ops", {"args": {"confirm": True}}, "Delete item"))
            await asyncio.sleep(0)
            interaction.decide(interaction.pending["id"], False)
            with self.assertRaises(MCPError):
                await denied
            self.assertIsNone(interaction.pending)
            expired = asyncio.create_task(interaction.before_call(
                "hub_manage_destructive_ops", {"confirm": True}, "Reboot"))
            await asyncio.sleep(0)
            approval_id = interaction.pending["id"]
            expired.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await expired
            with self.assertRaises(ValueError):
                interaction.decide(approval_id, True)
        asyncio.run(run())

    def test_agent_pauses_before_confirmed_write_and_preserves_receipt(self):
        class FakeMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [{"name": "hub_manage_rule_machine", "inputSchema": {"type": "object"}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                return {"content": [{"type": "text", "text": "created"}]}
        class FakeAgent(Agent):
            async def round(self, messages, tools, remaining):
                if messages[-1]["role"] == "tool":
                    return {"content": "Finished"}
                return {"content": "Create the requested automation.", "tool_calls": [
                    {"function": {"name": "hub_manage_rule_machine", "arguments": {
                        "tool": "hub_set_rule", "args": {"operation": "create", "confirm": True}}}}]}
        async def run():
            agent = FakeAgent("http://localhost:11434", "mock", "", 20)
            mcp = FakeMCP()
            interaction = Interaction()
            task = asyncio.create_task(agent.answer("Create automation", [], mcp, 60,
                                                   before_call=interaction.before_call))
            try:
                while interaction.pending is None:
                    if task.done():
                        self.fail("Agent completed without presenting confirmation")
                    await asyncio.sleep(0)
                self.assertEqual(mcp.calls, [])
                interaction.decide(interaction.pending["id"], True)
                answer = await task
                self.assertEqual(len(mcp.calls), 1)
                self.assertTrue(answer["tool_calls"][0]["success"])
                self.assertIn("created", answer["tool_calls"][0]["response"])
                denied = await agent.answer("Create automation", [], mcp, 60)
                self.assertEqual(len(mcp.calls), 1)
                self.assertFalse(denied["tool_calls"][0]["success"])
            finally:
                await agent.close()
        asyncio.run(run())

    def test_interface_cannot_be_cached_across_updates(self):
        import app as runtime
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.app),
                                         base_url="http://test") as client:
                page = await client.get("/")
                self.assertEqual(page.status_code, 200)
                self.assertIn("no-store", page.headers["cache-control"])
                self.assertIn('UI_VERSION="'+runtime.app.version+'"', page.text)
                # Even an old browser validator must receive the current HTML.
                refreshed = await client.get("/", headers={
                    "If-None-Match": page.headers["etag"],
                    "If-Modified-Since": page.headers["last-modified"]})
                self.assertEqual(refreshed.status_code, 200)
                self.assertIn("no-store", refreshed.headers["cache-control"])
                rejected = await client.post("/api/ask", json={"question": "Status?"})
                self.assertEqual(rejected.status_code, 403)
                self.assertIn("refresh", rejected.json()["detail"])
                self.assertIn("no-store", rejected.headers["cache-control"])
        asyncio.run(run())

    def test_http_confirmation_is_request_bound_and_requires_ui_header(self):
        import app as runtime
        from uuid import uuid4
        class FakeModel:
            def __init__(self):
                self.executed = False
            async def answer(self, question, history, mcp, seconds, before_call, **kwargs):
                await before_call("hub_manage_destructive_ops",
                                  {"tool": "hub_reboot", "args": {"confirm": True}}, "Reboot requested hub")
                self.executed = True
                return {"success": True, "answer": "Done", "tool_calls": []}
        async def run():
            runtime.app.state.interactions = {}
            runtime.app.state.ask_lock = asyncio.Lock()
            runtime.app.state.configuration_error = None
            runtime.app.state.options = {"model_base_url": "http://localhost:11434",
                                        "investigation_timeout_seconds": 60}
            runtime.app.state.mcp = object()
            runtime.app.state.model = FakeModel()
            request_id = str(uuid4())
            headers = {"X-Homebrain-Request": "1"}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.app),
                                         base_url="http://test") as client:
                rejected = await client.post("/api/ask", json={"question": "Reboot"})
                self.assertEqual(rejected.status_code, 403)
                task = asyncio.create_task(client.post("/api/ask", headers=headers,
                    json={"request_id": request_id, "question": "Reboot"}))
                try:
                    while True:
                        status = (await client.get("/api/activity/" + request_id)).json()
                        if status["pending"]:
                            break
                        if task.done():
                            self.fail(task.result().text)
                        await asyncio.sleep(0)
                    self.assertFalse(runtime.app.state.model.executed)
                    approval = {"id": status["pending"]["id"], "approved": True}
                    url = "/api/activity/" + request_id + "/confirm"
                    self.assertEqual((await client.post(url, json=approval)).status_code, 403)
                    other = "/api/activity/" + str(uuid4()) + "/confirm"
                    self.assertEqual((await client.post(other, headers=headers, json=approval)).status_code, 409)
                    self.assertEqual((await client.post(url, headers=headers, json={
                        **approval, "approved": "true"})).status_code, 422)
                    self.assertEqual((await client.post(url, headers=headers, json=approval)).status_code, 200)
                    self.assertTrue((await task).json()["success"])
                    self.assertTrue(runtime.app.state.model.executed)
                    self.assertEqual(runtime.app.state.interactions, {})
                    self.assertEqual((await client.post(url, headers=headers, json=approval)).status_code, 409)
                finally:
                    if not task.done():
                        task.cancel()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
