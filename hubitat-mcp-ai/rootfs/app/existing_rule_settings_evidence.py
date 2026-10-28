"""Bounded current-value evidence for installed Hubitat automation configuration.

This reader never claims a *complete* Rule Machine action tree. It projects
only explicitly allowlisted fields from ID-verified current app settings into
typed, redacted, source-qualified receipts; page HTML and arbitrary names,
credentials, URLs and app-specific strings remain private.

Indexed RM settings establish *field values*, not complete compiled actions
or successful runtime execution. The existing_rule_verification completion gate
therefore deliberately does not treat these partial receipts as full logic proof.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from mcp_client import tool_succeeded

_INDEXED = re.compile(r"^(delayMinute|cancelAct|onOffSwitch|onOff)\.([1-9]\d{0,3})$")
_CONTROLLER_DURATION = re.compile(
    r"^(?:inactive|motionInactive|motionOff|backupOff|verifyAfterOff)"
    r"[A-Za-z]{0,36}(?:Seconds|Minutes|Delay)$"
)
_IDENT = re.compile(r"^[1-9]\d{0,8}$")
_MAX_SETTINGS = 384
_MAX_FACTS = 28
_MAX_DEVICE_IDS = 8
# Explicit Hubitat settings keys expressing device selections, not arbitrary
# integers in labels, schedules, URL strings or other config fields.
_SENSOR_REFERENCE_KEYS = frozenset({
    "motionSensors", "motionSensor", "keepOnSensors", "keepOnSensor",
    "contactSensors", "contactSensor", "presenceSensors", "presenceSensor",
    "temperatureSensors", "temperatureSensor", "humiditySensors",
    "humiditySensor", "illuminanceSensors", "illuminanceSensor",
})
_MAX_REFERENCE_GROUPS = 8


def _selected_sensor_ids(value: Any) -> list[str]:
    """Extract native device-selection identifiers, never numbers from labels.

    A Hubitat selection is a map keyed by device IDs, a list of IDs, or a
    bounded list of objects with an explicit id. Arbitrary strings that look
    like Groovy names are never scraped for digits.
    """
    raw: list[Any]
    if isinstance(value, dict):
        raw = list(value.keys())[:32]
    elif isinstance(value, (list, tuple)):
        raw = list(value)[:32]
    else:
        raw = [value]
    ids: set[str] = set()
    for row in raw:
        candidate = row.get("id") if isinstance(row, dict) else row
        if (type(candidate) in (str, int)
                and _IDENT.fullmatch(str(candidate))):
            ids.add(str(candidate))
    return sorted(ids, key=int)[:_MAX_DEVICE_IDS]



def _boolean(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    if type(value) is str and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def _number(value: Any, *, maximum: float) -> int | float | None:
    if type(value) in (int, float):
        parsed = float(value)
    elif isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d{1,3})?", value.strip()):
        parsed = float(value.strip())
    else:
        return None
    if not 0 <= parsed <= maximum or parsed != parsed:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def project_installed_app_settings(data: Any, expected_app_id: str) -> dict[str, Any]:
    """Extract allowlisted values, not page text or a guessed rule topology."""
    empty: dict[str, Any] = {
        "appId": expected_app_id,
        "settingsReadable": False,
        "settingsTruncated": False,
        "indexedFields": [],
        "controllerFields": [],
        "semanticFieldsValidated": False,
        "orderedActionsValidated": False,
        "conditionsValidated": False,
    }
    if not isinstance(data, dict) or data.get("success") is False:
        return empty
    app = data.get("app")
    if (not isinstance(app, dict)
            or str(app.get("id") or "") != str(expected_app_id)):
        return empty
    settings = data.get("settings")
    if not isinstance(settings, dict):
        return empty
    if len(settings) > _MAX_SETTINGS:
        # Never assert the listed actions are exhaustive if the map exceeds
        # the limit; use bounded extraction and surface truncation explicitly.
        empty["settingsTruncated"] = True
    result = dict(empty, settingsReadable=True)
    indexed: list[dict[str, Any]] = []
    controller: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    for key, value in list(settings.items())[:_MAX_SETTINGS]:
        if len(indexed) + len(controller) >= _MAX_FACTS:
            result["settingsTruncated"] = True
            break
        if not isinstance(key, str) or len(key) > 64:
            continue
        if key in _SENSOR_REFERENCE_KEYS:
            ids = _selected_sensor_ids(value)
            if ids and len(references) < _MAX_REFERENCE_GROUPS:
                references.append({"key": key, "deviceIds": ids})
            if len(ids) == _MAX_DEVICE_IDS or len(references) >= _MAX_REFERENCE_GROUPS:
                # The bounded projection does not claim to contain every
                # sensor in a large controller configuration.
                result["settingsTruncated"] = True
            continue
        index = _INDEXED.fullmatch(key)
        if index:
            family = index.group(1)
            recorded: dict[str, Any] = {"key": key}
            if family == "delayMinute":
                number = _number(value, maximum=1440)
                if number is None:
                    continue
                recorded["minutes"] = number
            elif family in ("cancelAct", "onOff"):
                parsed = _boolean(value)
                if parsed is None:
                    continue
                recorded["value"] = parsed
            else:
                # The setting is a native device selection, not proof that an
                # app actually sent an OFF command or acted on this selection.
                if not isinstance(value, dict):
                    continue
                ids = sorted({
                    str(identifier)
                    for identifier in list(value)[:32]
                    if isinstance(identifier, (int, str))
                    and _IDENT.fullmatch(str(identifier))
                }, key=int)
                if not ids:
                    continue
                recorded["deviceIds"] = ids[:_MAX_DEVICE_IDS]
                if len(ids) > _MAX_DEVICE_IDS or len(value) > 32:
                    result["settingsTruncated"] = True
            indexed.append(recorded)
            continue
        if key == "inactiveAction" and isinstance(value, str):
            if value.strip().lower() in {"off", "on", "none"}:
                controller.append({"key": key, "value": value.strip().lower()})
        elif key in {"scheduledOffEnabled", "backupOffEnabled",
                     "verifyAfterOffEnabled", "manualOverrideEnabled"}:
            flag = _boolean(value)
            if flag is not None:
                controller.append({"key": key, "value": flag})
        elif _CONTROLLER_DURATION.fullmatch(key):
            number = _number(value, maximum=10080)
            if number is not None:
                controller.append({"key": key, "numericValue": number,
                                   "unitFromKey": (
                                       "seconds" if key.endswith("Seconds")
                                       else "minutes" if key.endswith("Minutes")
                                       else "unspecified"
                                   )})
    result["indexedFields"] = indexed
    result["controllerFields"] = controller
    if references:
        result["deviceReferences"] = references
    return result


async def prefetch_installed_app_settings(
    mcp: Any,
    evidence: Any,
    *,
    app_id: str,
    available_names: set[str] | frozenset[str],
    messages: list[dict[str, str]],
) -> bool:
    """Perform one ID-scoped read with includeSettings=true; never write."""
    if not _IDENT.fullmatch(app_id) or "hub_read_apps_code" not in available_names:
        return False
    args = {"tool": "hub_get_app_config",
            "args": {"appId": app_id, "includeSettings": True}}
    started = time.monotonic()
    try:
        result = await mcp.call_tool("hub_read_apps_code", args)
        data = getattr(result, "data", None)
        good = bool(tool_succeeded(result) and isinstance(data, dict))
    except Exception:
        data, good = None, False
    projected = project_installed_app_settings(data, app_id)
    success = good and projected["settingsReadable"]
    evidence.record(
        "hub_read_apps_code", args,
        success=success, elapsed_ms=round((time.monotonic() - started) * 1000),
        summary=("ID-verified typed settings projection" if success
                 else "app settings unavailable or unmatched"),
        supports_live_claim=success,
        evidence_kind="typed_existing_rule_partial_settings",
        mutates=False, effect="read", details=projected,
    )
    if success:
        messages.append({
            "role": "user",
            "content": (
                "HOST ID-VERIFIED PARTIAL PERSISTED SETTINGS (read only)\n"
                + json.dumps(projected, ensure_ascii=False, sort_keys=True)
                + "\nThese are individually verified field values, NOT a "
                  "certified action sequence, complete trigger list, "
                  "full delay logic, controller decision branch or runtime "
                  "execution. Do not invent missing settings. Distinguish "
                  "indexed settings from compiled Rule Machine actions."
            ),
        })
    return success


__all__ = ["project_installed_app_settings", "prefetch_installed_app_settings"]
