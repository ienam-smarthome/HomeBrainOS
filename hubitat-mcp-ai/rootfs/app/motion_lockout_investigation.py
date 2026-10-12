"""Bounded, read-only history preflight for manual-OFF motion lockouts.

A configuration / device-health snapshot does not establish whether a lockout
activated during a particular historical event. Read an exact light history,
then local journal evidence for relevant controllers and configured motion
sensors, plus source-scoped application logs. All unavailable histories remain
unverified, never silently treated as evidence that a timer did or did not run.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import re
import time
from typing import Any

from causal_rule_decision_context import configuration_text

_APP_ID = re.compile(r"\b(?:app|rule)\s*(?:#|id\s*)?(\d{3,6})\b", re.I)
_LOCKOUT = re.compile(r"\b(?:lock[- ]?out|inhibit(?:ion|ed)?|suppres(?:s|sed|sion))\b", re.I)
_MANUAL_OFF = re.compile(
    r"\b(?:manual(?:ly)?|button|switch|physical)\b.{0,100}?\b(?:off|motion)"
    r"|\b(?:off|motion)\b.{0,100}?\b(?:manual(?:ly)?|button|physical)\b",
    re.I,
)
_INVESTIGATE = re.compile(
    r"\b(?:investigat(?:e|ion)|why|whether|did|check|verify|trace|diagnos(?:e|is))\b",
    re.I,
)


def is_motion_lockout_investigation(prompt: str) -> bool:
    text = str(prompt or "")
    return bool(
        _LOCKOUT.search(text) and _MANUAL_OFF.search(text)
        and _INVESTIGATE.search(text)
    )


def _time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None


def _label(item: dict[str, Any]) -> str:
    return str(item.get("label") or item.get("name") or "").strip()


def _room(item: dict[str, Any]) -> str:
    return str(item.get("room") or "").strip()


def _attribute(item: dict[str, Any], attribute: str) -> bool:
    raw = item.get("attributes") or {}
    names = (
        list(raw.keys()) if isinstance(raw, dict)
        else [str(x.get("name") or "") if isinstance(x, dict) else str(x)
              for x in raw] if isinstance(raw, list) else []
    )
    capabilities = [
        re.sub(r"[^a-z]", "", str(c).casefold())
        for c in (item.get("capabilities") or [])
    ]
    return attribute.casefold() in {s.casefold() for s in names} or {
        "switch": "switch", "motion": "motionsensor", "pushed": "pushablebutton",
    }.get(attribute, "") in capabilities


def resolve_named_light(prompt: str, identities: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = " ".join(str(prompt).casefold().split())
    matches = []
    for item in identities:
        if not isinstance(item, dict) or not _attribute(item, "switch"):
            continue
        label = _label(item)
        if len(label) < 7 or not str(item.get("id") or "").isdecimal():
            continue
        if re.search(r"(?<!\w)" + re.escape(label.casefold()) + r"(?!\w)", normalized):
            matches.append(item)
    if not matches:
        return None
    matches.sort(key=lambda row: -len(_label(row)))
    if (len(matches) > 1
            and len(_label(matches[0])) == len(_label(matches[1]))):
        return None
    return matches[0]


def last_observed_off(subject: dict[str, Any]) -> datetime | None:
    temporal = subject.get("temporalAnalysis") or {}
    candidates: list[datetime] = []
    for row in (temporal.get("observedIntervals") or []):
        if not isinstance(row, dict):
            continue
        end = _time(row.get("end"))
        if end is not None and not row.get("clippedAtWindowEnd"):
            candidates.append(end)
    # Event-by-event fallback when the latest history cannot form ON/OFF pairs.
    for row in (subject.get("correlationEvents") or
                subject.get("observedEvents") or []):
        if isinstance(row, dict) and str(row.get("value") or "").casefold() == "off":
            stamp = _time(row.get("date") or row.get("timestamp"))
            if stamp:
                candidates.append(stamp)
    return max(candidates) if candidates else None


def _candidate_devices(
    identities: list[dict[str, Any]], light: dict[str, Any], config: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    room = _room(light).casefold()
    sensors, buttons = [], []
    for row in identities:
        if not isinstance(row, dict) or str(row.get("id") or "") == str(light.get("id")):
            continue
        name = _label(row)
        if not name or not str(row.get("id") or "").isdecimal():
            continue
        same_room = bool(room and _room(row).casefold() == room)
        exact_config_name = bool(config and name.casefold() in config)
        if _attribute(row, "motion") and (exact_config_name or same_room):
            sensors.append((0 if exact_config_name else 1, row))
        if (
            (_attribute(row, "pushed") or re.search(r"\b(?:dimmer|button|remote)\b", name, re.I))
            and (same_room or exact_config_name)
        ):
            buttons.append((0 if exact_config_name else 1, row))
    sensors.sort(key=lambda x: (x[0], _label(x[1]).casefold()))
    buttons.sort(key=lambda x: (x[0], _label(x[1]).casefold()))
    return [row for _, row in sensors[:5]], [row for _, row in buttons[:3]]


def _sanitized_rows(data: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    output = []
    for row in (data.get("events") or [])[:limit]:
        if not isinstance(row, dict) or row.get("stream") != "events":
            continue
        output.append({
            "value": str(row.get("value") or "")[:32],
            "attribute": str(row.get("attribute") or "")[:32],
            "observedAt": str(row.get("observed_at") or ""),
            "timestampBasis": str(row.get("timestamp_basis") or "unknown"),
        })
    return output


async def prefetch_motion_lockout(
    host: Any, prompt: str, *, catalog: Any, messages: list[dict[str, Any]],
) -> bool:
    """Gather focal sequence or explicitly report which evidence was unavailable.

    NEVER claims 'manual OFF', 'lockout engaged', 'lockout failed', or 'rule
    executed' without a contemporaneous source confirming that conclusion.
    """
    if not is_motion_lockout_investigation(prompt):
        return False
    started = time.monotonic()
    try:
        identities = await host.mcp.get_device_identities()
    except Exception:
        identities = []
    light = resolve_named_light(prompt, identities if isinstance(identities, list) else [])
    app_match = _APP_ID.search(prompt)
    app_id = app_match.group(1) if app_match else ""
    findings: dict[str, Any] = {
        "status": "incomplete", "appId": app_id,
        "subject": _label(light) if light else "",
        "lightDeviceId": str(light.get("id")) if light else "",
        "manualOffVerified": False,
        "lockoutExecutionVerified": False,
        "lockoutFailureVerified": False,
        "coverageComplete": False,
        "notEvidenceOfFailure": True,
        "readOnly": True,
        "sources": [],
    }
    subject_data: dict[str, Any] = {}
    tool = catalog.declared_tool("homebrain_device_history")
    if light and tool is not None:
        args = {
            "name": _label(light), "attribute": "switch", "limit": 50,
            "_resolved_target": dict(light),
            "_include_command_provenance": True,
        }
        result = await host.executor.execute(
            "homebrain_device_history", args,
            tool=tool, supports_live_claim=True,
            evidence_kind="deterministic_device_event_history",
        )
        if result.success and result.result is not None:
            subject_data = (
                result.result.data if isinstance(result.result.data, dict) else {}
            )
        findings["sources"].append({
            "source": "bounded-light-device-history", "success": bool(result.success),
            "observedIntervals": len(
                ((subject_data.get("temporalAnalysis") or {}).get("observedIntervals") or [])
            ),
        })
    off = last_observed_off(subject_data)
    if off is not None:
        findings["focalOff"] = off.isoformat()
    config_search = ""
    async def remote(gateway: str, leaf: str, args: dict[str, Any]) -> dict[str, Any] | None:
        try:
            result = await host.mcp.call_tool(gateway, {"tool": leaf, "args": args})
            if not host._tool_succeeded(result):
                return None
            return result.data if isinstance(result.data, dict) else None
        except Exception:
            return None
    if app_id:
        config = await remote(
            "hub_read_apps_code", "hub_get_app_config",
            {"appId": app_id, "includeSettings": False},
        )
        if config:
            _, config_search = configuration_text(config)
        findings["sources"].append({
            "source": "present-day-app-configuration", "appId": app_id,
            "available": config is not None,
            "historicalExecutionProven": False,
        })
    if off:
        # Never reinterpret a specific requested exact timestamp as "latest".
        first = off - timedelta(seconds=20)
        last = min(off + timedelta(seconds=195), datetime.now(timezone.utc))
        if last <= first:
            last = off + timedelta(seconds=1)
        findings["window"] = {
            "since": first.isoformat(), "until": last.isoformat(),
            "threeMinuteWindowElapsed": datetime.now(timezone.utc) >= (
                off + timedelta(minutes=3)
            ),
        }
        if app_id:
            logs = await remote("hub_read_diagnostics", "hub_get_logs", {
                "appId": app_id, "since": first.isoformat(),
                "until": last.isoformat(), "limit": 60,
            })
            findings["sources"].append({
                "source": "bounded-app-execution-logs", "appId": app_id,
                "readSucceeded": logs is not None,
                "returnedRows": (
                    len(logs.get("logs")) if isinstance(logs, dict)
                    and isinstance(logs.get("logs"), list) else None
                ),
                "emptyDoesNotProveNoExecution": True,
            })
        archive = getattr(host, "historical_journal", None)
        if (
            light and archive is not None
            and getattr(archive, "enabled", False)
            and getattr(archive, "_started", False)
        ):
            sensors, buttons = _candidate_devices(
                identities if isinstance(identities, list) else [],
                light, config_search,
            )
            targets = [(light, "switch", "light")]
            targets += [(item, "motion", "sensor") for item in sensors]
            targets += [(item, "pushed", "button") for item in buttons]
            async def lookup(device: dict[str, Any], attr: str, kind: str):
                try:
                    res = await asyncio.to_thread(
                        archive.query, since=first.isoformat(),
                        until=last.isoformat(),
                        device_id=str(device.get("id")), attribute=attr, limit=100,
                    )
                    return {
                        "source": "Historical Journal", "kind": kind,
                        "deviceId": str(device.get("id")),
                        "label": _label(device), "attribute": attr,
                        "observations": _sanitized_rows(res),
                        "returnedRows": res.get("count"),
                        "gapCount": len(res.get("gaps") or []),
                        "timestampCompletenessVerified": False,
                    }
                except Exception:
                    return {
                        "source": "Historical Journal", "kind": kind,
                        "deviceId": str(device.get("id")),
                        "label": _label(device), "available": False,
                    }
            journal = await asyncio.gather(*(
                lookup(device, attr, kind) for device, attr, kind in targets
            ))
            findings["journal"] = journal
            findings["sources"].append({
                "source": "Historical Journal",
                "deviceScopesChecked": len(journal),
                "retentionCoverageVerified": False,
            })
            # A near-synchronous button event is association, not proof that
            # the OFF command was caused by that device.
            related = []
            for item in journal:
                if item.get("kind") != "button":
                    continue
                for event in item.get("observations") or []:
                    stamp = _time(event.get("observedAt"))
                    if stamp is not None and abs(
                        (stamp - off).total_seconds()
                    ) <= 2:
                        related.append({
                            "deviceId": item.get("deviceId"),
                            "label": item.get("label"),
                            "deltaMs": round((stamp-off).total_seconds()*1000),
                            "timestampBasis": event.get("timestampBasis"),
                        })
            findings["nearbyButtonEvents"] = related[:8]
            findings["manualOffVerified"] = False
    findings["status"] = (
        "partial-focal-sequence" if off else "no-focal-off-observed"
    )
    host.evidence.record(
        "homebrain_motion_lockout_investigation",
        {"appId": app_id, "lightDeviceId": findings["lightDeviceId"]},
        success=True, elapsed_ms=round((time.monotonic()-started)*1000),
        summary="Read-only manual-off lockout sequence investigation",
        supports_live_claim=bool(off),
        evidence_kind="bounded_motion_lockout_evidence",
        effect="read", mutates=False,
        details=findings,
    )
    messages.append({
        "role": "user",
        "content": (
            "HOST LOCKOUT HISTORICAL EVIDENCE (read-only):\n"
            + json.dumps(findings, ensure_ascii=False, default=str)
            + "\nExplain focal OFF, button evidence, motion and subsequent ON "
            "events, configured lockout versus actual execution, and data "
            "coverage separately. Never infer lockout success just because "
            "there was no ON, or claim manual OFF solely from a physical "
            "light-state event. If history is missing, say investigation "
            "is incomplete rather than replacing it with device health."
        ),
    })
    return True


__all__ = [
    "is_motion_lockout_investigation", "resolve_named_light",
    "last_observed_off", "prefetch_motion_lockout",
]
