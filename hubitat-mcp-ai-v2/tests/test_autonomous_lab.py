"""Isolated autonomous first-answer evaluation: synthetic tools + real agent loop.

All fixtures and responses are fabricated; tests must never use Hubitat, HA,
actual device IDs, user exports, or real LLM network calls.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi import FastAPI

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"rootfs"/"app"))

from agent import Agent
from autonomous_lab import (AutonomousLab, SyntheticMCP, scenario_definitions,
                            _check_coverage, GATEWAYS, MAX_MODEL_ROUNDS)
from autonomous_routes import router


def tool_call(name,tool,args):
    return {"id":"synthetic-"+tool,"type":"function","function":{
        "name":name,"arguments":args}}


class SyntheticMCPTests(unittest.TestCase):
    def test_scenarios_are_fictional_not_live_and_have_distinct_domains(self):
        cases=scenario_definitions()
        self.assertEqual(len(cases),6)
        self.assertEqual(len({c["id"] for c in cases}),6)
        self.assertGreaterEqual(len({c["domain"] for c in cases}),4)
        for case in cases:
            self.assertNotIn("192.168.",json.dumps(case))
            self.assertNotIn("7851",json.dumps(case))
            self.assertNotIn("7829",json.dumps(case))
            self.assertTrue(all(d["id"].startswith("LAB-") for d in case["devices"]))

    def test_synthetic_commands_can_never_reach_a_real_hub(self):
        async def exercise():
            c=scenario_definitions()[0]
            m=SyntheticMCP(c)
            available=await m.list_tools()
            self.assertTrue(all(t["name"] in GATEWAYS for t in available))
            catalog=await m.call("hub_read_devices",{})
            self.assertEqual(json.loads(catalog["content"][0]["text"])["mode"],"catalog")
            self.assertFalse(catalog.get("isError"))
            schema,discovered=await m.gateway_leaf_schema(
                "hub_manage_devices","hub_call_device_command")
            self.assertTrue(discovered)
            self.assertIn("parameters",schema["inputSchema"]["properties"])
            self.assertNotIn("params",schema["inputSchema"]["properties"])
            self.assertIn("hub_call_device_command",
                m.cached_leaf_schemas()["hub_manage_devices"])
            # The former synthetic-only "params" wire key MUST be rejected.
            incompatible=await m.call("hub_manage_devices",{
                "tool":"hub_call_device_command",
                "args":{"deviceId":"LAB-101","command":"setLevel","params":[40]}})
            self.assertTrue(incompatible["isError"])
            self.assertEqual(json.loads(incompatible["content"][0]["text"])["reason_code"],
                             "invalid_leaf_arguments")

            before=await m.call("hub_read_devices",{"tool":"hub_list_devices",
                "args":{"labelFilter":"Bench Study Lamp"}})
            self.assertEqual(json.loads(before["content"][0]["text"])["count"],1)
            wrong=await m.call("hub_manage_devices",{"tool":"hub_call_device_command",
                "args":{"deviceId":"LAB-101","command":"off"}})
            self.assertTrue(wrong["isError"])
            accepted=await m.call("hub_manage_devices",{"tool":"hub_call_device_command",
                "args":{"deviceId":"LAB-101","command":"setLevel","parameters":["40"]}})
            data=json.loads(accepted["content"][0]["text"])
            self.assertTrue(data["success"])
            self.assertEqual(data["state"]["level"],"15")
            second=await m.call("hub_manage_devices",{"tool":"hub_call_device_command",
                "args":{"deviceId":"LAB-101","command":"setLevel","parameters":["40"]}})
            self.assertTrue(second["isError"],"Even a simulated duplicate is prohibited")
            level=await m.call("hub_read_devices",{"tool":"hub_get_device_attribute",
                "args":{"deviceId":"LAB-101","attribute":"level"}})
            switch=await m.call("hub_read_devices",{"tool":"hub_get_device_attribute",
                "args":{"deviceId":"LAB-101","attribute":"switch"}})
            self.assertEqual(json.loads(level["content"][0]["text"])["value"],"40")
            self.assertEqual(json.loads(switch["content"][0]["text"])["value"],"on")
            checks=_check_coverage(c,m.calls)
            self.assertEqual([q["observed"] for q in checks],[True]*4)
            self.assertEqual(len(m.simulated_writes),1)
            self.assertEqual(m.blocked_attempts,3)
            read_only=SyntheticMCP(scenario_definitions()[2])
            forbidden=await read_only.call("hub_manage_devices",{
                "tool":"hub_call_device_command",
                "args":{"deviceId":"LAB-301","command":"on"}})
            self.assertTrue(forbidden["isError"])
            self.assertEqual(len(read_only.simulated_writes),0)
        asyncio.run(exercise())

    def test_historical_coverage_requires_individual_device_reads(self):
        async def run():
            c=scenario_definitions()[2]
            m=SyntheticMCP(c)
            for did,attr in [("LAB-301","thermostatOperatingState"),
                             ("LAB-301","heatingSetpoint"),
                             ("LAB-302","thermostatOperatingState"),
                             ("LAB-303","thermostatOperatingState")]:
                await m.call("hub_read_devices",{"tool":"hub_list_device_events",
                              "args":{"deviceId":did,"attribute":attr}})
            checks=_check_coverage(c,m.calls)
            self.assertEqual(sum(x["observed"] for x in checks),4)
            self.assertFalse(checks[-1]["observed"])
            # An empty historical result IS a checked source, not proof of idle.
            x=await m.call("hub_read_devices",{"tool":"hub_list_device_events",
                            "args":{"deviceId":"LAB-304",
                                    "attribute":"thermostatOperatingState"}})
            data=json.loads(x["content"][0]["text"])
            self.assertEqual(data["events"],[])
            self.assertEqual(data["history_complete"],"unknown")
            self.assertEqual(sum(x["observed"] for x in _check_coverage(c,m.calls)),5)
        asyncio.run(run())


class FirstAnswerLabTests(unittest.TestCase):
    def test_real_agent_selects_synthetic_gateway_actions_and_fresh_read(self):
        async def run():
            with tempfile.TemporaryDirectory() as folder:
                lab=AutonomousLab(Path(folder)/"synthetic")
                calls=[]
                def model(request):
                    self.assertEqual(request.url.path,"/api/chat")
                    doc=json.loads(request.content)
                    self.assertTrue(doc.get("tools"),"Agent must own model tool selection")
                    self.assertFalse(any("192.168." in json.dumps(row) for row in doc["messages"]))
                    self.assertFalse(any("7851" in json.dumps(row) for row in doc["messages"]))
                    n=len(calls);calls.append(doc)
                    if n==0:
                        response={"tool_calls":[tool_call("hub_read_devices",
                            "hub_list_devices",{"tool":"hub_list_devices",
                                                "args":{"labelFilter":"Bench Study Lamp"}})]}
                    elif n==1:
                        response={"tool_calls":[tool_call("hub_manage_devices",
                            "hub_call_device_command",{"tool":"hub_call_device_command",
                                "args":{"deviceId":"LAB-101","command":"setLevel",
                                        "parameters":["40"]}})]}
                    elif n==2:
                        response={"tool_calls":[tool_call("hub_read_devices",
                            "hub_get_device_attribute",{"tool":"hub_get_device_attribute",
                                "args":{"deviceId":"LAB-101","attribute":"level"}}),
                            tool_call("hub_read_devices","hub_get_device_attribute",
                                {"tool":"hub_get_device_attribute",
                                 "args":{"deviceId":"LAB-101","attribute":"switch"}})]}
                    else:
                        if n==4:
                            self.assertNotIn("hub_manage_devices",[
                                t["function"]["name"] for t in doc["tools"]])
                            self.assertIn("Action/outcome source review",
                                          doc["messages"][-1]["content"])
                        response={"content":("Synthetic hub reports level 40 and switch on "
                                             "after an independent read; physical brightness "
                                             "not independently confirmed.")}
                    return httpx.Response(200,json={"message":response})
                agent=Agent("https://ollama.com","synthetic-test","FAKE_TEST_KEY",30)
                await agent.client.aclose()
                agent.client=httpx.AsyncClient(transport=httpx.MockTransport(model))
                try:
                    await lab.run("lab-01",agent)
                    result=lab.case("lab-01")
                    self.assertEqual(len(calls),5)
                    self.assertTrue(result["success"])
                    self.assertEqual(result["rounds"],5)
                    self.assertEqual(result["simulated_commands"],1)
                    self.assertEqual(result["unsafe_live_actions"],0)
                    self.assertEqual(sum(item["observed"] for item in result["coverage"]),4)
                    self.assertIn("physical brightness",result["answer"])
                    self.assertEqual(len(result["tool_calls"]),4)
                    with self.assertRaises(ValueError):
                        await lab.run("lab-01",agent)
                    good={"factual_grounding":2,"source_completeness":2,
                          "causal_calibration":2,"command_outcome":2,"usefulness":2}
                    with self.assertRaises(ValueError):
                        lab.score("lab-01",dict(good,usefulness=True))
                    lab.score("lab-01",good)
                    rep=lab.report()
                    self.assertEqual(rep["cases_answered"],1)
                    self.assertEqual(rep["cases_graded"],1)
                    self.assertEqual(rep["cases"][0]["observed_evidence_checks"],4)
                    self.assertEqual(rep["live_mcp_calls"],0)
                    self.assertNotIn("Bench Study Lamp",json.dumps(rep))
                    self.assertNotIn("synthetic hub reports level",json.dumps(rep).lower())
                    lab.delete()
                    self.assertEqual(lab.report()["cases_answered"],0)
                finally:
                    await agent.close()
        asyncio.run(run())

    def test_failed_round_limit_is_not_counted_as_answer_and_safe_retry_preserves_evidence(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as folder:
                lab=AutonomousLab(Path(folder)/"synthetic")
                lab.root.mkdir(parents=True,exist_ok=True)
                old={"id":"lab-01",
                     "answer":"Model/transport failure: synthetic round budget",
                     "success":False,"rounds":8,"elapsed_ms":9000,
                     "tool_calls":[{"name":"hub_manage_devices","success":False}],
                     "blocked_attempts":10,"simulated_commands":0,"coverage":[]}
                lab._answer_path("lab-01").write_text(json.dumps(old),encoding="utf-8")
                item=lab.summary()["cases"][0]
                self.assertTrue(item["failed"])
                self.assertFalse(item["answered"])
                report=lab.report()
                self.assertEqual(report["cases_attempted"],1)
                self.assertEqual(report["cases_answered"],0)
                self.assertEqual(report["cases_failed"],1)
                with self.assertRaises(ValueError):
                    lab.score("lab-01",dict.fromkeys(
                        ("factual_grounding","source_completeness",
                         "causal_calibration","command_outcome","usefulness"),0))
                agent=Agent("https://ollama.com","synthetic-test","FAKE_TEST_KEY",30)
                await agent.client.aclose()
                def reply(request):
                    self.assertTrue(json.loads(request.content).get("tools"))
                    return httpx.Response(200,json={"message":{
                        "content":"Synthetic evaluation complete; no live actions."}})
                agent.client=httpx.AsyncClient(transport=httpx.MockTransport(reply))
                try:
                    with self.assertRaises(ValueError):
                        await lab.run("lab-01",agent)
                    await lab.run("lab-01",agent,retry_failed=True)
                    self.assertTrue(lab._failed_archives("lab-01"))
                    archived=json.loads(lab._failed_archives("lab-01")[0].read_text())
                    self.assertEqual(archived["blocked_attempts"],10)
                    status=lab.summary()["cases"][0]
                    self.assertTrue(status["answered"])
                    self.assertFalse(status["failed"])
                    self.assertEqual(status["previous_failed_attempts"],1)
                    report=lab.report()
                    self.assertEqual(report["cases_attempted"],1)
                    self.assertEqual(report["cases_answered"],1)
                    self.assertEqual(report["cases_failed"],0)
                    self.assertEqual(report["prior_failed_attempts"],1)
                    with self.assertRaises(ValueError):
                        await lab.run("lab-01",agent,retry_failed=True)
                    lab.delete()
                    self.assertFalse(lab._failed_archives("lab-01"))
                    self.assertEqual(lab.report()["cases_attempted"],0)
                finally:
                    await agent.close()
        asyncio.run(exercise())

    def test_http_routes_require_manual_consent_and_are_separate_from_mcp(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as folder:
                web=FastAPI()
                web.include_router(router)
                web.state.autolab=AutonomousLab(Path(folder)/"lab")
                web.state.autolab_progress={"running":False,"error":None}
                web.state.autolab_task=None
                web.state.configuration_error=None
                web.state.options={"model_base_url":"https://ollama.com",
                                   "model_name":"gemma4:31b-cloud",
                                   "model_api_key":"FAKE_TEST_KEY",
                                   "model_timeout_seconds":30}
                model=Agent("https://ollama.com","synthetic-test","FAKE_TEST_KEY",30)
                await model.client.aclose()
                network=[]
                def response(request):
                    network.append(json.loads(request.content))
                    return httpx.Response(200,json={"message":{
                        "content":"Cannot verify cause from synthetic returned sources."}})
                model.client=httpx.AsyncClient(transport=httpx.MockTransport(response))
                web.state.model=model
                # A real MCP connection deliberately DOES NOT EXIST in this test.
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=web),
                                            base_url="http://test") as client:
                    h={"X-Homebrain-Request":"1"}
                    self.assertEqual((await client.get("/api/autonomous/status")).status_code,403)
                    s=(await client.get("/api/autonomous/status",headers=h)).json()
                    self.assertEqual(len(s["cases"]),6)
                    self.assertTrue(s["synthetic_only"])
                    body={"case_id":"lab-05","model_execution_consent":False,
                          "cloud_transfer_consent":False}
                    self.assertEqual((await client.post("/api/autonomous/run",
                        json=body,headers=h)).status_code,403)
                    body["model_execution_consent"]=True
                    self.assertEqual((await client.post("/api/autonomous/run",
                        json=body,headers=h)).status_code,403)
                    self.assertEqual(len(network),0)
                    body["cloud_transfer_consent"]=True
                    self.assertEqual((await client.post("/api/autonomous/run",
                        json=body,headers=h)).status_code,200)
                    await web.state.autolab_task
                    self.assertEqual(len(network),1)
                    self.assertTrue(network[0].get("tools"))
                    detail=(await client.get("/api/autonomous/case/lab-05",headers=h)).json()
                    self.assertEqual(detail["answer"],"Cannot verify cause from synthetic returned sources.")
                    self.assertEqual(detail["unsafe_live_actions"],0)
                    report=(await client.get("/api/autonomous/report",headers=h)).json()
                    self.assertEqual(report["cases_answered"],1)
                    self.assertNotIn("Cannot verify cause",json.dumps(report))
                    self.assertEqual((await client.post("/api/autonomous/delete",
                        json={"confirm_delete":False},headers=h)).status_code,400)
                    self.assertEqual((await client.post("/api/autonomous/delete",
                        json={"confirm_delete":True},headers=h)).status_code,200)
                    self.assertEqual(web.state.autolab.report()["cases_answered"],0)
                await model.close()
        asyncio.run(exercise())


if __name__=="__main__":
    unittest.main()
