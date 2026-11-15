"""Fresh native-source verification of bridge-backed component LIGHTS.

A Hubitat component's "virtual" inventory protocol does NOT by itself mean
that its light is a software-only switch. It can be a child endpoint exposed
by a physical lighting bridge. Conversely, a parentDeviceId and the word
"Light" do not establish a safe bridge: only a strict child/parent relationship
grounded in new original MCP receipts may qualify.

This module performs READ-ONLY source checks. It never selects, proposes,
approves or sends a device command, and never treats model prose as evidence.
"""
from __future__ import annotations

import asyncio
import json
import re
import time

from mcp import MCPError, redact
from routine_action_fastpath import _normal, _original

# Generic native *lighting* component families, not particular device IDs,
# household labels, bridge brands, rooms, or model-generated aliases.
_COMPONENT_DIMMER = re.compile(
    r"\bcomponent\b.*\b(?:dimmer|light|bulb)\b", re.IGNORECASE,
)
_BRIDGE_ROLE = re.compile(r"\b(?:bridge|lighting gateway)\b", re.IGNORECASE)
_PARENT_SENSITIVE_ROLE = re.compile(
    r"\b(?:internet|network|router|vpn|block|security|alarm|lock|"
    r"thermostat|heating|boiler|hvac|camera|cctv|garage|door|gate|"
    r"gas|water|pump|freezer|fridge|oven|power policy|mesh)\b",
    re.IGNORECASE,
)
_PHYSICAL_PARENT_PROTOCOLS = frozenset({"matter", "zigbee", "z-wave", "zwave"})


def _target_inventory_rows(candidate: dict, receipts: list[dict]) -> list[dict]:
    identifier = candidate.get("device_id") if isinstance(candidate, dict) else None
    if not isinstance(identifier, str) or not identifier:
        return []
    found = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("name") != "hub_list_devices":
            continue
        doc = _original(row)
        if not doc or not isinstance(doc.get("devices"), list):
            continue
        for item in doc["devices"]:
            if (isinstance(item, dict)
                    and str(item.get("id", "")).strip() == identifier):
                found.append(item)
    return found


def component_parent_id(candidate: dict | None,
                        receipts: list[dict]) -> str | None:
    """Find the original native parent relationship of a light-only dimmer.

    The candidate MUST have already passed routine_candidate(), which proves
    the original imperative, a fresh verified child detail, advertised native
    command and opposite switch state. This does not authorize a write.
    """
    if not isinstance(candidate, dict) or not isinstance(receipts, list):
        return None
    identifier = candidate.get("device_id")
    label = candidate.get("label")
    if (not isinstance(identifier, str) or not identifier
            or not isinstance(label, str) or not label
            or candidate.get("command") not in ("on", "off")):
        return None
    # Exactly one original child details receipt at the current command ID.
    details = [
        _original(row) for row in receipts
        if isinstance(row, dict)
        and row.get("name") == "hub_get_device"
        and isinstance(row.get("arguments"), dict)
        and str(row["arguments"].get("deviceId", "")).strip() == identifier
    ]
    if len(details) != 1 or not isinstance(details[0], dict):
        return None
    child = details[0]
    caps = child.get("capabilities")
    if (str(child.get("id", "")).strip() != identifier
            or _normal(str(child.get("label", ""))) != _normal(label)
            or not isinstance(caps, list)
            or not all(isinstance(x, str) for x in caps)
            or not {"Light", "Switch", "SwitchLevel"}.issubset(set(caps))
            or "Outlet" in caps):
        return None
    matches = _target_inventory_rows(candidate, receipts)
    if not matches:
        return None
    parents = set()
    for item in matches:
        parent = item.get("parentDeviceId")
        driver = item.get("driver")
        if (str(item.get("protocol", "")).casefold() != "virtual"
                or not isinstance(driver, str)
                or not _COMPONENT_DIMMER.search(driver)
                or item.get("disabled") is True
                or _normal(str(item.get("label", ""))) != _normal(label)
                or type(parent) not in (str, int)):
            return None
        parent_id = str(parent).strip()
        if (not parent_id.isascii() or not parent_id.isdigit()
                or len(parent_id) > 12 or parent_id == identifier):
            return None
        parents.add(parent_id)
    return next(iter(parents)) if len(parents) == 1 else None


def verified_physical_bridge_parent(
    candidate: dict | None, receipts: list[dict],
) -> bool:
    """Require current original parent detail AND matching physical inventory.

    A guessed parent name, child relationship alone, cached source or arbitrary
    virtual parent never passes this class. The parent name is only evidence of
    bridge role after native protocol, matching IDs and labels are checked.
    """
    parent_id = component_parent_id(candidate, receipts)
    if parent_id is None:
        return False
    parent_reads = [
        row for row in receipts
        if isinstance(row, dict) and row.get("name") == "hub_get_device"
        and isinstance(row.get("arguments"), dict)
        and str(row["arguments"].get("deviceId", "")).strip() == parent_id
    ]
    others = [
        row for row in receipts
        if isinstance(row, dict) and row.get("name") == "hub_get_device"
        and isinstance(row.get("arguments"), dict)
        and str(row["arguments"].get("deviceId", "")).strip()
        not in (parent_id, candidate["device_id"])
    ]
    if len(parent_reads) != 1 or others:
        return False
    parent_doc = _original(parent_reads[0])
    if (not isinstance(parent_doc, dict)
            or str(parent_doc.get("id", "")).strip() != parent_id
            or parent_doc.get("disabled") is True):
        return False
    parent_label = parent_doc.get("label")
    if (not isinstance(parent_label, str) or not parent_label.strip()
            or "\n" in parent_label):
        return False
    parent_inventory = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("name") != "hub_list_devices":
            continue
        arguments = row.get("arguments")
        if (not isinstance(arguments, dict)
                or arguments.get("labelFilter") != parent_label):
            continue
        doc = _original(row)
        if (not isinstance(doc, dict)
                or doc.get("labelFilter") != parent_label
                or not isinstance(doc.get("devices"), list)
                or type(doc.get("count")) is not int
                or type(doc.get("total")) is not int
                or doc["count"] != doc["total"]
                or doc["count"] != len(doc["devices"])
                or doc.get("hasMore") is True
                or doc.get("nextCursor") not in (None, "")):
            return False
        matches = [item for item in doc["devices"]
                   if isinstance(item, dict)
                   and str(item.get("id", "")).strip() == parent_id]
        if len(matches) != 1:
            return False
        parent_inventory.append(matches[0])
    if len(parent_inventory) != 1:
        return False
    row = parent_inventory[0]
    if (row.get("disabled") is True
            or _normal(str(row.get("label", ""))) != _normal(parent_label)
            or str(row.get("protocol", "")).casefold()
            not in _PHYSICAL_PARENT_PROTOCOLS
            or row.get("parentDeviceId") not in (None, "")):
        return False
    # A native physical bridge record, not a generic virtual/simulated hub.
    driver = str(row.get("driver") or "")
    parent_description = " ".join([
        parent_label, driver, str(parent_doc.get("name") or "")
    ])
    if ("virtual" in driver.casefold()
            or _PARENT_SENSITIVE_ROLE.search(parent_description)):
        return False
    return bool(_BRIDGE_ROLE.search(parent_description))


def _original_read_receipt(name: str, args: dict, response: dict | None,
                           elapsed_ms: int, *, error: str = "") -> dict:
    record = {
        "name": name, "arguments": args, "success": False,
        "elapsed_ms": elapsed_ms,
        "result_kind": "tool_result",
        "read_only": True, "operation_executed": response is not None,
        "client_component_parent_verification_read": True,
    }
    if response is not None:
        text = json.dumps(redact(response), ensure_ascii=False, default=str)
        record["response"] = text
        record["response_characters"] = len(text)
        record["success"] = (response.get("isError") is not True)
    if error:
        record["error"] = str(redact(error))[:180]
    return record


async def read_component_parent_evidence(mcp, parent_id: str,
                                         *, budget_seconds: float = 4.0,
                                         ) -> list[dict]:
    """Max two current-request native READS; fail closed on any error.

    The original device ID was already selected by the model. Only the
    source-declared parent ID is queried, with no native write possible here.
    """
    if (not isinstance(parent_id, str) or not parent_id.isascii()
            or not parent_id.isdigit() or len(parent_id) > 12):
        return []
    start = time.monotonic()
    collected = []
    async def fetch(name: str, args: dict, timeout: float):
        begin = time.monotonic()
        try:
            raw = await asyncio.wait_for(mcp.call(name, args), timeout=timeout)
            record = _original_read_receipt(
                name, args, raw, round((time.monotonic()-begin)*1000))
        except (MCPError, asyncio.TimeoutError, ValueError) as exc:
            record = _original_read_receipt(
                name, args, None, round((time.monotonic()-begin)*1000),
                error=str(exc))
        collected.append(record)
        return _original(record)

    parent = await fetch("hub_get_device", {"deviceId": parent_id},
                         timeout=min(2.0, max(0.1, budget_seconds)))
    if (not isinstance(parent, dict)
            or str(parent.get("id", "")).strip() != parent_id
            or not isinstance(parent.get("label"), str)
            or not parent["label"].strip()):
        return collected
    remaining = budget_seconds - (time.monotonic() - start)
    if remaining < 0.5:
        return collected
    await fetch(
        "hub_list_devices",
        {"format": "summary", "labelFilter": parent["label"]},
        timeout=min(2.0, remaining),
    )
    return collected
