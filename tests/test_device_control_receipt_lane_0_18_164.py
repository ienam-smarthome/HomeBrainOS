"""v0.18.164 control acceptance lane: full local service + presenter, no hub IO."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from device_command_receipts import adjudicate_command_receipt
from device_control_service import DeviceControlService
from deterministic_tool_presenter import present_tool_result
from mcp_client import MCPToolResult
from test_device_control_service import ControlMCP, BEDROOM1_LIGHT

class SimulatedHub(ControlMCP):
    """Deterministic fake Hubitat gateway; rejects unexpected real IO."""
    def __init__(self, devices, *, case="converged"):
        super().__init__(devices)
        self.case=case
    async def call_tool(self, gateway, arguments):
        if arguments.get("tool")!="hub_call_device_command":
            return await super().call_tool(gateway,arguments)
        self.calls.append((gateway,arguments))
        expected=arguments["args"].get("waitFor",{}).get("expectedValue")
        if self.case=="reject":
            return MCPToolResult(gateway,arguments,{},"rejected",{"success":False,"error":"simulated rejection"},is_error=True)
        if self.case=="exception":
            raise TimeoutError("simulated ambiguous command transport timeout")
        if self.case=="missing":
            data={"success":True}
        elif self.case=="not_converged":
            data={"success":True,"waitFor":{"converged":False,"value":"off"}}
        elif self.case=="string_false":
            data={"success":True,"waitFor":{"converged":"false","value":expected}}
        elif self.case=="mismatch":
            data={"success":True,"waitFor":{"converged":True,"value":"unexpected"}}
        else:
            data={"success":True,"waitFor":{"converged":True,"value":expected}}
        return MCPToolResult(gateway,arguments,{},"accepted",data)

def _args(command, **kwargs):
    return {"device_names":["Bedroom 1 Light"],"device_kind":"auto","command":command,**kwargs}

@pytest.mark.parametrize("wait,status,verified",[
    ({"converged":True,"value":"on"},"reported_state_converged",True),
    ({"converged":"false","value":"on"},"confirmation_invalid",False),
    ({"converged":True,"value":"off"},"confirmation_mismatch",False),
    ({"converged":False,"value":"off"},"not_converged",False),
    (None,"confirmation_missing",False),
])
def test_typed_state_acknowledgements(wait,status,verified):
    receipt=adjudicate_command_receipt(accepted=True,expected="on",wait_for=wait)
    assert receipt.status==status
    assert receipt.state_verified is verified

@pytest.mark.asyncio
@pytest.mark.parametrize("command",["on","off"])
async def test_on_off_reach_verified_hubitat_state_without_retry(command):
    mcp=SimulatedHub([BEDROOM1_LIGHT])
    receipts=[]
    service=DeviceControlService(mcp,lambda *args,**kwargs: receipts.append(kwargs))
    result=await service.execute(_args(command))
    assert result.data["success"] is True
    assert result.data["state_verified"] is True
    assert len(result.data["succeeded"])==1
    item=result.data["succeeded"][0]
    assert item["verification_status"]=="reported_state_converged"
    assert item["state_verification_source"]=="hubitat_wait_for"
    assert item["verified"] is True
    commands=[args for name,args in mcp.calls if args.get("tool")=="hub_call_device_command"]
    assert len(commands)==1
    assert commands[0]["args"]["waitFor"]["expectedValue"]==command
    assert any(x.get("evidence_kind")=="device_command_result" for x in receipts)

@pytest.mark.asyncio
@pytest.mark.parametrize("case,status",[
    ("not_converged","not_converged"),
    ("string_false","confirmation_invalid"),
    ("mismatch","confirmation_mismatch"),
    ("missing","confirmation_missing"),
])
async def test_ack_without_valid_convergence_does_not_claim_state_or_retry(case,status):
    mcp=SimulatedHub([BEDROOM1_LIGHT],case=case)
    output=await DeviceControlService(mcp,lambda *a,**k:None).execute(_args("on"))
    assert output.data["success"] is False
    assert output.data["state_verified"] is False
    target=output.data["failed"][0]
    assert target["command_sent"] is True
    assert target["verified"] is False
    assert target["verification_status"]==status
    assert target["changed"] is False
    message=present_tool_result("homebrain_control_devices",output.data)
    assert "state verification failed" in message
    assert len([a for _,a in mcp.calls if a.get("tool")=="hub_call_device_command"])==1

@pytest.mark.asyncio
async def test_transport_exception_must_not_retry_non_idempotent_control():
    mcp=SimulatedHub([BEDROOM1_LIGHT],case="exception")
    output=await DeviceControlService(mcp,lambda *a,**k:None).execute(_args("toggle"))
    assert output.data["success"] is False
    assert output.data["failed"][0]["command_sent"] is False
    assert len([a for _,a in mcp.calls if a.get("tool")=="hub_call_device_command"])==1

@pytest.mark.asyncio
async def test_toggle_missing_preread_is_sent_not_described_as_state_change():
    mcp=SimulatedHub([BEDROOM1_LIGHT])
    output=await DeviceControlService(mcp,lambda *a,**k:None).execute(_args("toggle"))
    assert output.data["success"] is True  # accepted by gateway (legacy field)
    assert output.data["state_verified"] is False
    target=output.data["succeeded"][0]
    assert target["verified"] is None
    assert target["verification_status"]=="accepted_unverified"
    assert target["changed"] is False
    message=present_tool_result("homebrain_control_devices",output.data)
    assert "Command accepted" in message and "state" in message
    assert "Turned on" not in message and "Turned off" not in message
    assert len([a for _,a in mcp.calls if a.get("tool")=="hub_call_device_command"])==1

@pytest.mark.asyncio
async def test_absolutely_scoped_brightness_command_formats_and_verifies():
    mcp=SimulatedHub([BEDROOM1_LIGHT])
    output=await DeviceControlService(mcp,lambda *a,**k:None).execute(
        {"device_names":["Bedroom 1 Light"],"device_kind":"light","command":"set_level","level":30})
    assert output.data["state_verified"] is True
    command=[a for _,a in mcp.calls if a.get("tool")=="hub_call_device_command"][0]
    assert command["args"]["parameters"]==["30"]
    assert command["args"]["waitFor"]["expectedValue"]=="30"
