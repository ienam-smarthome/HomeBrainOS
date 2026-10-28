"""Canonical, fail-closed *observations* for Investigation V2 (RFC Phase B).

This is a passive read adapter, not an investigator, source-completeness oracle,
claim verifier, or tool executor. No device-specific routing or inferred actors.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from .adapters import supplemental_events
from .read_diagnostics import safe_code as safe_failure_code

STAGES = frozenset({
    "command_issued", "state_reported", "app_log_statement",
    "config_stored", "app_execution_observed", "transport_ack",
    "independent_physical_observation",
})


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _rows(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _id(value: Any) -> str | None:
    # Do not substitute labels, actor names or arbitrary objects for a Hubitat ID.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    value = str(value).strip()
    return value if value.isdecimal() else None


def _instant(raw: Any) -> tuple[str, str] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None  # in particular, never guess the DST fold
    return dt.astimezone(timezone.utc).isoformat(), raw.strip()


def _boolean(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _argument_map(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    arguments = _mapping(receipt.get("arguments"))
    return _mapping(arguments.get("args")) if isinstance(arguments.get("args"), dict) else arguments


@dataclass(frozen=True)
class EvidenceItem:
    record_id: str
    source_request_id: str
    tool: str
    operation: str
    source_category: str
    target_id: str | None
    producer_id: str | None
    producer_label: str | None
    timestamp_utc: str
    timestamp_original: str
    stage: str
    action: str
    value: str | None
    raw_references: tuple[str, ...]
    time_basis: str = "event_time"


@dataclass(frozen=True)
class Coverage:
    source_request_id: str
    tool: str
    operation: str
    query_target_id: str | None
    requested_filters: Mapping[str, Any]
    returned_rows: int
    oldest_utc: str | None
    newest_utc: str | None
    page_reaches_start: bool | None
    source_complete: bool | None
    truncated: bool | None
    source_integrity_verified: bool | None
    pagination_cursor: str | None
    succeeded: bool
    errors: tuple[str, ...] = ()
    source_returned_rows: int | None = None
    source_oldest_utc: str | None = None
    source_newest_utc: str | None = None
    requested_window_reached: bool | None = None
    projection_drop_counts: dict[str, int] = field(default_factory=dict)
    failure_code: str | None = None


@dataclass
class CaseFile:
    original_user_request: str
    records: list[EvidenceItem] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    app_identities: dict[str, str] = field(default_factory=dict)
    device_snapshots: list[dict[str, Any]] = field(default_factory=list)
    # Current app selections attested by an event-proven command issuer.
    # These are NOT historical evidence of a sensor's state at command time.
    app_sensor_references: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_user_request": self.original_user_request,
            "records": [asdict(item) for item in self.records],
            "coverage": [asdict(item) for item in self.coverage],
            "errors": list(self.errors),
            "app_identities": dict(self.app_identities),
            "device_snapshots": list(self.device_snapshots),
            "app_sensor_references": dict(self.app_sensor_references),
        }

    def evidence_brief(self) -> str:
        """Lossless-to-observation timeline for the model, not a causal verdict."""
        lines = [f"Original question: {self.original_user_request}",
                 "Observed records (UTC; source clocks retained):"]
        for item in self.records:
            lines.append(
                f"[{item.record_id}] {item.timestamp_utc} "
                f"(source {item.timestamp_original}) {item.stage}: "
                f"target={item.target_id or 'unknown'} "
                f"action={item.action} value={item.value if item.value is not None else 'unknown'} "
                f"issuer={item.producer_id or 'unverified'} "
                f"basis={item.time_basis} from {item.tool}/{item.operation}"
            )
        for snapshot in self.device_snapshots:
            lines.append("Current device status at read time only (not historical event): "
                         + str(snapshot.get("deviceId")) + " "
                         + str(snapshot.get("attributes", {})))
        lines.append("Coverage (page reach is not source completeness):")
        for c in self.coverage:
            lines.append(
                f"{c.source_request_id} target={c.query_target_id or 'unknown'} "
                f"rows={c.returned_rows} page_reaches_start={c.page_reaches_start} "
                f"source_complete={c.source_complete} "
                f"integrity={c.source_integrity_verified} truncated={c.truncated} "
                f"source_rows={c.source_returned_rows} source_oldest={c.source_oldest_utc} "
                f"requested_window_reached={c.requested_window_reached}"
            )
        if self.app_identities:
            lines.append("Current app identity lookup (names are not historical execution proof):")
            for app_id, name in sorted(self.app_identities.items(), key=lambda row: int(row[0])):
                if any(row.producer_id == app_id for row in self.records):
                    lines.append(f"issuer #{app_id}: {name}")
        if self.app_sensor_references:
            lines.append("Event-issuer app's CURRENT stored sensor selections "
                         "(not historical state or proven trigger):")
            for app_id, refs in sorted(self.app_sensor_references.items(), key=lambda x: int(x[0])):
                for ref in refs:
                    lines.append(f"app #{app_id} setting={ref['key']} "
                                 f"sensor IDs={','.join(ref['deviceIds'])}")
        lines.append("Stored configuration is a read-time snapshot, not verified historical "
                     "effective code or event-time automation behaviour.")
        lines.append("Unverified: physical execution of command records and causal attribution "
                     "without independently linked evidence.")
        return "\n".join(lines)


def _event_stage(event: Mapping[str, Any]) -> str | None:
    kind = str(event.get("name") or event.get("eventName") or "").strip()
    if kind.startswith("command-") or event.get("type") == "command":
        return "command_issued"
    if kind and event.get("type") not in ("command", "log"):
        return "state_reported"
    return None


def _record(source_id: str, tool: str, operation: str, category: str,
            target: str | None, event: Mapping[str, Any], pointer: str,
            *, stage: str | None = None,
            time_basis: str = "event_time") -> EvidenceItem | None:
    stage = stage or _event_stage(event)
    if stage not in STAGES:
        return None
    stamp = _instant(event.get("date") or event.get("timestamp") or event.get("observedAt"))
    if stamp is None:
        return None
    explicit_target = _id(event.get("deviceId"))
    if explicit_target and target and explicit_target != target:
        return None  # a different device's event cannot prove this target's activity
    target = explicit_target or target
    actor = _mapping(event.get("producedBy"))
    producer = _id(actor.get("id"))
    producer_label = str(actor["label"])[:100] if producer and isinstance(actor.get("label"), str) else None
    action = str(event.get("name") or event.get("eventName") or ("log" if stage == "app_log_statement" else "unknown"))[:80]
    value_raw = event.get("value")
    value = str(value_raw)[:120] if isinstance(value_raw, (str, int, float, bool)) else None
    signature = (tool, operation, target, stamp[0], stage, action, value, producer, time_basis)
    digest = sha256(json.dumps(signature, separators=(",", ":")).encode()).hexdigest()[:20]
    return EvidenceItem(
        digest, source_id, tool, operation, category, target, producer,
        producer_label, stamp[0], stamp[1], stage, action, value, (pointer,), time_basis,
    )


def build_case_file(original_user_request: str,
                    receipts: Iterable[Mapping[str, Any]]) -> CaseFile:
    """Read actual typed MCP receipts; never parse narrative summaries as facts.

    Supports established hub_list_device_events and hub_get_logs evidence
    shapes. Other successful receipt types remain coverage-only until adapters
    exist; they are never silently promoted to a verified device observation.
    """
    case = CaseFile(original_user_request=original_user_request)
    dedup: dict[str, EvidenceItem] = {}
    pending_sensor_references: list[tuple[str, list[dict[str, Any]]]] = []
    for index, raw in enumerate(receipts):
        if not isinstance(raw, dict):
            case.errors.append(f"receipt[{index}]: not an object")
            continue
        tool = str(raw.get("tool") or "")
        op = str(raw.get("sub_tool") or _mapping(raw.get("arguments")).get("tool") or tool)
        args = _argument_map(raw)
        details = _mapping(raw.get("details"))
        target = _id(args.get("deviceId"))
        # An explicitly conflicting target in the response is not resolved by label.
        response_target = _id(details.get("deviceId"))
        source_id = str(raw.get("source_request_id") or raw.get("sourceRequestId") or f"receipt-{index}")
        succeeded = raw.get("success") is True
        errors: list[str] = []
        if (succeeded and op in ("hub_list_apps", "hub_list_rules")
                and raw.get("evidence_kind") == "typed_app_identity_catalogue"
                and details.get("appCatalogReadable") is True):
            for entry in _rows(details.get("appIdentities")):
                app_id = _id(entry.get("id"))
                label = entry.get("name")
                if (app_id and isinstance(label, str) and 0 < len(label) <= 101
                        and all(ch.isprintable() and ch not in "<>[]{}" for ch in label)):
                    if app_id in case.app_identities and case.app_identities[app_id] != label:
                        case.app_identities.pop(app_id, None)
                    else:
                        case.app_identities[app_id] = label
        if (succeeded and op == "hub_get_app_config"
                and raw.get("evidence_kind") == "typed_existing_rule_partial_settings"
                and details.get("settingsReadable") is True):
            expected_app = _id(args.get("appId"))
            if expected_app and _id(details.get("appId")) == expected_app:
                refs = details.get("deviceReferences")
                if isinstance(refs, list) and len(refs) <= 8:
                    verified: list[dict[str, Any]] = []
                    accepted_keys = frozenset({
                        "motionSensors", "motionSensor",
                        "keepOnSensors", "keepOnSensor",
                        "contactSensors", "contactSensor",
                        "presenceSensors", "presenceSensor",
                        "temperatureSensors", "temperatureSensor",
                        "humiditySensors", "humiditySensor",
                        "illuminanceSensors", "illuminanceSensor",
                    })
                    for ref in refs:
                        if not isinstance(ref, dict) or ref.get("key") not in accepted_keys:
                            continue
                        ids = ref.get("deviceIds")
                        if (not isinstance(ids, list) or not 0 < len(ids) <= 8
                                or any(_id(ident) is None for ident in ids)):
                            continue
                        verified.append({
                            "key": ref["key"],
                            "deviceIds": sorted({_id(x) for x in ids}, key=int),
                            "source_request_id": source_id,
                            "source_basis": "read_time_stored_controller_config",
                        })
                    if verified:
                        pending_sensor_references.append((expected_app, verified))
        if (succeeded and raw.get("evidence_kind") == "typed_current_device_snapshot"
                and target and (response_target is None or response_target == target)):
            snap = details.get("deviceSnapshot")
            if isinstance(snap, dict) and _id(snap.get("deviceId")) == target:
                attrs = snap.get("attributes")
                if isinstance(attrs, dict):
                    # Host-projected snapshot is observation-at-read-time.
                    # Never turn current values into historical transitions.
                    case.device_snapshots.append({
                        "deviceId": target,
                        "attributes": {str(k): v for k, v in attrs.items()
                                       if isinstance(k, str) and
                                       type(v) in (str, int, float, bool)},
                    })
        if target and response_target and target != response_target:
            errors.append("response target does not match request target")
        if not succeeded:
            errors.append("source read not successful")
        is_events = op == "hub_list_device_events" or tool == "homebrain_device_history"
        is_logs = op == "hub_get_logs"
        source_rows: list[tuple[str, int, Mapping[str, Any]]] = []
        if succeeded and not (target and response_target and target != response_target):
            if is_events:
                # Different arrays may each hold unique commands or states.
                # Stable record IDs remove repeated representations of a row.
                keys = ("windowEvents", "events", "observedEvents", "boundaryEvents")
            else:
                keys = ("logs",) if is_logs else ()
            for key in keys:
                source_rows.extend((key, i, event) for i, event in
                                   enumerate(_rows(details.get(key))))
        supplemental, adapter_errors = supplemental_events(
            raw, source_id, tool, op, args, details)
        errors.extend(adapter_errors)
        times: list[str] = []
        for rows_key, row_index, event in source_rows:
            if (event_id := _id(event.get("deviceId"))) and target and event_id != target:
                errors.append(f"{rows_key}[{row_index}]: target mismatch")
                continue
            stage = "app_log_statement" if is_logs else None
            item = _record(source_id, tool, op, "logs" if is_logs else "device_events",
                           target or response_target, event,
                           f"{source_id}.details.{rows_key}[{row_index}]", stage=stage)
            if item is None:
                errors.append(f"{rows_key}[{row_index}]: missing offset/time/type")
                continue
            times.append(item.timestamp_utc)
            previous = dedup.get(item.record_id)
            if previous is None:
                dedup[item.record_id] = item
            elif item.raw_references[0] not in previous.raw_references:
                dedup[item.record_id] = replace(previous, raw_references=(
                    *previous.raw_references, *item.raw_references))
        for extra in supplemental:
            item = _record(
                source_id, tool, op, extra["category"], extra["target_id"],
                extra["event"], extra["pointer"], stage=extra["stage"],
                time_basis=extra["time_basis"],
            )
            if item is None:
                errors.append(f'{extra["pointer"]}: missing offset/time/type')
                continue
            times.append(item.timestamp_utc)
            previous = dedup.get(item.record_id)
            if previous is None:
                dedup[item.record_id] = item
            elif item.raw_references[0] not in previous.raw_references:
                dedup[item.record_id] = replace(previous, raw_references=(
                    *previous.raw_references, *item.raw_references))
        integrity = _boolean(details.get("historySourceIntegrityVerified"))
        if integrity is None:
            integrity = _boolean(details.get("sourceIntegrityVerified"))
        truncated = _boolean(details.get("observedEventsTruncated"))
        if truncated is None:
            truncated = _boolean(details.get("truncated"))
        page_reach = _boolean(details.get("sourceCompleteToWindowStart"))
        if page_reach is None:
            page_reach = _boolean(details.get("pageReachesStart"))
        # Explicit claims of source completeness require independent source
        # integrity, never inferred from hoursBack, page reach, or row count.
        complete_flag = _boolean(details.get("sourceComplete"))
        source_complete = (succeeded and not errors and complete_flag is True and integrity is True and truncated is False)
        if complete_flag is None and truncated is not True:
            source_complete = None
        filters = {key: args[key] for key in ("attribute", "hoursBack", "limit", "since", "until", "appId")
                   if key in args and isinstance(args[key], (str, int, float, bool))}
        case.coverage.append(Coverage(
            source_id, tool, op, target or _id(args.get("appId")), filters, len(source_rows) + len(supplemental),
            min(times) if times else None, max(times) if times else None,
            page_reach, source_complete, truncated, integrity,
            str(details["nextCursor"]) if isinstance(details.get("nextCursor"), str) else None,
            succeeded, tuple(errors),
            details.get("sourceEventCount") if type(details.get("sourceEventCount")) is int else None,
            details.get("sourceOldestReturnedUtc") if isinstance(details.get("sourceOldestReturnedUtc"), str) else None,
            details.get("sourceNewestReturnedUtc") if isinstance(details.get("sourceNewestReturnedUtc"), str) else None,
            details.get("requestedWindowReached") if type(details.get("requestedWindowReached")) is bool else None,
            {key: value for key, value in
             _mapping(details.get("sourceProjectionDropCounts")).items()
             if key in ("wrong_target", "invalid_device_id", "invalid_name_or_time",
                        "outside_incident", "retention_cap")
             and type(value) is int and 0 <= value <= 100000},
            safe_failure_code(raw.get("failure_code")),
        ))
        case.errors.extend(f"{source_id}: {issue}" for issue in errors)
    case.records = sorted(dedup.values(), key=lambda e: (e.timestamp_utc, e.record_id))
    attested_issuers = {item.producer_id for item in case.records
                        if item.stage == "command_issued" and item.producer_id}
    for app_id, refs in pending_sensor_references:
        if app_id in attested_issuers:
            case.app_sensor_references[app_id] = refs
    return case
