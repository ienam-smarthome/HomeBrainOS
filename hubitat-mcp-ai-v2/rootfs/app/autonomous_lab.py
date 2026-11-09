"""Isolated autonomous-first-answer evaluation with synthetic native-shaped MCP.

The *real* v2 Agent.answer loop selects tools. Tools are served exclusively by
SyntheticMCP in memory. No Hubitat endpoint, HA endpoint, network address,
real device ID, user source, repo credential or external MCP client exists here.
Even allowed command simulations update only an in-memory fixture.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from agent import Agent
from benchmark import _private_write
from mcp import MCPError

CRITERIA = ("factual_grounding", "source_completeness", "causal_calibration",
            "command_outcome", "usefulness")
MAX_MODEL_ROUNDS = 8
MAX_TOOL_ATTEMPTS = 24
SANDBOX_DEADLINE_SECONDS = 90

def ev(value, at, *, produced_by="SIMULATED_DEVICE", triggered=None):
    return {"name": "synthetic", "value": str(value), "date": at,
            "isStateChange": True, "producedBy": {"name": produced_by},
            "triggered": triggered or []}


def scenario_definitions() -> list[dict]:
    """Fictional scenarios deliberately distinct from the private A/B cases."""
    return [
        {
            "id": "lab-01", "title": "Verified dimmer command",
            "domain": "device_command", "allow_command": ("LAB-101", "setLevel", 40),
            "question": ("In this synthetic evaluation sandbox, set Bench Study Lamp to "
                         "40% brightness. Independently read both the level and switch "
                         "state after the command. Only report success for the "
                         "hub-reported requested state, not independently verified photons."),
            "devices": [{"id":"LAB-101","label":"Bench Study Lamp","capabilities":["Switch","SwitchLevel"],
                         "currentStates":{"level":"15","switch":"off"}}],
            "events": {}, "apps": {}, "command_history": {},
            "after_command": {"LAB-101":{"level":"40","switch":"on"}},
            "checks": [
                {"label":"Target device resolved","leaf":"hub_list_devices","id":"LAB-101"},
                {"label":"Simulated setLevel command","leaf":"hub_call_device_command","id":"LAB-101"},
                {"label":"Fresh brightness read after command","leaf":"fresh_level","id":"LAB-101"},
                {"label":"Fresh switch read after command","leaf":"fresh_switch","id":"LAB-101"},
            ],
        },
        {
            "id":"lab-02","title":"Accepted command, outcome unconfirmed",
            "domain":"device_command","allow_command":("LAB-201","on",None),
            "question": ("In this synthetic evaluation sandbox, turn ON Bench Workshop Fan, "
                         "then independently read its switch state. If the read still "
                         "says off, investigate without repeating the ON command. "
                         "Distinguish accepted command from achieved device state."),
            "devices":[{"id":"LAB-201","label":"Bench Workshop Fan","capabilities":["Switch"],
                        "currentStates":{"switch":"off"}}],
            "events":{"LAB-201":{"switch":[
                ev("off","2026-11-10T09:00:00Z")
            ]}},
            "apps":{},"after_command":{"LAB-201":{"switch":"off"}},
            "checks":[
                {"label":"Target device resolved","leaf":"hub_list_devices","id":"LAB-201"},
                {"label":"Simulated ON command","leaf":"hub_call_device_command","id":"LAB-201"},
                {"label":"Fresh switch read after command","leaf":"fresh_switch","id":"LAB-201"},
                {"label":"Historical switch events checked","leaf":"hub_list_device_events","id":"LAB-201"},
            ],
        },
        {
            "id":"lab-03","title":"Historical demand vs current snapshot",
            "domain":"heating","allow_command":None,
            "question": ("Investigate why Bench Boiler reported heating at 09:10 although "
                         "the zone valves now appear idle. Check historical operating-state "
                         "events for ALL three zone thermostats and historical main "
                         "setpoint. Do not infer past demand from the current snapshot. "
                         "State what remains unknown. Do not change anything."),
            "devices":[
                {"id":"LAB-301","label":"Bench Boiler","capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle","heatingSetpoint":"12","temperature":"21"}},
                {"id":"LAB-302","label":"Bench Zone East","capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle","heatingSetpoint":"21"}},
                {"id":"LAB-303","label":"Bench Zone West","capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle","heatingSetpoint":"21"}},
                {"id":"LAB-304","label":"Bench Zone Attic","capabilities":["Thermostat"],
                 "currentStates":{"thermostatOperatingState":"idle","heatingSetpoint":"21"}},
            ],
            "events":{
                "LAB-301":{
                    "thermostatOperatingState":[ev("idle","2026-11-10T09:34:00Z"),
                        ev("heating","2026-11-10T09:10:00Z")],
                    "heatingSetpoint":[ev("12","2026-11-10T09:33:45Z"),
                        ev("25","2026-11-10T09:09:40Z")]},
                "LAB-302":{"thermostatOperatingState":[
                    ev("idle","2026-11-10T09:23:00Z"),ev("heating","2026-11-10T09:09:55Z")]},
                "LAB-303":{"thermostatOperatingState":[
                    ev("idle","2026-11-10T09:30:00Z"),ev("heating","2026-11-10T09:10:06Z")]},
                "LAB-304":{"thermostatOperatingState":[]},
            },
            "apps":{},
            "checks":[
                {"label":"Main thermostat historical state","leaf":"hub_list_device_events","id":"LAB-301","attribute":"thermostatOperatingState"},
                {"label":"Main thermostat historical setpoint","leaf":"hub_list_device_events","id":"LAB-301","attribute":"heatingSetpoint"},
                {"label":"East zone historical state","leaf":"hub_list_device_events","id":"LAB-302"},
                {"label":"West zone historical state","leaf":"hub_list_device_events","id":"LAB-303"},
                {"label":"Attic zone checked despite missing history","leaf":"hub_list_device_events","id":"LAB-304"},
            ],
        },
        {
            "id":"lab-04","title":"Schedule coincidence vs causal proof",
            "domain":"ventilation","allow_command":None,
            "question": ("Why did Bench Air Extractor turn on near 12:00? Compare recorded "
                         "command issuer, returned humidity readings and automation "
                         "schedule. Explain whether the exact internal cause is proven. "
                         "Do not change anything."),
            "devices":[
                {"id":"LAB-401","label":"Bench Air Extractor","capabilities":["Switch"],
                 "currentStates":{"switch":"off"}},
                {"id":"LAB-402","label":"Bench Humidity Gauge","capabilities":["RelativeHumidityMeasurement"],
                 "currentStates":{"humidity":"48"}},
            ],
            "events":{
                "LAB-401":{"switch":[
                    ev("off","2026-11-10T12:20:00Z",produced_by="Test Bridge"),
                    ev("on","2026-11-10T12:00:00Z",produced_by="Test Bridge",
                       triggered=[{"name":"Bench Airflow Rule","appId":"LAB-APP-401","handler":"eventHandler"}])]},
                "LAB-402":{"humidity":[
                    ev("48","2026-11-10T12:20:00Z"),ev("51","2026-11-10T11:40:00Z")]}
            },
            "command_history":{"LAB-401":[
                {"command":"on","date":"2026-11-10T11:59:59.900Z",
                 "issuer":"Bench Airflow Rule","appId":"LAB-APP-401"},
                {"command":"off","date":"2026-11-10T12:19:59.900Z",
                 "issuer":"Bench Airflow Rule","appId":"LAB-APP-401"}
            ]},
            "apps":{"LAB-APP-401":{
                "name":"Bench Airflow Rule","scheduled_enabled":True,
                "scheduled_times":["08:00","12:00","18:00"],"duration_minutes":20,
                "humidity_threshold_percent":65,
                "internal_trigger_execution_logs":"not provided",
                "configuration_observed_at":"2026-11-10T13:00:00Z"
            }},
            "checks":[
                {"label":"Extractor switch events","leaf":"hub_list_device_events","id":"LAB-401"},
                {"label":"Command issuer history","leaf":"hub_get_device_command_history","id":"LAB-401"},
                {"label":"Automation schedule and threshold","leaf":"hub_get_app_config","id":"LAB-APP-401"},
                {"label":"Humidity history and reporting gaps","leaf":"hub_list_device_events","id":"LAB-402"},
            ],
        },
        {
            "id":"lab-05","title":"Stale sensor vs verified outage",
            "domain":"telemetry","allow_command":None,
            "question": ("Investigate the last reported activity of Bench Cellar Sensor. "
                         "Distinguish stale telemetry from proven device outage or MQTT "
                         "session failure. Check the device health, relevant events "
                         "and logs. State limitations of paginated logs and whether "
                         "other stale devices establish a common cause. Read only."),
            "devices":[
                {"id":"LAB-501","label":"Bench Cellar Sensor","capabilities":["TemperatureMeasurement"],
                 "lastActivity":"2026-11-09T09:00:00Z",
                 "currentStates":{"temperature":"17"}},
                {"id":"LAB-502","label":"Bench Roof Sensor MQTT","capabilities":["TemperatureMeasurement"],
                 "lastActivity":"2026-11-09T04:00:00Z",
                 "currentStates":{"temperature":"11"}},
            ],
            "events":{"LAB-501":{"temperature":[ev("17","2026-11-09T09:00:00Z")]}},
            "health":{"checked_at":"2026-11-10T12:00:00Z","stale_threshold_hours":24,
                      "devices":[{"deviceId":"LAB-501","status":"stale",
                                  "lastActivity":"2026-11-09T09:00:00Z"},
                                 {"deviceId":"LAB-502","status":"stale",
                                  "lastActivity":"2026-11-09T04:00:00Z"}]},
            "logs":{"entries":[{"timestamp":"2026-11-10T11:50:00Z",
                                "message":"Routine synthetic hub diagnostics; no relevant device exception"}],
                    "count":1,"total":7840,"limit":25,"offset":0,"complete":False},
            "apps":{},
            "checks":[
                {"label":"Device health classification","leaf":"hub_get_device_health"},
                {"label":"Cellar's device event history","leaf":"hub_list_device_events","id":"LAB-501"},
                {"label":"Hub log coverage inspected","leaf":"hub_get_logs"},
            ],
        },
        {
            "id":"lab-06","title":"Event reporter vs command issuer",
            "domain":"causal_attribution","allow_command":None,
            "question": ("Determine who caused Bench Corridor Lamp to turn OFF at 18:42. "
                         "Distinguish a bridge reporting the state, downstream apps "
                         "listed as triggered listeners, and actual command issuers. "
                         "If no command evidence is available, report cause unverified. "
                         "Read only."),
            "devices":[
                {"id":"LAB-601","label":"Bench Corridor Lamp","capabilities":["Switch","SwitchLevel"],
                 "currentStates":{"switch":"off","level":"55"}},
            ],
            "events":{"LAB-601":{"switch":[
                ev("off","2026-11-10T18:42:00Z",produced_by="Synthetic Lighting Bridge",
                   triggered=[{"name":"Bench Scene Listener","appId":"LAB-APP-601",
                               "handler":"switchHandler"}]),
                ev("on","2026-11-10T18:22:00Z",produced_by="Synthetic Lighting Bridge")]}},
            "command_history":{"LAB-601":[]},
            "apps":{"LAB-APP-601":{"name":"Bench Scene Listener",
                                   "event_subscription":"switch",
                                   "action":"records a change; does not originate this event"}},
            "checks":[
                {"label":"Lamp switch events","leaf":"hub_list_device_events","id":"LAB-601"},
                {"label":"Command issuer history","leaf":"hub_get_device_command_history","id":"LAB-601"},
            ],
        }
    ]


def _leaf_def(name: str) -> dict:
    properties = {
        "hub_list_devices":{"labelFilter":{"type":"string"}},
        "hub_get_device":{"deviceId":{"type":"string"}},
        "hub_get_device_attribute":{"deviceId":{"type":"string"},"attribute":{"type":"string"}},
        "hub_list_device_events":{"deviceId":{"type":"string"},"attribute":{"type":"string"},"limit":{"type":"integer"},"since":{"type":"string"},"until":{"type":"string"}},
        "hub_get_device_command_history":{"deviceId":{"type":"string"}},
        "hub_get_device_health":{},
        "hub_get_logs":{"limit":{"type":"integer"},"query":{"type":"string"}},
        "hub_get_app_config":{"appId":{"type":"string"}},
        "hub_call_device_command":{"deviceId":{"type":"string"},"command":{"type":"string"},
                                   "params":{"type":"array","items":{"type":["integer","number","string"]}}},
    }[name]
    return {"name":name,
            "description": {
                "hub_list_devices":"Find devices by label and return their current states. Current states are not historical.",
                "hub_get_device":"Read current states of one identified device.",
                "hub_get_device_attribute":"Read a named current attribute from one device.",
                "hub_list_device_events":"Read bounded historical events for one device and optionally one attribute.",
                "hub_get_device_command_history":"Read the stored command-issuer history, if any. Missing records do not prove no command happened.",
                "hub_get_device_health":"Read current hub stale-activity classification, not physical reachability.",
                "hub_get_logs":"Read one limited recent log page, not an exhaustive historical search.",
                "hub_get_app_config":"Read a current automation configuration snapshot, not its internal past decision.",
                "hub_call_device_command":"SYNTHETIC ONLY: simulate a sandbox device command. Never reaches a hub; execute at most once.",
            }[name],
            "inputSchema":{"type":"object","properties":properties,
                           "required": ["deviceId"] if name in (
                               "hub_get_device","hub_get_device_command_history") else
                           (["deviceId","attribute"] if name=="hub_get_device_attribute" else
                            ["deviceId","command"] if name=="hub_call_device_command" else
                            ["deviceId"] if name=="hub_list_device_events" else
                            ["appId"] if name=="hub_get_app_config" else []),
                           "additionalProperties":False},
    }


GATEWAYS = {
    "hub_read_devices": ("hub_list_devices","hub_get_device",
                         "hub_get_device_attribute","hub_get_device_health"),
    "hub_read_history": ("hub_list_device_events","hub_get_device_command_history",
                         "hub_get_logs"),
    "hub_read_apps": ("hub_get_app_config",),
    "hub_manage_devices": ("hub_call_device_command",),
}


def _native(payload: dict, *, error: bool = False) -> dict:
    return {"isError":error, "content":[{"type":"text","text":json.dumps(payload,
             ensure_ascii=False, separators=(",", ":"))}]}


class SyntheticMCP:
    """Fail-closed native-shaped MCP adapter, never instantiates MCPClient."""
    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.devices = {d["id"]:json.loads(json.dumps(d)) for d in scenario["devices"]}
        self.calls: list[dict] = []
        self.simulated_writes: list[dict] = []
        self.blocked_attempts = 0

    async def list_tools(self, refresh: bool = False) -> list[dict]:
        return [
            {"name":name,"description": "Synthetic sandbox gateway: "+
                 ("simulated device control" if name=="hub_manage_devices" else "read-only")+
                 ". Call with {} to discover leaf schemas or with top-level tool and args.",
             "inputSchema":{"type":"object","properties":{
                 "tool":{"type":"string","enum":list(names)},
                 "args":{"type":"object","description":"Leaf-specific arguments"}
             },"additionalProperties":False}}
            for name,names in GATEWAYS.items()
        ]

    async def call(self, name: str, arguments: dict) -> dict:
        if len(self.calls) >= MAX_TOOL_ATTEMPTS:
            self.blocked_attempts += 1
            return _native({"error":"Synthetic tool-attempt limit reached"},error=True)
        if name not in GATEWAYS or not isinstance(arguments,dict):
            self.blocked_attempts += 1
            self.calls.append({"leaf":"invalid","success":False})
            return _native({"error":"No such sandbox tool"},error=True)
        if not arguments:
            self.calls.append({"leaf":"catalog","success":True})
            return _native({"mode":"catalog","gateway":name,
                            "tools":[_leaf_def(x) for x in GATEWAYS[name]]})
        leaf=arguments.get("tool")
        args=arguments.get("args",{})
        if (leaf not in GATEWAYS[name] or set(arguments)!={"tool","args"}
                or not isinstance(args,dict)):
            self.blocked_attempts+=1
            self.calls.append({"leaf":"invalid","success":False})
            return _native({"error":"Invalid gateway/leaf shape"},error=True)
        # This validation is ONLY for the synthetic tool schema; it is never
        # applied to live MCP sources or to production Agent.
        spec=_leaf_def(leaf)["inputSchema"]
        if (set(args)-set(spec["properties"]) or any(k not in args for k in spec["required"])
                or any(not isinstance(args[k],str)
                       for k in ("deviceId","attribute","appId","command") if k in args)):
            self.blocked_attempts+=1
            self.calls.append({"leaf":leaf,"success":False})
            return _native({"error":"Malformed synthetic leaf arguments"},error=True)
        did=str(args.get("deviceId") or args.get("appId") or "")
        if leaf=="hub_call_device_command":
            allowed=self.scenario.get("allow_command")
            params=args.get("params",[])
            candidate_value=(params[0] if params else None)
            if (not allowed or did!=allowed[0] or args["command"]!=allowed[1]
                    or allowed[2]!=candidate_value or self.simulated_writes):
                self.blocked_attempts+=1
                self.calls.append({"leaf":leaf,"id":did,"success":False,"simulated":True})
                return _native({"error":"Synthetic sandbox command prohibited or duplicate"},
                               error=True)
            self.simulated_writes.append({"deviceId":did,"command":args["command"]})
            # The command response intentionally carries a *stale* snapshot;
            # the new current state is exposed only through subsequent reads.
            prior=json.loads(json.dumps(self.devices[did]["currentStates"]))
            self.devices[did]["currentStates"].update(self.scenario["after_command"][did])
            result={"success":True,"accepted":True,"deviceId":did,"command":args["command"],
                    "command_response_snapshot_not_fresh":prior,
                    "physical_outcome":"not independently measured"}
        elif leaf=="hub_list_devices":
            filt=str(args.get("labelFilter") or "").casefold()
            matches=[d for d in self.devices.values() if filt in d["label"].casefold()]
            result={"devices":matches,"count":len(matches),"total":len(self.devices)}
        elif leaf=="hub_get_device":
            result=self.devices.get(did) or {"error":"Unknown synthetic device"}
        elif leaf=="hub_get_device_attribute":
            item=self.devices.get(did)
            result={"deviceId":did,"attribute":args["attribute"],
                    "value":item.get("currentStates",{}).get(args["attribute"]) if item else None,
                    "read_at":"synthetic fresh read","source":"current synthetic hub attribute"}
        elif leaf=="hub_list_device_events":
            events=self.scenario.get("events",{}).get(did,{})
            attr=args.get("attribute")
            selected=events.get(attr,[]) if attr else [row for seq in events.values() for row in seq]
            limit=max(1,min(200,args.get("limit",50))) if type(args.get("limit",50)) is int else 50
            result={"source":"device","deviceId":did,"attributeFilter":attr,
                    "events":selected[:limit],"count":len(selected[:limit]),
                    "requested_limit":limit,"source_scope":"returned event rows only",
                    "history_complete":"unknown"}
        elif leaf=="hub_get_device_command_history":
            rows=self.scenario.get("command_history",{}).get(did,[])
            result={"deviceId":did,"commands":rows,"count":len(rows),
                    "coverage":"synthetic bounded records; missing command unverified"}
        elif leaf=="hub_get_app_config":
            result=self.scenario.get("apps",{}).get(did,{"error":"No matching app"})
        elif leaf=="hub_get_device_health":
            result=self.scenario.get("health",{"status":"not included in this scenario"})
        elif leaf=="hub_get_logs":
            result=self.scenario.get("logs",{"entries":[],"count":0,"total":0,
                                             "coverage":"no matching logs supplied"})
        else:
            self.blocked_attempts+=1
            return _native({"error":"Unknown synthetic tool"},error=True)
        self.calls.append({"leaf":leaf,"id":did,"attribute":args.get("attribute"),
                           "returned_ids":[d["id"] for d in matches] if leaf=="hub_list_devices" else [],
                           "success":True,"simulated":leaf=="hub_call_device_command"})
        return _native(result)


class BoundedAgent(Agent):
    """Use unmodified Agent.answer and native-shaped tools, cap cloud rounds."""
    def __init__(self, configured: Agent):
        self.base_url = configured.base_url
        self.model = configured.model
        self.timeout = min(60, configured.timeout)
        self.client = configured.client
        self.model_rounds = 0

    async def round(self, messages: list[dict], tools: list[dict], remaining: float) -> dict:
        if self.model_rounds >= MAX_MODEL_ROUNDS:
            raise RuntimeError("Autonomous lab model-round safety limit reached")
        self.model_rounds += 1
        return await super().round(messages,tools,min(remaining,60))


def _check_coverage(scenario: dict, calls: list[dict]) -> list[dict]:
    checks=[]
    for requirement in scenario["checks"]:
        leaf=requirement["leaf"]
        did=requirement.get("id")
        matching=False
        for position,call in enumerate(calls):
            if not call.get("success"):
                continue
            if leaf in ("fresh_level","fresh_switch"):
                command_positions=[j for j,c in enumerate(calls) if c.get("leaf")==
                    "hub_call_device_command" and c.get("success") and c.get("id")==did]
                if not command_positions or position<=command_positions[0]:
                    continue
                attr=leaf.removeprefix("fresh_")
                matching=(call.get("id")==did and (
                    call.get("leaf")=="hub_get_device" or
                    call.get("leaf")=="hub_get_device_attribute" and
                    call.get("attribute")==attr))
            else:
                matching=(call.get("leaf")==leaf and
                          (did is None or call.get("id")==did or
                           leaf=="hub_list_devices" and did in call.get("returned_ids",[])) and
                          (requirement.get("attribute") is None or
                           call.get("attribute")==requirement["attribute"]))
            if matching:
                break
        checks.append({"label":requirement["label"],"observed":bool(matching)})
    return checks


class AutonomousLab:
    def __init__(self,root: Path):
        self.root=Path(root)
        self.catalog={case["id"]:case for case in scenario_definitions()}

    def summary(self,progress:dict | None=None) -> dict:
        state=progress or {}
        return {"version":"synthetic-autonomous-first-answer.v1",
                "synthetic_only":True,"running":bool(state.get("running")),
                "error":state.get("error"),
                "progress":{k:v for k,v in state.items()
                            if k in ("case_id","started","rounds")},
                "cases":[{
                    "id":sid,"title":case["title"],"domain":case["domain"],
                    "answered":self._answer_path(sid).is_file(),
                    "graded":self._ratings_path(sid).is_file(),
                } for sid,case in self.catalog.items()]}

    def _answer_path(self,sid:str)->Path:
        return self.root / (sid+"-answer.json")

    def _ratings_path(self,sid:str)->Path:
        return self.root / (sid+"-ratings.json")

    def case(self,sid:str) -> dict:
        if sid not in self.catalog:
            raise ValueError("Unknown synthetic lab case")
        case=self.catalog[sid]
        result={"id":sid,"title":case["title"],"domain":case["domain"],
                "question":case["question"],"synthetic_only":True,
                "answer":None,"ratings":None,"coverage":None}
        if self._answer_path(sid).is_file():
            raw=json.loads(self._answer_path(sid).read_text(encoding="utf-8"))
            result.update({"answer":raw.get("answer"),
                           "success":raw.get("success"),"rounds":raw.get("rounds"),
                           "elapsed_ms":raw.get("elapsed_ms"),
                           "tool_calls":raw.get("tool_calls"),
                           "coverage":raw.get("coverage"),
                           "simulated_commands":raw.get("simulated_commands"),
                           "blocked_attempts":raw.get("blocked_attempts"),
                           "unsafe_live_actions":0})
        if self._ratings_path(sid).is_file():
            result["ratings"]=json.loads(self._ratings_path(sid).read_text(encoding="utf-8"))
        return result

    async def run(self,sid:str,configured_model:Agent) -> None:
        if sid not in self.catalog:
            raise ValueError("Unknown synthetic lab case")
        if self._answer_path(sid).exists():
            raise ValueError("Case already completed; data cannot be overwritten")
        scenario=self.catalog[sid]
        fake=SyntheticMCP(scenario)
        agent=BoundedAgent(configured_model)
        result=await agent.answer(scenario["question"],[],fake,SANDBOX_DEADLINE_SECONDS)
        written={"id":sid,
                 "answer":str(result.get("answer") or "")[:250000],
                 "success":bool(result.get("success")),
                 "rounds":result.get("rounds"),
                 "elapsed_ms":result.get("elapsed_ms"),
                 "tool_calls":result.get("tool_calls",[])[:MAX_TOOL_ATTEMPTS],
                 "coverage":_check_coverage(scenario,fake.calls),
                 "simulated_commands":len(fake.simulated_writes),
                 "blocked_attempts":fake.blocked_attempts,
                 "unsafe_live_actions":0,
                 "model_rounds":agent.model_rounds}
        _private_write(self._answer_path(sid),json.dumps(written,ensure_ascii=False))

    def score(self,sid:str,scores:dict) -> None:
        if sid not in self.catalog or not self._answer_path(sid).is_file():
            raise ValueError("Run this synthetic case before scoring")
        if not isinstance(scores,dict) or set(scores)!=set(CRITERIA) or any(
                type(v) is not int and v!="n/a" or
                type(v) is int and v not in (0,1,2)
                for v in scores.values()):
            raise ValueError("Score all five criteria using 0, 1, 2 or n/a")
        _private_write(self._ratings_path(sid),json.dumps(scores))

    def report(self)->dict:
        summary=self.summary()
        rows=[]
        for row in summary["cases"]:
            path=self._answer_path(row["id"])
            if not path.is_file():
                continue
            raw=json.loads(path.read_text(encoding="utf-8"))
            grade=(json.loads(self._ratings_path(row["id"]).read_text(encoding="utf-8"))
                   if self._ratings_path(row["id"]).is_file() else None)
            coverage=raw.get("coverage") or []
            rows.append({"case":row["id"],"domain":row["domain"],
                         "model_answered":bool(raw.get("success")),
                         "rounds":raw.get("rounds"),
                         "tool_attempts":len(raw.get("tool_calls") or []),
                         "required_evidence_checks":len(coverage),
                         "observed_evidence_checks":sum(bool(x.get("observed")) for x in coverage),
                         "simulated_commands":raw.get("simulated_commands",0),
                         "blocked_attempts":raw.get("blocked_attempts",0),
                         "ratings":grade})
        return {"schema":"homebrain-v2-autonomous-first-answer.v1",
                "synthetic_only":True,"cases_prepared":len(self.catalog),
                "cases_answered":len(rows),
                "cases_graded":sum(r["ratings"] is not None for r in rows),
                "live_mcp_calls":0,"live_device_actions":0,
                "cases":rows,
                "interpretation":("Synthetic model-driven tool selection and first-answer "
                                  "evaluation, not proof of live Hubitat tool reliability, "
                                  "device causation or physical actuation. Evidence-check "
                                  "counts measure retrieved source coverage, not answer correctness.")}

    def delete(self)->None:
        # Whitelist only the six known scenario result files.
        for sid in self.catalog:
            self._answer_path(sid).unlink(missing_ok=True)
            self._ratings_path(sid).unlink(missing_ok=True)
