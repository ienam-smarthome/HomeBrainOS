"""Model-facing Investigation V2 acceptance tests using fake HTTP/MCP only.

No real provider key and no physical Hubitat calls. Exercises actual
ChatTransport.chat() plus V2 proposal validation, read loop and synthesis.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from chat_transport import ChatTransport
from investigation_v2 import build_case_file
from investigation_v2.model_adapter import V2ModelProposer, _json_object
from investigation_v2.read_loop import Hypothesis
from investigation_v2.synthesis import assemble_grounded_answer, synthesize_with_chat
from investigation_v2.evaluate import evaluate_v2_with_model
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect

FIXTURE = Path(__file__).parent / "fixtures" / "investigation_v2_overnight.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def real_case():
    f = fixture()
    return build_case_file(f["question"], f["receipts"])


def tools():
    return [
        MCPTool("hub_read_devices", "Hubitat device observation history", {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": [
                    "hub_list_device_events", "hub_get_device"]},
                "args": {"type": "object", "properties": {
                    "deviceId": {"type": "string"}, "attribute": {"type": "string"},
                    "hoursBack": {"type": "integer"}, "limit": {"type": "integer"},
                }, "required": ["deviceId"], "additionalProperties": False},
            }, "required": ["tool", "args"], "additionalProperties": False,
        }, annotations={"readOnlyHint": True}),
        MCPTool("hub_manage_devices", "Dangerous device controls", {
            "type": "object", "properties": {"tool": {"type": "string",
                 "enum": ["hub_call_device_command"]}}}, annotations={"mutates": True}),
    ]


class FakeMCP:
    def __init__(self):
        self.list_count = 0

    async def list_tools(self):
        self.list_count += 1
        return tools()


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp = mcp
        self.calls = []

    async def execute(self, name, arguments, **kwargs):
        self.calls.append((name, arguments, kwargs))
        result = MCPToolResult(
            name=name, arguments=arguments, raw={}, text="NEVER MODEL RAW PAYLOAD",
            data={
                "deviceId": "7805",
                "events": [
                    {"name": "switch", "value": "off",
                     "date": "2026-10-25T00:42:01+01:00",
                     "secret": "SECRET_123"}
                ],
                "historySourceIntegrityVerified": False,
            }, is_error=False)
        return ToolExecution(name=name, arguments=arguments, effect=ToolEffect.READ,
                             success=True, elapsed_ms=5, content="RAW", result=result)


class FakeHTTPResponse:
    def __init__(self, response):
        self.response = response

    def json(self):
        return self.response

    def raise_for_status(self):
        return None


class FakeOllamaHTTP:
    def __init__(self, messages=None):
        self.calls = []
        self.messages = list(messages or [])
    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.messages:
            raise AssertionError("Unexpected model round")
        value = self.messages.pop(0)
        return FakeHTTPResponse({"message": {
            "role": "assistant", "content": json.dumps(value) if isinstance(value, dict) else value,
        }})


def plan(case, finish=False):
    source = case.records[0].record_id
    if finish:
        return {"hypotheses": [], "reads": [], "finish": True}
    return {
        "hypotheses": [{
            "id": "h-off", "explanation": "The recorded OFF may not have taken effect",
            "supporting_record_ids": [source],
            "conflicting_record_ids": [],
            "missing_discriminator": "Check independent switch state around 00:41",
        }],
        "reads": [{
            "tool": "hub_read_devices",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": "7805", "attribute": "switch",
                                   "hoursBack": 24, "limit": 100}},
            "discriminator": "Did the switch report OFF?",
            "information_gain": "Disambiguate dispatch from device state",
            "hypothesis_ids": ["h-off"],
        }],
        "finish": False,
    }


@pytest.mark.asyncio
async def test_existing_real_chat_transport_powers_safe_v2_plan_and_synthesis():
    data = fixture()
    p = plan(real_case())
    source = real_case().records[0].record_id
    http = FakeOllamaHTTP([p, plan(real_case(), finish=True), {
        "selected_record_ids": [source],
        "hypothesis_order": ["h-off"],
    }])
    transport = ChatTransport(
        api_key="dummy-for-fake-http", model_name="gemma4:31b-cloud",
        base_url="https://ollama.example", client=http,
    )
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)
    output = await evaluate_v2_with_model(
        explicitly_authorised=True, question=data["question"],
        chat=transport.chat, mcp=mcp, executor=executor,
        verified_entity_ids={"7805"}, initial_receipts=data["receipts"],
        max_rounds=3, max_total_reads=4,
    )
    assert len(http.calls) == 3
    assert mcp.list_count == 2
    assert len(executor.calls) == 1
    assert executor.calls[0][0] == "hub_read_devices"
    assert executor.calls[0][2]["record_evidence"] is False
    assert output.investigation.executed_reads == 1
    assert output.investigation.stopped_because == "model_finished"
    assert output.answer.root_cause_verified is False
    assert output.answer.human_review_required is True
    assert output.investigation.case.original_user_request == data["question"]
    assert "00:41:40.085+01:00" in output.answer.text
    assert "00:49:52.008+01:00" in output.answer.text
    assert "2026-10-25T00:42:01+01:00" in output.answer.text
    assert "PRIVATE" not in json.dumps(output.to_dict())
    assert "SECRET_123" not in json.dumps(output.to_dict())
    assert "NEVER MODEL RAW" not in json.dumps(output.to_dict())
    assert "material_command_omitted_by_model" in output.answer.validation_issues
    for url, payload in http.calls:
        assert url == "https://ollama.example/api/chat"
        assert payload["json"]["tools"] is None  # ChatTransport serializes no tools as null
    await transport.close()


@pytest.mark.asyncio
async def test_opt_in_required_before_any_model_or_mcp_lookup():
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)
    async def impossible(_messages, _tools):
        raise AssertionError("Model must not be called")
    with pytest.raises(PermissionError):
        await evaluate_v2_with_model(
            question="Why?", chat=impossible, mcp=mcp, executor=executor,
            verified_entity_ids={"7805"})
    assert mcp.list_count == 0 and executor.calls == []


@pytest.mark.asyncio
async def test_model_receives_verified_schema_without_write_gateway():
    observed = []
    async def chat(messages, native_tools):
        observed.extend(messages)
        assert native_tools == []
        return {"content": json.dumps(plan(real_case(), finish=True))}
    proposer = V2ModelProposer(chat, tools())
    result = await proposer(real_case(), 0)
    assert result["finish"] is True
    sent = json.loads(observed[-1]["content"])
    assert sent["original_question"] == real_case().original_user_request
    assert [t["name"] for t in sent["available_tools"]] == ["hub_read_devices"]
    assert "hub_manage_devices" not in observed[-1]["content"]
    assert "command-off" in sent["case_file"]


@pytest.mark.parametrize("payload", [
    "", "[]", "null", "{", " " * 16001,
])
def test_malformed_planner_json_is_rejected(payload):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _json_object(payload)


@pytest.mark.asyncio
async def test_planner_refuses_native_provider_tool_calls():
    async def chat(_messages, _tools):
        return {"content": json.dumps(plan(real_case())),
                "tool_calls": [{"function": {"name": "hub_manage_devices",
                                                "arguments": {"command": "off"}}}]}
    with pytest.raises(ValueError, match="never native tool"):
        await V2ModelProposer(chat, tools())(real_case(), 0)


@pytest.mark.asyncio
async def test_unsupported_model_synthesis_falls_back_without_erasing_commands():
    async def malicious(_messages, _tools):
        return {"content": "The hub reboot definitely caused everything"}
    answer = await synthesize_with_chat(case=real_case(), hypotheses=[], chat=malicious)
    assert len(answer.displayed_record_ids) >= 6
    assert "00:41:40.085+01:00" in answer.text
    assert "00:49:52.008+01:00" in answer.text
    assert "hub reboot definitely" not in answer.text
    assert "missing_or_invalid_model_evidence_selection" in answer.validation_issues


def test_hypothesis_cannot_prove_root_cause_and_unknown_ids_are_flagged():
    case = real_case()
    hyp = Hypothesis(
        "h1", "A guessed reboot", (case.records[0].record_id,), (),
        "Check exact reboot timestamp", "supported_candidate")
    ans = assemble_grounded_answer(
        case, [hyp], {"selected_record_ids": ["fabricated-id"],
                      "hypothesis_order": ["imaginary", "h1"]})
    assert "unknown_evidence_reference" in ans.validation_issues
    assert "unknown_hypothesis_reference" in ans.validation_issues
    assert ans.root_cause_verified is False
    assert "Unverified possibility" in ans.text
    assert len(ans.omitted_material_record_ids) == 6
    assert len([r for r in case.records if r.stage == "command_issued"]) == 6


def test_command_materials_survive_model_silence_and_state_not_inferred():
    case = real_case()
    out = assemble_grounded_answer(case, [], {})
    assert "00:41:40.085+01:00" in out.text
    assert "00:49:52.008+01:00" in out.text
    assert "01:09:41.597+01:00" in out.text
    assert "physical" in out.text.lower()
    assert "History coverage is not independently proven complete" in out.text
    assert out.root_cause_verified is False
    assert len(out.omitted_material_record_ids) == 6


@pytest.mark.asyncio
async def test_long_case_does_not_silently_truncate_model_input():
    async def forbidden(_messages, _tools):
        raise AssertionError("Must not send truncated evidence")
    model = V2ModelProposer(forbidden, tools(), max_case_chars=1000)
    # A larger case must fail before contacting any provider.
    with pytest.raises(ValueError, match="bounded model context"):
        await model(real_case(), 0)

@pytest.mark.asyncio
async def test_incomplete_but_valid_json_is_rejected_by_planner_contract():
    async def missing_fields(_messages, _tools):
        return {"content": '{"reads":[]}'}
    with pytest.raises(ValueError, match="hypothesis list"):
        await V2ModelProposer(missing_fields, tools())(real_case(), 0)
