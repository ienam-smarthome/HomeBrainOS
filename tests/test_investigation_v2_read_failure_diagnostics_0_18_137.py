"""Privacy-preserving failure details for V2 MCP reads, no live Hubitat access."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.read_diagnostics import (
    classify_exception, classify_execution, safe_code,
)
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.investigation_report import format_investigation_report


def manifest():
    return [MCPTool("hub_read_apps_code", "Read apps", {
        "type":"object",
        "properties":{
            "tool":{"type":"string","enum":["hub_get_app_config"]},
            "args":{"type":"object","properties":{"appId":{"type":"string"}},
                    "required":["appId"],"additionalProperties":False}},
        "required":["tool","args"],"additionalProperties":False,
    }, annotations={"readOnlyHint":True})]


class MCP:
    async def list_tools(self):
        return manifest()


class Executor:
    def __init__(self, mcp, result_kind: str):
        self.mcp=mcp
        self.result_kind=result_kind
        self.calls=[]
    async def execute(self, name, args, *, tool, record_evidence):
        self.calls.append((name, args))
        assert record_evidence is False
        assert tool.annotations.get("readOnlyHint") is True
        base={"name":name, "arguments":args, "effect":ToolEffect.READ,
              "elapsed_ms":14, "content":"PRIVATE TOKEN supersecret"}
        if self.result_kind=="reported_failure":
            return ToolExecution(
                **base, success=False,
                result=MCPToolResult(name, args, raw={"server":"SECRET"},
                                     text="PRIVATE TOKEN supersecret",
                                     data={"success":False,"error":"secret URL https://xxx/token"},
                                     is_error=True))
        if self.result_kind=="exception_result":
            return ToolExecution(
                **base, success=False,
                error=ConnectionError("private URL https://username:password@host:1234"))
        if self.result_kind=="no_result":
            return ToolExecution(**base, success=True, result=None)
        if self.result_kind=="raised":
            raise RuntimeError("S3CR3T/credentials/protected")
        raise AssertionError(self.result_kind)


async def plan(case, round_index):
    return {"hypotheses":[], "finish":False,
            "reads":[{
                "tool":"hub_read_apps_code",
                "arguments":{"tool":"hub_get_app_config","args":{"appId":"4019"}},
                "discriminator":"Check source app from explicit trusted ID 4019",
                "information_gain":"Read stored app configuration and compare states",
                "hypothesis_ids":[],
            }]}


@pytest.mark.parametrize(("kind","expected"), [
    ("reported_failure","mcp_tool_reported_error"),
    ("exception_result","transport_unavailable"),
    ("no_result","no_authoritative_result"),
    ("raised","read_execution_error"),
])
@pytest.mark.asyncio
async def test_read_failures_are_specific_and_never_expose_mcp_secrets(kind,expected):
    mcp=MCP()
    ex=Executor(mcp,kind)
    result=await run_read_only_investigation(
        question="Inspect verified app 4019",
        mcp=mcp, executor=ex, propose=plan,
        verified_entity_ids=["4019"], max_total_reads=1, max_rounds=1)
    assert len(ex.calls)==1
    assert result.read_failures[0]["code"]==expected
    assert result.read_failures[0]["operation"]=="hub_get_app_config"
    assert result.read_failures[0]["target_id"]=="4019"
    assert result.read_failures[0]["source_request_id"]=="v2-0-1"
    assert result.case.coverage[0].succeeded is False
    assert result.case.coverage[0].failure_code==expected
    assert result.stopped_because=="read_budget_reached"
    output=json.dumps(result.to_dict())
    assert "4019" in output
    for value in ("S3CR3T","PRIVATE TOKEN","username","password@","secret URL","xxx/token"):
        assert value not in output
    report=format_investigation_report(result.case, result.hypotheses,
                                       result.stopped_because, None)
    assert "Failed source reads" in report
    assert expected in report


def test_failed_read_classification_never_uses_remote_error_message():
    fake=ToolExecution(name="hub_read_apps_code",arguments={},
                       effect=ToolEffect.READ,success=False,elapsed_ms=0,
                       content="password=secret",
                       error=RuntimeError("token=must_not_appear"))
    assert classify_execution(fake,"hub_read_apps_code")=="read_execution_error"
    assert classify_execution(fake,"wrong_gateway")=="response_identity_mismatch"
    assert classify_exception(asyncio.TimeoutError("private_url"))=="read_timeout"
    assert safe_code("private_api_token") is None
    assert safe_code("read_timeout")=="read_timeout"

