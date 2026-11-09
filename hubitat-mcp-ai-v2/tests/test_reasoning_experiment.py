"""New synthetic holdout evaluation: model-led A/B, no real MCP or cloud calls."""
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
from autonomous_lab import SyntheticMCP, CRITERIA
from reasoning_experiment import (
    CANDIDATE_GUIDANCE, ExperimentalAgent, ReasoningExperiment,
    holdout_scenarios, tool_metrics,
)
from reasoning_routes import router


def function_call(gateway,leaf,args):
    return {"id":"synthetic-"+leaf,"type":"function",
            "function":{"name":gateway,"arguments":{"tool":leaf,"args":args}}}


class HoldoutFixturesTests(unittest.TestCase):
    def test_six_new_cases_are_fictional_and_have_valid_grounded_checks(self):
        scenarios=holdout_scenarios()
        self.assertEqual(len(scenarios),6)
        self.assertEqual(len({x["id"] for x in scenarios}),6)
        self.assertEqual(len({x["domain"] for x in scenarios}),6)
        self.assertTrue(all(c["id"].startswith("hold-") for c in scenarios))
        for c in scenarios:
            blob=json.dumps(c)
            self.assertNotIn("192.168.",blob)
            for prohibited in ("Bench Study Lamp","Bench Workshop Fan","Bench Boiler",
                               "Bench Cellar Sensor","Bench Corridor Lamp","LAB-"):
                self.assertNotIn(prohibited,blob)
            ids={device["id"] for device in c["devices"]}
            self.assertTrue(ids)
            self.assertTrue(all(x.startswith("HOLD-") for x in ids))
            self.assertTrue(c["checks"])
            for check in c["checks"]:
                self.assertIn(check["leaf"],(
                    "hub_list_devices","hub_list_device_events",
                    "hub_get_app_config","hub_get_device_health","hub_get_logs",
                    "hub_call_device_command","fresh_switch"))
                if "id" in check:
                    self.assertTrue(check["id"] in ids or
                                    check["id"] in c["apps"])
        self.assertEqual(sum(c["allow_command"] is not None for c in scenarios),1)

    def test_fixture_does_not_allow_unrequested_write(self):
        async def exercise():
            for c in holdout_scenarios()[:-1]:
                fake=SyntheticMCP(c)
                response=await fake.call("hub_manage_devices",{
                    "tool":"hub_call_device_command",
                    "args":{"deviceId":c["devices"][0]["id"],"command":"off"}})
                self.assertTrue(response["isError"])
                self.assertFalse(fake.simulated_writes)
            command=holdout_scenarios()[-1]
            fake=SyntheticMCP(command)
            first=await fake.call("hub_manage_devices",{
                "tool":"hub_call_device_command",
                "args":{"deviceId":"HOLD-601","command":"on"}})
            self.assertFalse(first["isError"])
            self.assertEqual(len(fake.simulated_writes),1)
            duplicate=await fake.call("hub_manage_devices",{
                "tool":"hub_call_device_command",
                "args":{"deviceId":"HOLD-601","command":"on"}})
            self.assertTrue(duplicate["isError"])
            self.assertEqual(len(fake.simulated_writes),1)
        asyncio.run(exercise())

    def test_contract_error_count_is_separate_from_server_rejection_count(self):
        c=holdout_scenarios()[-1]
        fake=SyntheticMCP(c)
        result={"success":True,"answer":"synthetic",
                "tool_calls":[
                    {"name":"hub_manage_devices","result_kind":"contract_error",
                     "success":False,"operation_executed":False},
                    {"name":"hub_read_devices","result_kind":"tool_result",
                     "success":True},
                ]}
        result_metrics=tool_metrics(result,fake,c)
        self.assertEqual(result_metrics["client_contract_errors"],1)
        self.assertEqual(result_metrics["simulator_rejections"],0)
        self.assertEqual(result_metrics["other_failed_calls"],0)


class BlindReasoningStudyTests(unittest.TestCase):
    def test_model_owns_each_tool_sequence_and_only_candidate_gets_guidance(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as temp:
                exp=ReasoningExperiment(Path(temp)/"reasoning")
                queries={"candidate":[],"baseline":[]}
                counters={"candidate":0,"baseline":0}
                def model(request):
                    self.assertEqual(request.url.path,"/api/chat")
                    payload=json.loads(request.content)
                    self.assertTrue(payload["tools"])
                    system=payload["messages"][0]["content"]
                    condition=("candidate" if CANDIDATE_GUIDANCE in system else "baseline")
                    queries[condition].append(payload)
                    counter=counters[condition]
                    counters[condition]+=1
                    if counter==0:
                        body={"tool_calls":[function_call(
                            "hub_read_devices","hub_list_devices",
                            {"labelFilter":"Bench Test Beacon"})]}
                    elif counter==1:
                        body={"tool_calls":[function_call(
                            "hub_manage_devices","hub_call_device_command",
                            {"deviceId":"HOLD-601","command":"on"})]}
                    elif counter==2:
                        body={"tool_calls":[function_call(
                            "hub_read_devices","hub_get_device_attribute",
                            {"deviceId":"HOLD-601","attribute":"switch"})]}
                    elif counter==3:
                        body={"tool_calls":[function_call(
                            "hub_read_devices","hub_list_device_events",
                            {"deviceId":"HOLD-601","attribute":"switch"})]}
                    else:
                        body={"content":(
                            "Synthetic command accepted. Independent state still OFF. "
                            "Cause remains unverified; no command repeated.")}
                    return httpx.Response(200,json={"message":body})
                agent=Agent("https://ollama.com","fixture-model","TEST_FAKE",30)
                await agent.client.aclose()
                agent.client=httpx.AsyncClient(transport=httpx.MockTransport(model))
                try:
                    await exp.run_pair("hold-06",agent)
                    self.assertEqual(len(queries["candidate"]),5)
                    self.assertEqual(len(queries["baseline"]),5)
                    self.assertTrue(all(CANDIDATE_GUIDANCE in x["messages"][0]["content"]
                                        for x in queries["candidate"]))
                    self.assertTrue(all(CANDIDATE_GUIDANCE not in x["messages"][0]["content"]
                                        for x in queries["baseline"]))
                    self.assertEqual(
                        queries["candidate"][0]["messages"][-1],
                        queries["baseline"][0]["messages"][-1],
                        "First user prompt must be identical in both arms")
                    detail=exp.case("hold-06")
                    self.assertNotIn("candidate_label",json.dumps(detail))
                    self.assertNotIn("hidden_condition",json.dumps(detail))
                    self.assertNotIn("EXPERIMENTAL INVESTIGATION",json.dumps(detail))
                    self.assertEqual(set(detail["arms"]),{"A","B"})
                    for arm in detail["arms"].values():
                        self.assertTrue(arm["success"])
                        self.assertEqual(arm["simulated_commands"],1)
                        self.assertEqual(arm["client_contract_errors"],0)
                        self.assertEqual(sum(row["observed"] for row in arm["coverage"]),4)
                        self.assertIn("OFF",arm["answer"])
                    with self.assertRaises(ValueError):
                        await exp.run_pair("hold-06",agent)
                    self.assertNotIn("unblinded_conditions",exp.report())
                    excellent={k:2 for k in CRITERIA}
                    exp.score("hold-06",{"A":excellent,"B":excellent})
                    self.assertFalse(exp.report()["condition_mapping_revealed"])
                    with self.assertRaises(ValueError):
                        await exp.run_pair("hold-06",agent)
                finally:
                    await agent.close()
        asyncio.run(exercise())

    def test_mapping_is_unblinded_only_after_all_six_pairs_scored(self):
        with tempfile.TemporaryDirectory() as temp:
            exp=ReasoningExperiment(Path(temp)/"holdout")
            exp.root.mkdir(parents=True,exist_ok=True)
            ratings={"A":{k:2 for k in CRITERIA},
                     "B":{k:1 for k in CRITERIA}}
            for i,sid in enumerate(exp.catalog):
                allocation=exp._allocation(sid)
                self.assertEqual(set(allocation.values()),{"baseline","candidate"})
                for label in ("A","B"):
                    exp._answer_path(sid,label).write_text(
                        json.dumps({"success":True,"rounds":2,"elapsed_ms":1000,
                                    "tool_calls":[],"coverage":[]}),
                        encoding="utf-8")
                if i<5:
                    exp.score(sid,ratings)
                    with self.assertRaisesRegex(ValueError,"already saved"):
                        exp.score(sid,{"A":{k:0 for k in CRITERIA},
                                       "B":{k:0 for k in CRITERIA}})
            self.assertEqual(sum(exp._allocation(sid)["A"]=="candidate" for sid in exp.catalog),3)
            self.assertEqual(sum(exp._allocation(sid)["B"]=="candidate" for sid in exp.catalog),3)
            before=exp.report()
            self.assertFalse(before["condition_mapping_revealed"])
            self.assertNotIn("unblinded_conditions",before)
            self.assertNotIn("candidate_label",json.dumps(before))
            last=list(exp.catalog)[-1]
            exp.score(last,ratings)
            with self.assertRaisesRegex(ValueError,"already saved"):
                exp.score(last,{"A":{k:0 for k in CRITERIA},
                                "B":{k:0 for k in CRITERIA}})
            report=exp.report()
            self.assertTrue(report["condition_mapping_revealed"])
            self.assertEqual(report["paired_answers_completed"],6)
            self.assertEqual(report["paired_blind_ratings"],6)
            self.assertEqual(len(report["unblinded_conditions"]),6)
            self.assertEqual(report["criterion_effects"]["causal_calibration"]["compared_pairs"],6)
            self.assertEqual(report["live_device_actions"],0)
            self.assertNotIn("HOLD-201",json.dumps(report),"Reports omit source/device IDs")
            self.assertNotIn(CANDIDATE_GUIDANCE,json.dumps(report))
            with self.assertRaises(ValueError):
                exp.score("missing",ratings)
            with self.assertRaises(ValueError):
                exp.score("hold-06",{"A":{},"B":{}})
            exp.delete()
            self.assertFalse(any(exp.root.glob("*")), "Only study files existed")

    def test_failure_archive_does_not_overwrite_completed_arm(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as temp:
                exp=ReasoningExperiment(Path(temp)/"holdout")
                exp._allocation("hold-06")
                exp.root.mkdir(parents=True,exist_ok=True)
                old={"success":True,"answer":"successful prior A",
                     "tool_calls":[],"coverage":[]}
                failed={"success":False,"answer":"model timeout",
                        "tool_calls":[],"coverage":[]}
                exp._answer_path("hold-06","A").write_text(json.dumps(old))
                exp._answer_path("hold-06","B").write_text(json.dumps(failed))
                with self.assertRaises(ValueError):
                    exp.can_run("hold-06")
                exp.can_run("hold-06",retry_failed=True)
                def model(request):
                    return httpx.Response(200,json={"message":{
                        "content":"Synthetic answer after retry."}})
                agent=Agent("https://ollama.com","test","TEST",30)
                await agent.client.aclose()
                agent.client=httpx.AsyncClient(transport=httpx.MockTransport(model))
                try:
                    await exp.run_pair("hold-06",agent,retry_failed=True)
                    self.assertEqual(exp.case("hold-06")["arms"]["A"]["answer"],
                                     "successful prior A")
                    self.assertEqual(len(exp._attempts("hold-06","B")),1)
                    self.assertEqual(exp.case("hold-06")["arms"]["B"]["success"],True)
                    self.assertEqual(
                        json.loads(exp._attempts("hold-06","B")[0].read_text())["answer"],
                        "model timeout")
                finally:
                    await agent.close()
        asyncio.run(exercise())

    def test_http_opt_in_blind_pair_and_report_never_use_real_mcp(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as temp:
                app=FastAPI()
                app.include_router(router)
                app.state.reasoning_lab=ReasoningExperiment(Path(temp)/"holdout")
                app.state.reasoning_progress={"running":False,"error":None}
                app.state.reasoning_task=None
                app.state.autolab_progress={"running":False,"error":None}
                app.state.benchmark_progress={"running":False,"error":None}
                app.state.configuration_error=None
                app.state.options={"model_base_url":"https://ollama.com",
                                   "model_name":"gemma4:31b-cloud",
                                   "model_api_key":"FAKE_TEST",
                                   "model_timeout_seconds":30}
                requests=[]
                def mock(request):
                    requests.append(json.loads(request.content))
                    return httpx.Response(200,json={"message":{
                        "content":"No causal conclusion verified from synthetic fixtures."}})
                model=Agent("https://ollama.com","fixture","FAKE_TEST",30)
                await model.client.aclose()
                model.client=httpx.AsyncClient(transport=httpx.MockTransport(mock))
                app.state.model=model
                try:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                                base_url="http://test") as client:
                        h={"X-Homebrain-Request":"1"}
                        self.assertEqual(
                            (await client.get("/api/reasoning-ab/status")).status_code,403)
                        data=(await client.get("/api/reasoning-ab/status",headers=h)).json()
                        self.assertEqual(len(data["cases"]),6)
                        req={"case_id":"hold-01","model_execution_consent":False,
                             "cloud_transfer_consent":False}
                        self.assertEqual((await client.post("/api/reasoning-ab/run",
                            json=req,headers=h)).status_code,403)
                        req["model_execution_consent"]=True
                        self.assertEqual((await client.post("/api/reasoning-ab/run",
                            json=req,headers=h)).status_code,403)
                        self.assertEqual(len(requests),0)
                        req["cloud_transfer_consent"]=True
                        self.assertEqual((await client.post("/api/reasoning-ab/run",
                            json=req,headers=h)).status_code,200)
                        await app.state.reasoning_task
                        self.assertEqual(len(requests),2,
                                         "Independent model calls must be made for both arms")
                        case=(await client.get("/api/reasoning-ab/case/hold-01",
                                               headers=h)).json()
                        self.assertEqual(set(case["arms"]),{"A","B"})
                        self.assertNotIn("candidate_label",json.dumps(case))
                        report=(await client.get("/api/reasoning-ab/report",headers=h)).json()
                        self.assertEqual(report["paired_answers_completed"],1)
                        self.assertFalse(report["condition_mapping_revealed"])
                        self.assertNotIn("unblinded_conditions",report)
                        score={"A":{k:2 for k in CRITERIA},"B":{k:1 for k in CRITERIA}}
                        r=await client.post("/api/reasoning-ab/case/hold-01/score",
                                             json={"scores":score},headers=h)
                        self.assertEqual(r.status_code,200)
                        self.assertTrue(r.json()["mapping_hidden"])
                        again=await client.post("/api/reasoning-ab/case/hold-01/score",
                                                 json={"scores":score},headers=h)
                        self.assertEqual(again.status_code,400)
                        self.assertIn("locked",again.json()["detail"])
                        self.assertEqual((await client.post("/api/reasoning-ab/run",
                            json=req,headers=h)).status_code,409)
                        self.assertEqual((await client.post("/api/reasoning-ab/delete",
                            json={"confirm_delete":False},headers=h)).status_code,400)
                        self.assertEqual((await client.post("/api/reasoning-ab/delete",
                            json={"confirm_delete":True},headers=h)).status_code,200)
                        self.assertEqual(app.state.reasoning_lab.report()["paired_answers_completed"],0)
                finally:
                    await model.close()
        asyncio.run(exercise())


if __name__=="__main__":
    unittest.main()
