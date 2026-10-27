"""Adaptive advisory budget with complete typed evidence; no real MCP calls."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from mcp_client import MCPToolResult
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.read_loop import run_read_only_investigation

class EmptyMCP:
    async def list_tools(self): return []
class ForbiddenExecutor:
    def __init__(self, mcp): self.mcp = mcp
    async def execute(self, *args, **kwargs):
        raise AssertionError("Never execute MCP for preloaded evidence")

def trusted_receipts(with_config):
    args = {"tool": "hub_list_device_events", "args": {"deviceId": "7103"}}
    rows = [
        {"deviceId":"7103","name":"command-off","type":"command",
         "date":"2026-10-12T00:30:01+00:00","producedBy":{"id":"3950"}},
        {"deviceId":"7103","name":"switch","value":"off",
         "date":"2026-10-12T00:30:02+00:00","producedBy":{"id":"7103"}},
        {"deviceId":"7103","name":"healthStatus","value":"offline",
         "date":"2026-10-12T00:33:46+00:00","producedBy":{"id":"7103"}},
    ]
    result = MCPToolResult("hub_read_devices",args,raw={},text="DONT_PRINT",
                           data={"deviceId":"7103","events":rows},is_error=False)
    receipts = [project_read_receipt("hub_read_devices", args, result, source_request_id="events")]
    if with_config:
        args2 = {"tool":"hub_get_app_config",
                 "args":{"appId":"3950","includeSettings":True}}
        result2 = MCPToolResult("hub_read_apps_code",args2,raw={},text="DONT_PRINT",
                     data={"app":{"id":"3950"},"settings":{"onOff.3":False,
                                                      "onOffSwitch.3":["7103"]}},is_error=False)
        receipts.append(project_read_receipt("hub_read_apps_code",args2,
                         result2,source_request_id="controller"))
    return receipts

@pytest.mark.asyncio
@pytest.mark.parametrize("config,expected",[(True,15000),(False,35000)])
async def test_optional_advisory_planning_has_bounded_budget(config, expected):
    mcp = EmptyMCP()
    seen=[]
    async def propose(case, round_index):
        seen.append((len(case.records), sum(r.stage=="config_stored" for r in case.records)))
        return {"hypotheses":[],"reads":[],"finish":True}
    result = await run_read_only_investigation(
        question="Why offline?",mcp=mcp,executor=ForbiddenExecutor(mcp),propose=propose,
        verified_entity_ids=["7103"],initial_receipts=trusted_receipts(config),
        bootstrap_source_identity=False,max_rounds=1,planning_timeout_seconds=35)
    assert result.stopped_because=="model_finished"
    assert result.planning_diagnostics[0]["budget_ms"]==expected
    assert result.planning_diagnostics[0]["budget_policy"]==(
        "source_backed_advisory" if config else "full_discriminating_plan")
    assert seen[0][0]>=3
    assert result.executed_reads==0
