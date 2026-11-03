"""Synthetic tests for offline native delay candidate.

The real ordered action methods and settings/triggers were read. MCP-created execution is UNVERIFIED.
No Hubitat device, backup or model is accessed.
"""
from __future__ import annotations
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import native_rule_delay_candidate as n

NOW = datetime(2026, 11, 3, 10, 0, 7, tzinfo=timezone.utc)
GUIDE = ('I-HAVE-READ-THE-GUIDE-set_rule_reference-c15e90a2 '
         'hub_set_rule(operation:"create",args:{parent_id,name,changes:[...]},confirm:true)')
CONTROL_GUIDE = ('I-HAVE-READ-THE-GUIDE-builtin_app_tools_rules-a73b19cf '
                 'hub_call_rule hub_set_rule_paused')
REQ = n.DelayRequest("6923", "Test Internet Switch", 900)


class Hub:
    def __init__(self, *, corrupt=None, jobs=1, timeout=False,
                 partial=False, start_ok=True, backup_ok=True,
                 have_backup=True, type_found=True, pause_ok=True,
                 list_ok=True, guide=GUIDE, type_namespace="hubitat",
                 summary=None):
        self.calls = []
        self.rules = {}
        self.corrupt = corrupt
        self.jobs = jobs
        self.timeout = timeout
        self.partial = partial
        self.start_ok = start_ok
        self.backup_ok = backup_ok
        self.pause_ok = pause_ok
        self.type_found = type_found
        self.type_namespace = type_namespace
        self.summary = summary
        self.list_ok = list_ok
        self.guide = guide
        self.backups = [{"createTimeOrig": "2026-11-03T03:01:07+0000"}] if have_backup else []
        self.runs = []
        self.paused = []

    def calls_for(self, name):
        return [params for _, tool, params in self.calls if tool == name]

    def __call__(self, gateway, tool, params):
        self.calls.append((gateway, tool, deepcopy(params)))
        if gateway == "hub_get_tool_guide":
            section = params.get("section")
            return {"success": True, "content": (
                CONTROL_GUIDE if section == "builtin_app_tools_rules"
                else self.guide if section == "set_rule_reference" else ""
            )}
        if tool == "hub_list_apps":
            if params["scope"] == "instances":
                return {"apps": [{"id": 169, "name": "Rule Machine", "type": "Rule Machine",
                                  "appTypeId": 18, "user": False, "parentId": None,
                                  "hasChildren": True}]}
            return {"apps": [
                {"id": 19, "name": "Rule Machine Legacy", "system": True,
                 "isBuiltIn": True, "allowNewInstances": False},
                *([{"id": 18, "name": "Rule Machine", "system": True,
                    "namespace": self.type_namespace,
                    "isBuiltIn": True, "allowNewInstances": True}] if self.type_found else []),
            ]}
        if tool == "hub_get_app_config":
            return deepcopy(self.summary) if self.summary is not None else {"success": False}
        if tool == "hub_list_rules":
            if not self.list_ok:
                return {"success": False}
            return {"rules": [
                {"id": rid, "label": rule["name"]}
                for rid, rule in self.rules.items()
                if params.get("labelFilter", "") in rule["name"]
            ]}
        if tool == "hub_list_backups":
            return {"hubLocalBackups": deepcopy(self.backups)}
        if gateway == "hub_create_backup":
            if self.backup_ok:
                self.backups.append({"createTimeOrig": "2026-11-03T10:00:00+0000"})
            return {"success": self.backup_ok}
        if tool == "hub_set_rule" and params.get("operation") == "create":
            self.rules[5000] = {"name": params["args"]["name"],
                                "changes": deepcopy(params["args"]["changes"])}
            if self.timeout:
                raise TimeoutError("uncertain create outcome")
            if self.partial:
                return {"success": False, "rule_id": 5000, "broken": True, "results": []}
            return {"success": True, "rule_id": 5000, "broken": False,
                    "results": [{"result": {"success": True}} for _ in params["args"]["changes"]]}
        if tool == "hub_set_rule" and params.get("operation") == "read":
            settings, actions = [], []
            for i, action in enumerate(self.rules[5000]["changes"], 1):
                val = action["value"]
                actions.append({"id": str(i), "value": {"method": val["subtype"]}})
                settings.append({"name": f"actSubType.{i}", "value": val["subtype"]})
                for field in val["fields"]:
                    value = field["value"]
                    name = field["name"].replace("#", str(i))
                    if field["type"] == "capability.switch":
                        settings.append({"name": name, "device_ids": list(value)})
                    else:
                        settings.append({"name": name,
                                         "value": str(value).lower() if isinstance(value, bool) else str(value)})
            doc = {"success": True, "nativeHealth": {"broken": False},
                   "settings": settings, "actions": actions, "triggers": {}}
            if self.corrupt == "missing_triggers":
                doc.pop("triggers")
            if self.corrupt == "extra_action":
                actions.append({"id": "3", "value": {"method": "getDelay"}})
            if self.corrupt == "missing_action_value":
                actions[0].pop("value")
            if self.corrupt == "wrong_action_method":
                actions[0]["value"]["method"] = "getOnOffSwitch"
            if self.corrupt == "legacy_fake_subtype":
                actions[0] = {"id": 1, "subtype": "getDelay"}
            if self.corrupt == "duplicate_action_id":
                actions[1]["id"] = actions[0]["id"]
            if self.corrupt == "extra_setting_action":
                settings.append({"name": "actSubType.3", "value": "getDelay"})
            if self.corrupt == "wrong_device":
                next(x for x in settings if x["name"] == "onOffSwitch.2")["device_ids"] = ["8888"]
            if self.corrupt == "wrong_delay":
                next(x for x in settings if x["name"] == "delayMinute.1")["value"] = "99"
            # Live manual Rule 4259 read returned blank values for these
            # inputs. Blank is NOT equivalent to stored zero/false. The
            # synthetic writer must refuse to start on unknown readback.
            blank_fields = {
                "blank_delay_hour": "delayHour.1",
                "blank_delay_second": "delaySecond.1",
                "blank_user_variable": "uVar.1",
                "blank_cancel": "cancelAct.1",
                "blank_random": "randomAct.1",
                "blank_on_off": "onOff.2",
            }
            if self.corrupt in blank_fields:
                next(x for x in settings if x["name"] ==
                     blank_fields[self.corrupt])["value"] = ""
            if self.corrupt == "has_trigger":
                doc["triggers"] = [{"id": 1}]
            if self.corrupt == "broken":
                doc["nativeHealth"]["broken"] = True
            return doc
        if tool == "hub_set_rule_paused":
            self.paused.append(params["ruleId"])
            return {"success": self.pause_ok}
        if tool == "hub_call_rule":
            self.runs.append(params)
            return {"success": self.start_ok}
        if tool == "hub_get_rule_health":
            return {"ok": True, "broken": False, "paused": False, "stopped": False,
                    "scheduledJobCount": self.jobs}
        raise AssertionError((gateway, tool, params))


def schedule(hub, request=REQ, now=NOW):
    return n.schedule_delayed_switch(hub, request, now, enabled=True, approved=True)


def test_default_disabled_and_confirmation_required_before_any_hub_call():
    assert n.NATIVE_DELAY_ENABLED is False
    hub = Hub()
    with pytest.raises(n.Refuse, match="native_delay_disabled"):
        n.schedule_delayed_switch(hub, REQ, NOW)
    with pytest.raises(n.Refuse, match="confirmation_required"):
        n.schedule_delayed_switch(hub, REQ, NOW, enabled=True)
    assert not hub.calls


def test_due_is_not_floored_earlier_than_user_delay_and_label_is_idempotent():
    p = n.plan(REQ, NOW)
    assert p.requested_due_utc.isoformat() == "2026-11-03T10:15:07+00:00"
    assert n.plan(REQ, NOW + timedelta(seconds=20)).label == p.label
    assert n.plan(REQ, NOW + timedelta(minutes=1)).label != p.label


@pytest.mark.parametrize("seconds,code", [(30,"delay_too_short"), (86400,"delay_too_long"), (True,"delay_too_short")])
def test_delay_bounds(seconds,code):
    with pytest.raises(n.Refuse) as error:
        n.plan(n.DelayRequest("6923","Test",seconds), NOW)
    assert error.value.code == code


def test_clock_device_and_dst():
    with pytest.raises(n.Refuse, match="clock_unverified"):
        n.plan(REQ, datetime(2026,11,3,10,0))
    with pytest.raises(n.Refuse, match="target_unverified"):
        n.plan(n.DelayRequest(True,"Test",900),NOW)
    start = datetime(2027,3,28,0,50,7,tzinfo=ZoneInfo("Europe/London"))
    assert n.plan(REQ,start).requested_due_utc.isoformat() == "2027-03-28T01:05:07+00:00"


def test_synthetic_happy_path_does_not_claim_physical_block():
    hub=Hub()
    outcome=schedule(hub)
    assert outcome.ok and outcome.rule_id==5000
    assert "physical device action remain unverified" in outcome.note
    assert len(hub.runs)==1
    writes=hub.calls_for("hub_set_rule")
    assert [x["operation"] for x in writes]==["create","read"]
    # The wire-format read is the upstream native actionList projection:
    # ordered entries carry {id, value:{method}}, not top-level subtype.
    read_doc = hub("hub_manage_rule_machine", "hub_set_rule",
                   {"operation": "read", "rule_id": 5000,
                    "args": {"sections": ["actions", "settings", "triggers"]}})
    assert read_doc["actions"] == [
        {"id": "1", "value": {"method": "getDelay"}},
        {"id": "2", "value": {"method": "getOnOffSwitch"}},
    ]
    changes=writes[0]["args"]["changes"]
    assert [(v["part"],v["value"]["subtype"]) for v in changes]==[
        ("action","getDelay"),("action","getOnOffSwitch")]
    assert {f["name"]:f["value"] for f in changes[1]["value"]["fields"]}["onOff.#"] is False


def test_each_write_tool_uses_correct_live_guide_section_key():
    hub = Hub()
    assert schedule(hub).ok
    guide_sections = [
        args["section"] for gateway, _, args in hub.calls
        if gateway == "hub_get_tool_guide"
    ]
    assert guide_sections[:2] == ["set_rule_reference", "builtin_app_tools_rules"]
    create = next(x for x in hub.calls_for("hub_set_rule")
                  if x["operation"] == "create")
    assert create["bestPracticeKey"].startswith(
        "I-HAVE-READ-THE-GUIDE-set_rule_reference-")
    run = hub.calls_for("hub_call_rule")[0]
    assert run["bestPracticeKey"].startswith(
        "I-HAVE-READ-THE-GUIDE-builtin_app_tools_rules-")
    assert run["bestPracticeKey"] != create["bestPracticeKey"]


def test_wrong_control_guide_stops_before_backup_or_create():
    hub = Hub()
    original = hub.__call__
    def invalid_control_guide(gateway, tool, params):
        if gateway == "hub_get_tool_guide" and params.get("section") == "builtin_app_tools_rules":
            hub.calls.append((gateway, tool, deepcopy(params)))
            return {"success": True, "content": GUIDE}
        return original(gateway, tool, params)
    with pytest.raises(n.Refuse, match="rm_contract_changed"):
        n.schedule_delayed_switch(invalid_control_guide, REQ, NOW, enabled=True, approved=True)
    assert not hub.calls_for("hub_set_rule")
    assert not hub.calls_for("hub_create_backup")
    assert not hub.runs


def test_partial_create_pause_uses_control_guide_acknowledgment():
    hub = Hub(partial=True)
    with pytest.raises(n.Refuse, match="create_failed"):
        schedule(hub)
    pause = hub.calls_for("hub_set_rule_paused")[0]
    assert pause["bestPracticeKey"].startswith(
        "I-HAVE-READ-THE-GUIDE-builtin_app_tools_rules-")


def test_allow_is_switch_on():
    hub=Hub()
    assert schedule(hub,n.DelayRequest("6923","Test",600,False)).ok
    fields=hub.calls_for("hub_set_rule")[0]["args"]["changes"][1]["value"]["fields"]
    assert {f["name"]:f["value"] for f in fields}["onOff.#"] is True


def test_existing_rule_never_restarts_actions():
    hub=Hub()
    schedule(hub)
    with pytest.raises(n.Refuse,match="duplicate_rule_exists"):
        schedule(hub,now=NOW+timedelta(seconds=8))
    assert len(hub.runs)==1
    assert len([x for x in hub.calls_for("hub_set_rule") if x.get("operation")=="create"])==1


def test_create_timeout_may_leave_rule_and_never_retries_or_starts():
    hub=Hub(timeout=True)
    with pytest.raises(n.Refuse,match="create_outcome_unknown"):
        schedule(hub)
    assert len(hub.calls_for("hub_set_rule"))==1
    assert len(hub.rules)==1 and not hub.runs


def test_partial_create_pauses_before_refusing():
    hub=Hub(partial=True)
    with pytest.raises(n.Refuse,match="create_failed"):
        schedule(hub)
    assert hub.paused==[5000] and not hub.runs


def test_failed_pause_requires_manual_review():
    hub=Hub(partial=True,pause_ok=False)
    with pytest.raises(n.Refuse,match="partial_rule_needs_manual_review"):
        schedule(hub)
    assert not hub.runs


@pytest.mark.parametrize("corrupt", ["missing_triggers","extra_action","extra_setting_action",
                                      "wrong_device","wrong_delay","has_trigger","broken",
                                      "missing_action_value","wrong_action_method",
                                      "legacy_fake_subtype","duplicate_action_id",
                                      "blank_delay_hour","blank_delay_second",
                                      "blank_user_variable","blank_cancel",
                                      "blank_random","blank_on_off"])
def test_bad_readback_is_paused_and_never_started(corrupt):
    hub=Hub(corrupt=corrupt)
    with pytest.raises(n.Refuse,match="verify_failed"):
        schedule(hub)
    assert hub.paused==[5000] and not hub.runs


def test_failed_run_actions_not_retried_or_reported_success():
    hub=Hub(start_ok=False)
    with pytest.raises(n.Refuse,match="start_outcome_unknown"):
        schedule(hub)
    assert len(hub.runs)==1


def test_zero_scheduled_jobs_is_unverified():
    hub=Hub(jobs=0)
    result=schedule(hub)
    assert not result.ok and "do not rely" in result.note


def test_legacy_parent_type_19_cannot_substitute_missing_type_18():
    hub=Hub(type_found=False)
    with pytest.raises(n.Refuse,match="rm_parent_type_mismatch"):
        schedule(hub)
    assert not hub.calls_for("hub_set_rule")


@pytest.mark.parametrize("namespace", ["community", "", None])
def test_parent_type_namespace_not_attested_never_creates_rule(namespace):
    hub = Hub(type_namespace=namespace)
    with pytest.raises(n.Refuse, match="rm_parent_type_mismatch"):
        schedule(hub)
    assert not hub.calls_for("hub_set_rule")
    assert not hub.calls_for("hub_create_backup")
    assert not hub.runs


def test_rule_inventory_failure_never_becomes_no_duplicate():
    hub=Hub(list_ok=False)
    with pytest.raises(n.Refuse,match="inventory_unverified"):
        schedule(hub)
    assert not hub.calls_for("hub_set_rule")


def test_guide_change_rejected_before_write():
    hub=Hub(guide="addTrigger only")
    with pytest.raises(n.Refuse,match="rm_contract_changed"):
        schedule(hub)
    assert not hub.calls_for("hub_set_rule")


def test_stale_backup_requires_create_and_fresh_readback():
    hub=Hub(have_backup=False)
    assert schedule(hub).ok
    assert len([x for x in hub.calls if x[0]=="hub_create_backup"])==1
    assert len(hub.calls_for("hub_list_backups"))==2


def test_backup_failure_prevents_rule_creation():
    hub=Hub(have_backup=False,backup_ok=False)
    with pytest.raises(n.Refuse,match="backup_failed"):
        schedule(hub)
    assert not hub.calls_for("hub_set_rule")


def test_cleanup_disabled_without_completed_action_proof():
    hub=Hub()
    with pytest.raises(n.Refuse,match="cleanup_requires_completion_evidence"):
        n.cleanup_expired(hub,NOW)
    assert not hub.calls


@pytest.mark.parametrize("summary,expected", [
    ({"success": True, "id": 169, "type": "Rule Machine",
      "namespace": "hubitat", "user": False}, True),
    ({"success": True, "id": 169, "type": "Rule Machine",
      "namespace": "community", "user": False}, False),
    ({"success": True, "id": 169, "type": "Rule Machine",
      "namespace": "", "user": False}, False),
    ({"success": True, "id": 169, "type": "Rule Machine",
      "user": False}, False),
    ({"success": True, "id": 169, "type": "Rule Machine",
      "namespace": "hubitat", "user": True}, False),
    ({"success": True, "id": 170, "type": "Rule Machine",
      "namespace": "hubitat", "user": False}, False),
    ({"success": True, "id": 169, "type": "Unrelated App",
      "namespace": "hubitat", "user": False}, False),
    ({"success": True, "id": 169, "type": "Rule Machine",
      "namespace": "hubitat", "user": False, "appTypeId": 99}, False),
    ({"success": False, "id": 169, "type": "Rule Machine",
      "namespace": "hubitat", "user": False}, False),
])
def test_upstream_515_summary_parent_proof_only_if_exact_typed_source(summary, expected):
    hub = Hub(type_found=False, summary=summary)
    if expected:
        assert n.find_parent(hub) == 169
        assert hub.calls_for("hub_get_app_config") == [
            {"appId": "169", "summary": True}
        ]
    else:
        with pytest.raises(n.Refuse, match="rm_parent_type_mismatch"):
            n.find_parent(hub)
    assert not hub.calls_for("hub_set_rule")
    assert not hub.calls_for("hub_create_backup")


def test_verified_type_list_keeps_priority_without_extra_summary():
    hub = Hub(summary={"success": False})
    assert n.find_parent(hub) == 169
    assert not hub.calls_for("hub_get_app_config")
