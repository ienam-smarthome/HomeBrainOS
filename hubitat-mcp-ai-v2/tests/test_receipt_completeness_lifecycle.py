"""Synthetic model lifecycle: audit sees exact source chronology with zero tool offers."""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"rootfs"/"app"))
from agent import Agent

EVENTS=[]
for i, clock in enumerate(("09:00:00.101","09:30:00.102","10:00:00.103",
                           "10:30:00.104","11:00:00.105","11:30:00.106")):
    for name,val in (("thermostatOperatingState","idle"),("level","0")):
        EVENTS.append({"name":name,"value":val,"date":f"2030-04-02T{clock}+0000"})
EVENTS.append({"name":"command-setHeatingSetpoint","type":"command",
               "date":"2030-04-02T11:15:03.621+0000",
               "producedBy":{"appId":123,"name":"Fictional Writer"}})


class CompletenessFinalModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_review_audit_gets_all_rows_and_issuer_without_extra_read(self):
        class MCP:
            def __init__(self): self.calls=[]
            async def list_tools(self, refresh=False):
                return [{"name":"hub_list_device_events",
                         "inputSchema":{"type":"object","properties":{
                             "deviceId":{"type":"integer"},
                             "hoursBack":{"type":"integer"}}}}]
            async def call(self,name,args):
                self.calls.append((name,args))
                if name!="hub_list_device_events":
                    raise AssertionError("Unexpected tool")
                return {"content":[{"type":"text","text":json.dumps({
                    "events":list(reversed(EVENTS)),"count":len(EVENTS),
                    "sinceTimestamp":"2030-04-02T08:59:00+0000"
                })}]}
        class Model(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434","fictional","",20)
                self.seen=[]
                self.offered=[]
            async def round(self,messages,tools,remaining):
                self.seen.append([dict(m) for m in messages])
                self.offered.append([t["function"]["name"] for t in tools])
                r=len(self.seen)
                if r==1:
                    return {"tool_calls":[{"function":{
                        "name":"hub_list_device_events",
                        "arguments":{"deviceId":101,"hoursBack":3}}}]}
                if r==2:
                    return {"content":"Four hourly thermostatOperatingState and level samples."}
                if r==3:
                    return {"content":"Four thermostatOperatingState/level samples; no commands."}
                if r==4:
                    return {"content":("Six reported idle/0 observations at 30-minute "
                       "intervals, plus one recorded command; the internal "
                       "reason for the command is unknown.")}
                raise AssertionError("Unexpected additional model round")
        model,mcp=Model(),MCP()
        try:
            result=await model.answer(
                "Did a fictional valve remain heating continuously throughout "
                "the last three hours? Do not change anything.",
                [],mcp,90,enable_causal_follow_through=False)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"],4)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"],"historical_measurement")
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"],"completed")
        self.assertEqual(len(mcp.calls),1)
        self.assertEqual(model.offered[-1],[])
        prompt=model.seen[-1][-1]["content"]
        self.assertIn('"original_event_completeness":',prompt)
        self.assertIn('"original_returned_rows_for_name":6',prompt)
        self.assertIn('"recorded_issuer_app_id":123',prompt)
        self.assertIn("Six reported",result["answer"])


if __name__=="__main__":
    unittest.main()
