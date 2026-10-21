"""Safe, bounded Rule Machine 5.x settings-shape interpreter.

RM indexed keys can hold typed device *references*. Their presence alone
does not identify an action target, trigger subscription or execution. This
module never returns settings values, device labels, URLs or arbitrary keys.
"""
from __future__ import annotations

import re
from typing import Any

_RM_TYPE = re.compile(r"^(?:Rule-5(?:\.\d+)?|Rule Machine(?: 5(?:\.\d+)?)?)$", re.I)
_REFERENCE_KEY = re.compile(r"^onOffSwitch\.[1-9]\d{0,4}$")
_TRIGGER_KEY = re.compile(r"^tCapab[1-9]\d{0,4}$")
_TIME_KEY = re.compile(r"^(?:startingA|endingA|selectHoursC)[1-9]\d{0,4}$")
_DEVICE_ID = re.compile(r"^[1-9]\d{1,8}$")
_MAX_KEYS = 256
_MAX_REFS = 24


def is_rule_machine_app(item: dict[str, Any] | None,
                        config: dict[str, Any] | None = None) -> bool:
    """Only a source-described RM type qualifies, never a user's label."""
    for source in (item, (config or {}).get("app")):
        if not isinstance(source, dict):
            continue
        for key in ("type", "name"):
            value = source.get(key)
            if isinstance(value, str) and _RM_TYPE.fullmatch(value.strip()):
                return True
    return False


def interpret_rm_settings(response: dict[str, Any], expected_id: str) -> dict[str, Any]:
    """Declassify only allowlisted key-family counts and numeric device IDs.

    This parser is deliberately *not* a Rule Machine action compiler. It
    surfaces weak, provenance-labelled device references for corroboration
    through the upstream device-dependent index.
    """
    empty = {
        "rmSettingsInspected": False,
        "rmSettingsShape": "unavailable",
        "rmReferenceDeviceIds": [],
        "rmKeyFamilyCounts": {"device_reference": 0, "trigger_capability": 0,
                              "time_or_schedule": 0},
        "rmActionTargetsVerified": False,
        "rmTriggerLogicVerified": False,
        "rmSettingsTruncated": False,
    }
    if not isinstance(response, dict):
        return empty
    app = response.get("app")
    if not isinstance(app, dict) or str(app.get("id") or "") != str(expected_id):
        return empty
    if response.get("success") is False or not is_rule_machine_app(None, response):
        return empty
    settings = response.get("settings")
    if not isinstance(settings, dict):
        return empty
    out = dict(empty, rmSettingsInspected=True, rmSettingsShape="rm-indexed-map")
    counts = {"device_reference": 0, "trigger_capability": 0, "time_or_schedule": 0}
    references: set[str] = set()
    for key, value in list(settings.items())[:_MAX_KEYS]:
        if not isinstance(key, str):
            continue
        if _REFERENCE_KEY.fullmatch(key):
            counts["device_reference"] += 1
            if isinstance(value, dict):
                for ident in list(value)[:_MAX_REFS]:
                    if isinstance(ident, (str, int)) and _DEVICE_ID.fullmatch(str(ident)):
                        references.add(str(ident))
        elif _TRIGGER_KEY.fullmatch(key):
            counts["trigger_capability"] += 1
        elif _TIME_KEY.fullmatch(key):
            counts["time_or_schedule"] += 1
    out["rmKeyFamilyCounts"] = counts
    out["rmReferenceDeviceIds"] = sorted(references, key=int)[:_MAX_REFS]
    out["rmSettingsTruncated"] = len(settings) > _MAX_KEYS or len(references) > _MAX_REFS
    return out


__all__ = ["is_rule_machine_app", "interpret_rm_settings"]
