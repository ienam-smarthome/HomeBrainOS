"""Offline regressions for hub-owned Cudy Internet timers (no live hub writes)."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from device_read_contract import device_read_plan  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from timed_internet_control import TOOL_NAME  # noqa: E402
from timed_internet_control import (  # noqa: E402
    TimedInternetControl, MAX_BATCH, HUB_TIMEZONE, timed_internet_intent,
)
from tool_registry import classify_tool_effect, timed_internet_tool, ToolEffect  # noqa: E402

DEVICES = [
    (6923, "Block Media-Google-TV-Streamer", "Cudy Managed Device"),
    (6919, "Block Media-Google-Nest-Mini", "Cudy Managed Device"),
    (6913, "Block Phone-Enam-S25-Ultra", "Cudy Managed Device"),
    (6910, "Block Phone-Runa-Pixel-9a", "Cudy Managed Device"),
    (6918, "Block Home-Assistant", "Cudy Managed Device"),
    (6926, "Block Hub-C8-Pro", "Cudy Managed Device"),
    (6917, "Block PC-NucBox-M6Ultra", "Cudy Managed Device"),
    (6997, "Block wlan0", "Cudy Managed Device"),
    (7902, "Block Media", "Cudy Category Device"),
] + [(9000 + i, f"Block Device-192.168.1.{i}", "Cudy Managed Device")
     for i in range(30)]


class FakeHub:
    def __init__(self, patched=True, fail=False, wrong_deadline=False,
                 missing_ack=False, partial_failure=False):
        self.patched = patched
        self.fail = fail
        self.wrong_deadline = wrong_deadline
        self.missing_ack = missing_ack
        self.partial_failure = partial_failure
        self.timers: dict[int, tuple[int, datetime]] = {}
        self.writes = []
        self.reads = []
        self.guide_calls = 0
        self.detailed_manifest_calls = 0

    async def list_tools(self):
        return [
            MCPTool("hub_read_devices", "Read hub devices", {"type": "object"}),
            MCPTool("hub_manage_devices", "Control hub devices", {"type": "object"}),
            MCPTool("hub_get_tool_guide", "Read tool guide", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        self.detailed_manifest_calls += 1
        return [
            {"id": str(did), "label": label, "driver": driver}
            for did, label, driver in DEVICES
        ]

    @staticmethod
    def _ret(name, args, data, *, is_error=False, text=""):
        return MCPToolResult(name, args, {}, text, data, is_error=is_error)

    async def call_tool(self, name, arguments):
        self.reads.append((name, arguments))
        if name == "hub_get_tool_guide":
            self.guide_calls += 1
            return self._ret(name, arguments, {"success": True},
                             text="Acknowledgment: I-HAVE-READ-THE-GUIDE-hub_admin_write_devices-test123")
        leaf, args = arguments["tool"], arguments["args"]
        if name == "hub_read_devices" and leaf == "hub_list_devices":
            cursor = args.get("cursor", "")
            if cursor == "":
                selected = DEVICES[:18]
                nxt = "18"
            elif cursor == "18":
                selected = DEVICES[18:]
                nxt = None
            else:
                raise AssertionError("Bad cursor")
            return self._ret(name, arguments, {
                "devices": [{"id": str(i), "label": label, "driver": driver}
                            for i, label, driver in selected], "nextCursor": nxt,
            })
        if name == "hub_read_devices" and leaf == "hub_get_device_attribute":
            did = int(args["deviceId"])
            attr = args["attribute"]
            if not self.patched:
                value = None
            elif did not in self.timers:
                value = 0 if attr == "timedBlockMins" else "none"
            else:
                mins, deadline = self.timers[did]
                if attr == "timedBlockMins":
                    value = mins
                else:
                    if self.wrong_deadline:
                        deadline += timedelta(hours=1)
                    value = deadline.strftime("%Y-%m-%d %H:%M:%S")
            return self._ret(name, arguments, {"value": value})
        if name == "hub_manage_devices" and leaf == "hub_call_device_command":
            commands = args["commands"]
            assert args.get("bestPracticeKey", "").startswith("I-HAVE-READ-THE-GUIDE-")
            assert len(commands) <= MAX_BATCH
            self.writes.append(commands)
            if self.fail:
                raise RuntimeError("simulated timeout, outcome unknown")
            results = []
            for c in commands:
                did = int(c["deviceId"])
                if self.partial_failure and did == 6923:
                    results.append({"success": False, "error": "Rejected"})
                    continue
                if c["command"] == "cancelTimedBlock":
                    self.timers.pop(did, None)
                else:
                    mins = int(c["parameters"][0])
                    self.timers[did] = (
                        mins, datetime.now(HUB_TIMEZONE) + timedelta(minutes=mins),
                    )
                results.append({"success": True, "deviceId": str(did)})
            if self.missing_ack:
                return self._ret(name, arguments, {"success": True})
            return self._ret(name, arguments, {
                "success": all(r["success"] for r in results), "results": results,
                "failedDeviceIds": [6923] if self.partial_failure and
                any(int(c["deviceId"]) == 6923 for c in commands) else [],
            })
        raise AssertionError(f"Unexpected call {name} {arguments}")


def run(hub, action, targets=None, minutes=None):
    payload = {"action": action}
    if targets is not None:
        payload["targets"] = targets
    if minutes is not None:
        payload["minutes"] = minutes
    return asyncio.run(TimedInternetControl(hub).handle(payload)).data


def test_exact_relative_grammar_preempts_rule_machine():
    assert timed_internet_intent("Block TV after 30 mins") == {
        "action": "block_in", "targets": ["TV"], "minutes": 30}
    assert timed_internet_intent("Block Google TV in 1 hour")["minutes"] == 60
    assert timed_internet_intent("Please allow Doorbell for 3 minutes then block it") == {
        "action": "allow_for", "targets": ["Doorbell"], "minutes": 3}


@pytest.mark.parametrize("prompt", [
    "Why did TV block after 30 minutes?", "Don't block TV after 30 mins",
    "Block TV after 0 minutes", "Block TV after 25 hours",
    "Block TV now", "Block TV after 30 mins and also block phone",
])
def test_grammar_rejects_read_only_or_unsupported_prompts(prompt):
    assert timed_internet_intent(prompt) is None


def test_structured_effects_status_read_writes_sensitive():
    tool = timed_internet_tool()
    assert classify_tool_effect(tool, {"action": "status"}) == ToolEffect.READ
    for action in ("block_in", "allow_for", "cancel", "unknown"):
        assert classify_tool_effect(tool, {"action": action}) == ToolEffect.SENSITIVE_WRITE
    assert classify_tool_effect(MCPTool("homebrain_unlisted", "", {}),
                                {"action": "status"}) == ToolEffect.READ


def test_tv_selected_by_live_driver_id_and_verified_deadline():
    hub = FakeHub()
    result = run(hub, "block_in", ["Google TV"], 30)
    assert result["verified"] and result["success"]
    assert result["confirmed"][0]["id"] == 6923
    assert result["confirmed"][0]["fires_at"] != "none"
    assert list(hub.timers) == [6923]
    assert hub.writes[0][0]["command"] == "blockInMinutes"


def test_all_skips_protected_and_only_managed_driver_and_batches():
    hub = FakeHub()
    result = run(hub, "block_in", ["all"], 20)
    assert result["verified"] and result["success"]
    for did in (6918, 6926, 6917, 6997, 7902):
        assert did not in hub.timers
    assert all(len(batch) <= 20 for batch in hub.writes)
    assert len(hub.writes) == 2


def test_phone_is_ambiguous_without_writes():
    hub = FakeHub()
    result = run(hub, "block_in", ["phone"], 15)
    assert result["status"] == "needs_clarification"
    assert result["success"] is False
    assert len(result["problems"][0]["options"]) == 2
    assert hub.writes == []


def test_protected_device_cannot_be_written_even_by_exact_name():
    hub = FakeHub()
    result = run(hub, "block_in", ["Home-Assistant"], 5)
    assert result["success"] is False
    assert not hub.writes


def test_category_devices_not_selected():
    hub = FakeHub()
    result = run(hub, "cancel", ["Block Media"])
    assert result["success"] is False
    assert not hub.writes


def test_missing_driver_patch_never_claims_verified():
    hub = FakeHub(patched=False)
    result = run(hub, "block_in", ["Google TV"], 30)
    assert not result["success"] and not result.get("verified")


def test_wrong_deadline_not_verified_even_with_positive_minutes():
    hub = FakeHub(wrong_deadline=True)
    result = run(hub, "block_in", ["Google TV"], 30)
    assert not result["verified"]
    assert result["unverified"]
    assert result["confirmed"] == []


def test_timeout_unknown_not_claimed_safe_to_retry():
    hub = FakeHub(fail=True)
    result = run(hub, "block_in", ["Google TV"], 30)
    assert not result["verified"] and not result["success"]
    assert "outcome unknown" in result["failed"][0]["reason"].lower()


def test_missing_per_device_ack_never_claims_schedule():
    hub = FakeHub(missing_ack=True)
    result = run(hub, "block_in", ["Google TV"], 30)
    assert not result["verified"]


def test_partial_failure_is_not_hidden_by_other_success():
    hub = FakeHub(partial_failure=True)
    result = run(hub, "block_in", ["Google TV", "Google Nest Mini"], 20)
    assert not result["verified"] and not result["success"]
    assert result["failed"] and result["failed"][0]["id"] == 6923
    assert len(result["confirmed"]) == 1


def test_allow_for_and_cancel_receipts_and_status():
    hub = FakeHub()
    assert run(hub, "allow_for", ["Google TV"], 10)["verified"]
    assert run(hub, "status")["pending"][0]["id"] == 6923
    cleared = run(hub, "cancel", ["Google TV"])
    assert cleared["verified"] and not hub.timers


@pytest.mark.parametrize("bad", [0, -1, 1441, "20", 1.5, True, None])
def test_invalid_minutes_rejected_before_hub_read(bad):
    hub = FakeHub()
    result = asyncio.run(TimedInternetControl(hub).handle({
        "action": "block_in", "targets": ["TV"], "minutes": bad,
    })).data
    assert not result["success"] and hub.reads == []


def test_bulk_write_uses_one_guide_ack_and_sequential_gateway_calls():
    hub = FakeHub()
    result = run(hub, "block_in", ["all"], 5)
    assert result["success"]
    assert hub.guide_calls == 1
    assert len(hub.writes) == 2


class NoModel:
    async def post(self, *_args, **_kwargs):
        raise AssertionError("Deterministic timed Internet route must not use an AI round")

    async def aclose(self):
        return None


def test_driver_field_is_explicit_in_managed_device_manifest():
    plan = device_read_plan(include_states=False, include_capabilities=True, include_commands=True)
    assert "driver" in plan.fields


@pytest.mark.asyncio
async def test_real_orchestrator_queues_after_driver_preflight_and_executes_after_confirmation():
    hub = FakeHub()
    agent = UnifiedMCPAgent(
        hub, "fake-key", "gemma4:31b", ai_client=NoModel(),
        rule_write_enabled=True, require_sensitive_confirmation=True,
    )
    first = await agent.process_user_request_result(
        "Block Google TV after 30 mins", session_id="timer-confirm-test",
    )
    assert first.confirmation_required is True
    assert first.confirmation_count == 1
    assert "6923" in first.message
    assert hub.detailed_manifest_calls == 0
    summary_calls = [
        args["args"] for name, args in hub.reads
        if name == "hub_read_devices" and args.get("tool") == "hub_list_devices"
    ]
    assert len(summary_calls) == 2  # Synthetic Cudy fleet spans two pages.
    assert all(page["format"] == "summary" for page in summary_calls)
    assert all(page["fields"] == ["id", "label", "driver"] for page in summary_calls)
    assert all(page["limit"] == 50 for page in summary_calls)
    assert not hub.writes
    pending = agent.confirmations.pending["timer-confirm-test"]
    assert len(pending.actions) == 1
    tool, arguments = pending.actions[0]
    assert tool == TOOL_NAME
    assert arguments["_expected_ids"] == [6923]
    assert arguments["action"] == "block_in"
    approval = await agent.process_user_request_result(
        "yes", session_id="timer-confirm-test",
    )
    assert approval.confirmation_required is False
    assert hub.timers[6923][0] == 30
    assert "read-back verified" in approval.message
    assert "Actual future execution" in approval.message


@pytest.mark.asyncio
async def test_orchestrator_does_not_queue_timer_when_driver_not_patched():
    hub = FakeHub(patched=False)
    agent = UnifiedMCPAgent(
        hub, "fake-key", "gemma4:31b", ai_client=NoModel(),
        rule_write_enabled=True, require_sensitive_confirmation=True,
    )
    outcome = await agent.process_user_request_result(
        "Block Google TV after 30 mins", session_id="timer-unpatched-test",
    )
    assert outcome.confirmation_required is False
    assert "driver does not report" in outcome.message
    assert not hub.writes



@pytest.mark.asyncio
async def test_driver_path_avoids_full_detailed_manifest_even_if_it_is_broken():
    class NoDetailedManifest(FakeHub):
        async def get_cached_devices(self):
            raise AssertionError("Expensive detailed manifest must not be used")

    hub = NoDetailedManifest()
    agent = UnifiedMCPAgent(
        hub, "fake-key", "gemma4:31b", ai_client=NoModel(),
        rule_write_enabled=True, require_sensitive_confirmation=True,
    )
    outcome = await agent.process_user_request_result(
        "Block Google TV after 2 mins", session_id="summary-only",
    )
    assert outcome.confirmation_required is True
    assert not hub.writes


@pytest.mark.asyncio
async def test_incomplete_filtered_summary_fails_closed_without_rule_machine_fallback():
    class Incomplete(FakeHub):
        async def call_tool(self, name, arguments):
            result = await super().call_tool(name, arguments)
            if name == "hub_read_devices" and arguments["tool"] == "hub_list_devices":
                return self._ret(name, arguments, {
                    "devices": result.data["devices"], "partial": True,
                    "nextCursor": result.data.get("nextCursor"),
                })
            return result

    hub = Incomplete()
    agent = UnifiedMCPAgent(
        hub, "fake-key", "gemma4:31b", ai_client=NoModel(),
        rule_write_enabled=True, require_sensitive_confirmation=True,
    )
    result = await agent.process_user_request_result(
        "Block Google TV after 2 mins", session_id="incomplete-summary",
    )
    assert result.confirmation_required is False
    assert "could not be verified" in result.message
    assert not hub.writes
    assert "rule_schedule_fastpath" not in result.metrics.get("counters", {})


def test_summary_total_mismatch_never_admits_unique_target():
    class Truncated(FakeHub):
        async def call_tool(self, name, arguments):
            result = await super().call_tool(name, arguments)
            if name == "hub_read_devices" and arguments["tool"] == "hub_list_devices":
                return self._ret(name, arguments, {
                    "devices": result.data["devices"],
                    "total": 50,
                    "nextCursor": None,
                })
            return result

    hub = Truncated()
    with pytest.raises(RuntimeError, match="Incomplete device inventory total"):
        asyncio.run(TimedInternetControl(hub).list_devices())
    assert not hub.writes


@pytest.mark.asyncio
async def test_non_cudy_timer_request_keeps_legacy_route_without_driver_write():
    hub = FakeHub()
    agent = UnifiedMCPAgent(
        hub, "fake-key", "gemma4:31b", ai_client=NoModel(),
        rule_write_enabled=True, require_sensitive_confirmation=True,
    )
    outcome = await agent.process_user_request_result(
        "Block Tab S9 FE after 5 mins", session_id="non-cudy",
    )
    assert "Rule Machine write gateway is unavailable" in outcome.message
    assert not outcome.confirmation_required
    assert not hub.writes
