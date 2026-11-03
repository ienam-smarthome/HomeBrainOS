"""OFFLINE-ONLY MCP 5.1.5 native one-time dated Rule Machine BAT candidate.

Not imported by HomeBrainOS runtime. Never changes a hub unless a caller
supplies an injected transport AND both disabled gates are explicitly opened.
The real installed MCP source and exact trigger readback require a separate
non-production, harmless virtual-switch BAT with the user's explicit approval.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from native_rule_delay_candidate import (
    Call, Refuse, _utc, _numeric_id, _response,
    get_contract, get_rule_control_contract, find_parent, _existing,
    _pause,
)

NATIVE_DATED_ENABLED = False
MIN_LEAD_SECONDS = 180
MAX_LEAD_SECONDS = 30 * 86400
LABEL_PREFIX = "HB one-time BAT | "
HUB_TIMEZONE = "Europe/London"
TRIGGER_NAME = "Certain Time (and optional date)"


@dataclass(frozen=True)
class DatedRequest:
    device_id: str
    device_label: str
    due_utc: datetime
    block: bool = True


@dataclass(frozen=True)
class DatedPlan:
    label: str
    due_utc: datetime
    date_value: str
    time_value: str


@dataclass(frozen=True)
class DatedResult:
    rule_id: int
    label: str
    due_utc: datetime
    source_scheduled_jobs: int
    note: str


def plan(req: DatedRequest, now: datetime) -> DatedPlan:
    at = _utc(now)
    due = _utc(req.due_utc)
    if type(req.block) is not bool or not _numeric_id(req.device_id):
        raise Refuse("target_unverified")
    label = " ".join(str(req.device_label).replace("|", "/").strip().split())
    if not label or len(label) > 82:
        raise Refuse("target_unverified")
    if (due - at).total_seconds() < MIN_LEAD_SECONDS:
        raise Refuse("date_too_soon")
    if (due - at).total_seconds() > MAX_LEAD_SECONDS:
        raise Refuse("date_too_far")
    # Rule Machine's date/time GUI exposes minute precision. Never round a
    # requested deadline earlier than the user specified.
    if due.second or due.microsecond:
        due = due.replace(second=0, microsecond=0) + timedelta(minutes=1)
    local = due.astimezone(ZoneInfo(HUB_TIMEZONE))
    date = local.strftime("%Y-%m-%d")
    time = local.strftime("%Y-%m-%dT%H:%M:00.000%z")
    verb = "block" if req.block else "allow"
    digest = hashlib.sha256(
        f"{req.device_id}|{verb}|{due.isoformat()}".encode("utf-8")
    ).hexdigest()[:12]
    name = f"{LABEL_PREFIX}{label} {verb} | {due:%Y-%m-%dT%H:%MZ} | {digest}"
    return DatedPlan(name, due, date, time)


def require_existing_fresh_backup(call: Call, now: datetime) -> None:
    """Read-only, fail closed; NEVER create a backup as a side effect."""
    timestamp = _utc(now)
    data = _response(
        call("hub_read_apps_code", "hub_list_backups", {"scope": "hub_local"}),
        "backup_unverified",
    )
    rows = data.get("hubLocalBackups")
    if not isinstance(rows, list):
        raise Refuse("backup_unverified")
    for row in rows:
        raw = row.get("createTimeOrig") if isinstance(row, dict) else None
        if not isinstance(raw, str):
            continue
        try:
            created = datetime.strptime(
                raw, "%Y-%m-%dT%H:%M:%S%z"
            ).astimezone(timezone.utc)
        except ValueError:
            continue
        if timedelta(0) <= timestamp - created < timedelta(hours=23):
            return
    raise Refuse("fresh_backup_missing")


def create_args(parent_id: int, p: DatedPlan, req: DatedRequest, key: str) -> dict[str, Any]:
    return {
        "operation": "create",
        "confirm": True,
        "bestPracticeKey": key,
        "args": {
            "parent_id": parent_id,
            "name": p.label,
            "changes": [
                {"part": "trigger", "value": {
                    "capability": TRIGGER_NAME,
                    "fields": [
                        {"name": "time#", "type": "enum", "value": "A specific time"},
                        {"name": "atTime#", "type": "time", "value": p.time_value},
                        {"name": "date#", "type": "bool", "value": True},
                        {"name": "year#", "type": "bool", "value": False},
                        {"name": "atDate#", "type": "date", "value": p.date_value},
                    ],
                }},
                {"part": "action", "value": {
                    "type": "switchActs",
                    "subtype": "getOnOffSwitch",
                    "fields": [
                        {"name": "onOffSwitch.#", "type": "capability.switch",
                         "value": [str(req.device_id)]},
                        {"name": "onOff.#", "type": "bool", "value": not req.block},
                    ],
                }},
            ],
        },
    }


def verify_rule(call: Call, rule_id: int, req: DatedRequest, p: DatedPlan) -> None:
    doc = _response(call(
        "hub_manage_rule_machine", "hub_set_rule",
        {"operation": "read", "rule_id": rule_id,
         "args": {"sections": ["settings", "actions", "triggers"]}},
    ), "dated_readback_unverified")
    if _numeric_id(doc.get("rule_id")) != str(rule_id):
        raise Refuse("dated_readback_unverified")
    health = doc.get("nativeHealth")
    if (not isinstance(health, dict) or health.get("available") is not True
            or health.get("broken") is not False
            or health.get("stopped") is True
            or health.get("paused") is True):
        raise Refuse("dated_readback_unverified")
    actions = doc.get("actions")
    if (not isinstance(actions, list) or len(actions) != 1
            or not isinstance(actions[0], dict)
            or _numeric_id(actions[0].get("id")) is None
            or not isinstance(actions[0].get("value"), dict)
            or actions[0]["value"].get("method") != "getOnOffSwitch"):
        raise Refuse("dated_readback_unverified")
    index = _numeric_id(actions[0]["id"])
    triggers = doc.get("triggers")
    if (not isinstance(triggers, dict) or len(triggers) != 1
            or not all(_numeric_id(i) for i in triggers)):
        raise Refuse("dated_readback_unverified")
    trigger_id, trigger_value = next(iter(triggers.items()))
    # Exact capability is required, not merely a non-empty trigger row.
    if trigger_value != TRIGGER_NAME:
        raise Refuse("dated_readback_unverified")
    rows = doc.get("settings")
    if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
        raise Refuse("dated_readback_unverified")
    settings: dict[str, dict[str, Any]] = {}
    for row in rows:
        n = row.get("name")
        if not isinstance(n, str) or n in settings:
            raise Refuse("dated_readback_unverified")
        settings[n] = row

    def exact(name: str, value: Any) -> bool:
        row = settings.get(name)
        if not isinstance(row, dict):
            return False
        stored = row.get("value")
        if type(value) is bool:
            return stored is value or (
                isinstance(stored, str) and stored.lower() == str(value).lower()
            )
        return str(stored) == str(value) if stored is not None else False

    if not all([
        exact(f"actSubType.{index}", "getOnOffSwitch"),
        exact(f"onOff.{index}", not req.block),
        exact(f"tCapab{trigger_id}", TRIGGER_NAME),
        exact(f"time{trigger_id}", "A specific time"),
        exact(f"atTime{trigger_id}", p.time_value),
        exact(f"date{trigger_id}", True),
        exact(f"atDate{trigger_id}", p.date_value),
    ]):
        raise Refuse("dated_readback_unverified")
    # An absent year toggle is acceptable if only the native dated-event
    # selection is returned; an explicit true or unparseable value is not.
    if f"year{trigger_id}" in settings and not exact(f"year{trigger_id}", False):
        raise Refuse("dated_readback_unverified")
    selector = settings.get(f"onOffSwitch.{index}")
    if not isinstance(selector, dict) or selector.get("device_ids") != [str(req.device_id)]:
        raise Refuse("dated_readback_unverified")


def schedule_dated_switch(
    call: Call, req: DatedRequest, now: datetime, *,
    enabled: bool = False, approved: bool = False,
    server_515_verified: bool = False, virtual_target_verified: bool = False,
) -> DatedResult:
    """Single BAT-only rule creation: no Run Actions, delete or cleanup.

    The two verified flags are *prerequisites*, not evidence themselves; a
    future runtime integration must obtain and attach corresponding verified
    read-only source receipts, not accept arbitrary user/model booleans.
    """
    p = plan(req, now)
    if not enabled or not NATIVE_DATED_ENABLED:
        raise Refuse("native_dated_disabled")
    if not approved:
        raise Refuse("confirmation_required")
    if server_515_verified is not True:
        raise Refuse("mcp_515_unverified")
    if virtual_target_verified is not True:
        raise Refuse("virtual_target_unverified")
    guide_key = get_contract(call)
    control_key = get_rule_control_contract(call)
    parent_id = find_parent(call)
    if _existing(call, p.label):
        raise Refuse("duplicate_rule_exists")
    require_existing_fresh_backup(call, now)
    try:
        res = call(
            "hub_manage_rule_machine", "hub_set_rule",
            create_args(parent_id, p, req, guide_key),
        )
    except Exception as exc:
        raise Refuse("create_outcome_unknown") from exc
    if not isinstance(res, dict):
        raise Refuse("create_outcome_unknown")
    rid = _numeric_id(res.get("rule_id"))
    if not rid:
        raise Refuse("create_outcome_unknown")
    valid = (
        res.get("success") is True and res.get("broken") is False
        and isinstance(res.get("results"), list) and len(res["results"]) == 2
        and all(isinstance(x, dict) and isinstance(x.get("result"), dict)
                and x["result"].get("success") is True for x in res["results"])
    )
    if not valid:
        _pause(call, int(rid), control_key)
        raise Refuse("create_failed")
    try:
        verify_rule(call, int(rid), req, p)
    except Exception as exc:
        _pause(call, int(rid), control_key)
        raise Refuse("dated_readback_unverified") from exc

    # Native "Certain Time" schedules automatically. Never Run Actions;
    # that would turn the target off immediately instead of at the date.
    jobs = res.get("scheduledJobs")
    if not isinstance(jobs, list) or not jobs:
        _pause(call, int(rid), control_key)
        raise Refuse("schedule_activation_unverified")
    return DatedResult(
        int(rid), p.label, p.due_utc, len(jobs),
        "Hub reported a scheduled native job; exact due/fire, reboot "
        "survival, command attribution and Internet access remain unverified.",
    )


def cleanup_completed(*_args: Any, **_kwargs: Any) -> None:
    raise Refuse("cleanup_requires_source_attributed_completion")
