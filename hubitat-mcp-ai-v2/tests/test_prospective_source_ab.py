"""No-network tests for prospective real-source experiment safeguards.

Every hub, tool, model response and device in this module is fictional.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from mcp import MCPContractError
from prospective_source_ab import (
    ProspectiveWorkspace, ProspectiveError, ReadOnlyMCP,
    verify_read_only_client, SCHEMA, CRITERIA,
)
from source_ledger_experiment import SourceLedgerExperimentalAgent


def wrapped(body):
    return {"content": [{"type": "text", "text": json.dumps(body)}]}


class FakeMCP:
    def __init__(self, grant=None):
        self.calls = []
        self.grant = ({"client": "SIMULATED-RESTRICTED-CLIENT", "readEnabled": True,
                       "writeEnabled": False} if grant is None else grant)
        self.catalog = [
            {"name": "hub_get_info", "annotations": {"readOnlyHint": True},
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "hub_read_devices", "annotations": {"readOnlyHint": True},
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "hub_call_device_command",
             "annotations": {"readOnlyHint": False},
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_get_info":
            result = {"readEnabled": True, "writeEnabled": True}
            if self.grant is not False:
                result["clientAccess"] = self.grant
            return wrapped(result)
        if name == "hub_read_devices":
            return wrapped({"devices": [
                {"currentStates": {"temperature": "18"}},
                {"currentStates": {}},
            ], "count": 2, "unfilteredTotal": 19})
        if name == "hub_call_device_command":
            raise AssertionError("No device command may reach the fake hub")
        raise AssertionError("Unexpected tool name " + name)

    async def gateway_leaf_schema(self, name, leaf):
        raise AssertionError("No gateway requested")

    def cached_leaf_schemas(self):
        return {}

    def validate_leaf_arguments(self, definition, arguments):
        return None


class Scripted:
    async def round(self, messages, tools, remaining):
        if not hasattr(self, "round_count"):
            self.round_count = 0
        self.round_count += 1
        if self.round_count % 2:
            return {"content": "", "tool_calls": [
                {"function": {"name": "hub_read_devices", "arguments": {}}}
            ]}
        self.received = list(messages)
        return {"content": "FICTIONAL RESPONSE", "tool_calls": []}


class TestBaseline(Scripted, Agent):
    pass


class TestCandidate(Scripted, SourceLedgerExperimentalAgent):
    pass


def ratings():
    return {label: {dim: 2 for dim in CRITERIA} for label in ("A", "B")}


class ReadOnlyGateTests(unittest.TestCase):
    def test_valid_client_is_not_confused_with_global_write(self):
        async def run():
            mcp = FakeMCP()
            receipt = await verify_read_only_client(mcp)
            self.assertEqual(receipt["per_client_write_enabled"], False)
            self.assertTrue(receipt["global_write_enabled"])
            self.assertFalse(receipt["permission_enforcement_independently_tested"])
            self.assertEqual(mcp.calls, [("hub_get_info", {})])
        asyncio.run(run())

    def test_main_token_or_client_with_write_cannot_run(self):
        async def run():
            for grant in (False, {"client": "SIMULATED-WRITABLE",
                                 "readEnabled": True, "writeEnabled": True},
                          {"client": "SIMULATED-READOFF",
                           "readEnabled": False, "writeEnabled": False}):
                with self.subTest(grant=grant):
                    with self.assertRaises(ProspectiveError):
                        await verify_read_only_client(FakeMCP(grant))
        asyncio.run(run())

    def test_client_gate_requires_explicit_live_server_readonly_hint(self):
        async def run():
            mcp = FakeMCP()
            mcp.catalog[0]["annotations"] = {}
            with self.assertRaises(ProspectiveError):
                await verify_read_only_client(mcp)
        asyncio.run(run())

    def test_model_cannot_select_write_tool_even_if_server_catalog_contains_it(self):
        async def run():
            mcp = FakeMCP()
            safe = ReadOnlyMCP(mcp)
            selected = await safe.list_tools(refresh=True)
            self.assertEqual(
                {tool["name"] for tool in selected},
                {"hub_get_info", "hub_read_devices"}
            )
            with self.assertRaises(MCPContractError):
                await safe.call("hub_call_device_command", {})
            self.assertNotIn(("hub_call_device_command", {}), mcp.calls)
        asyncio.run(run())


class FakeGatewayMCP(FakeMCP):
    def __init__(self):
        super().__init__()
        self.catalog.append({
            "name": "hub_read_environment",
            "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object", "properties": {
                "tool": {"type": "string"}, "args": {"type": "object"}}},
        })
        self.catalog.append({
            "name": "hub_manage_devices",
            "annotations": {"readOnlyHint": False},
            "inputSchema": {"type": "object", "properties": {
                "tool": {"type": "string"}, "args": {"type": "object"}}},
        })

    async def gateway_leaf_schema(self, name, leaf):
        if name != "hub_read_environment":
            raise AssertionError("Write-bearing gateway metadata should not be touched")
        if leaf == "hub_list_temperature":
            return {"name": leaf, "annotations": {"readOnlyHint": True},
                    "inputSchema": {"type": "object"}}, False
        if leaf == "hub_set_temperature":
            return {"name": leaf, "annotations": {"readOnlyHint": False},
                    "inputSchema": {"type": "object"}}, False
        return None, False

    async def call(self, name, args):
        if name == "hub_read_environment":
            self.calls.append((name, args))
            return wrapped({"temperature": "18"})
        return await super().call(name, args)


class GatewaySafetyTests(unittest.TestCase):
    def test_native_subtool_must_itself_be_explicitly_read_only(self):
        async def run():
            mcp = FakeGatewayMCP()
            safe = ReadOnlyMCP(mcp)
            names = [t["name"] for t in await safe.list_tools(refresh=True)]
            self.assertIn("hub_read_environment", names)
            self.assertNotIn("hub_manage_devices", names)
            result = await safe.call("hub_read_environment",
                                     {"tool": "hub_list_temperature", "args": {}})
            self.assertEqual(json.loads(result["content"][0]["text"])["temperature"], "18")
            with self.assertRaises(MCPContractError):
                await safe.call("hub_read_environment",
                                {"tool": "hub_set_temperature", "args": {}})
            with self.assertRaises(MCPContractError):
                await safe.call("hub_manage_devices",
                                {"tool": "hub_set_temperature", "args": {}})
            self.assertEqual(
                [x for x in mcp.calls if x[0] == "hub_read_environment"],
                [("hub_read_environment",
                  {"tool": "hub_list_temperature", "args": {}})]
            )
        asyncio.run(run())


class TrialWorkspaceTests(unittest.TestCase):
    def test_prepare_is_frozen_and_rejects_reused_question_text(self):
        workspace = ProspectiveWorkspace()
        prepared = workspace.prepare(["Investigate fixture A", "Investigate fixture B"])
        self.assertEqual(prepared["cases_prepared"], 2)
        self.assertEqual(len(prepared["study_sha256"]), 64)
        with self.assertRaises(ProspectiveError):
            workspace.prepare(["Another", "More"])
        other = ProspectiveWorkspace()
        with self.assertRaises(ProspectiveError):
            other.prepare(["A", "A"])
        self.assertIsNone(ProspectiveWorkspace().summary()["study_sha256"])

    def test_experiment_runs_baseline_and_candidate_with_same_read_tools(self):
        async def run():
            workspace = ProspectiveWorkspace()
            workspace.prepare(["Private source question one",
                               "Private source question two"])
            mcp = FakeMCP()
            baseline = TestBaseline("http://localhost:11434", "fictional", "", 15)
            candidate = TestCandidate("http://localhost:11434", "fictional", "", 15)
            try:
                await workspace.run("new-01", baseline, candidate, mcp, 30)
                result = workspace.case("new-01")
                self.assertEqual(set(result["arms"]), {"A", "B"})
                self.assertTrue(result["mapping_hidden"])
                for arm in result["arms"].values():
                    self.assertEqual(arm["result"]["answer"], "FICTIONAL RESPONSE")
                    self.assertTrue(arm["token_scope_before_arm"]["read_only_grant_reported"])
                    self.assertEqual(arm["result"]["rounds"], 2)
                # Exactly one hub_get_info preflight and one read per arm.
                self.assertEqual(
                    [name for name, _ in mcp.calls].count("hub_get_info"), 2
                )
                self.assertEqual(
                    [name for name, _ in mcp.calls].count("hub_read_devices"), 2
                )
                self.assertEqual(
                    [name for name, _ in mcp.calls].count("hub_call_device_command"), 0
                )
                with self.assertRaises(ProspectiveError):
                    await workspace.run("new-01", baseline, candidate, mcp, 30)
                # Both arms get the original native source; only candidate has
                # the derived ledger, under hidden assignment labels.
                ledgers = []
                for agent in (baseline, candidate):
                    payload = json.loads(agent.received[-1]["content"])
                    ledgers.append("client_collection_source_ledger" in payload)
                    self.assertEqual(json.loads(payload["content"][0]["text"])["count"], 2)
                self.assertEqual(ledgers, [False, True])
            finally:
                await baseline.close()
                await candidate.close()
        asyncio.run(run())

    def test_fails_closed_before_model_call_if_grant_is_writable(self):
        async def run():
            workspace = ProspectiveWorkspace()
            workspace.prepare(["A fresh question", "Another fresh question"])
            mcp = FakeMCP({"client": "SIMULATED", "readEnabled": True,
                           "writeEnabled": True})
            baseline = TestBaseline("http://localhost:11434", "fictional", "", 15)
            candidate = TestCandidate("http://localhost:11434", "fictional", "", 15)
            try:
                with self.assertRaises(ProspectiveError):
                    await workspace.run("new-01", baseline, candidate, mcp, 30)
                self.assertEqual(mcp.calls, [("hub_get_info", {})])
                self.assertFalse(workspace.case("new-01")["arms"])
                self.assertIsNone(workspace.active_case)
            finally:
                await baseline.close()
                await candidate.close()
        asyncio.run(run())

    def test_human_ratings_are_blind_and_safe_aggregate_requires_completion(self):
        w = ProspectiveWorkspace()
        w.prepare(["HIDDEN PRIVATE A", "HIDDEN PRIVATE B"])
        # One case is not sufficient to unmask the hidden assignment.
        w.questions["new-01"]["arms"] = {"A": {"result": {}}, "B": {"result": {}}}
        w.private_conditions["new-01"] = {"A": "baseline", "B": "candidate"}
        w.rate("new-01", ratings())
        self.assertFalse(w.report()["condition_mapping_revealed"])
        self.assertEqual(w.report()["effects"]["causal_calibration"]["paired_ratings"], 0)
        with self.assertRaises(ProspectiveError):
            w.rate("new-01", ratings())
        w.questions["new-02"]["arms"] = {"A": {"result": {}}, "B": {"result": {}}}
        w.private_conditions["new-02"] = {"A": "candidate", "B": "baseline"}
        w.rate("new-02", ratings())
        report = w.report()
        self.assertTrue(report["condition_mapping_revealed"])
        self.assertEqual(report["effects"]["causal_calibration"]["paired_ratings"], 2)
        self.assertEqual(report["effects"]["causal_calibration"]["ties"], 2)
        self.assertNotIn("HIDDEN PRIVATE", json.dumps(report))
        self.assertFalse(report["model_accuracy_independently_verified"])
        self.assertFalse(report["matching_live_source_snapshots_verified"])

    def test_deletion_clears_private_question_set(self):
        w = ProspectiveWorkspace()
        w.prepare(["secret sample", "secret other sample"])
        w.delete()
        self.assertEqual(w.summary()["cases_prepared"], 0)
        self.assertNotIn("secret sample", json.dumps(w.summary()))
        w.prepare(["new one", "new two"])


if __name__ == "__main__":
    unittest.main()
