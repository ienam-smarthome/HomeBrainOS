"""Additive, shadow-only investigation evidence and identity contract.

Consumes previously recorded read receipts; it never runs tools, writes to
Hubitat, changes the model planner, or publishes an answer. Source-reported
states are not physical acknowledgements; temporal proximity is not causation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any, Literal, Mapping, Sequence

IdentityKind = Literal["device", "app"]
ClockBasis = Literal["source", "source-reported", "collector-received"]
EventRole = Literal["reported-state", "input-report", "issued-command"]
_ATTRIBUTES = frozenset({
    "switch", "motion", "occupancy", "presence", "level", "temperature",
    "humidity", "power", "energy", "battery", "contact", "illuminance",
    "thermostatMode", "thermostatOperatingState", "heatingSetpoint",
    "coolingSetpoint", "valve", "windowShade", "mode", "lock",
})
_HISTORY_SUMMARY = re.compile(r"^\d+ device events for '([^'\n]{1,72})'$")


def _id(value: Any) -> str | None:
    if type(value) not in (str, int):
        return None
    value = str(value)
    return (str(int(value)) if value.isdecimal() and 0 < len(value) <= 16
            and int(value) > 0 else None)


def _label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (not text or len(text) > 72 or text.isdecimal()
            or any(ord(ch) < 32 or ord(ch) == 96 or ch in "<>|[]{}" for ch in text)):
        return None
    return text


def _time(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (instant.astimezone(timezone.utc).isoformat()
                if instant.utcoffset() is not None else None)
    except (TypeError, ValueError, OverflowError):
        return None


def _value(value: Any) -> str | None:
    if type(value) not in (str, int, float, bool):
        return None
    result = str(value).lower() if type(value) is bool else str(value)
    if not result or len(result) > 32 or any(ord(ch) < 32 for ch in result):
        return None
    return result


def _args(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    outer = receipt.get("arguments")
    if not isinstance(outer, Mapping):
        return {}
    inner = outer.get("args")
    return inner if isinstance(inner, Mapping) else outer


def _read(receipt: Any) -> bool:
    return (isinstance(receipt, Mapping)
            and receipt.get("success") is True
            and receipt.get("mutates") is not True
            and receipt.get("effect") in (None, "read"))


@dataclass(frozen=True)
class VerifiedIdentity:
    kind: IdentityKind
    entity_id: str
    label: str
    source: str
    receipt_index: int
    rank: int


@dataclass(frozen=True)
class CanonicalEvent:
    entity_id: str
    attribute: str
    value: str
    role: EventRole
    time_utc: str
    clock_basis: ClockBasis
    source: str
    receipt_index: int
    issuer_app_id: str | None = None
    physical_ack_verified: bool = False


@dataclass(frozen=True)
class EvidenceCoverage:
    entity_id: str
    source: str
    gap_count: int
    truncated: bool
    complete: bool
    receipt_index: int


@dataclass(frozen=True)
class CanonicalEvidenceView:
    identities: tuple[VerifiedIdentity, ...]
    events: tuple[CanonicalEvent, ...]
    coverage: tuple[EvidenceCoverage, ...]
    schema: str = "homebrain-canonical-evidence.v1"
    shadow_only: bool = True

    def verified_label(self, kind: IdentityKind, entity_id: str) -> str | None:
        """Highest independently scoped authority wins; ties fail closed."""
        rows = [item for item in self.identities
                if item.kind == kind and item.entity_id == _id(entity_id)]
        if not rows:
            return None
        rank = max(row.rank for row in rows)
        labels = {row.label for row in rows if row.rank == rank}
        return next(iter(labels)) if len(labels) == 1 else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "shadow_only": True,
            "identities": [asdict(item) for item in self.identities],
            "events": [asdict(item) for item in self.events],
            "coverage": [asdict(item) for item in self.coverage],
        }


def build_canonical_evidence_view(
    receipts: Sequence[Mapping[str, Any]],
    *, max_receipts: int = 160, max_events_per_receipt: int = 120,
) -> CanonicalEvidenceView:
    """Bounded, read-only adapter; never turn a correlation into a command.

    A device name must be sourced from a scoped Hubitat identity read, scoped
    dependency read, or paired native-ID read and host-verified named history.
    Only native command producers can attest app issuer identities; subscribers
    in triggered[] are never classified as command issuers.
    """
    identities: list[VerifiedIdentity] = []
    events: list[CanonicalEvent] = []
    coverage: list[EvidenceCoverage] = []
    max_receipts = max(0, min(int(max_receipts), 500))
    max_events_per_receipt = max(0, min(int(max_events_per_receipt), 200))
    previous: Mapping[str, Any] | None = None

    def admit(kind: IdentityKind, entity_id: Any, label: Any, source: str,
              index: int, rank: int) -> None:
        ident, safe = _id(entity_id), _label(label)
        if ident and safe:
            found = VerifiedIdentity(kind, ident, safe, source, index, rank)
            if found not in identities:
                identities.append(found)

    for index, receipt in enumerate(receipts[:max_receipts], 1):
        if not _read(receipt):
            previous = None
            continue
        args = _args(receipt)
        details = receipt.get("details")
        details = details if isinstance(details, Mapping) else {}
        operation = str(receipt.get("sub_tool") or receipt.get("tool") or "")
        if (operation == "hub_list_devices"
                and receipt.get("evidence_kind") == "targeted_device_lookup"):
            state = details.get("reportedDeviceState")
            if (isinstance(state, Mapping)
                    and state.get("source") == "targeted-hubitat-device-state"):
                admit("device", state.get("deviceId"), state.get("label"),
                      "scoped-hubitat-device", index, 4)

        if operation == "hub_list_device_dependents":
            wanted, actual = _id(args.get("deviceId")), _id(details.get("deviceId"))
            if wanted and wanted == actual:
                admit("device", actual, details.get("deviceName"),
                      "scoped-hubitat-dependency", index, 4)

        # Host-verified history labels do not themselves contain a device ID.
        # Pair only with the immediately preceding successful ID-scoped read
        # when its exact host-produced summary names the same device.
        if operation == "homebrain_device_history" and previous:
            scoped = _id(_args(previous).get("deviceId"))
            summary = previous.get("summary")
            match = (_HISTORY_SUMMARY.fullmatch(summary)
                     if isinstance(summary, str) else None)
            name = _label(details.get("label"))
            if (previous.get("sub_tool") == "hub_list_device_events"
                    and scoped and match and name
                    and match.group(1) == name and args.get("name") == name):
                admit("device", scoped, name, "paired-scoped-device-history", index, 2)

        if operation == "hub_list_device_events":
            scoped = _id(args.get("deviceId"))
            rows = details.get("observedEvents")
            for row in (rows if isinstance(rows, list) else [])[:max_events_per_receipt]:
                if not scoped or not isinstance(row, Mapping):
                    continue
                name, stamp = row.get("name"), _time(row.get("date"))
                if not isinstance(name, str) or not stamp:
                    continue
                command = name.startswith("command-")
                attribute = name[8:] if command else name
                if command:
                    if attribute not in {"on", "off", "toggle", "setLevel",
                                         "setHeatingSetpoint", "setThermostatMode",
                                         "open", "close", "setPosition"}:
                        continue
                elif attribute not in _ATTRIBUTES:
                    continue
                producer = row.get("producedBy")
                producer = producer if isinstance(producer, Mapping) else {}
                app_id = _id(producer.get("appId")) if command else None
                if app_id:
                    admit("app", app_id, producer.get("name"),
                          "native-command-issuer", index, 3)
                value = attribute if command else _value(row.get("value"))
                if value is None:
                    continue
                events.append(CanonicalEvent(
                    scoped, attribute, value,
                    "issued-command" if command else
                    "input-report" if attribute in {"motion", "occupancy", "presence"}
                    else "reported-state",
                    stamp, "source-reported", "scoped-native-device-events", index,
                    issuer_app_id=app_id,
                ))
            if scoped and details.get("observedEventsTruncated") is True:
                coverage.append(EvidenceCoverage(
                    scoped, "scoped-native-device-events", 0, True, False, index))

        if (receipt.get("tool") == "homebrain_evidence_journal"
                and operation == "homebrain_evidence_journal"
                and receipt.get("evidence_kind") in {
                    "group_archived_switch_history", "group_archived_input_history",
                }):
            scoped, wanted = _id(details.get("deviceId")), _id(args.get("device_id"))
            if scoped and scoped == wanted:
                rows = details.get("observations")
                for row in (rows if isinstance(rows, list) else [])[:max_events_per_receipt]:
                    if not isinstance(row, Mapping) or _id(row.get("device_id")) != scoped:
                        continue
                    attr, basis = row.get("attribute"), row.get("timestamp_basis")
                    if attr not in _ATTRIBUTES or basis not in {"source", "collector-received"}:
                        continue
                    stamp, value = _time(row.get("date")), _value(row.get("value"))
                    if stamp and value is not None:
                        events.append(CanonicalEvent(
                            scoped, attr, value,
                            "input-report" if attr in {"motion", "occupancy", "presence"}
                            else "reported-state",
                            stamp, basis, "historical-journal", index,
                        ))
                gaps = details.get("gapCount")
                coverage.append(EvidenceCoverage(
                    scoped, "historical-journal",
                    max(0, min(gaps, 10000)) if type(gaps) is int else 0,
                    details.get("truncated") is True, False, index))
        previous = receipt

    return CanonicalEvidenceView(tuple(identities), tuple(events), tuple(coverage))


__all__ = [
    "VerifiedIdentity", "CanonicalEvent", "EvidenceCoverage",
    "CanonicalEvidenceView", "build_canonical_evidence_view",
]
