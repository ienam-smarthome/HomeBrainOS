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
from decision_claim_reconciliation import reconcile_decision_claims
from focal_event_cross_source import correlate_requested_focal_sources
from focal_history_lookback import explicit_focal_history_lookback
from focal_event_provenance import (
    current_config_facts, physical_button_observations, select_focal_off,
    off_candidates,
    source_offset_for_request, explicit_british_clock_source,
)
from scoped_execution_evidence import (
    bounded_app_log_evidence, event_handler_associations, model_only_log_packet,
)
from investigation_intelligence import plan_investigation

_APP_ID = re.compile(r"\b(?:app|rule)\s*(?:#|id\s*)?(\d{3,6})\b", re.I)
_LOCKOUT = re.compile(r"\b(?:lock[- ]?out|inhibit(?:ion|ed)?|suppres(?:s|sed|sion))\b", re.I)
_MANUAL_OFF = re.compile(
    r"\b(?:manual(?:ly)?|button|switch|physical)\b.{0,100}?\b(?:off|motion)"
    r"|\b(?:off|motion)\b.{0,100}?\b(?:manual(?:ly)?|button|physical)\b",
    re.I,
)
_INVESTIGATE = re.compile(
    r"\b(?:investigat(?:e|ion)|reconstruct|correlate|why|whether|did|check|verify|trace|diagnos(?:e|is))\b",
    re.I,
)



def _lockout_app_id(prompt: str) -> str:
    """Choose the app *owning the lockout*, not a preceding button app.

    In questions naming "app 1251's OFF command" and "app 4019's lockout
    decision", the first app ID is not the target for execution logs.
    Ambiguous multiple app mentions fail closed.
    """
    matches = list(_APP_ID.finditer(str(prompt or "")))
    if len(matches) == 1:
        return matches[0].group(1)
    candidates = []
    for match in matches:
        clause = str(prompt)[match.end():match.end() + 65].split(",")[0].split(".")[0]
        if re.search(r"\block[- ]?out\b", clause, re.I):
            candidates.append(match.group(1))
    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else ""


def is_motion_lockout_investigation(prompt: str) -> bool:
    """Agree with the shared investigation goal, not just legacy phrasing."""
    contract = plan_investigation(prompt)
    if contract is not None and contract.domain == "manual_motion_lockout":
        return True
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
    """Match a unique switch identity, not its ephemeral display-state badges."""
    normalized = " ".join(str(prompt).casefold().split())
    matches: list[tuple[int, dict[str, Any]]] = []
    for item in identities:
        if not isinstance(item, dict) or not _attribute(item, "switch"):
            continue
        label = _label(item)
        if len(label) < 7 or not str(item.get("id") or "").isdecimal():
            continue
        # Labels may append live states, e.g. "Light 1 (Lights On, Motion
        # Active)". Driver name and the undecorated label are stable aliases.
        # Uniqueness is mandatory; never replace an ambiguous light by a guess.
        aliases = {
            label,
            str(item.get("name") or "").strip(),
            re.sub(r"\s*\([^()]*\)\s*$", "", label).strip(),
        }
        matched = [
            alias for alias in aliases
            if len(alias) >= 7 and re.search(
                r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)",
                normalized,
            )
        ]
        if matched:
            matches.append((max(len(name) for name in matched), item))
    if not matches:
        return None
    matches.sort(key=lambda row: -row[0])
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None
    return matches[0][1]


def completed_light_intervals(subject: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize history producer and compact evidence-receipt representations.

    The native DeviceHistoryService returns temporalAnalysis.intervals; the
    privacy-bounded evidence renderer calls the same rows observedIntervals.
    Treat either as an observed interval. A tool call succeeded even when
    no observed transitions exist, so never synthesize missing intervals.
    """
    temporal = subject.get("temporalAnalysis") or {}
    if not isinstance(temporal, dict):
        return []
    for field in ("intervals", "observedIntervals"):
        rows = temporal.get(field)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def last_observed_off(subject: dict[str, Any]) -> datetime | None:
    candidates: list[datetime] = []
    for row in completed_light_intervals(subject):
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


def focal_command_provenance(
    subject: dict[str, Any], *, off: datetime,
    tolerance_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Match independently retained command rows to an observed OFF edge.

    Command provenance identifies the source that sent a command; a producer
    named 'button 1 pushed' is not itself a separately captured hardware
    button event. Keep these epistemic levels distinct.
    """
    matched = []
    for row in subject.get("commandEvents") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("name") or "").casefold() != "command-off":
            continue
        stamp = _time(row.get("date") or row.get("timestamp"))
        if stamp is None:
            continue
        delta = (off - stamp).total_seconds()
        if delta < 0 or delta > tolerance_seconds:
            continue
        producer = row.get("producedBy") or {}
        if not isinstance(producer, dict):
            producer = {}
        matched.append({
            "command": "off",
            "commandAt": stamp.isoformat(),
            "stateAt": off.isoformat(),
            "commandPrecedesStateMs": round(delta * 1000, 1),
            "producer": {
                "id": str(producer.get("id") or ""),
                "type": str(producer.get("type") or ""),
                "label": str(producer.get("label") or "")[:100],
            },
            "source": "retained device command history",
            "commandProducerVerified": bool(producer.get("id")),
            "hardwareButtonPressVerified": False,
            "lockoutExecutionVerified": False,
        })
    return sorted(matched, key=lambda row: row["commandPrecedesStateMs"])[:3]



def source_local_off_time(subject: dict[str, Any], off: datetime) -> str | None:
    """Preserve the actual Hubitat offset from a matching native source row.

    Data collection and time-window queries use UTC. Display can use the
    original explicit event offset, but must not assume the host's machine
    timezone is the Hubitat hub's timezone.
    """
    candidates = [
        row.get("end") for row in completed_light_intervals(subject)
        if not row.get("clippedAtWindowEnd")
    ]
    candidates.extend(
        row.get("date") or row.get("timestamp")
        for row in (subject.get("boundaryEvents") or
                    subject.get("observedEvents") or [])
        if isinstance(row, dict)
        and str(row.get("value") or "").casefold() == "off"
    )
    for raw in candidates:
        stamp = _time(raw)
        if stamp is not None and abs((stamp - off).total_seconds()) <= 0.001:
            try:
                original = datetime.fromisoformat(
                    str(raw).replace("Z", "+00:00")
                )
                if original.utcoffset() is not None:
                    return original.isoformat(timespec="milliseconds")
            except (TypeError, ValueError):
                continue
    return None


def observed_motion_correlations(
    journal: list[dict[str, Any]], *, off: datetime,
    local_off: str | None = None,
) -> list[dict[str, Any]]:
    """Observed activity is not proof that a sensor can activate a light."""
    local_tz = None
    if local_off:
        try:
            local_tz = datetime.fromisoformat(local_off).tzinfo
        except ValueError:
            pass
    output = []
    for entry in journal:
        if not isinstance(entry, dict) or entry.get("kind") != "sensor":
            continue
        for row in entry.get("observations") or []:
            if str(row.get("value") or "").casefold() != "active":
                continue
            stamp = _time(row.get("observedAt"))
            if stamp is None:
                continue
            seconds = (stamp - off).total_seconds()
            if not (0 <= seconds <= 180):
                continue
            output.append({
                "deviceId": str(entry.get("deviceId") or ""),
                "label": str(entry.get("label") or ""),
                "observedAtUtc": stamp.isoformat(timespec="milliseconds"),
                "observedAtHubOffset": (
                    stamp.astimezone(local_tz).isoformat(timespec="milliseconds")
                    if local_tz else None
                ),
                "secondsAfterOff": round(seconds, 3),
                "timestampBasis": row.get("timestampBasis", "unknown"),
                "eligibleActivationSourceVerified": (
                    entry.get("activationSourceVerified") is True
                ),
                "role": entry.get("activationRole", "unverified"),
            })
    return sorted(output, key=lambda row: row["secondsAfterOff"])[:20]


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
        # Button devices often belong to the virtual Button Controllers room.
        # Match a distinctive physical room prefix from the light's label.
        light_prefix = re.split(
            r"\b(?:lights?|lamps?|bulbs?|switch(?:es)?)\b",
            _label(light).casefold(), maxsplit=1,
        )[0].strip()
        named_room = bool(
            len(light_prefix) >= 6
            and re.sub(r"[^a-z0-9]", "", name.casefold()).startswith(
                re.sub(r"[^a-z0-9]", "", light_prefix)
            )
        )
        exact_config_name = bool(config and name.casefold() in config.casefold())
        if _attribute(row, "motion") and (exact_config_name or same_room):
            sensors.append((0 if exact_config_name else 1, row))
        if (
            (_attribute(row, "pushed") or re.search(r"\b(?:dimmer|button|remote)\b", name, re.I))
            and (same_room or named_room or exact_config_name)
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
    app_id = _lockout_app_id(prompt)
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
    native_lookback = explicit_focal_history_lookback(prompt)
    findings["nativeHistoryLookback"] = native_lookback
    history_hours = int(native_lookback["hoursBackRequested"])
    tool = catalog.declared_tool("homebrain_device_history")
    if light and tool is not None:
        args = {
            "name": _label(light), "attribute": "switch", "limit": 50,
            "hours_back": history_hours,
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
            "requestedHoursBack": history_hours,
            "observedIntervals": len(
                completed_light_intervals(subject_data)
            ),
            "eventClockWithinWindow": any(
                abs((stamp - _time(native_lookback.get("requestedEventUtc"))).total_seconds()) <= 3
                for stamp in off_candidates(subject_data)
            ) if native_lookback.get("requestedEventUtc") else None,
            "requestBoundNotRetentionProof": True,
        })
    # Select a focal event *after* receiving the configured button identity
    # and (when available) one targeted native physical-button history.
    off = None
    config_search = ""
    async def remote(gateway: str, leaf: str, args: dict[str, Any]) -> dict[str, Any] | None:
        try:
            declared = catalog.declared_tool(gateway)
            if declared is not None:
                # Use the standard tool budget/metrics path, but avoid copying
                # unfiltered app-log message text into evidence receipts.
                execution = await host.executor.execute(
                    gateway, {"tool": leaf, "args": args},
                    tool=declared, supports_live_claim=leaf == "hub_get_logs",
                    record_evidence=False,
                )
                if not execution.success or execution.result is None:
                    return None
                data = execution.result.data
            else:
                result = await host.mcp.call_tool(
                    gateway, {"tool": leaf, "args": args}
                )
                if not host._tool_succeeded(result):
                    return None
                data = result.data
            if not isinstance(data, dict) or data.get("status") in (
                "pending", "in_progress",
            ):
                return None
            return data
        except Exception:
            return None
    if app_id:
        config = await remote(
            "hub_read_apps_code", "hub_get_app_config",
            {"appId": app_id, "includeSettings": True},
        )
        if config:
            _, config_search = configuration_text(config)
        findings["currentConfiguration"] = current_config_facts(config)
        findings["configSource"] = "hub_get_app_config(includeSettings=True)"
        findings["userExpectedDurationIsNotConfigProof"] = True
        findings["sources"].append({
            "source": "present-day-app-configuration", "appId": app_id,
            "available": config is not None,
            "historicalExecutionProven": False,
        })
    # Target only the configured/relevant physical controller. This is one
    # historical read, not a room-wide event scan or generic inventory.
    physical_presses: list[dict[str, Any]] = []
    candidates = _candidate_devices(
        identities if isinstance(identities, list) else [],
        light, config_search,
    )[1] if light else []
    configured_button = next(
        (item for item in candidates if config_search and
         _label(item).casefold() in config_search.casefold()), None
    )
    # When the user explicitly identifies a physical button device ID,
    # resolve that exact identity rather than requiring a rendered app page
    # to mention a label. Never choose a device merely by room proximity.
    if configured_button is None:
        match = re.search(
            r"\bdevice\s+(\d{2,6})(?:'s)?\s+(?:physical\s+)?button\b",
            prompt, re.I,
        )
        if match:
            configured_button = next((
                item for item in (identities if isinstance(identities, list) else [])
                if isinstance(item, dict)
                and str(item.get("id") or "") == match.group(1)
                and (_attribute(item, "pushed") or re.search(
                    r"\bbutton\b", _label(item), re.I
                ))
            ), None)
    if (
        configured_button is None
        and len(candidates) == 1
        and _attribute(candidates[0], "pushed")
    ):
        configured_button = candidates[0]
        findings["controllerSelectionBasis"] = (
            "unique-room-name-controller-candidate-not-config-proof"
        )
    if configured_button is not None and catalog.declared_tool(
        "homebrain_device_history"
    ) is not None:
        button_result = await host.executor.execute(
            "homebrain_device_history", {
                "name": _label(configured_button), "attribute": "pushed",
                "limit": 50, "hours_back": history_hours,
                "_resolved_target": dict(configured_button),
            },
            tool=catalog.declared_tool("homebrain_device_history"),
            supports_live_claim=True,
            evidence_kind="bounded_physical_button_history",
        )
        if button_result.success and button_result.result is not None:
            raw_button = button_result.result.data
            if isinstance(raw_button, dict):
                physical_presses = physical_button_observations(
                    raw_button, str(configured_button.get("id"))
                )
        findings["sources"].append({
            "source": "targeted-native-controller-history",
            "deviceId": str(configured_button.get("id")),
            "readSucceeded": bool(button_result.success),
            "verifiedPhysicalPresses": len(physical_presses),
            "requestedHoursBack": history_hours,
            "sourceRetentionComplete": False,
        })
    latest = last_observed_off(subject_data)
    # When a historical wall clock is explicitly requested, its UTC offset
    # must come from a source event on that day, not the latest day's offset.
    source_clock = (
        explicit_british_clock_source(prompt)
        or source_offset_for_request(subject_data, prompt)
    )
    if source_clock is None and not re.search(
        r"\b\d{1,2}\s+(?:january|february|march|april|may|june|july|"
        r"august|september|october|november|december)\s+\d{4}\b",
        prompt, re.I,
    ):
        source_clock = source_local_off_time(subject_data, latest) if latest else None
    selection = select_focal_off(
        subject_data, prompt, physical_presses=physical_presses,
        source_local=source_clock,
    )
    findings["focalSelection"] = selection
    off = _time(selection.get("selectedOff"))
    findings["manualOffVerified"] = bool(selection.get("manualOffVerified"))
    findings["requestedEventUtc"] = selection.get("explicitTargetUtc")
    findings["requestedEventStateObserved"] = bool(off)
    # Report a source-limited absence as such, not as a proven absence of a
    # physical command or event. The upstream event pages are finite and
    # a wider requested lookback is not proof of full retention.
    if selection.get("explicitTargetUtc"):
        target_instant = _time(selection["explicitTargetUtc"])
        native_commands = [
            row for row in subject_data.get("commandEvents") or []
            if isinstance(row, dict)
            and str(row.get("name") or "").casefold() == "command-off"
            and (stamp := _time(row.get("date") or row.get("timestamp"))) is not None
            and abs((stamp - target_instant).total_seconds()) <= 3
        ] if target_instant is not None else []
        findings["nativeFocalCommandRowsRetained"] = len(native_commands)
        findings["nativeFocalCommandHistoryIncomplete"] = (
            len(native_commands) == 0
        )
        findings["nativeHistoryAbsenceConclusion"] = (
            "Targeted native command row not found within returned "
            f"{history_hours}-hour history; neither upstream retention "
            "nor absence of historical command is proven."
            if not native_commands else
            "Targeted native command rows present in returned history."
        )
    if off is not None:
        findings["focalOff"] = off.isoformat()
        findings["focalOffHubLocal"] = source_local_off_time(subject_data, off)
        findings["focalOffTimestampBasis"] = (
            "native Hubitat state-event clock with explicit UTC offset"
            if findings["focalOffHubLocal"] else
            "normalized UTC; original hub time offset unavailable"
        )
        findings["focalCommandProvenance"] = focal_command_provenance(
            subject_data, off=off,
        )
        findings["associatedAppEventHandlers"] = event_handler_associations(
            subject_data, focal_off=off, app_id=app_id,
        )
        findings["handlerReferenceIsNotExecutionProof"] = True
        findings["latestFocalOffBasis"] = selection["selectionBasis"]

    # When the user specified a trustworthy explicit clock but switch
    # history omitted that old state transition, query logs/journal around
    # the REQUESTED event without describing the anchor as an observed OFF.
    scope_anchor = off or _time(selection.get("explicitTargetUtc"))
    journal_for_correlation: list[dict[str, Any]] = []
    if scope_anchor:
        first = scope_anchor - timedelta(seconds=20)
        last = min(scope_anchor + timedelta(seconds=195), datetime.now(timezone.utc))
        if last <= first:
            last = scope_anchor + timedelta(seconds=1)
        findings["window"] = {
            "since": first.isoformat(), "until": last.isoformat(),
            "threeMinuteWindowElapsed": datetime.now(timezone.utc) >= (
                scope_anchor + timedelta(minutes=3)
            ),
        }
        if app_id:
            logs = await remote("hub_read_diagnostics", "hub_get_logs", {
                "appId": app_id, "since": first.isoformat(),
                "until": last.isoformat(), "limit": 60,
            })
            # The model previously received only a count (two log rows
            # in the live case), making any claimed content review unfounded.
            # Bound model-only excerpts and publish only count/provenance
            # metadata in the persistent technical evidence receipt.
            app_log_rows, log_summary = bounded_app_log_evidence(logs, app_id)
            # Reconcile independently retained timestamp/quantity/source facts
            # BEFORE authoring the answer. This is a report of a log claim,
            # not a verified account of subsequent effective inhibition.
            findings["decisionClaimReconciliation"] = reconcile_decision_claims(
                prompt, app_log_rows, focal_off=scope_anchor,
            )
            current = findings.get("currentConfiguration") or {}
            configured = current.get("configuredDurationSeconds")
            reconciled = findings["decisionClaimReconciliation"]
            if isinstance(configured, int):
                reconciled["decisionStage"]["configuredDurationVerified"] = True
                reconciled["configuredDurationSeconds"] = configured
                reconciled["configurationVsRequested"] = [
                    {
                        "requestedSeconds": x["seconds"],
                        "configuredSeconds": configured,
                        "matches": x["seconds"] == configured,
                    }
                    for x in reconciled.get("expectedDurations", [])[:4]
                ]
                reconciled["configurationVsLog"] = [
                    {
                        "sourceRowId": row.get("sourceRowId"),
                        "reportedSeconds": duration["seconds"],
                        "configuredSeconds": configured,
                        "matches": duration["seconds"] == configured,
                    }
                    for row in reconciled.get("logDeclarationCandidates", [])
                    for duration in row.get("reportedDurations", [])
                ][:12]
            findings["sources"].append({
                "source": "bounded-app-execution-logs", "appId": app_id,
                "readSucceeded": logs is not None,
                **log_summary,
                "emptyDoesNotProveNoExecution": True,
                "decisionContentProvidedToModel": bool(app_log_rows),
                "decisionContentReviewed": False,
                "lockoutDecisionConfirmed": False,
                "durationConflictChecked": bool(
                    findings["decisionClaimReconciliation"]["durationComparisons"]
                ),
                "durationMismatchObserved": findings[
                    "decisionClaimReconciliation"
                ]["durationMismatchObserved"],
            })
            if app_log_rows:
                messages.append({
                    "role": "user",
                    "content": model_only_log_packet(app_log_rows, app_id),
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
                        "activationSourceVerified": False if kind == "sensor" else None,
                        "activationRole": (
                            "unverified-from-current-configuration"
                            if kind == "sensor" else None
                        ),
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
            journal_for_correlation = journal
            findings["motionCorrelations"] = (
                observed_motion_correlations(
                    journal, off=scope_anchor, local_off=findings.get("focalOffHubLocal"),
                ) if off is not None else []
            )
            findings["sensorActivationEligibilityVerified"] = any(
                item["eligibleActivationSourceVerified"]
                for item in findings["motionCorrelations"]
            )
            findings["journalCaptureCompletenessVerified"] = False
            findings["journalGapWindowsReported"] = max(
                (int(item.get("gapCount") or 0) for item in journal),
                default=0,
            )
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
                        (stamp - scope_anchor).total_seconds()
                    ) <= 2:
                        related.append({
                            "deviceId": item.get("deviceId"),
                            "label": item.get("label"),
                            "deltaMs": round((stamp-scope_anchor).total_seconds()*1000),
                            "timestampBasis": event.get("timestampBasis"),
                        })
            findings["nearbyButtonEvents"] = related[:8]
            # The selected manual classification comes from time-linked
            # native press + command + state evidence, not journal reception.
    if selection.get("explicitTargetUtc"):
        fused = correlate_requested_focal_sources(
            subject_data, physical_presses, journal_for_correlation,
            anchor_utc=str(selection["explicitTargetUtc"]),
            light_device_id=findings["lightDeviceId"],
        )
        findings["crossSourceFocalProvenance"] = fused
        matched = fused.get("candidate")
        if (
            isinstance(matched, dict)
            and fused.get("nativeButtonCommandVerified") is True
            and fused.get("journalLightOffObserved") is True
            and off is None
        ):
            journal_off = matched.get("journalLightOff") or {}
            stamp = _time(journal_off.get("collectorReceivedAtUtc"))
            if stamp is not None:
                findings["motionCorrelations"] = observed_motion_correlations(
                    journal_for_correlation, off=stamp,
                    local_off=source_clock,
                )
                findings["motionCorrelationAnchor"] = (
                    "collector-received journal OFF (not native state clock)"
                )
                findings["sensorActivationEligibilityVerified"] = any(
                    row.get("eligibleActivationSourceVerified") is True
                    for row in findings["motionCorrelations"]
                )
    findings["status"] = (
        "partial-focal-sequence" if off
        else "explicit-event-not-observed" if scope_anchor
        else "no-focal-off-observed"
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
            "coverage separately. When focalCommandProvenance contains a "
            "matching command, explicitly disclose its actual app/controller "
            "producer without confusing that command with an independently "
            "recorded hardware button press. Use typed "
            "decisionClaimReconciliation to distinguish a logged textual "
            "decision, verified source identity, the intended duration and "
            "observed effect. Where the question asks for three minutes and "
            "the log reports a different duration, explicitly report "
            "the discrepancy without silently replacing the numeric value. "
            "CurrentConfiguration is authoritative only for settings at "
            "the time of this read, never for historical execution. "
            "Do not claim an activation was inhibited. "
            "Treat associatedAppEventHandlers "
            "as event-recipient metadata, not proof a handler executed a "
            "lockout decision. Cite bounded app-log row IDs if they contain "
            "actual decision evidence; otherwise state that the available "
            "rows did not establish that decision, not that no action ran. "
            "Distinguish observed sensor "
            "activity from VERIFIED motion-activation eligibility: a room "
            "sensor or keep-on sensor need not be an activation trigger. "
            "Use focalOffHubLocal as the human time when available, with "
            "its UTC offset, and preserve collector-received timestamp "
            "qualifiers for journal observations. If app logs expose only a "
            "row count, do not claim their execution messages were inspected "
            "or that they contain no lockout decision. Missing journal rows "
            "with capture gaps cannot prove a sensor stayed inactive. "
            "When crossSourceFocalProvenance contains a verified NATIVE "
            "physical-button-to-app-command link, explicitly report the "
            "native command producer even if the native switch event "
            "fell outside the newest-N state history. A collector-received "
            "journal OFF may support an observed OFF with its own later "
            "receipt clock but must NOT be upgraded to a native switch "
            "timestamp or proof that lockout activated. Describe reported "
            "post-OFF sensor events and unknown trigger eligibility separately. "
            "State nativeHistoryLookback.hoursBackRequested explicitly "
            "when earlier-than-default time is requested. If native "
            "source rows are missing, disclose age, window boundary and "
            "upstream retention uncertainty; never say no command existed. "
            "A journal button observation cannot be promoted to a native "
            "physical-button source timestamp. "
            "Do not say app command provenance is missing if native "
            "command history contains the linked command. "
            "Select the requested focal event using focalSelection: "
            "the latest observed OFF is NOT necessarily the latest VERIFIED "
            "manual OFF. Prefer a time-linked native physical press, "
            "command, and state chain only when the request asks for manual "
            "OFF. Do not silently substitute an unrelated new OFF. Current "
            "settings are evidence of settings NOW, not historical settings. "
            "Use the selected focal timestamp for every bounded app-log and "
            "journal query, with actual UTC offsets. Never "
            "infer lockout success just because there was no ON, or claim a "
            "hardware press solely from a labelled command producer. If history "
            "is missing, say investigation is incomplete rather than replacing "
            "it with device health."
        ),
    })
    return True


def collected_lockout_ready_for_synthesis(
    prompt: str, receipts: list[dict[str, Any]],
) -> bool:
    """Close only a fully grounded single-focal lockout read, not an open search.

    The host has already read the named light, configured controller,
    app settings and time-bounded app logs. A verified physical press,
    app command and OFF state makes further *unfocused* model tool rounds
    redundant. The logs may still be inconclusive about actual suppression:
    one evidence-scoped synthesis must disclose that uncertainty, not infer
    that the automation executed. Missing or failed sources fall through
    to the ordinary investigative path.
    """
    if not is_motion_lockout_investigation(prompt):
        return False
    if re.search(
        r"\b(?:and also|as well as|in addition|also (?:check|analyse|analyze|investigate|review)|plus (?:investigate|analyse|analyze|check))\b",
        str(prompt), re.I,
    ):
        return False
    for receipt in reversed(receipts):
        if not isinstance(receipt, dict) or receipt.get("tool") != (
            "homebrain_motion_lockout_investigation"
        ):
            continue
        if receipt.get("success") is not True:
            return False
        facts = receipt.get("details")
        if not isinstance(facts, dict):
            return False
        selected = facts.get("focalSelection")
        if (
            facts.get("status") != "partial-focal-sequence"
            or not facts.get("appId") or not facts.get("lightDeviceId")
            or facts.get("manualOffVerified") is not True
            or not isinstance(selected, dict)
            or selected.get("manualOffVerified") is not True
            or not selected.get("selectedOff")
            or selected["selectedOff"] != facts.get("focalOff")
        ):
            return False
        current = facts.get("currentConfiguration")
        if not isinstance(current, dict) or current.get("settingsRead") is not True:
            return False
        sources = facts.get("sources")
        if not isinstance(sources, list):
            return False
        by_source = {
            row.get("source"): row for row in sources
            if isinstance(row, dict) and isinstance(row.get("source"), str)
        }
        light = by_source.get("bounded-light-device-history") or {}
        button = by_source.get("targeted-native-controller-history") or {}
        config = by_source.get("present-day-app-configuration") or {}
        logs = by_source.get("bounded-app-execution-logs") or {}
        return bool(
            light.get("success") is True
            and button.get("readSucceeded") is True
            and int(button.get("verifiedPhysicalPresses") or 0) > 0
            and config.get("available") is True
            and logs.get("readSucceeded") is True
        )
    return False


def collected_explicit_focal_ready_for_synthesis(
    prompt: str, receipts: list[dict[str, Any]],
) -> bool:
    """One-pass bounded conclusion for a fully scoped but incompletely retained event.

    A journal OFF does NOT upgrade manualOffVerified to true without a native
    state row. This gate only prevents unnecessary model-driven additional
    searches once current config, native controller and command, collector
    observation, and scoped app logs have ALREADY been read. The final
    synthesis must report exactly which source-level conclusions are unknown.
    """
    if not is_motion_lockout_investigation(prompt):
        return False
    if re.search(
        r"\b(?:and also|as well as|in addition|also (?:check|analyse|analyze|investigate|review))\b",
        str(prompt), re.I,
    ):
        return False
    for receipt in reversed(receipts):
        if not isinstance(receipt, dict) or receipt.get("tool") != (
            "homebrain_motion_lockout_investigation"
        ):
            continue
        if receipt.get("success") is not True:
            return False
        facts = receipt.get("details") or {}
        if not isinstance(facts, dict):
            return False
        selection = facts.get("focalSelection") or {}
        fused = facts.get("crossSourceFocalProvenance") or {}
        if not (
            facts.get("status") == "explicit-event-not-observed"
            and selection.get("explicitTargetUtc")
            and not selection.get("selectedOff")
            and fused.get("requestedEventUtc") == selection["explicitTargetUtc"]
            and fused.get("nativeButtonCommandVerified") is True
            and fused.get("journalLightOffObserved") is True
            and fused.get("nativeLightStateObserved") is False
        ):
            return False
        config = facts.get("currentConfiguration") or {}
        if config.get("settingsRead") is not True:
            return False
        sources = {
            row.get("source"): row
            for row in (facts.get("sources") or [])
            if isinstance(row, dict)
        }
        return bool(
            sources.get("bounded-light-device-history", {}).get("success") is True
            and sources.get("targeted-native-controller-history", {}).get(
                "readSucceeded"
            ) is True
            and sources.get("bounded-app-execution-logs", {}).get(
                "readSucceeded"
            ) is True
            and sources.get("Historical Journal", {}).get(
                "deviceScopesChecked", 0
            ) > 0
        )
    return False


__all__ = [
    "is_motion_lockout_investigation", "resolve_named_light",
    "completed_light_intervals", "last_observed_off",
    "focal_command_provenance", "source_local_off_time",
    "observed_motion_correlations", "prefetch_motion_lockout",
    "collected_lockout_ready_for_synthesis",
    "collected_explicit_focal_ready_for_synthesis",
]
