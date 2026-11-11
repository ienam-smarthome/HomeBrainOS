"""Blinded candidate-vs-baseline experiment using *new* fictional MCP cases.

No live MCPClient is constructed. Both arms execute the same production
Agent.answer loop, independent SyntheticMCP fixtures and the same configured
Ollama model. The candidate receives ONLY general evidence-completion guidance.
No answers are prefilled, tools forced, writes permitted beyond one exact
simulated command, or live agent files changed.

Store answers/receipts and the hidden allocation privately in add-on /data;
report exports never include them. This is exploratory, not a statistical
proof of reasoning improvements on real Hubitat.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from agent import Agent
from autonomous_lab import (
    BoundedAgent, SyntheticMCP, _check_coverage, ev, CRITERIA,
    MAX_TOOL_ATTEMPTS, SANDBOX_DEADLINE_SECONDS,
)
from benchmark import _private_write

CANDIDATE_GUIDANCE = """EXPERIMENTAL INVESTIGATION COMPLETION AUDIT.
Apply this to new investigations without a fixed tool list or fixed conclusion.
Before finishing, identify which observations support each consequential
claim, distinguish source reports from historical state, command issuers from
event listeners, and command acceptance from confirmed current state.
Consider at least one plausible alternative to a causal explanation; look for
a *discriminating* read-only source if one is available and would materially
change the answer. Do not fetch unnecessary sources for already-supported
claims, repeat executed commands, invent historical continuity, or treat a
bounded empty history as proof of absence. When evidence cannot distinguish
causes, say what remains unverified and what specific observation would help.
You decide the tool sequence and when the evidence is sufficient; no special
answers or incident-specific action rules are provided.
"""

SANDBOX_NOTICE = (
    "SYNTHETIC BENCHMARK ONLY. All named devices, logs, commands and events "
    "come from an isolated in-memory fictional MCP server. No real Hubitat, "
    "Home Assistant or hardware is connected. Any authorised simulated command "
    "changes an in-memory fixture ONLY. Do not infer actual physical results. "
    "Choose tools yourself. Respond to the user's fictional question.\n\n"
)

MAX_FAILED_RETRIES=2


def holdout_scenarios() -> list[dict]:
    """New evidence and different questions from alpha.23's six public lab cases."""
    return [
        {
            "id":"hold-01","domain":"energy_history",
            "title":"Freezer power dip and alleged outage",
            "question":("Did Bench Cold Store actually lose electrical power around "
                        "03:00, and if so, how long was the outage? Investigate the "
                        "recorded history; distinguish power consumption from power "
                        "supply, and state anything not established. Do not change anything."),
            "allow_command":None,
            "devices":[
                {"id":"HOLD-101","label":"Bench Cold Store Plug",
                 "capabilities":["Switch","PowerMeter"],
                 "currentStates":{"switch":"on","power":"76"}}],
            "events":{"HOLD-101":{
                "power":[ev("76","2026-11-12T03:25:00Z"),
                         ev("0","2026-11-12T03:00:00Z"),
                         ev("2","2026-11-12T02:50:00Z")],
                "switch":[ev("on","2026-11-12T03:26:00Z"),
                          ev("on","2026-11-12T02:45:00Z")]}},
            "logs":{"entries":[{"timestamp":"2026-11-12T03:40:00Z",
                                "message":"Routine synthetic monitoring"}],
                    "count":1,"total":2040,"limit":20,"offset":0,"complete":False},
            "apps":{},
            "checks":[
                {"label":"Meter power event history","leaf":"hub_list_device_events",
                 "id":"HOLD-101","attribute":"power"},
                {"label":"Plug switch event history","leaf":"hub_list_device_events",
                 "id":"HOLD-101","attribute":"switch"},
                {"label":"Scoped diagnostic-log limitations","leaf":"hub_get_logs"}],
        },
        {
            "id":"hold-02","domain":"command_provenance",
            "title":"Entrance lamp with a confirmed issuer and event listener",
            "question":("Why did Bench Entrance Lamp go OFF at 18:19? Establish which "
                        "source reported the state, which app received the event, "
                        "and whether an actual OFF command and nearby entry-sensor "
                        "activity explain it. Do not change anything."),
            "allow_command":None,
            "devices":[
                {"id":"HOLD-201","label":"Bench Entrance Lamp",
                 "capabilities":["Switch"],"currentStates":{"switch":"off"}},
                {"id":"HOLD-202","label":"Bench Entry Contact",
                 "capabilities":["ContactSensor"],"currentStates":{"contact":"closed"}}],
            "events":{
                "HOLD-201":{"switch":[
                    ev("off","2026-11-12T18:19:00Z",produced_by="Synthetic Matter Bridge",
                       triggered=[{"name":"Bench Activity Journal",
                                   "appId":9201299,"handler":"switchHandler"}]),
                    ev("on","2026-11-12T18:05:00Z",produced_by="Synthetic Matter Bridge")]},
                "HOLD-202":{"contact":[
                    ev("closed","2026-11-12T18:18:40Z"),
                    ev("open","2026-11-12T18:18:12Z")]}},
            "command_history":{"HOLD-201":[
                {"command":"off","date":"2026-11-12T18:18:59.820Z",
                 "issuer":"Bench Entrance Auto-Off","appId":9201201}]},
            "apps":{"9201201":{
                "name":"Bench Entrance Auto-Off","contact_device":"HOLD-202",
                "on_closed_action":"off","inactive_delay_seconds":20,
                "configuration_observed_at":"2026-11-12T18:50:00Z",
                "internal_handler_execution_log":"not available"}},
            "checks":[
                {"label":"Lamp reported state transition","leaf":"hub_list_device_events",
                 "id":"HOLD-201","attribute":"switch"},
                {"label":"Native OFF command issuer history","leaf":"hub_list_device_events",
                 "id":"HOLD-201","attribute":"command-off"},
                {"label":"Entry contact event history","leaf":"hub_list_device_events",
                 "id":"HOLD-202","attribute":"contact"},
                {"label":"Automation configuration snapshot","leaf":"hub_get_app_config",
                 "id":"9201201"}],
        },
        {
            "id":"hold-03","domain":"humidity_intervals",
            "title":"Workshop moisture threshold timing",
            "question":("When did Bench Workshop Humidity first register above 70%, "
                        "and how long until it next registered below 60%? Distinguish "
                        "observed sample times from exact threshold crossing times. "
                        "Did the ventilation control necessarily activate? Read only."),
            "allow_command":None,
            "devices":[
                {"id":"HOLD-301","label":"Bench Workshop Humidity",
                 "capabilities":["RelativeHumidityMeasurement"],
                 "currentStates":{"humidity":"51"}},
                {"id":"HOLD-302","label":"Bench Workshop Ventilation",
                 "capabilities":["Switch"],"currentStates":{"switch":"off"}}],
            "events":{
                "HOLD-301":{"humidity":[
                    ev("51","2026-11-12T10:30:00Z"),
                    ev("58","2026-11-12T09:32:00Z"),
                    ev("62","2026-11-12T09:21:00Z"),
                    ev("72","2026-11-12T09:07:00Z"),
                    ev("76","2026-11-12T08:51:00Z"),
                    ev("61","2026-11-12T08:35:00Z")]},
                "HOLD-302":{"switch":[
                    ev("off","2026-11-12T10:00:00Z")]}},
            "apps":{},
            "checks":[
                {"label":"Historical humidity sequence","leaf":"hub_list_device_events",
                 "id":"HOLD-301","attribute":"humidity"},
                {"label":"Ventilation switch history","leaf":"hub_list_device_events",
                 "id":"HOLD-302","attribute":"switch"}],
        },
        {
            "id":"hold-04","domain":"historic_heating",
            "title":"Short boiler cycle and missing zone history",
            "question":("A fictional heating controller reported activity near 10:00, "
                        "although the zone thermostats are now idle. Explain what the "
                        "recorded operating-state histories and coordinator settings "
                        "can and cannot establish about heat demand at 10:00. Read only."),
            "allow_command":None,
            "devices":[
                {"id":"HOLD-401","label":"Bench Central Heater",
                 "controller_app_id":9201401,
                 "capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle",
                                  "heatingSetpoint":"13"}},
                {"id":"HOLD-402","label":"Bench Office Zone",
                 "capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle"}},
                {"id":"HOLD-403","label":"Bench Dining Zone",
                 "capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle"}},
                {"id":"HOLD-404","label":"Bench Loft Zone",
                 "capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle"}}],
            "events":{
                "HOLD-401":{"thermostatOperatingState":[
                    ev("idle","2026-11-12T10:33:00Z"),
                    ev("heating","2026-11-12T10:00:02Z")],
                    "heatingSetpoint":[ev("13","2026-11-12T10:32:40Z"),
                                       ev("24","2026-11-12T09:59:39Z")]},
                "HOLD-402":{"thermostatOperatingState":[
                    ev("idle","2026-11-12T10:14:00Z"),
                    ev("heating","2026-11-12T09:59:57Z")]},
                "HOLD-403":{"thermostatOperatingState":[
                    ev("idle","2026-11-12T10:28:00Z"),
                    ev("heating","2026-11-12T10:00:15Z")]},
                "HOLD-404":{"thermostatOperatingState":[]}},
            "apps":{"9201401":{
                "name":"Bench Heat-Demand Coordinator",
                "demand_policy":"any zone calling",
                "controller_source":"synthetic control rules",
                "configuration_observed_at":"2026-11-12T11:00:00Z",
                "historical_internal_decisions":"not available"}},
            "checks":[
                {"label":"Controller historical operating state","leaf":"hub_list_device_events",
                 "id":"HOLD-401","attribute":"thermostatOperatingState"},
                {"label":"Controller historical setpoint","leaf":"hub_list_device_events",
                 "id":"HOLD-401","attribute":"heatingSetpoint"},
                {"label":"Office historical demand","leaf":"hub_list_device_events",
                 "id":"HOLD-402"},
                {"label":"Dining historical demand","leaf":"hub_list_device_events",
                 "id":"HOLD-403"},
                {"label":"Loft checked even if empty","leaf":"hub_list_device_events",
                 "id":"HOLD-404"},
                {"label":"Current coordinator configuration","leaf":"hub_get_app_config",
                 "id":"9201401"}],
        },
        {
            "id":"hold-05","domain":"connectivity",
            "title":"Two independent devices with stale observations",
            "question":("Bench Nursery Sensor and Bench Roof Sensor both show old "
                        "measurements. Was there a common network or MQTT failure, "
                        "or only stale reports? Investigate health, device histories "
                        "and diagnostic-log coverage, and say what is unknown. Read only."),
            "allow_command":None,
            "devices":[
                {"id":"HOLD-501","label":"Bench Nursery Sensor",
                 "capabilities":["TemperatureMeasurement"],
                 "lastActivity":"2026-11-11T07:20:00Z",
                 "currentStates":{"temperature":"19"}},
                {"id":"HOLD-502","label":"Bench Roof Sensor",
                 "capabilities":["TemperatureMeasurement"],
                 "lastActivity":"2026-11-11T00:10:00Z",
                 "currentStates":{"temperature":"9"}}],
            "events":{
                "HOLD-501":{"temperature":[
                    ev("19","2026-11-11T07:20:00Z")]},
                "HOLD-502":{"temperature":[
                    ev("9","2026-11-11T00:10:00Z")]}},
            "health":{"checked_at":"2026-11-12T14:00:00Z",
                      "stale_threshold_hours":24,
                      "devices":[
                          {"deviceId":"HOLD-501","status":"stale",
                           "lastActivity":"2026-11-11T07:20:00Z"},
                          {"deviceId":"HOLD-502","status":"stale",
                           "lastActivity":"2026-11-11T00:10:00Z"}]},
            "logs":{"entries":[
                {"timestamp":"2026-11-12T13:55:00Z",
                 "message":"Synthetic event queue routine check"}],
                "count":1,"total":4270,"limit":25,"offset":0,"complete":False},
            "apps":{},
            "checks":[
                {"label":"Stale activity classifications","leaf":"hub_get_device_health"},
                {"label":"Nursery event history","leaf":"hub_list_device_events",
                 "id":"HOLD-501"},
                {"label":"Roof event history","leaf":"hub_list_device_events",
                 "id":"HOLD-502"},
                {"label":"Bounded diagnostic logs inspected","leaf":"hub_get_logs"}],
        },
        {
            "id":"hold-06","domain":"command_outcome",
            "title":"Accepted beacon command without state change",
            "question":("In this fictional test sandbox, turn ON Bench Test Beacon "
                        "and check whether the requested state was actually reported "
                        "afterwards. If still OFF, investigate without repeating the "
                        "ON action, and explain what is and is not verified."),
            "allow_command":("HOLD-601","on",None),
            "devices":[
                {"id":"HOLD-601","label":"Bench Test Beacon",
                 "capabilities":["Switch"],"currentStates":{"switch":"off"}}],
            "after_command":{"HOLD-601":{"switch":"off"}},
            "events":{"HOLD-601":{"switch":[
                ev("off","2026-11-12T13:00:00Z")]}},
            "apps":{},
            "checks":[
                {"label":"Beacon identity","leaf":"hub_list_devices","id":"HOLD-601"},
                {"label":"Exactly one authorised simulated ON","leaf":"hub_call_device_command",
                 "id":"HOLD-601"},
                {"label":"Fresh switch state after command","leaf":"fresh_switch",
                 "id":"HOLD-601"},
                {"label":"Device switch history","leaf":"hub_list_device_events",
                 "id":"HOLD-601"}],
        },
    ]


class ExperimentalAgent(BoundedAgent):
    """Single isolated model-input difference; production Agent stays unchanged."""
    def __init__(self, configured: Agent, *, candidate: bool):
        super().__init__(configured)
        self.candidate=candidate

    async def round(self,messages:list[dict],tools:list[dict],remaining:float)->dict:
        if not self.candidate:
            return await super().round(messages,tools,remaining)
        # Preserve the same role sequence, tool schemas and messages. Only the
        # additional general candidate text differs in the first system turn.
        amended=list(messages)
        if not amended or amended[0].get("role")!="system":
            raise RuntimeError("Unexpected agent system-message structure")
        amended[0]={**amended[0],
                    "content":amended[0]["content"]+"\n\n"+CANDIDATE_GUIDANCE}
        return await super().round(amended,tools,remaining)


def tool_metrics(result:dict,fake:SyntheticMCP,scenario:dict)->dict:
    receipts=(result.get("tool_calls") or [])[:MAX_TOOL_ATTEMPTS]
    contract_errors=sum(x.get("result_kind")=="contract_error" for x in receipts)
    other_call_failures=sum(not x.get("success") and
                            x.get("result_kind")!="contract_error" for x in receipts)
    return {
        "success":bool(result.get("success")),
        "answer":str(result.get("answer") or "")[:250000],
        "failure_type":result.get("error") if not result.get("success") else None,
        "rounds":result.get("rounds"),
        "elapsed_ms":result.get("elapsed_ms"),
        "tool_calls":receipts,
        "coverage":_check_coverage(scenario,fake.calls),
        "client_contract_errors":contract_errors,
        "other_failed_calls":other_call_failures,
        "simulator_rejections":fake.blocked_attempts,
        "blocked_reasons":{code:sum(x.get("reason_code")==code for x in fake.calls)
            for code in sorted({x["reason_code"] for x in fake.calls if x.get("reason_code")})},
        "simulated_commands":len(fake.simulated_writes),
        "live_mcp_calls":0,
        "live_device_actions":0,
    }


class ReasoningExperiment:
    def __init__(self,root:Path):
        self.root=Path(root)
        self.catalog={x["id"]:x for x in holdout_scenarios()}

    def _manifest_path(self,sid:str)->Path:
        return self.root/f"{sid}-allocation.json"

    def _answer_path(self,sid:str,label:str)->Path:
        return self.root/f"{sid}-{label}-answer.json"

    def _ratings_path(self,sid:str)->Path:
        return self.root/f"{sid}-ratings.json"

    def _failed_path(self,sid:str,label:str,attempt:int)->Path:
        return self.root/f"{sid}-{label}-failed-{attempt:02d}.json"

    def _attempts(self,sid:str,label:str)->list[Path]:
        return [p for i in range(1,MAX_FAILED_RETRIES+1)
                if (p:=self._failed_path(sid,label,i)).exists()]

    def _allocation(self,sid:str)->dict[str,str]:
        if sid not in self.catalog:
            raise ValueError("Unknown fictional holdout case")
        path=self._manifest_path(sid)
        if path.exists():
            mapping=json.loads(path.read_text(encoding="utf-8"))
            if set(mapping)=={"A","B"} and set(mapping.values())=={"baseline","candidate"}:
                return mapping
            raise ValueError("Invalid private condition allocation; no new model runs authorised")
        # Randomised *and counterbalanced*: across six cases, candidate is
        # assigned A three times and B three times. This reduces order/label
        # confounding while keeping the allocation private. Cases are started
        # one at a time by the API; existing assignments are immutable.
        earlier=[]
        for other in self.catalog:
            other_path=self._manifest_path(other)
            if other==sid or not other_path.is_file():
                continue
            row=json.loads(other_path.read_text(encoding="utf-8"))
            if set(row)!={"A","B"} or set(row.values())!={"baseline","candidate"}:
                raise ValueError("Invalid previous private allocation")
            earlier.append(row)
        max_first=(len(self.catalog)+1)//2
        max_second=len(self.catalog)//2
        candidate_a=sum(row["A"]=="candidate" for row in earlier)
        candidate_b=sum(row["B"]=="candidate" for row in earlier)
        if candidate_a>=max_first:
            first=False
        elif candidate_b>=max_second:
            first=True
        else:
            first=bool(secrets.randbits(1))
        mapping=({"A":"candidate","B":"baseline"} if first
                 else {"A":"baseline","B":"candidate"})
        _private_write(path,json.dumps(mapping))
        return mapping

    def summary(self,progress:dict|None=None)->dict:
        status=progress or {}
        cases=[]
        for sid,c in self.catalog.items():
            arm_status={}
            for label in ("A","B"):
                path=self._answer_path(sid,label)
                if path.is_file():
                    raw=json.loads(path.read_text(encoding="utf-8"))
                    arm_status[label]="completed" if raw.get("success") else "failed"
                else:
                    arm_status[label]="not_run"
            cases.append({
                "id":sid,"title":c["title"],"domain":c["domain"],
                "arms":arm_status,
                "ready_to_rate":all(x=="completed" for x in arm_status.values()),
                "graded":self._ratings_path(sid).exists(),
            })
        return {"schema":"homebrain-v2-reasoning-holdout-status.v1",
                "synthetic_only":True,"running":bool(status.get("running")),
                "error":status.get("error"),
                "progress":{k:v for k,v in status.items() if k in ("case_id","arm")},
                "cases":cases}

    def case(self,sid:str)->dict:
        if sid not in self.catalog:
            raise ValueError("Unknown fictional holdout case")
        scenario=self.catalog[sid]
        result={"id":sid,"title":scenario["title"],"domain":scenario["domain"],
                "question":scenario["question"],"synthetic_only":True,"arms":{},
                "ratings":None}
        for label in ("A","B"):
            path=self._answer_path(sid,label)
            if path.exists():
                raw=json.loads(path.read_text(encoding="utf-8"))
                result["arms"][label]={k:v for k,v in raw.items()
                    if k not in ("condition","hidden_condition","mapping")}
                result["arms"][label]["previous_failed_attempts"]=len(self._attempts(sid,label))
        if self._ratings_path(sid).exists():
            result["ratings"]=json.loads(self._ratings_path(sid).read_text(encoding="utf-8"))
        return result

    def can_run(self,sid:str,retry_failed:bool=False)->None:
        if sid not in self.catalog:
            raise ValueError("Unknown fictional holdout case")
        if self._ratings_path(sid).exists():
            raise ValueError("Rated pairs cannot be run again")
        states=[]
        for label in ("A","B"):
            path=self._answer_path(sid,label)
            if not path.exists():
                states.append("missing")
                continue
            raw=json.loads(path.read_text(encoding="utf-8"))
            if raw.get("success"):
                states.append("completed")
            else:
                if not retry_failed:
                    raise ValueError("A failed arm needs an explicitly consented retry")
                if len(self._attempts(sid,label))>=MAX_FAILED_RETRIES:
                    raise ValueError("Retry limit reached for an arm; clear synthetic data explicitly")
                states.append("failed")
        if all(x=="completed" for x in states):
            raise ValueError("Both arms already completed; score without rerunning")
        if retry_failed and "failed" not in states:
            raise ValueError("There is no failed arm to retry")

    async def run_pair(self,sid:str,configured_model:Agent,*,retry_failed:bool=False,
                       progress:dict|None=None)->None:
        self.can_run(sid,retry_failed)
        scenario=self.catalog[sid]
        mapping=self._allocation(sid)
        for label in ("A","B"):
            path=self._answer_path(sid,label)
            if path.exists():
                existing=json.loads(path.read_text(encoding="utf-8"))
                if existing.get("success"):
                    continue
                attempts=self._attempts(sid,label)
                slot=self._failed_path(sid,label,len(attempts)+1)
                os.replace(path,slot)
            if progress is not None:
                progress["arm"]=label
            # Fresh, independent synthetic tools and default agent history.
            synthetic=SyntheticMCP(scenario)
            agent=ExperimentalAgent(configured_model,
                                    candidate=mapping[label]=="candidate")
            # This blinded two-arm study measures the pre-existing guidance
            # contrast. Keep its historical one-completion-per-arm protocol;
            # alpha.44's extra source-review round belongs to normal Ask.
            # Both arms use the identical opt-out, so condition isolation holds.
            result=await agent.answer(SANDBOX_NOTICE+scenario["question"],[],
                                      synthetic,SANDBOX_DEADLINE_SECONDS,
                                      enable_source_review=False)
            payload=tool_metrics(result,synthetic,scenario)
            payload["id"]=sid
            payload["label"]=label
            _private_write(path,json.dumps(payload,ensure_ascii=False))
            if not result.get("success"):
                break

    @staticmethod
    def _validate_ratings(scores:dict)->None:
        if (not isinstance(scores,dict) or set(scores)!={"A","B"} or
            any(not isinstance(score,dict) or set(score)!=set(CRITERIA) or
                any((type(value) is not int or value not in (0,1,2))
                    and value!="n/a" for value in score.values())
                for score in scores.values())):
            raise ValueError("Rate both blinded arms in all five categories (0/1/2/n/a)")

    def score(self,sid:str,scores:dict)->None:
        if sid not in self.catalog:
            raise ValueError("Unknown fictional holdout case")
        # Blind ratings must be immutable once saved. Otherwise a reviewer
        # could change earlier scores after the final report unmasks A/B,
        # silently invalidating the prospective comparison.
        if self._ratings_path(sid).exists():
            raise ValueError("Blind ratings already saved; this case is locked")
        if not all(self._answer_path(sid,label).exists() and
                   json.loads(self._answer_path(sid,label).read_text(encoding="utf-8")).get("success")
                   for label in ("A","B")):
            raise ValueError("Both arms must finish successfully before blind rating")
        self._validate_ratings(scores)
        _private_write(self._ratings_path(sid),json.dumps(scores))

    def report(self)->dict:
        rows=[]
        for sid,case in self.catalog.items():
            arms={}
            for label in ("A","B"):
                path=self._answer_path(sid,label)
                if not path.exists():
                    continue
                data=json.loads(path.read_text(encoding="utf-8"))
                checks=data.get("coverage") or []
                arms[label]={
                    "completed":bool(data.get("success")),
                    "rounds":data.get("rounds"),
                    "elapsed_ms":data.get("elapsed_ms"),
                    "tool_attempts":len(data.get("tool_calls") or []),
                    "retrieved":sum(x.get("observed") is True for x in checks),
                    "required":len(checks),
                    "client_contract_errors":data.get("client_contract_errors",0),
                    "simulator_rejections":data.get("simulator_rejections",0),
                    "simulated_commands":data.get("simulated_commands",0),
                    "previous_failed_attempts":len(self._attempts(sid,label)),
                }
            ratings=(json.loads(self._ratings_path(sid).read_text(encoding="utf-8"))
                     if self._ratings_path(sid).is_file() else None)
            rows.append({"id":sid,"domain":case["domain"],
                         "arms":arms,"ratings":ratings})
        complete=all(row["ratings"] is not None and
                     all(row["arms"].get(label,{}).get("completed") for label in ("A","B"))
                     for row in rows)
        report={
            "schema":"homebrain-v2-reasoning-holdout-report.v1",
            "synthetic_only":True,
            "model_requested_pairs":sum(bool(x["arms"]) for x in rows),
            "paired_answers_completed":sum(
                all(x["arms"].get(label,{}).get("completed") for label in ("A","B"))
                for x in rows),
            "paired_blind_ratings":sum(x["ratings"] is not None for x in rows),
            "cases_prepared":len(self.catalog),
            "live_mcp_calls":0,"live_device_actions":0,
            "condition_mapping_revealed":complete,
            "cases":rows,
            "limitations":("Exploratory paired synthetic first answers, same model and "
                           "separate identical fictional MCP fixtures. Manual ratings "
                           "are not independent external assessments; source retrieval "
                           "does not establish causal correctness or live reliability."),
        }
        if complete:
            conditions=[]
            for row in rows:
                allocation=self._allocation(row["id"])
                score=row["ratings"]
                differences={}
                for criterion in CRITERIA:
                    a=next((label for label in ("A","B")
                            if allocation[label]=="candidate"))
                    b="B" if a=="A" else "A"
                    av=score[a][criterion]
                    bv=score[b][criterion]
                    if type(av) is int and type(bv) is int:
                        differences[criterion]=av-bv
                    else:
                        differences[criterion]=None
                conditions.append({"id":row["id"],
                                   "candidate_label":a,"baseline_label":b,
                                   "score_difference_candidate_minus_baseline":differences})
            effects={}
            for criterion in CRITERIA:
                nums=[v["score_difference_candidate_minus_baseline"][criterion]
                      for v in conditions
                      if v["score_difference_candidate_minus_baseline"][criterion] is not None]
                effects[criterion]={
                    "compared_pairs":len(nums),
                    "mean_candidate_minus_baseline":sum(nums)/len(nums) if nums else None,
                    "candidate_better":sum(v>0 for v in nums),
                    "baseline_better":sum(v<0 for v in nums),
                    "ties":sum(v==0 for v in nums),
                }
            report["unblinded_conditions"]=conditions
            report["criterion_effects"]=effects
        return report

    def delete(self)->None:
        for sid in self.catalog:
            self._manifest_path(sid).unlink(missing_ok=True)
            self._ratings_path(sid).unlink(missing_ok=True)
            for label in ("A","B"):
                self._answer_path(sid,label).unlink(missing_ok=True)
                for p in self._attempts(sid,label):
                    p.unlink(missing_ok=True)
