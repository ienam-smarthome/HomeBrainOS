"""OFFLINE ONLY: review candidate for native Rule Machine delayed switch actions.

Native dated triggers remain unsupported by upstream 5.1.1 (issue #575).
This module has no HomeBrainOS runtime import or invocation. The writer accepts
only an injected *test* transport and needs explicit confirmation + enablement.
The upstream source documents readback shape but live Rule 4259 read failed.\nReal Run Actions via MCP, job attribution and completion are unverified.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

Call = Callable[[str, str, dict[str, Any]], dict[str, Any]]
NATIVE_DELAY_ENABLED = False
MIN_DELAY_SECONDS = 60
MAX_DELAY_SECONDS = 86400 - 1
LABEL_PREFIX = "HB delay | "


class Refuse(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class DelayRequest:
    device_id: str
    device_label: str
    delay_seconds: int
    block: bool = True


@dataclass(frozen=True)
class Plan:
    label: str
    requested_due_utc: datetime
    h: int
    m: int
    s: int


@dataclass(frozen=True)
class Result:
    ok: bool
    rule_id: int
    label: str
    requested_due_utc: datetime
    note: str


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise Refuse("clock_unverified")
    return value.astimezone(timezone.utc)


def _numeric_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and value.isdecimal() and int(value) > 0:
        return str(int(value))
    return None


def plan(req: DelayRequest, now: datetime) -> Plan:
    now = _utc(now)
    if type(req.delay_seconds) is not int or req.delay_seconds < MIN_DELAY_SECONDS:
        raise Refuse("delay_too_short")
    if req.delay_seconds > MAX_DELAY_SECONDS:
        raise Refuse("delay_too_long")
    if not _numeric_id(req.device_id) or type(req.block) is not bool:
        raise Refuse("target_unverified")
    label = " ".join(str(req.device_label).replace("|", "/").strip().split())
    if not label or len(label) > 90:
        raise Refuse("target_unverified")
    due = now + timedelta(seconds=req.delay_seconds)
    slot = now.replace(second=0, microsecond=0)
    verb = "block" if req.block else "allow"
    digest = hashlib.sha256(f"{req.device_id}|{verb}|{req.delay_seconds}|{slot.isoformat()}".encode()).hexdigest()[:12]
    name = f"{LABEL_PREFIX}{label} {verb} | requested {slot:%Y-%m-%dT%H:%MZ} | {digest}"
    h, rem = divmod(req.delay_seconds, 3600)
    m, s = divmod(rem, 60)
    return Plan(name, due, h, m, s)


def _response(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("success") is False:
        raise Refuse(code)
    return value


def _guide_section_key(call: Call, section: str) -> tuple[str, str]:
    """Inspect the server's current guide; a section-specific key is not reusable."""
    guide = _response(
        call("hub_get_tool_guide", "", {"section": section}),
        "rm_contract_changed",
    )
    content = guide.get("content")
    if not isinstance(content, str):
        raise Refuse("rm_contract_changed")
    key = re.search(
        r"I-HAVE-READ-THE-GUIDE-" + re.escape(section) + r"-[0-9a-fA-F]+",
        content,
    )
    if not key:
        raise Refuse("rm_contract_changed")
    return key.group(0), content


def get_contract(call: Call) -> str:
    key, content = _guide_section_key(call, "set_rule_reference")
    if not all(x in content for x in ('operation:"create"', "parent_id", "changes")):
        raise Refuse("rm_contract_changed")
    return key


def get_rule_control_contract(call: Call) -> str:
    """Run Actions / pause need builtin_app_tools_rules, NOT the set_rule key."""
    key, content = _guide_section_key(call, "builtin_app_tools_rules")
    if "hub_call_rule" not in content or "hub_set_rule_paused" not in content:
        raise Refuse("rm_contract_changed")
    return key


def _list(call: Call, gateway: str, tool: str, args: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursors: set[str] = set()
    for _ in range(12):
        data = _response(call(gateway, tool, args), "inventory_unverified")
        page = data.get(key)
        if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
            raise Refuse("inventory_unverified")
        items.extend(page)
        cursor = data.get("nextCursor")
        if not cursor:
            if data.get("hasMore") is True:
                raise Refuse("inventory_unverified")
            return items
        if not isinstance(cursor, str) or cursor in cursors:
            raise Refuse("inventory_unverified")
        cursors.add(cursor)
        args = {**args, "cursor": cursor}
    raise Refuse("inventory_unverified")


def find_parent(call: Call) -> int:
    inst = _list(call, "hub_read_apps_code", "hub_list_apps",
                 {"scope": "instances", "nameFilter": "Rule Machine"}, "apps")
    candidates = [a for a in inst if a.get("name") == a.get("type") == "Rule Machine"
                  and a.get("user") is False and a.get("parentId") is None
                  and a.get("hasChildren") is True and _numeric_id(a.get("id"))
                  and _numeric_id(a.get("appTypeId"))]
    if len(candidates) != 1:
        raise Refuse("rm_parent_not_unique")
    parent = candidates[0]
    types = _list(call, "hub_read_apps_code", "hub_list_apps",
                  {"scope": "types", "nameFilter": "Rule Machine"}, "apps")
    match = [t for t in types if _numeric_id(t.get("id")) == _numeric_id(parent["appTypeId"])]
    if len(match) != 1 or match[0].get("name") != "Rule Machine" or not all(
        match[0].get(k) is True for k in ("system", "isBuiltIn", "allowNewInstances")
    ):
        raise Refuse("rm_parent_type_mismatch")
    return int(parent["id"])


def _existing(call: Call, label: str) -> list[dict[str, Any]]:
    rows = _list(call, "hub_manage_rule_machine", "hub_list_rules",
                 {"labelFilter": label}, "rules")
    return [r for r in rows if (r.get("label") or r.get("name")) == label]


def ensure_backup(call: Call, now: datetime) -> None:
    now = _utc(now)

    def fresh() -> bool:
        data = _response(call("hub_read_apps_code", "hub_list_backups", {"scope": "hub_local"}), "backup_unverified")
        rows = data.get("hubLocalBackups")
        if not isinstance(rows, list):
            raise Refuse("backup_unverified")
        for row in rows:
            stamp = row.get("createTimeOrig") if isinstance(row, dict) else None
            if not isinstance(stamp, str):
                continue
            try:
                at = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)
            except ValueError:
                continue
            if timedelta(0) <= now - at < timedelta(hours=23):
                return True
        return False

    if not fresh():
        created = _response(call("hub_create_backup", "", {"confirm": True}), "backup_failed")
        if created.get("success") is not True or not fresh():
            raise Refuse("backup_unverified")


def create_args(parent_id: int, p: Plan, req: DelayRequest, key: str) -> dict[str, Any]:
    return {"operation": "create", "confirm": True, "bestPracticeKey": key,
            "args": {"parent_id": parent_id, "name": p.label, "changes": [
                {"part": "action", "value": {"type": "delayActs", "subtype": "getDelay", "fields": [
                    {"name": "uVar.#", "type": "bool", "value": False},
                    {"name": "delayHour.#", "type": "number", "value": p.h},
                    {"name": "delayMinute.#", "type": "number", "value": p.m},
                    {"name": "delaySecond.#", "type": "decimal", "value": p.s},
                    {"name": "cancelAct.#", "type": "bool", "value": False},
                    {"name": "randomAct.#", "type": "bool", "value": False}]}},
                {"part": "action", "value": {"type": "switchActs", "subtype": "getOnOffSwitch", "fields": [
                    {"name": "onOffSwitch.#", "type": "capability.switch", "value": [str(req.device_id)]},
                    {"name": "onOff.#", "type": "bool", "value": not req.block}]}}
            ]}}


def verify_rule(call: Call, rule_id: int, req: DelayRequest, p: Plan) -> None:
    doc = _response(call("hub_manage_rule_machine", "hub_set_rule",
        {"operation": "read", "rule_id": rule_id, "args": {"sections": ["settings", "actions", "triggers"]}}),
        "verify_failed")
    if doc.get("nativeHealth", {}).get("broken") is not False:
        raise Refuse("verify_failed")
    # Missing trigger section is UNKNOWN, not evidence that no triggers exist.
    if "triggers" not in doc or doc["triggers"] not in ({}, []):
        raise Refuse("verify_failed")
    actions = doc.get("actions")
    if not isinstance(actions, list) or len(actions) != 2:
        raise Refuse("verify_failed")
    ids = []
    for action, method in zip(actions, ("getDelay", "getOnOffSwitch")):
        # Native document source: toolGetRuleDocument returns the ordered
        # actionList as [{id: "1", value: nativeState.actions["1"]}, ...].
        # The method sits under value.method, NOT in a top-level subtype.
        # Never accept the invented test-only {id, subtype} shape.
        if not isinstance(action, dict):
            raise Refuse("verify_failed")
        value = action.get("value")
        if not isinstance(value, dict) or value.get("method") != method:
            raise Refuse("verify_failed")
        index = _numeric_id(action.get("id"))
        if index is None or index in ids:
            raise Refuse("verify_failed")
        ids.append(index)
    raw = doc.get("settings")
    if not isinstance(raw, list) or not all(isinstance(x, dict) for x in raw):
        raise Refuse("verify_failed")
    settings = {}
    for setting in raw:
        name = setting.get("name")
        if not isinstance(name, str) or name in settings:
            raise Refuse("verify_failed")
        settings[name] = setting
    selectors = {name: row.get("value") for name, row in settings.items() if name.startswith("actSubType.")}
    if selectors != {f"actSubType.{ids[0]}": "getDelay", f"actSubType.{ids[1]}": "getOnOffSwitch"}:
        raise Refuse("verify_failed")
    def matches(name: str, value: str) -> bool:
        row = settings.get(name)
        return isinstance(row, dict) and str(row.get("value")).lower() == value.lower()
    if not all((
        matches(f"delayHour.{ids[0]}", str(p.h)),
        matches(f"delayMinute.{ids[0]}", str(p.m)),
        matches(f"delaySecond.{ids[0]}", str(p.s)),
        matches(f"uVar.{ids[0]}", "false"),
        matches(f"cancelAct.{ids[0]}", "false"),
        matches(f"randomAct.{ids[0]}", "false"),
        matches(f"onOff.{ids[1]}", "false" if req.block else "true"),
    )):
        raise Refuse("verify_failed")
    target = settings.get(f"onOffSwitch.{ids[1]}")
    if not isinstance(target, dict) or target.get("device_ids") != [str(req.device_id)]:
        raise Refuse("verify_failed")


def _pause(call: Call, rule_id: int, control_key: str) -> None:
    try:
        result = _response(call("hub_manage_rule_machine", "hub_set_rule_paused",
                                {"ruleId": rule_id, "paused": True, "bestPracticeKey": control_key}), "pause_failed")
        if result.get("success") is not True:
            raise Refuse("pause_failed")
    except Exception as exc:
        raise Refuse("partial_rule_needs_manual_review") from exc


def schedule_delayed_switch(
    call: Call, req: DelayRequest, now: datetime, *, enabled: bool = False,
    approved: bool = False,
) -> Result:
    p = plan(req, now)
    if not enabled or not approved:
        raise Refuse("native_delay_disabled" if not enabled else "confirmation_required")
    guide_key = get_contract(call)
    control_key = get_rule_control_contract(call)
    parent_id = find_parent(call)
    if _existing(call, p.label):
        # Never restart a pending or previously completed rule just because
        # the request matches its label.
        raise Refuse("duplicate_rule_exists")
    ensure_backup(call, now)
    try:
        res = call("hub_manage_rule_machine", "hub_set_rule",
                   create_args(parent_id, p, req, guide_key))
    except Exception as exc:
        # A timeout can leave a child. Never assume failure and retry.
        raise Refuse("create_outcome_unknown") from exc
    if not isinstance(res, dict):
        raise Refuse("create_outcome_unknown")
    rid = _numeric_id(res.get("rule_id") or res.get("app_id"))
    success = (res.get("success") is True and res.get("broken") is False
               and isinstance(res.get("results"), list)
               and len(res["results"]) == 2
               and all(isinstance(x, dict) and isinstance(x.get("result"), dict)
                       and x["result"].get("success") is True for x in res["results"]))
    if not success or rid is None:
        if rid is not None:
            _pause(call, int(rid), control_key)
        raise Refuse("create_failed" if rid else "create_outcome_unknown")
    rule_id = int(rid)
    try:
        verify_rule(call, rule_id, req, p)
    except Exception as exc:
        _pause(call, rule_id, control_key)
        raise Refuse("verify_failed") from exc
    # Never retry Run Actions automatically; no duplicate execution risk.
    try:
        run = call("hub_manage_rule_machine", "hub_call_rule",
                   {"ruleId": rule_id, "action": "actions", "bestPracticeKey": control_key})
    except Exception as exc:
        raise Refuse("start_outcome_unknown") from exc
    if not isinstance(run, dict) or run.get("success") is not True or run.get("failedRuleIds"):
        raise Refuse("start_outcome_unknown")
    health = _response(call("hub_read_rules", "hub_get_rule_health", {"appId": rule_id}),
                       "start_unverified")
    if health.get("ok") is not True or health.get("broken") is not False or (
        health.get("paused") is True or health.get("stopped") is True
    ):
        raise Refuse("start_unverified")
    if type(health.get("scheduledJobCount")) is not int or health["scheduledJobCount"] < 1:
        return Result(False, rule_id, p.label, p.requested_due_utc,
                      "Run Actions sent but no verified pending job; do not rely on the action")
    return Result(True, rule_id, p.label, p.requested_due_utc,
                  "Hub reported a pending job; actual due and physical device action remain unverified")


def cleanup_expired(*_args: Any, **_kwargs: Any) -> None:
    # An estimated due time and a textual name cannot establish completion
    # or exclusive ownership, so never delete a possibly pending job.
    raise Refuse("cleanup_requires_completion_evidence")
