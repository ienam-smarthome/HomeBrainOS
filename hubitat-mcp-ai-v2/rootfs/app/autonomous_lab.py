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
from mcp import MCPError, _validate_arguments

CRITERIA = ("factual_grounding", "source_completeness", "causal_calibration",
            "command_outcome", "usefulness")
MAX_MODEL_ROUNDS = 12
MAX_TOOL_ATTEMPTS = 40
SANDBOX_DEADLINE_SECONDS = 120

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
                {"label":"Command issuer event history","leaf":"hub_list_device_events","id":"LAB-401","attribute":"command-on"},
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
                {"label":"Command issuer event history","leaf":"hub_list_device_events","id":"LAB-601","attribute":"command-off"},
            ],
        }
    ]


def _leaf_def(name: str) -> dict:
    """Synthetic subset of the native Hubitat MCP Rule Server 5.1.x schemas.

    Native parameter names and gateway placement are used unchanged. Features
    outside the simulator (physical I/O, batch writes, network diagnostics) are
    intentionally not advertised. Models may still attempt an undeclared
    argument; it is rejected and counted, never forwarded.
    """
    names={
        "hub_list_devices": {
            "format":{"type":"string","enum":["summary","detailed","ids","context"]},
            "labelFilter":{"type":"string","description":"Case-insensitive device label substring"},
            "scope":{"type":"string","enum":["authorized","all","owned"]},
            "roomFilter":{"type":"string"},"limit":{"type":"integer","minimum":1},
            "attributeNames":{"type":"array","items":{"type":"string"}}},
        "hub_get_device":{
            "deviceId":{"type":"string"},"mode":{"type":"string",
                "enum":["summary","configuration","details"]}},
        "hub_get_device_attribute":{
            "deviceId":{"type":["string","integer"]},"attribute":{"type":"string"},
            "expectedValue":{"type":"string"}},
        "hub_list_device_events":{
            "deviceId":{"type":["string","integer"]},"attribute":{"type":"string"},
            "limit":{"type":"integer","minimum":1},"since":{"type":"string"},
            "until":{"type":"string"},"hoursBack":{"type":"integer","minimum":1}},
        "hub_get_device_health":{
            "staleHours":{"type":"number","minimum":0},
            "includeHealthy":{"type":"boolean"}},
        "hub_get_logs":{
            "mode":{"type":"string"},"limit":{"type":"integer","minimum":1},
            "deviceId":{"type":["string","integer"]},"pattern":{"type":"string"}},
        "hub_get_app_config":{
            "appId":{"type":"string","description":"Fictional LAB-APP identifier; native uses numeric app ID"}},
        "hub_call_device_command":{
            "deviceId":{"type":["string","integer"]},
            "command":{"type":"string"},
            "parameters":{"type":"array","items":{"type":"string"},
                "description":"Native command arguments, e.g. [\"40\"] for setLevel"},
            "includeState":{"type":"boolean"},
            "waitFor":{"type":"object","properties":{
                "attribute":{"type":"string"},"expectedValue":{"type":"string"}},
                "required":["attribute"],"additionalProperties":False}},
    }
    descriptions={
        "hub_list_devices":"List devices and their current states; filter by label. Current state is not historical.",
        "hub_get_device":"Inspect the current attributes and supported commands of one device.",
        "hub_get_device_attribute":"Read an independently fresh current attribute after any command. Polling is not implemented in this sandbox.",
        "hub_list_device_events":"Return bounded historical device event rows; attribute='command-on/off' reads recorded command issuer events.",
        "hub_get_device_health":"Read stale-activity classification, not proof of network/physical outage.",
        "hub_get_logs":"Read one bounded page of synthetic diagnostic logs, not a complete log archive.",
        "hub_get_app_config":"Read a fictional app configuration snapshot, not an internal decision trace.",
        "hub_call_device_command":"SYNTHETIC MEMORY ONLY. Accept exactly one authorised sandbox command. Native args: deviceId, command, parameters (string array). A successful command response is not a fresh device state read.",
    }
    if name not in names:
        raise ValueError("Unknown synthetic tool")
    required={
        "hub_get_device":["deviceId"],
        "hub_get_device_attribute":["attribute"],
        "hub_list_device_events":["deviceId"],
        "hub_get_app_config":["appId"],
    }.get(name,[])
    # The upstream native command has two wire forms and does not declare
    # JSON Schema required fields; the simulator checks the single-target
    # subset itself, before any in-memory mutation.
    return {"name":name,"description":descriptions[name],
            "inputSchema":{"type":"object","properties":names[name],
                           "required":required,"additionalProperties":False}}


# Gateway names/membership mirror the corresponding native server surfaces.
# Every name not present in an actual native gateway is excluded.
GATEWAYS={
    "hub_read_devices":("hub_list_devices","hub_get_device",
                        "hub_get_device_attribute","hub_list_device_events"),
    "hub_manage_devices":("hub_call_device_command","hub_list_devices",
                          "hub_get_device","hub_get_device_attribute",
                          "hub_list_device_events"),
    "hub_read_diagnostics":("hub_get_device_health","hub_get_logs"),
    "hub_read_apps_code":("hub_get_app_config",),
}


def _native(payload: dict, *, error: bool = False) -> dict:
    return {"isError":error, "content":[{"type":"text","text":json.dumps(payload,
             ensure_ascii=False, separators=(",", ":"))}]}


class SyntheticMCP:
    """Fail-closed native-shaped MCP adapter, never instantiates MCPClient.

    Schema discovery matches the real MCPClient path used by Agent.answer.
    Every 'call' is an in-memory evaluation; no network/hub object is held.
    """
    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.devices = {d["id"]:json.loads(json.dumps(d)) for d in scenario["devices"]}
        self.calls: list[dict] = []
        self.simulated_writes: list[dict] = []
        self.blocked_attempts = 0
        self._gateway_leaf_catalogs: dict[str, dict[str, dict]] = {}
        self._requested_leaves: dict[str, set[str]] = {}

    async def list_tools(self, refresh: bool = False) -> list[dict]:
        # Discovery is a read: preserve successfully inspected leaf schemas.
        return [
            {"name":name,
             "description":("Synthetic MCP " + ("write/read" if name=="hub_manage_devices"
                 else "read-only") + " gateway. "
                 "Call with {} to discover the native leaf argument schemas, or "
                 "with top-level {\"tool\":\"leaf\",\"args\":{...}} to execute. "
                 "Allowed leaves: " + ", ".join(names) +
                 ". All data and commands are in-memory fictional test fixtures."),
             "inputSchema":{"type":"object","properties":{
                 "tool":{"type":"string","enum":list(names),
                         "description":"Top-level leaf selector; omit for catalog discovery"},
                 "args":{"type":"object","description":"Leaf arguments only; no nested tool selector"}
             },"additionalProperties":False}}
            for name,names in GATEWAYS.items()
        ]

    def cached_leaf_schemas(self) -> dict[str, dict[str, dict]]:
        return {gateway:{leaf:self._gateway_leaf_catalogs[gateway][leaf]
                for leaf in selected if leaf in self._gateway_leaf_catalogs[gateway]}
                for gateway,selected in self._requested_leaves.items()
                if gateway in self._gateway_leaf_catalogs}

    async def gateway_leaf_schema(self,gateway:str,leaf:str) -> tuple[dict|None,bool]:
        if gateway not in GATEWAYS or leaf not in GATEWAYS[gateway]:
            return None,False
        fetched=False
        if gateway not in self._gateway_leaf_catalogs:
            # The same read-only discovery that the real MCPClient performs.
            response=await self.call(gateway,{})
            catalog=json.loads(response["content"][0]["text"])
            if catalog.get("mode")!="catalog":
                return None,False
            self._gateway_leaf_catalogs[gateway]={
                item["name"]:item for item in catalog["tools"]}
            fetched=True
        self._requested_leaves.setdefault(gateway,set()).add(leaf)
        return self._gateway_leaf_catalogs[gateway].get(leaf),fetched

    @staticmethod
    def validate_leaf_arguments(definition:dict|None,args:dict)->None:
        if isinstance(definition,dict):
            _validate_arguments(args,definition["inputSchema"])

    def _reject(self,reason:str,leaf:str="invalid",did:str="") -> dict:
        self.blocked_attempts+=1
        self.calls.append({"leaf":leaf,"id":did,"success":False,
                           "reason_code":reason,"simulated":True})
        # Codes carry no model prompt, source data, device detail or credentials.
        return _native({"error":"Synthetic tool was rejected",
                        "reason_code":reason,
                        "hint":{
                            "unknown_tool":"Select a name from the advertised synthetic tools/list",
                            "invalid_gateway_shape":"Use gateway({tool:leaf,args:{...}}) or {} to inspect its catalog",
                            "invalid_leaf_arguments":"Use the leaf's schema; command arguments are 'parameters', not 'params'",
                            "unsupported_command":"The requested command is not authorised in this synthetic scenario",
                            "duplicate_command":"Do not repeat an accepted device command",
                            "tool_budget":"Synthetic call budget was exhausted",
                        }.get(reason,"Inspect the synthetic tool contract")},error=True)

    async def call(self,name:str,arguments:dict)->dict:
        if len(self.calls)>=MAX_TOOL_ATTEMPTS:
            return self._reject("tool_budget")
        if name not in GATEWAYS or not isinstance(arguments,dict):
            return self._reject("unknown_tool")
        if not arguments:
            self.calls.append({"leaf":"catalog","gateway":name,"success":True})
            return _native({"mode":"catalog","gateway":name,
                            "tools":[_leaf_def(leaf) for leaf in GATEWAYS[name]]})
        leaf=arguments.get("tool")
        args=arguments.get("args")
        if (not isinstance(leaf,str) or leaf not in GATEWAYS[name]
                or set(arguments)!={"tool","args"} or not isinstance(args,dict)):
            return self._reject("invalid_gateway_shape")
        try:
            _validate_arguments(args,_leaf_def(leaf)["inputSchema"])
        except (MCPError,ValueError,TypeError):
            return self._reject("invalid_leaf_arguments",leaf)
        did=str(args.get("deviceId") or args.get("appId") or "")
        if leaf=="hub_call_device_command":
            allowed=self.scenario.get("allow_command")
            # Native MCP sends arguments in the 'parameters' string array,
            # not the fabricated 'params' field used by the old simulator.
            parameters=args.get("parameters",[])
            if not isinstance(parameters,list) or any(not isinstance(x,str)
                                                       for x in parameters):
                return self._reject("invalid_leaf_arguments",leaf,did)
            if self.simulated_writes:
                return self._reject("duplicate_command",leaf,did)
            if (not allowed or did!=str(allowed[0])
                    or args.get("command")!=allowed[1]
                    or parameters!=([str(allowed[2])] if allowed[2] is not None else [])):
                return self._reject("unsupported_command",leaf,did)
            if did not in self.devices:
                return self._reject("unsupported_command",leaf,did)
            self.simulated_writes.append({"deviceId":did,
                                          "command":args["command"]})
            previous=json.loads(json.dumps(self.devices[did]["currentStates"]))
            self.devices[did]["currentStates"].update(self.scenario["after_command"][did])
            result={"success":True,"accepted":True,"deviceId":did,
                    "command":args["command"],
                    "state":previous,"command_response_snapshot_not_fresh":True,
                    "physical_outcome":"not independently measured"}
        elif leaf=="hub_list_devices":
            filt=str(args.get("labelFilter") or "").casefold()
            matches=[item for item in self.devices.values()
                     if filt in item["label"].casefold()]
            # Device lookup can be broader than one member. Current states
            # represent only this snapshot, never historical demand.
            result={"devices":matches,"count":len(matches),
                    "total":len(self.devices),"format":args.get("format","summary")}
        elif leaf=="hub_get_device":
            result=self.devices.get(did) or {"error":"Unknown synthetic device"}
        elif leaf=="hub_get_device_attribute":
            item=self.devices.get(did)
            value=(item.get("currentStates",{}).get(args["attribute"]) if item else None)
            result={"deviceId":did,"attribute":args["attribute"],
                    "currentValue":value,"value":value,
                    "read_at":"synthetic fresh read",
                    "source":"current synthetic hub attribute"}
            if "expectedValue" in args:
                result["converged"]=str(value)==args["expectedValue"]
        elif leaf=="hub_list_device_events":
            events=self.scenario.get("events",{}).get(did,{})
            attr=args.get("attribute")
            if isinstance(attr,str) and attr.startswith("command-"):
                # Represent stored command issuer history through the actual
                # native event-history tool, rather than a fictional one.
                selected=[{"name":attr,"date":e["date"],"value":e["command"],
                           "producedBy":{"name":e["issuer"],"appId":e["appId"]}}
                          for e in self.scenario.get("command_history",{}).get(did,[])
                          if "command-"+e["command"]==attr]
            else:
                selected=(events.get(attr,[]) if attr
                          else [row for seq in events.values() for row in seq])
            limit=max(1,min(200,args.get("limit",50))) if type(args.get("limit",50)) is int else 50
            result={"source":"device","deviceId":did,"attributeFilter":attr,
                    "events":selected[:limit],"count":len(selected[:limit]),
                    "requested_limit":limit,"source_scope":"returned event rows only",
                    "history_complete":"unknown"}
        elif leaf=="hub_get_app_config":
            result=self.scenario.get("apps",{}).get(did,{"error":"No matching app"})
        elif leaf=="hub_get_device_health":
            result=self.scenario.get("health",{"status":"not included in this scenario"})
        elif leaf=="hub_get_logs":
            result=self.scenario.get("logs",{"entries":[],"count":0,"total":0,
                                            "coverage":"no matching logs supplied"})
        else:
            return self._reject("unknown_tool",leaf,did)
        self.calls.append({"leaf":leaf,"id":did,"attribute":args.get("attribute"),
                           "returned_ids":[item["id"] for item in matches]
                           if leaf=="hub_list_devices" else [],
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
        # Explicitly tell the MODEL it is testing a fictional MCP environment,
        # including for read-only scenarios. Do not alter the production skill.
        sandbox_prompt = (
            "SYNTHETIC TEST ONLY. This is a fictional isolated MCP server. "
            "Every device, event, ID, app, and command response is simulated. "
            "No real Hubitat or Home Assistant is connected. When authorised "
            "by the following question, a sandbox command modifies ONLY an "
            "in-memory fixture. Treat synthetic observations as evidence for "
            "this test, not claims about a real physical device. "
            "Choose tools yourself and state evidence limits.\\n\\n"
        ) + scenario["question"]
        result=await agent.answer(sandbox_prompt,[],fake,SANDBOX_DEADLINE_SECONDS)
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
