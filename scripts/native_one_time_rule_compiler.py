"""Offline, source-attested Rule Machine one-time Switch compiler foundation.

This module NEVER calls MCP, queues confirmation, or executes a rule. It
translates the old *dated* one-off intent to an actual native-document
create envelope ONLY when a complete one-off native read, current
native-document guide/schema, and native Rule Machine parent are furnished
by the caller. An existing daily rule is not a one-off template.

The native create handler can leave an active child after partial failure.
Consequently a generated candidate is NOT authorization to submit it; a
separate, unimplemented coordinator must verify backup, fresh identity,
duplicate-free inventory, requested-time freshness, user confirmation,
partial-failure handling and typed post-write readback before enabling.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from native_rule_document_preflight import (
    assess_native_schedule_preflight,
    native_schedule_batch_shape_valid,
)

_ONETIME_NAME = re.compile(
    r"^.{1,160} \(One-time (?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<clock>\d{2}:\d{2})\)$"
)
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_VALID_ID = re.compile(r"[1-9]\d{0,8}")


@dataclass(frozen=True)
class NativeOneTimeCandidate:
    request: dict[str, Any] | None
    gaps: tuple[str, ...]
    reference_rule_id: int | None = None

    @property
    def write_ready(self) -> bool:
        # No production write/confirmation adapter has been validated yet.
        return False


def _source_one_time_sample(document: Any) -> tuple[dict[str, Any] | None, str]:
    """Validate existing one-time native persisted fields; never infer from prose."""
    if not isinstance(document, dict):
        return None, "native_one_time_reference_missing"
    rule_id = document.get("rule_id")
    if type(rule_id) is not int or rule_id <= 0:
        return None, "native_one_time_reference_unmatched"
    validation = document.get("validation")
    health = document.get("nativeHealth")
    if (not isinstance(validation, dict)
            or validation.get("structuralIssues") != []
            or not isinstance(health, dict)
            or health.get("broken") is not False):
        return None, "native_one_time_reference_health_unverified"
    actions, triggers = document.get("actions"), document.get("triggers")
    if (not isinstance(actions, list) or len(actions) != 1
            or not isinstance(triggers, dict) or len(triggers) != 1
            or document.get("conditions") != {}
            or document.get("expressions") != {}
            or not isinstance(document.get("settings"), list)):
        return None, "native_one_time_reference_structure_unverified"
    action = actions[0]
    if (not isinstance(action, dict) or str(action.get("id")) != "1"
            or not isinstance(action.get("value"), dict)
            or action["value"].get("method") != "getOnOffSwitch"):
        return None, "native_one_time_reference_action_unverified"
    if (triggers.get("1") is None
            or not isinstance(triggers["1"], str)
            or not triggers["1"].strip()):
        return None, "native_one_time_reference_trigger_unverified"

    rows = {}
    for row in document["settings"]:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            return None, "native_one_time_reference_settings_unverified"
        if row["name"] in rows or row.get("redacted") is True:
            return None, "native_one_time_reference_settings_unverified"
        rows[row["name"]] = row
    expected = {
        "origLabel": ("text", None),
        "tCapab1": ("enum", "Certain Time (and optional date)"),
        "time1": ("enum", "A specific time"),
        "atTime1": ("time", None),
        "actType.1": ("enum", "switchActs"),
        "onOff.1": ("bool", None),
        "onOffSwitch.1": ("capability.switch", None),
    }
    if not expected.keys() <= rows.keys():
        return None, "native_one_time_reference_fields_missing"
    for name, (kind, value) in expected.items():
        row = rows[name]
        if row.get("type") != kind or (value is not None and row.get("value") != value):
            return None, "native_one_time_reference_fields_invalid"
    subtype = rows.get("actSubType.1")
    if subtype is not None and (
        subtype.get("type") != "enum" or subtype.get("value") != "getOnOffSwitch"
    ):
        return None, "native_one_time_reference_action_unverified"
    # Reject extra date selectors rather than silently dropping information
    # about a native date constraint we have not learnt to compile.
    if any(name.startswith(("date", "atDate", "time", "tCapab", "actType", "actSubType",
                            "onOff", "onOffSwitch")) and name not in {
                                "time1", "tCapab1", "atTime1", "actType.1",
                                "actSubType.1", "onOff.1", "onOffSwitch.1",
                            } for name in rows):
        return None, "native_one_time_reference_extra_fields"
    actual_time = rows["atTime1"].get("value")
    if not isinstance(actual_time, str) or not _DATETIME.fullmatch(actual_time):
        return None, "native_one_time_reference_not_dated"
    try:
        date = datetime.fromisoformat(actual_time)
    except ValueError:
        return None, "native_one_time_reference_not_dated"
    if date.tzinfo is not None:
        return None, "native_one_time_reference_timezone_format_unverified"
    label = rows["origLabel"].get("value")
    match = _ONETIME_NAME.fullmatch(label) if isinstance(label, str) else None
    if not match or match.group("date") != date.date().isoformat() or match.group(
        "clock"
    ) != date.strftime("%H:%M"):
        return None, "native_one_time_reference_label_mismatch"
    off = rows["onOff.1"].get("value")
    if off not in (False, True, "false", "true"):
        return None, "native_one_time_reference_action_unverified"
    devices = rows["onOffSwitch.1"].get("device_ids")
    if (rows["onOffSwitch.1"].get("multiple") is not True
            or not isinstance(devices, list) or not devices
            or any(not isinstance(v, str) or not _VALID_ID.fullmatch(v)
                   for v in devices)):
        return None, "native_one_time_reference_action_unverified"
    return {"id": rule_id, "timeFormat": actual_time}, ""


def _unique_real_wall_clock(when: datetime) -> bool:
    """Reject DST gaps and repeated local hours unsupported by native ISO."""
    if when.tzinfo is None:
        return False
    if when.replace(fold=0).utcoffset() != when.replace(fold=1).utcoffset():
        return False
    try:
        return when.astimezone(timezone.utc).astimezone(when.tzinfo) == when
    except (OverflowError, ValueError):
        return False


def compile_native_one_time_switch(
    *, guide: Any, schema_reply: Any, parent: Any,
    reference_document: Any, name: str, device_id: int,
    command: str, scheduled_at: datetime, hub_now: datetime,
) -> NativeOneTimeCandidate:
    """Return an offline candidate, never executable authority.

    Generic switch=off means Internet blocked only after an independent
    Internet-room device identity/command check performed by the caller.
    The reference can be any already-persisted, genuinely dated, healthy
    one-time Switch rule on this installed native server, not a guessed
    template or a recurring 22:00 rule.
    """
    gaps: list[str] = []
    if (not isinstance(hub_now, datetime) or hub_now.tzinfo is None
            or not isinstance(scheduled_at, datetime)
            or scheduled_at.tzinfo is None
            or not hasattr(hub_now.tzinfo, "key")
            or not hasattr(scheduled_at.tzinfo, "key")
            or hub_now.tzinfo.key != scheduled_at.tzinfo.key
            or not _unique_real_wall_clock(scheduled_at)
            or scheduled_at <= hub_now
            or scheduled_at > hub_now + timedelta(days=7)):
        gaps.append("fresh_same_hub_timezone_one_time_clock_unverified")
    if (type(device_id) is not int or not 0 < device_id <= 999999999
            or command not in ("on", "off")):
        gaps.append("verified_switch_target_and_command_unavailable")
    if not isinstance(name, str) or len(name) > 200 or _ONETIME_NAME.fullmatch(name) is None:
        gaps.append("homebrain_one_time_name_unverified")
    sample, sample_gap = _source_one_time_sample(reference_document)
    if sample_gap:
        gaps.append(sample_gap)
    if gaps:
        return NativeOneTimeCandidate(None, tuple(gaps),
                                      sample["id"] if sample else None)
    assert isinstance(scheduled_at, datetime) and sample is not None
    label_match = _ONETIME_NAME.fullmatch(name)
    assert label_match is not None
    if (label_match.group("date") != scheduled_at.strftime("%Y-%m-%d")
            or label_match.group("clock") != scheduled_at.strftime("%H:%M")):
        return NativeOneTimeCandidate(None, ("one_time_name_clock_mismatch",),
                                      sample["id"])
    fields = [
        {"name": "time#", "type": "enum", "value": "A specific time"},
        {"name": "atTime#", "type": "time",
         "value": scheduled_at.strftime("%Y-%m-%dT%H:%M:%S")},
    ]
    changes = [
        {"part": "trigger", "value": {
            "capability": "Certain Time (and optional date)",
            "fields": fields,
        }},
        {"part": "action", "value": {
            "type": "switchActs",
            "subtype": "getOnOffSwitch",
            "fields": [
                {"name": "onOffSwitch.#", "type": "capability.switch",
                 "value": [str(device_id)]},
                {"name": "onOff.#", "type": "bool", "value": command == "on"},
            ],
        }},
    ]
    if not native_schedule_batch_shape_valid(changes):
        return NativeOneTimeCandidate(None, ("atomic_native_batch_invalid",),
                                      sample["id"])
    checks = assess_native_schedule_preflight(
        guide=guide, schema_reply=schema_reply, parent=parent, changes=changes,
    )
    blocking = [gap for gap in checks.gaps if gap in {
        "installed_native_contract_unverified",
        "native_create_schema_unverified",
        "native_rule_machine_parent_unverified",
        "atomic_trigger_action_shape_unverified",
    }]
    if blocking:
        return NativeOneTimeCandidate(None, tuple(blocking), sample["id"])
    # IMPORTANT: This envelope must NEVER be sent directly from the offline
    # compiler. Future runtime integration must re-run actual identity,
    # duplicate, backup, guide/schema and consent checks, then read back the
    # newly allocated rule ID without blind retry after partial failure.
    request = {
        "tool": "hub_set_rule",
        "args": {
            "operation": "create",
            "args": {
                "parent_id": parent["id"],
                "name": name,
                "changes": changes,
            },
        },
    }
    return NativeOneTimeCandidate(request, ("approved_native_write_and_readback_not_implemented",),
                                  sample["id"])


__all__ = ["NativeOneTimeCandidate", "compile_native_one_time_switch"]
