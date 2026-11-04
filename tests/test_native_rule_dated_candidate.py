"""Synthetic-only native dated one-time BAT, no live MCP or Hubitat writes."""
from __future__ import annotations

import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import native_rule_dated_candidate as d
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))
from native_rule_inventory_source import project_rule_inventory
from test_native_rule_delay_candidate import Hub

UTC = timezone.utc
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
REQ = d.DatedRequest("9001", "Synthetic BAT Switch", NOW + timedelta(minutes=5))


class DatedHub(Hub):
    def __init__(self, *, corrupt=None, scheduled_jobs=True, bad_create=False,
                 unknown_create=False, **kwargs):
        super().__init__(corrupt=corrupt, **kwargs)
        self.scheduled_jobs = scheduled_jobs
        self.bad_create = bad_create
        self.unknown_create = unknown_create
        self.created = 0

    def __call__(self, gateway, tool, params):
        if tool == "hub_set_rule" and params.get("operation") == "create":
            self.calls.append((gateway, tool, deepcopy(params)))
            self.created += 1
            self.rules[5000] = {
                "name": params["args"]["name"],
                "changes": deepcopy(params["args"]["changes"]),
            }
            if self.unknown_create:
                raise TimeoutError("response lost after native create")
            if self.bad_create:
                return {"success": False, "partial": True, "rule_id": 5000,
                        "broken": True, "results": []}
            return {"success": True, "created": True, "rule_id": 5000,
                    "broken": False,
                    "results": [{"result": {"success": True}}] * 2,
                    "scheduledJobs": ([{"id": "job-1"}]
                                      if self.scheduled_jobs else [])}
        if tool == "hub_set_rule" and params.get("operation") == "read":
            self.calls.append((gateway, tool, deepcopy(params)))
            create = self.rules[5000]["changes"]
            trigger, action = create
            fields = trigger["value"]["fields"]
            settings = [
                {"name": x["name"].replace("#", "1"),
                 "value": str(x["value"]).lower() if isinstance(x["value"], bool)
                          else x["value"]}
                for x in fields
            ]
            settings += [
                {"name": "tCapab1", "value": trigger["value"]["capability"]},
                {"name": "actSubType.1", "value": action["value"]["subtype"]},
                {"name": "onOff.1", "value": "false"},
                {"name": "onOffSwitch.1", "device_ids": ["9001"]},
            ]
            document = {
                "success": True, "rule_id": 5000,
                "nativeHealth": {"available": True, "broken": False,
                                 "paused": False, "stopped": False},
                "actions": [{"id": "1", "value": {"method": "getOnOffSwitch"}}],
                "triggers": {"1": d.TRIGGER_NAME},
                "settings": settings,
            }
            if self.corrupt == "wrong_date":
                next(x for x in settings if x["name"] == "atDate1")["value"] = "2026-11-04"
            if self.corrupt == "no_date":
                settings[:] = [x for x in settings if x["name"] != "atDate1"]
            if self.corrupt == "wrong_time":
                next(x for x in settings if x["name"] == "atTime1")["value"] = "2026-11-03T10:00:00.000+0000"
            if self.corrupt == "unknown_target":
                next(x for x in settings if x["name"] == "onOffSwitch.1")["device_ids"] = []
            if self.corrupt == "wrong_trigger":
                document["triggers"] = {"1": "Switch"}
            if self.corrupt == "no_trigger":
                document["triggers"] = {}
            if self.corrupt == "extra_action":
                document["actions"].append({"id": "2", "value": {"method": "getDelay"}})
            if self.corrupt == "paused":
                document["nativeHealth"]["paused"] = True
            if self.corrupt == "year_true":
                next(x for x in settings if x["name"] == "year1")["value"] = "true"
            if self.corrupt == "wrong_source_id":
                document["rule_id"] = 5001
            if self.corrupt == "duplicate_settings":
                settings.append(deepcopy(settings[0]))
            return document
        return super().__call__(gateway, tool, params)


def call(hub, req=REQ, now=NOW):
    return d.schedule_dated_switch(
        hub, req, now, enabled=True, approved=True,
        server_515_verified=True, virtual_target_verified=True)


def test_bat_writer_is_disabled_and_all_gates_fail_without_any_call():
    hub = DatedHub()
    assert d.NATIVE_DATED_ENABLED is False
    with pytest.raises(d.Refuse, match="native_dated_disabled"):
        d.schedule_dated_switch(hub, REQ, NOW)
    assert not hub.calls
    d.NATIVE_DATED_ENABLED = True
    try:
        for kwargs, why in [
            ({"enabled": True}, "confirmation_required"),
            ({"enabled": True, "approved": True}, "mcp_515_unverified"),
            ({"enabled": True, "approved": True, "server_515_verified": True},
             "virtual_target_unverified"),
        ]:
            with pytest.raises(d.Refuse, match=why):
                d.schedule_dated_switch(hub, REQ, NOW, **kwargs)
        assert not hub.calls
    finally:
        d.NATIVE_DATED_ENABLED = False


@pytest.fixture
def enabled():
    assert d.NATIVE_DATED_ENABLED is False
    d.NATIVE_DATED_ENABLED = True
    try:
        yield
    finally:
        d.NATIVE_DATED_ENABLED = False


def test_plan_native_date_and_dst_never_before_requested_deadline():
    req = d.DatedRequest("9001", "BAT", NOW + timedelta(minutes=5, seconds=7))
    p = d.plan(req, NOW)
    assert p.date_value == "2026-11-03"
    assert p.time_value == "2026-11-03T10:06:00.000+0000"
    assert p.due_utc > req.due_utc
    assert "| 2026-11-03T10:06Z" in p.label
    assert p.label.endswith("(One-time 2026-11-03 10:06)")

    summer_now = datetime(2027, 3, 28, 0, 50, tzinfo=UTC)
    future = summer_now + timedelta(minutes=20)
    summer = d.plan(d.DatedRequest("9001", "BAT", future), summer_now)
    assert summer.time_value == "2027-03-28T02:10:00.000+0100"
    assert summer.date_value == "2027-03-28"
    assert summer.label.endswith("(One-time 2027-03-28 02:10)")
    assert summer.due_utc == future
    assert future.astimezone(ZoneInfo("Europe/London")).hour == 2

    fall_now = datetime(2027, 10, 31, 0, 50, tzinfo=UTC)
    repeated = d.plan(
        d.DatedRequest("9001", "BAT", fall_now + timedelta(minutes=20)),
        fall_now,
    )
    assert repeated.time_value == "2027-10-31T01:10:00.000+0000"
    assert repeated.label.endswith("(One-time 2027-10-31 01:10)")


def test_offline_dated_bat_name_is_discoverable_by_the_runtime_inventory():
    """The once-only BAT cannot become invisible to a subsequent read-only audit."""
    p = d.plan(REQ, NOW)
    assert len(p.label) <= 200
    instances = {
        "apps": [
            {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
             "appTypeId": 18, "parentId": None},
            {"id": 5000, "name": p.label, "type": "Rule-5.1",
             "appTypeId": 19, "parentId": 169},
        ], "count": 2, "totalOnHub": 2,
    }
    types = {
        "apps": [
            {"id": 18, "name": "Rule Machine", "namespace": "hubitat",
             "system": True, "isBuiltIn": True},
            {"id": 19, "name": "Rule-5.1", "namespace": "hubitat",
             "system": True, "isBuiltIn": True},
        ], "count": 2,
    }
    rules = {"rules": [{"id": 5000, "name": p.label}], "count": 1}
    report = project_rule_inventory(instances, types, rules)
    assert report["parentIdentityComplete"] is True
    assert report["oneTimeMatchCount"] == 1
    assert report["oneTimeRules"] == [{
        "appId": "5000", "name": p.label,
        "sourceKinds": ["hub_list_rules", "hub_list_apps"], "parentId": "169",
    }]

    # The terminal marker is required; an internal one-time phrase or
    # UTC/hash metadata alone must not count as the inventory's exact suffix.
    legacy_name = p.label.split(" (One-time ")[0]
    inst_legacy = {**instances, "apps": [
        instances["apps"][0], {**instances["apps"][1], "name": legacy_name},
    ]}
    old_report = project_rule_inventory(
        inst_legacy, types, {"rules": [{"id": 5000, "name": legacy_name}],
                             "count": 1}
    )
    assert old_report["oneTimeMatchCount"] == 0


def test_plan_never_uses_naive_dates_invalid_targets_or_early_deadlines():
    with pytest.raises(d.Refuse, match="clock_unverified"):
        d.plan(d.DatedRequest("9001", "BAT", datetime(2026, 11, 4)), NOW)
    for sec, error in [(10, "date_too_soon"), (31 * 86400, "date_too_far")]:
        with pytest.raises(d.Refuse, match=error):
            d.plan(d.DatedRequest("9001", "BAT", NOW + timedelta(seconds=sec)), NOW)
    with pytest.raises(d.Refuse, match="target_unverified"):
        d.plan(d.DatedRequest("not-id", "BAT", NOW + timedelta(minutes=5)), NOW)
    with pytest.raises(d.Refuse, match="clock_unverified"):
        d.plan(REQ, datetime(2026, 11, 3, 10, 0))


def test_dated_bat_parent_uses_readonly_summary_when_builtin_catalog_omits_namespace():
    hub = DatedHub(type_namespace=None, summary={
        "success": True, "id": 169, "type": "Rule Machine",
        "namespace": "hubitat", "user": False, "appTypeId": 18,
        "parentId": None,
    })
    assert d.find_parent(hub) == 169
    assert hub.calls_for("hub_get_app_config") == [
        {"appId": "169", "summary": True}
    ]
    assert not hub.calls_for("hub_set_rule")
    assert not hub.calls_for("hub_create_backup")


def test_dated_create_exact_source_declared_trigger_no_run_actions(enabled):
    hub = DatedHub(type_found=False, summary={
        "success": True, "id": 169, "type": "Rule Machine",
        "namespace": "hubitat", "user": False,
    })
    out = call(hub)
    assert out.rule_id == 5000
    assert out.source_scheduled_jobs == 1
    assert "physical" not in out.note or "remain unverified" in out.note
    assert hub.created == 1
    assert not hub.calls_for("hub_call_rule")
    assert not hub.calls_for("hub_create_backup")
    created = hub.calls_for("hub_set_rule")[0]
    assert created["operation"] == "create"
    changes = created["args"]["changes"]
    assert [x["part"] for x in changes] == ["trigger", "action"]
    fields = {x["name"]: x for x in changes[0]["value"]["fields"]}
    assert fields["atDate#"] == {
        "name": "atDate#", "type": "date", "value": "2026-11-03",
    }
    assert fields["date#"]["value"] is True
    assert fields["year#"]["value"] is False
    assert fields["atTime#"]["type"] == "time"
    assert "getDelay" not in str(changes)
    assert hub.calls_for("hub_get_app_config") == [
        {"appId": "169", "summary": True}
    ]


@pytest.mark.parametrize("corrupt", [
    "wrong_date", "no_date", "wrong_time", "unknown_target",
    "wrong_trigger", "no_trigger", "extra_action", "paused",
    "year_true", "wrong_source_id", "duplicate_settings",
])
def test_bad_dated_readback_is_paused_never_run(enabled, corrupt):
    hub = DatedHub(corrupt=corrupt)
    with pytest.raises(d.Refuse, match="dated_readback_unverified"):
        call(hub)
    assert hub.created == 1
    assert hub.paused == [5000]
    assert not hub.calls_for("hub_call_rule")


def test_no_verified_native_timer_is_paused_not_reported_scheduled(enabled):
    hub = DatedHub(scheduled_jobs=False)
    with pytest.raises(d.Refuse, match="schedule_activation_unverified"):
        call(hub)
    assert hub.paused == [5000]
    assert not hub.calls_for("hub_call_rule")


def test_partial_native_create_is_paused_before_refusal(enabled):
    hub = DatedHub(bad_create=True)
    with pytest.raises(d.Refuse, match="create_failed"):
        call(hub)
    assert hub.paused == [5000]
    assert not hub.calls_for("hub_call_rule")


def test_ambiguous_create_timeout_is_never_retried_or_started(enabled):
    hub = DatedHub(unknown_create=True)
    with pytest.raises(d.Refuse, match="create_outcome_unknown"):
        call(hub)
    assert hub.created == 1
    assert hub.paused == []  # no confirmed ID at transport boundary
    assert not hub.calls_for("hub_call_rule")


def test_no_backup_creation_on_missing_recent_backup(enabled):
    hub = DatedHub(have_backup=False)
    with pytest.raises(d.Refuse, match="fresh_backup_missing"):
        call(hub)
    assert not hub.calls_for("hub_create_backup")
    assert hub.created == 0
    assert not hub.calls_for("hub_call_rule")


def test_duplicate_rule_never_reused_or_restarted(enabled):
    hub = DatedHub()
    assert call(hub).rule_id == 5000
    with pytest.raises(d.Refuse, match="duplicate_rule_exists"):
        call(hub)
    assert hub.created == 1
    assert not hub.calls_for("hub_call_rule")


def test_cleanup_still_requires_independent_completion_proof():
    with pytest.raises(d.Refuse, match="cleanup_requires_source_attributed_completion"):
        d.cleanup_completed()
