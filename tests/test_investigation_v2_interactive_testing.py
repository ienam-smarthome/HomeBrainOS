from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai" / "rootfs" / "app"))

from investigation_v2.test_service import match_verified_device_ids, require_test_access
from investigation_v2.model_adapter import V2ModelProposer
from investigation_v2.evidence import CaseFile
from investigation_v2.planning import review_model_read_proposals
from mcp_client import MCPTool


def test_test_mode_is_default_off_and_requires_both_token_and_explicit_opt_in():
    for enabled, secret, supplied, confirm in [
        (False, "a"*20, "a"*20, True),
        (True, "", "", True),
        (True, "short", "short", True),
        (True, "a"*20, "a"*20, False),
        (True, "a"*20, "bad", True),
        (True, "a"*20, "", True),
    ]:
        with pytest.raises(PermissionError):
            require_test_access(enabled=enabled, configured_token=secret,
                                supplied_token=supplied, explicit_opt_in=confirm)
    require_test_access(enabled=True, configured_token="a"*20,
                        supplied_token="a"*20, explicit_opt_in=True)


def test_ids_must_be_present_in_live_hubitat_manifest_not_model_assertions():
    manifest = [{"id":7805,"label":"Livingroom Light 1"},{"id":"7103","label":"Bedroom 3 Mesh"}]
    assert match_verified_device_ids(["7805", "7103"], manifest) == ("7805","7103")
    for choices in (["99999"], ["7805","7805"], ["7805","4019"], ["7805","x"],
                    [], ["7805"]*5):
        with pytest.raises(ValueError):
            match_verified_device_ids(choices, manifest)
    with pytest.raises(ValueError):
        match_verified_device_ids(["7805"], None)


@pytest.mark.asyncio
async def test_model_receives_host_verified_id_and_no_secret_or_write_tools():
    captured=[]
    async def chat(messages, tools):
        captured.append((messages, tools))
        return {"content":json.dumps({"hypotheses":[],"reads":[],"finish":True})}
    model=V2ModelProposer(chat, [MCPTool("hub_manage_devices","write",
                    {"type":"object","properties":{}},annotations={"readOnlyHint":False})],
                    verified_entity_ids=["7805","not-a-device"])
    plan=await model(CaseFile(original_user_request="Why?"),0)
    data=json.loads(captured[0][0][1]["content"])
    assert data["verified_target_ids"]==["7805"]
    assert data["available_tools"]==[]
    assert captured[0][1]==[]
    assert plan["finish"] is True


def test_existing_case_receipts_do_not_consume_new_v2_read_budget():
    from investigation_v2.evidence import Coverage
    case=CaseFile("Why?")
    case.coverage=[Coverage(str(n),"old","old","7805",{},0,None,None,
                            None,None,None,None,None,True) for n in range(20)]
    tool=MCPTool("hub_read_devices","Read",{"type":"object",
             "properties":{"tool":{"type":"string","enum":["hub_get_device"]},
                           "args":{"type":"object","properties":{"deviceId":{"type":"string"}}}},
             "required":["tool","args"]},annotations={"readOnlyHint":True})
    item={"tool":"hub_read_devices","arguments":{"tool":"hub_get_device","args":{"deviceId":"7805"}},
          "discriminator":"Confirm target configuration","information_gain":"Differentiate behaviour"}
    result=review_model_read_proposals(case,[item],[tool],verified_entity_ids=["7805"],
                                        max_total_reads=2,budget_used_reads=0)
    assert len(result.approved)==1


