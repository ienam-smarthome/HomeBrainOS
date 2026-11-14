"""Scripted V2 model+MCP path: no new model rounds, tools, writes or polling."""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent


def rows():
    events=[]
    for idx, value in enumerate(("on","off","on","off","on","off","on","off")):
        events.append({
            "name":"switch","value":value,
            "date":f"2030-04-02T{19+idx//4:02d}:{idx%4*10:02d}:00.000+0000",
            "isStateChange":True,"type":"physical",
            "producedBy":{"deviceId":"777","name":"Fictional Bridge"},
        })
    events.append({"name":"command-on","type":"command",
                   "date":"2030-04-02T20:31:00.000+0000",
                   "producedBy":{"appId":99,"name":"Fictional Controller"}})
    return list(reversed(events))


class TypedHistoryLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_final_audit_cannot_publish_missing_rows(self):
        class MCP:
            def __init__(self): self.calls=[]
            async def list_tools(self,refresh=False):
                return [{"name":"hub_list_device_events","description":"Read device events",
                         "inputSchema":{"type":"object","properties":{
                             "deviceId":{"type":"integer"},
                             "hoursBack":{"type":"integer"},
                             "limit":{"type":"integer"}}}}]
            async def call(self,name,args):
                self.calls.append((name,args))
                if name!="hub_list_device_events":
                    raise AssertionError("Unexpected write/tool")
                payload={"deviceId":"101","hoursBack":6,
                         "sinceTimestamp":"2030-04-02T16:30:00+0000",
                         "attributeFilter":None,"events":rows(),
                         "count":len(rows())}
                return {"content":[{"type":"text","text":json.dumps(payload)}]}
        class Model(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434","synthetic","",20)
                self.round_count=0
                self.audit_tool_names=[]
            async def round(self,messages,tools,remaining):
                self.round_count+=1
                r=self.round_count
                if r==1:
                    return {"tool_calls":[{"function":{
                        "name":"hub_list_device_events",
                        "arguments":{"deviceId":101,"hoursBack":6,"limit":500}}}]}
                if r==2:
                    return {"content":"Six returned switch state changes; three cycles."}
                if r==3:
                    return {"content":"Six returned switch state changes, no other commands."}
                if r==4:
                    self.audit_tool_names=[t["function"]["name"] for t in tools]
                    return {"content":"Six switch events, three ON/OFF cycles, all supported."}
                raise AssertionError("Unexpected model round")

        model,mcp=Model(),MCP()
        try:
            result=await model.answer(
                "List all "
                "returned ON/OFF state changes during the past six hours, exact timestamps, intervals, "
                "recorded commands and issuers. Do not change anything.",
                [],mcp,90,enable_causal_follow_through=False)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"],4)
        self.assertEqual(len(mcp.calls),1)
        self.assertTrue(result["source_review_invoked"])
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"],"completed")
        self.assertEqual(model.audit_tool_names,[])
        self.assertEqual(result["structured_history_verification"]["status"],
                         "source_ledger_used")
        self.assertEqual(result["structured_history_verification"]["selected_state_rows"],8)
        self.assertEqual(result["structured_history_verification"]["source_command_rows"],1)
        self.assertIn("**8 returned switch reports**",result["answer"])
        self.assertIn("app 99 (Fictional Controller)",result["answer"])
        self.assertNotIn("three ON/OFF cycles",result["answer"])
        # The assistant's unverified draft remains available to private review,
        # but cannot be published instead of original source-derived rows.
        self.assertIn("Six switch events",result["answer_stage_trace"][-1]["answer"])

    async def test_non_exhaustive_questions_pass_through_without_model_replacement(self):
        from typed_history_verification import verify_and_project_history
        r=verify_and_project_history(
            "Why was a lamp most recently switched OFF?",
            "Model explanation needs config evidence.",[])
        self.assertEqual(r["status"],"not_applicable")
        self.assertEqual(r["answer"],"Model explanation needs config evidence.")


if __name__=="__main__":
    unittest.main()
