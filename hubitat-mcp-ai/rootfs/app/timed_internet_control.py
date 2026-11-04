"""Hub-resident delayed Internet control for verified Cudy Managed Devices.

The driver owns each countdown.  This module resolves only driver-attested
device IDs, sends bounded sequential MCP commands, and verifies the driver-
reported deadline.  A receipt proves reported timer state, not future firing
or physical router enforcement.  Host confirmation is mandatory for writes.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mcp_client import HubitatMCPClient, MCPToolResult, tool_succeeded

TOOL_NAME = "homebrain_timed_internet"
MANAGED_DRIVER = "Cudy Managed Device"
MAX_BATCH = 20
MAX_MINUTES = 1440
HUB_TIMEZONE = ZoneInfo("Europe/London")
_GUIDE_KEY = re.compile(r"I-HAVE-READ-THE-GUIDE-[A-Za-z0-9_-]+")
_PROTECTED = (
    "home assistant", "homeassistant", "hub c8", "hubitat", "nucbox",
    "m6ultra", "mesh", "wlan0", "router", "gateway", "openwrt",
    "bluetooth proxy", "bluetoothproxy", "zerotier", "m3000",
    "zigbee coordinator", "zwave controller",
)


@dataclass(frozen=True)
class ManagedDevice:
    id: int
    label: str

    @property
    def words(self) -> tuple[str, ...]:
        return _words(self.label)


def _words(value: str) -> tuple[str, ...]:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return tuple(w for w in words if w != "block")


def _protected(device: ManagedDevice) -> bool:
    norm = " ".join(_words(device.label))
    return any(pattern in norm for pattern in _PROTECTED)


def _data(result: MCPToolResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, MCPToolResult):
        if not tool_succeeded(result):
            raise RuntimeError("Hubitat MCP returned an error or denied this operation")
        value = result.data
    else:
        value = result
    if not isinstance(value, dict):
        raise RuntimeError("Hubitat MCP did not return a structured result")
    for key in ("result", "data", "output"):
        inner = value.get(key)
        if isinstance(inner, dict) and not any(
            field in value for field in ("devices", "results", "value", "nextCursor", "success")
        ):
            value = inner
            break
    if value.get("success") is False or value.get("error"):
        raise RuntimeError(str(value.get("error") or "Hubitat MCP reported failure")[:250])
    return value


def _attr_value(data: dict[str, Any]) -> Any:
    for key in ("value", "currentValue"):
        if key in data:
            return data[key]
    attr = data.get("attribute")
    if isinstance(attr, dict):
        return attr.get("value")
    return None


def _parsed_deadline(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip() or raw == "none":
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.replace(tzinfo=HUB_TIMEZONE)


class TimedInternetControl:
    def __init__(self, mcp: HubitatMCPClient) -> None:
        self.mcp = mcp

    async def _call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return _data(await self.mcp.call_tool(name, args))

    async def list_devices(self) -> list[ManagedDevice]:
        devices: dict[int, ManagedDevice] = {}
        cursor = ""
        seen = set()
        for _ in range(50):
            if cursor in seen:
                raise RuntimeError("Device pagination repeated a cursor; refusing partial inventory")
            seen.add(cursor)
            data = await self._call("hub_read_devices", {
                "tool": "hub_list_devices",
                "args": {"format": "summary", "labelFilter": "Block", "cursor": cursor},
            })
            page = data.get("devices")
            if not isinstance(page, list):
                raise RuntimeError("Device inventory was not returned")
            for row in page:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("label") or row.get("name") or "")
                driver = str(row.get("driver") or "")
                if driver != MANAGED_DRIVER or not label.startswith("Block "):
                    continue
                try:
                    ident = int(row.get("id"))
                    if ident <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                if ident in devices and devices[ident].label != label:
                    raise RuntimeError("Conflicting Hubitat device identity across pages")
                devices[ident] = ManagedDevice(ident, label)
            nxt = data.get("nextCursor")
            if nxt is None or str(nxt) == "":
                if data.get("hasMore") is True:
                    raise RuntimeError("Device inventory indicates unreturned pages")
                return list(devices.values())
            if not str(nxt).isdecimal():
                raise RuntimeError("Untrusted device inventory cursor")
            cursor = str(nxt)
        raise RuntimeError("Device inventory exceeds the bounded pagination limit")

    @staticmethod
    def _resolve(query: str, devices: list[ManagedDevice]) -> tuple[ManagedDevice | None, list[str]]:
        q = _words(str(query))
        if not q:
            return None, []
        exact = [d for d in devices if d.words == q]
        matches = exact or [d for d in devices if set(q).issubset(d.words)]
        if len(matches) == 1:
            return matches[0], []
        return None, [d.label for d in sorted(matches, key=lambda d: d.label)[:12]]

    def _targets(self, requested: Any, devices: list[ManagedDevice], action: str
                 ) -> tuple[list[ManagedDevice], list[dict[str, Any]]]:
        if requested is None and action == "status":
            return devices, []
        if not isinstance(requested, list) or not requested:
            return [], [{"issue": "Provide at least one device target"}]
        if not all(isinstance(q, str) and q.strip() for q in requested):
            return [], [{"issue": "Targets must be nonempty device-name strings"}]
        if len(requested) > 100:
            return [], [{"issue": "Too many targets"}]
        lowered = [x.strip().casefold() for x in requested]
        if any(x in ("all", "everything", "all devices") for x in lowered):
            if len(requested) != 1:
                return [], [{"issue": "All cannot be mixed with named devices"}]
            return [d for d in devices if not _protected(d)], []
        chosen: dict[int, ManagedDevice] = {}
        problems = []
        for query in requested:
            found, choices = self._resolve(query, devices)
            if found is None:
                problems.append({"target": query, "issue": "ambiguous or unmatched",
                                 "options": choices})
            elif _protected(found) and action != "status":
                problems.append({"target": query, "issue": "protected network or hub device; refused"})
            else:
                chosen[found.id] = found
        return list(chosen.values()), problems

    async def _guide_key(self) -> str:
        response = await self.mcp.call_tool(
            "hub_get_tool_guide", {"section": "hub_admin_write_devices"})
        if isinstance(response, MCPToolResult) and not tool_succeeded(response):
            raise RuntimeError("Hubitat device-write guide was refused")
        text = (response.text if isinstance(response, MCPToolResult) else str(response))
        data = response.data if isinstance(response, MCPToolResult) else response
        match = _GUIDE_KEY.search(text + "\n" + str(data))
        if match is None:
            raise RuntimeError("Hubitat device-write acknowledgement key was not returned")
        return match.group(0)

    async def _attribute(self, ident: int, name: str) -> Any:
        response = await self._call("hub_read_devices", {
            "tool": "hub_get_device_attribute",
            "args": {"deviceId": str(ident), "attribute": name},
        })
        return _attr_value(response)

    async def _read_state(self, device: ManagedDevice) -> tuple[int | None, str | None]:
        mins = await self._attribute(device.id, "timedBlockMins")
        at = await self._attribute(device.id, "timedBlockAt")
        if isinstance(mins, bool):
            return None, None
        try:
            integer = int(mins)
            if str(mins).strip() not in (str(integer), str(float(integer))):
                return None, None
        except (ValueError, TypeError):
            return None, None
        return integer, at if isinstance(at, str) else None

    async def _write_batch(
        self, selected: list[ManagedDevice], action: str, minutes: int | None
    ) -> tuple[dict[int, str], set[int]]:
        failures: dict[int, str] = {}
        issued: set[int] = set()
        name = {"block_in": "blockInMinutes", "allow_for": "allowForMinutes",
                "cancel": "cancelTimedBlock"}[action]
        key = await self._guide_key()
        for offset in range(0, len(selected), MAX_BATCH):
            subset = selected[offset:offset + MAX_BATCH]
            commands = []
            for device in subset:
                item: dict[str, Any] = {"deviceId": str(device.id), "command": name}
                if minutes is not None:
                    item["parameters"] = [str(minutes)]
                commands.append(item)
            try:
                result = await self._call("hub_manage_devices", {
                    "tool": "hub_call_device_command",
                    "args": {"commands": commands, "bestPracticeKey": key},
                })
                rows = result.get("results")
                if not isinstance(rows, list) or len(rows) != len(subset):
                    raise RuntimeError("Missing or incomplete per-device command results")
                for device, row in zip(subset, rows):
                    if not isinstance(row, dict) or row.get("success") is not True:
                        failures[device.id] = "Device command not acknowledged"
                    elif row.get("deviceId") is not None and str(row["deviceId"]) != str(device.id):
                        failures[device.id] = "Command result identity mismatch"
                    else:
                        issued.add(device.id)
                for failed_id in result.get("failedDeviceIds") or []:
                    ident = int(failed_id)
                    if ident in [d.id for d in subset]:
                        issued.discard(ident)
                        failures[ident] = "Device command reported a partial failure"
            except Exception:
                # A timeout is an UNKNOWN write outcome, never proof nothing happened.
                for device in subset:
                    failures[device.id] = "Command outcome unknown or rejected; inspect hub before retrying"
                break
        return failures, issued

    async def handle(self, args: dict[str, Any]) -> MCPToolResult:
        action = args.get("action")
        if action not in {"block_in", "allow_for", "cancel", "status"}:
            return self._receipt(args, {"success": False, "error": "Unknown action"})
        minutes = args.get("minutes")
        if action in {"block_in", "allow_for"}:
            if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= MAX_MINUTES:
                return self._receipt(args, {"success": False, "error": "Minutes must be an integer from 1 to 1440"})
        else:
            minutes = None
        try:
            devices = await self.list_devices()
            selected, problems = self._targets(args.get("targets"), devices, action)
            if problems:
                return self._receipt(args, {
                    "success": False, "status": "needs_clarification", "problems": problems,
                })
            if not selected:
                return self._receipt(args, {"success": False, "error": "No eligible managed Block devices"})
            if action == "status":
                pending = []
                unknown = []
                for device in selected:
                    mins, at = await self._read_state(device)
                    if mins is None or at is None:
                        unknown.append({"id": device.id, "label": device.label})
                    elif mins > 0 and _parsed_deadline(at) is not None:
                        pending.append({"id": device.id, "label": device.label,
                                        "minutes_left_reported": mins, "fires_at": at})
                return self._receipt(args, {
                    "success": not unknown, "action": action, "pending": pending,
                    "unverified": unknown, "checked": len(selected),
                })
            started = datetime.now(HUB_TIMEZONE)
            failed, issued = await self._write_batch(selected, action, minutes)
            verified: list[dict[str, Any]] = []
            unverified: list[dict[str, Any]] = []
            for device in selected:
                if device.id not in issued:
                    continue
                try:
                    mins, at = await self._read_state(device)
                except Exception:
                    mins, at = None, None
                if action == "cancel":
                    valid = mins == 0 and at == "none"
                else:
                    deadline = _parsed_deadline(at)
                    now = datetime.now(HUB_TIMEZONE)
                    expected = started + timedelta(minutes=minutes)
                    valid = (
                        mins is not None and 0 < mins <= minutes
                        and deadline is not None and
                        abs((deadline - expected).total_seconds()) <= 120
                        and deadline > now
                    )
                if valid:
                    item = {"id": device.id, "label": device.label}
                    if action != "cancel":
                        item.update({"fires_at": at, "minutes_left_reported": mins})
                    verified.append(item)
                else:
                    unverified.append({"id": device.id, "label": device.label,
                                       "reason": "Driver deadline or timer state did not verify"})
            return self._receipt(args, {
                "success": not failed and not unverified and len(verified) == len(selected),
                "verified": bool(verified) and not failed and not unverified
                            and len(verified) == len(selected),
                "action": action, "confirmed": verified, "minutes": minutes,
                "failed": [{"id": d.id, "label": d.label, "reason": failed[d.id]}
                           for d in selected if d.id in failed],
                "unverified": unverified,
                "verification_scope": "driver-reported timer attributes, not future firing or router enforcement",
            })
        except Exception as exc:
            return self._receipt(args, {"success": False, "error": str(exc)[:250]})

    @staticmethod
    def _receipt(arguments: dict[str, Any], data: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(
            name=TOOL_NAME, arguments=dict(arguments), raw={},
            text=str(data), data=data, is_error=data.get("success") is not True,
        )


_TIMED_BLOCK_PHRASE = re.compile(
    r"^(?:please\s+)?(?:block|restrict|disable)\s+"
    r"(?:internet\s+(?:for\s+)?)?(?P<target>.+?)\s+"
    r"(?:in|after)\s+(?P<minutes>\d+)\s*"
    r"(?P<unit>minutes?|mins?|hours?|hrs?)\s*[.!]?$", re.I,
)
_ALLOW_FOR_PHRASE = re.compile(
    r"^(?:please\s+)?allow\s+(?:internet\s+(?:for\s+)?)?"
    r"(?P<target>.+?)\s+for\s+(?P<minutes>\d+)\s*"
    r"(?P<unit>minutes?|mins?|hours?|hrs?)"
    r"\s+(?:then\s+block(?:\s+it)?|before\s+blocking(?:\s+it)?)\s*[.!]?$", re.I,
)


def timed_internet_intent(prompt: str) -> dict[str, Any] | None:
    """Exact, bounded Internet-timer grammar, not an effect/authority classifier.

    Host mutation authorization and the sensitive-write confirmation gate
    remain independent of this optional deterministic routing.
    """
    value = " ".join(str(prompt or "").split())
    found = _TIMED_BLOCK_PHRASE.fullmatch(value)
    action = "block_in"
    if found is None:
        found = _ALLOW_FOR_PHRASE.fullmatch(value)
        action = "allow_for"
    if found is None:
        return None
    target = found.group("target").strip(" ,.-")
    # Explicitly constrained to one natural-language device; mixed actions
    # must not become an unintended partial single-target write.
    if not target or re.search(r"\b(?:and then|and also)\b", target, re.I):
        return None
    minutes = int(found.group("minutes"))
    if found.group("unit").casefold().startswith(("hour", "hr")):
        minutes *= 60
    if minutes < 1 or minutes > MAX_MINUTES:
        return None
    return {"action": action, "targets": [target], "minutes": minutes}
