"""HTTP regression: a V2 two-device switch question returns two readings, not 422."""
from __future__ import annotations
import importlib,json,sys
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.semantic_plan import SemanticPlan
from test_investigation_v2_multi_named_0_18_166 import DEVICES, QUESTION
TOKEN="two-device-safe-test-token-123456789"

def test_joint_snapshot_ignores_joined_name_from_model_and_reads_both(monkeypatch,tmp_path):
    path=tmp_path/"options.json"
    path.write_text(json.dumps({"investigation_v2_testing_enabled":True,
        "investigation_v2_test_token":TOKEN,
        "morning_health_check_enabled":False,
        "one_time_rule_cleanup_enabled":False}),encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH",str(path))
    sys.modules.pop("app",None)
    module=importlib.import_module("app")
    calls=[]
    async def fake_audit(*,identity_only=False):
        calls.append(identity_only)
        if identity_only:
            rows=[{k:v for k,v in item.items() if k in ("id","label","name","roomName")} for item in DEVICES]
        else:
            rows=DEVICES
        return rows,{"complete":True,"pages":1,
                     "projection":"identity_only" if identity_only else "full",
                     "page_timings_ms":[]}
    async def fake_plan(*_args,**_kwargs):
        return SemanticPlan(mode="inventory",scope="named",
          device_name="Hallway Light 1 and Livingroom Light 2",
          attribute="switch",aggregation="list",limit=1)
    async def fake_enrichment(plan,*_args,**_kwargs):
        return plan,{"outcome":"not_applicable","candidates":0,"accepted_hints":0}
    monkeypatch.setattr(module.mcp,"recent_verified_audit_identities",lambda:None)
    monkeypatch.setattr(module.mcp,"get_audit_devices",fake_audit)
    monkeypatch.setattr(module,"semantic_plan",fake_plan)
    monkeypatch.setattr(module,"enrich_measurement_roles",fake_enrichment)
    with TestClient(module.app) as client:
        response=client.post("/api/v2/test",json={"question":QUESTION,
            "explicit_opt_in":True},headers={"X-HomeBrain-V2-Test-Token":TOKEN,
            "X-HomeBrain-V2-Request":"read-only"})
    assert response.status_code==200,response.text
    data=response.json()
    assert calls==[True,False]
    assert data["answer_mode"]=="semantic_inventory"
    assert data["inventory_query"]["matched_count"]==2
    assert data["semantic_plan"]["device_names"]==["Hallway Light 1","Livingroom Light 2"]
    assert "Hallway Light 1 — on" in data["answer"]["text"]
    assert "Livingroom Light 2 — off" in data["answer"]["text"]
    assert {row["id"] for row in data["resolved_devices"]}=={"7829","7828"}
    assert data["test_mode"]=="explicit_read_only"
