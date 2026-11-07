"""HomeBrain typed-claim evidence contract v2 (shadow-only, no I/O).

Flow
----
model -> JSON claim envelope -> validate_claims() -> render_claims() -> text

* The model never writes published prose or numbers. It proposes typed claims
  that cite witness IDs; code validates role, entity, clock, event scope and
  coverage, computes all intervals/deltas, and renders from templates.
* Anything rejected is published only as "Not established: <kind> (<reason>)"
  built from allowlisted codes, never from model text.
* Mandatory disclosures (unverified cause, incomplete coverage) are derived
  from the evidence packet, so the model cannot omit them.

Extends causal_claim_attestation (v1). Use packet_from_v1_ledger() to feed it
the existing causal-witness-ledger.v1 during migration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
import re
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "homebrain-claims.v2"
SOURCE_CLOCKS = frozenset({"source", "source-reported"})
COMMAND_CLOCKS = frozenset({"hubitat-command", "source", "source-reported"})
REPORTER_ROLES = frozenset({"reporter", "input-report"})
MAX_CLAIMS = 24

KINDS = frozenset({
    "observed_value", "observed_interval", "calculation", "command_issued",
    "listener_notified", "correlation", "absent_in_scope", "cause_unverified",
    "journal_observation", "transition_pairing",
})

REASONS = frozenset({
    "malformed_envelope", "unknown_claim_kind", "claim_limit_exceeded",
    "missing_witness", "witness_count", "target_mismatch", "wrong_witness_role",
    "clock_unverified", "value_mismatch", "app_mismatch", "bad_time_order",
    "not_numeric", "unknown_operation", "out_of_scope_event",
    "missing_coverage", "coverage_target_mismatch", "cause_already_verified",
    "correlation_window", "coverage_unverified", "invalid_event_pair", "unit_mismatch",
    "coverage_window_mismatch", "sample_not_attested", "model_selected_sample",
})


# --------------------------------------------------------------------- model
@dataclass(frozen=True)
class Witness:
    witness_id: str
    entity: str
    event_class: str          # e.g. switch, motion, command-off
    role: str                 # reporter | input-report | initiator | listener
    time: str                 # ISO-8601, hub-local/GMT as recorded
    clock_basis: str = "unknown"
    value: str = ""
    event_key: str = ""       # which incident event this belongs to
    app_issuer: str = ""
    unit: str = ""
    source_class: str = ""


@dataclass(frozen=True)
class Coverage:
    coverage_id: str
    entity: str
    source: str               # e.g. "device command history"
    window_start: str = ""
    window_end: str = ""
    pages_checked: int = 0
    complete: bool = False    # fail-closed default
    successful: bool = False
    matched_count: int | None = None
    query_kind: str = ""


@dataclass(frozen=True)
class EvidencePacket:
    witnesses: Mapping[str, Witness]
    coverage: Mapping[str, Coverage] = field(default_factory=dict)
    focal_event_keys: frozenset = frozenset()
    root_cause_verified: bool = False
    max_correlation_lag_s: float = 300.0
    labels: Mapping[str, str] = field(default_factory=dict)  # entity -> name
    authorized_context_event_keys: frozenset[str] = frozenset()
    focal_time: str = ""  # trusted focus from source history or correlation
    focal_source: str = ""  # source-history-latest-off or host-correlation
    journal_reception_event_keys: frozenset[str] = frozenset()
    eligible_transition_keys: frozenset[str] = frozenset()
    candidate_sensor_count: int | None = None
    candidate_sensor_probed_count: int | None = None
    direct_sensor_windows_checked: int = 0
    internal_configuration_inspected: bool = False
    log_reads_total: int = 0
    log_reads_containing_focal: int = 0
    log_request_coverage: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimResult:
    claim: Mapping[str, Any]
    ok: bool
    reason: str = ""
    facts: Mapping[str, Any] = field(default_factory=dict)  # code-computed


@dataclass(frozen=True)
class Validation:
    results: Sequence[ClaimResult]
    envelope_ok: bool
    envelope_reason: str = ""

    @property
    def supported(self) -> list[ClaimResult]:
        return [r for r in self.results if r.ok]

    @property
    def rejected(self) -> list[ClaimResult]:
        return [r for r in self.results if not r.ok]


# ------------------------------------------------------------------- helpers
def _t(value: str) -> datetime | None:
    """Only source clocks with an explicit offset are comparable."""
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return instant.astimezone(timezone.utc) if instant.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _num(value: str) -> float | None:
    try:
        n = float(str(value).strip())
        return n if isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _wit(claim: Mapping[str, Any], packet: EvidencePacket,
         count: int | None = None) -> tuple[list[Witness], str]:
    keys = claim.get("witness_ids")
    if (not isinstance(keys, list) or not keys or len(keys) > 4
            or not all(isinstance(k, str) and k for k in keys)
            or len(set(keys)) != len(keys)):
        return [], "missing_witness"
    out = [packet.witnesses.get(k) for k in keys]
    if any(w is None for w in out):
        return [], "missing_witness"
    if count is not None and len(out) != count:
        return [], "witness_count"
    return list(out), ""  # type: ignore[arg-type]


def _scope_ok(claim: Mapping[str, Any], ws: Sequence[Witness],
              packet: EvidencePacket) -> bool:
    scope = claim.get("scope", "focal")
    if scope == "context":
        return bool(packet.authorized_context_event_keys) and all(
            bool(w.event_key) and w.event_key in packet.authorized_context_event_keys
            for w in ws
        )
    if scope != "focal" or not packet.focal_event_keys:
        return False
    return all(bool(w.event_key) and w.event_key in packet.focal_event_keys
               for w in ws)


def _clock_ok(ws: Sequence[Witness], *, command: bool = False) -> bool:
    bases = COMMAND_CLOCKS if command else SOURCE_CLOCKS
    return all(w.clock_basis in bases and _t(w.time) is not None for w in ws)


def _safe(value: Any, limit: int = 90) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "").strip())[:limit]


# ---------------------------------------------------------------- validators
def _observed_value(c, p):
    ws, err = _wit(c, p, 1)
    if err:
        return err, {}
    w = ws[0]
    if str(w.entity) != str(c.get("entity")):
        return "target_mismatch", {}
    if w.role not in REPORTER_ROLES:
        return "wrong_witness_role", {}
    if not _clock_ok(ws):
        return "clock_unverified", {}
    if (w.event_class != c.get("attribute")
            or str(w.value) != str(c.get("value"))):
        return "value_mismatch", {}
    if not _scope_ok(c, ws, p):
        return "out_of_scope_event", {}
    return "", {"entity": w.entity, "attribute": w.event_class,
                "value": w.value, "time": w.time, "reporter": True}


def _pair(c, p):
    ws, err = _wit(c, p, 2)
    if err:
        return None, err
    if ws[0].entity != ws[1].entity and c.get("kind") != "correlation":
        return None, "target_mismatch"
    if any(w.role not in REPORTER_ROLES for w in ws):
        return None, "wrong_witness_role"
    if not _clock_ok(ws):
        return None, "clock_unverified"
    if not _scope_ok(c, ws, p):
        return None, "out_of_scope_event"
    t1, t2 = _t(ws[0].time), _t(ws[1].time)
    if c.get("kind") != "correlation" and t2 <= t1:
        return None, "bad_time_order"
    return ws, ""


def _observed_interval(c, p):
    ws, err = _pair(c, p)
    if err:
        return err, {}
    start, end = ws
    if (start.event_class != end.event_class
            or (start.value.lower(), end.value.lower()) not in {
                ("on", "off"), ("active", "inactive"),
                ("present", "not present"), ("open", "closed"),
            }):
        return "invalid_event_pair", {}
    elapsed = (_t(end.time) - _t(start.time)).total_seconds()
    return "", {"entity": start.entity, "start": start.time,
                "end": end.time, "seconds": elapsed}


def _calculation(c, p):
    ws, err = _pair(c, p)
    if err:
        return err, {}
    first, second = ws
    op = c.get("op")
    if op == "elapsed":
        seconds = (_t(second.time) - _t(first.time)).total_seconds()
        return "", {"op": op, "seconds": seconds, "start": first.time,
                    "end": second.time, "entity": first.entity}
    if op == "delta":
        if (first.event_class != second.event_class or not first.unit
                or first.unit != second.unit):
            return "unit_mismatch", {}
        a, b = _num(first.value), _num(second.value)
        if a is None or b is None:
            return "not_numeric", {}
        return "", {"op": op, "delta": round(b - a, 6),
                    "from": first.value, "to": second.value,
                    "entity": first.entity, "attribute": first.event_class}
    return "unknown_operation", {}


def _command_issued(c, p):
    ws, err = _wit(c, p, 1)
    if err:
        return err, {}
    w = ws[0]
    if w.entity != str(c.get("entity")):
        return "target_mismatch", {}
    if w.role != "command-issuer":
        return "wrong_witness_role", {}
    if w.event_class != f"command-{str(c.get('command')).lower()}":
        return "value_mismatch", {}
    if not c.get("app_id") or w.app_issuer != str(c.get("app_id")):
        return "app_mismatch", {}
    if not _clock_ok(ws, command=True):
        return "clock_unverified", {}
    if not _scope_ok(c, ws, p):
        return "out_of_scope_event", {}
    return "", {"entity": w.entity, "command": c.get("command"),
                "app": w.app_issuer, "time": w.time}


def _listener_notified(c, p):
    ws, err = _wit(c, p, 1)
    if err:
        return err, {}
    w = ws[0]
    if w.role != "listener":
        return "wrong_witness_role", {}
    if not _clock_ok(ws):
        return "clock_unverified", {}
    if w.app_issuer != str(c.get("app_id")):
        return "app_mismatch", {}
    if not _scope_ok(c, ws, p):
        return "out_of_scope_event", {}
    return "", {"app": w.app_issuer, "entity": w.entity, "time": w.time}


def _correlation(c, p):
    ws, err = _pair(c, p)
    if err:
        return err, {}
    lag = abs((_t(ws[1].time) - _t(ws[0].time)).total_seconds())  # type: ignore
    if lag > p.max_correlation_lag_s:
        return "correlation_window", {}
    return "", {"a": ws[0], "b": ws[1], "lag_s": lag}


_ABSENCE_FILTERS = frozenset({
    "command-off", "command-on", "command-setlevel",
    "switch", "motion", "presence", "occupancy", "temperature",
    "humidity", "power", "energy", "app-log",
})


def _absent(c, p):
    cov = p.coverage.get(str(c.get("coverage_id")))
    if cov is None:
        return "missing_coverage", {}
    if cov.entity != str(c.get("entity")):
        return "coverage_target_mismatch", {}
    if (p.focal_time and (not _t(p.focal_time)
            or not _t(cov.window_start) or not _t(cov.window_end)
            or not _t(cov.window_start) <= _t(p.focal_time) <= _t(cov.window_end))):
        return "coverage_window_mismatch", {}
    if (not cov.successful or cov.pages_checked < 1
            or cov.matched_count != 0
            or cov.query_kind not in _ABSENCE_FILTERS
            or c.get("what") != cov.query_kind
            or not _t(cov.window_start) or not _t(cov.window_end)
            or _t(cov.window_start) >= _t(cov.window_end)):
        return "coverage_unverified", {}
    return "", {"what": cov.query_kind, "coverage": cov}



def _journal_observation(c, p):
    """Attest a RECEIPT, never an original sensor transition or causal lag."""
    ws, err = _wit(c, p, 1)
    if err:
        return err, {}
    w = ws[0]
    if w.role != "journal-reception" or w.clock_basis != "collector-received":
        return "wrong_witness_role", {}
    if w.source_class != "historical-journal" or _t(w.time) is None:
        return "clock_unverified", {}
    if (w.entity != str(c.get("entity"))
            or w.event_class != c.get("attribute")
            or w.value != str(c.get("value"))):
        return "value_mismatch", {}
    if (not w.event_key or
            w.event_key not in p.journal_reception_event_keys):
        return "out_of_scope_event", {}
    return "", {"entity": w.entity, "attribute": w.event_class,
                "value": w.value, "received_at": w.time,
                "source": "historical-journal", "event_clock_verified": False}


def _transition_pairing(c, p):
    """Host-selected full returned sample; model cannot cherry-pick IDs."""
    if "transition_ids" in c or "witness_ids" in c:
        return "model_selected_sample", {}
    entity = str(c.get("entity") or "")
    cov = p.coverage.get(str(c.get("coverage_id") or ""))
    if not cov:
        return "missing_coverage", {}
    if not entity or cov.entity != entity:
        return "coverage_target_mismatch", {}
    start, end = _t(cov.window_start), _t(cov.window_end)
    if (cov.query_kind != "command-off" or not cov.successful
            or cov.pages_checked < 1 or not isinstance(cov.matched_count, int)
            or cov.matched_count < 0 or not start or not end or end <= start
            or not p.eligible_transition_keys):
        return "coverage_unverified", {}
    off_by_time = {}
    for w in p.witnesses.values():
        if (w.role != "reporter" or w.entity != entity
                or w.event_class != "switch" or w.value != "off"
                or w.event_key not in p.eligible_transition_keys):
            continue
        moment = _t(w.time)
        if not moment or w.clock_basis not in SOURCE_CLOCKS:
            return "clock_unverified", {}
        if start <= moment <= end:
            off_by_time[moment] = w
    if not off_by_time:
        return "sample_not_attested", {}
    commands = []
    for w in p.witnesses.values():
        if (w.entity != entity or w.event_class != "command-off"
                or w.role != "command-issuer"):
            continue
        moment = _t(w.time)
        if (not moment or w.clock_basis not in COMMAND_CLOCKS
                or not w.app_issuer):
            return "clock_unverified", {}
        if start <= moment <= end:
            commands.append((moment, w))
    if len(commands) > cov.matched_count:
        return "coverage_unverified", {}
    unmatched = sorted(off_by_time)
    available = sorted(commands, reverse=True, key=lambda pair: pair[0])
    matches = []
    for off in sorted(off_by_time, reverse=True):
        eligible = [(off - at, i) for i, (at, _) in enumerate(available)
                    if 0 <= (off - at).total_seconds() <= 2.0]
        if eligible:
            _, ix = min(eligible, key=lambda p: p[0])
            when, cmd = available.pop(ix)
            matches.append((off_by_time[off], cmd))
            unmatched.remove(off)
    return "", {
        "entity": entity, "total": len(off_by_time),
        "matched": len(matches), "unmatched": len(unmatched),
        "matched_issuers": tuple(sorted({cmd.app_issuer for _, cmd in matches})),
        "threshold_seconds": 2, "complete_source_history": False,
        "scope": "returned_records_only",
    }


def _cause_unverified(c, p):
    if p.root_cause_verified:
        return "cause_already_verified", {}
    if not p.focal_event_keys:
        return "out_of_scope_event", {}
    return "", {}


_VALIDATORS: dict[str, Callable] = {
    "observed_value": _observed_value, "observed_interval": _observed_interval,
    "calculation": _calculation, "command_issued": _command_issued,
    "listener_notified": _listener_notified, "correlation": _correlation,
    "absent_in_scope": _absent, "cause_unverified": _cause_unverified,
    "journal_observation": _journal_observation,
    "transition_pairing": _transition_pairing,
}


def validate_claims(envelope: Any, packet: EvidencePacket) -> Validation:
    if (not isinstance(envelope, Mapping) or envelope.get("schema") != SCHEMA
            or not isinstance(envelope.get("claims"), list)):
        return Validation((), False, "malformed_envelope")
    claims = envelope["claims"]
    if not claims or len(claims) > MAX_CLAIMS:
        return Validation((), False, "claim_limit_exceeded")
    results: list[ClaimResult] = []
    for c in claims:
        if not isinstance(c, Mapping):
            results.append(ClaimResult({}, False, "malformed_envelope"))
            continue
        fn = _VALIDATORS.get(str(c.get("kind")))
        if fn is None:
            results.append(ClaimResult(c, False, "unknown_claim_kind"))
            continue
        reason, facts = fn(c, packet)
        results.append(ClaimResult(c, not reason, reason, facts))
    return Validation(results, True)


# ------------------------------------------------------------------ rendering
def _dur(seconds: float) -> str:
    s = int(round(abs(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return " ".join(x for x in (f"{h}h" if h else "", f"{m}m" if m else "",
                                f"{sec}s" if sec or not (h or m) else "") if x)


def _name(p: EvidencePacket, entity: str) -> str:
    return _safe(p.labels.get(entity, f"device {entity}"))


def _line(r: ClaimResult, p: EvidencePacket) -> tuple[str, str]:
    """Return (section, text) for a supported claim."""
    k, f = r.claim["kind"], r.facts
    ctx = r.claim.get("scope") == "context"
    sec = "context" if ctx else "verified"
    if k == "observed_value":
        return sec, (f"{_name(p, f['entity'])} reported {f['attribute']}="
                     f"{_safe(f['value'])} at {f['time']}.")
    if k == "observed_interval":
        return sec, (f"{_name(p, f['entity'])}: {_dur(f['seconds'])} between "
                     f"recorded events {f['start']} and {f['end']}.")
    if k == "calculation" and f["op"] == "elapsed":
        return sec, (f"{_name(p, f['entity'])}: {_dur(f['seconds'])} elapsed "
                     f"({f['start']} to {f['end']}).")
    if k == "calculation":
        return sec, (f"{_name(p, f['entity'])} {_safe(f['attribute'])} changed from "
                     f"{_safe(f['from'])} to {_safe(f['to'])} (delta {f['delta']:+g}).")
    if k == "command_issued":
        return sec, (f"Hubitat app {f['app']} issued {f['command']} to "
                     f"{_name(p, f['entity'])} at {f['time']}.")
    if k == "listener_notified":
        return sec, (f"App {f['app']} was notified of the event at "
                     f"{f['time']} (notification alone does not show whether "
                     f"it did or did not act).")
    if k == "correlation":
        a, b = f["a"], f["b"]
        return "correlation", (
            f"{_name(p, a.entity)} {_safe(a.event_class)}={_safe(a.value)} ({a.time}) and "
            f"{_name(p, b.entity)} {_safe(b.event_class)}={_safe(b.value)} ({b.time}) are "
            f"{_dur(f['lag_s'])} apart. This is a correlation, not shown to "
            f"be the cause.")
    if k == "journal_observation":
        return "context", (
            f"Historical Journal received {_name(p, f['entity'])} "
            f"{_safe(f['attribute'])}={_safe(f['value'])} at "
            f"{f['received_at']} (collector-received, not independently "
            "verified original sensor-event time)."
        )
    if k == "transition_pairing":
        return "scope", (
            f"Of {f['total']} source-reported OFF transitions for "
            f"{_name(p, f['entity'])} in the overlapping returned records, "
            f"{f['matched']} had a recorded Hubitat command-off within "
            f"{f['threshold_seconds']} seconds; {f['unmatched']} had no "
            "matching command in the returned records. Historical retention "
            "and unobserved command paths are not excluded; this does not "
            "prove an external cause."
        )
    if k == "absent_in_scope":
        cv = f["coverage"]
        scope = (f"{cv.pages_checked} page(s) of {_safe(cv.source)}"
                 + (f", {cv.window_start} to {cv.window_end}"
                    if cv.window_start else ""))
        tail = "" if cv.complete else " Coverage is incomplete, so this is not proof it never happened."
        return "scope", (f"No {_safe(f['what'])} found for {_name(p, cv.entity)} "
                         f"in the records checked ({scope}).{tail}")
    return "unknown", ""


_HEADINGS = (("verified", "Verified"), ("correlation", "Correlations"),
             ("scope", "Search scope"), ("context", "Other recorded events"))


def render_claims(v: Validation, p: EvidencePacket) -> str:
    sections: dict[str, list[str]] = {}
    for r in v.supported:
        if r.claim["kind"] == "cause_unverified":
            continue
        sec, text = _line(r, p)
        if text:
            sections.setdefault(sec, []).append(text)
    out: list[str] = []
    for key, title in _HEADINGS:
        if sections.get(key):
            out.append(f"{title}:\n" + "\n".join(f"- {t}" for t in sections[key]))
    not_est: list[str] = []
    if not p.root_cause_verified and p.focal_event_keys:
        not_est.append("What initiated the change is not established.")
    for r in v.rejected:
        kind = str(r.claim.get("kind", "claim"))
        if kind in KINDS and kind != "cause_unverified":
            not_est.append(f"A proposed '{kind}' statement could not be "
                           f"verified ({r.reason}).")
    if not_est:
        out.append("Not established:\n" + "\n".join(f"- {t}" for t in not_est))
    return "\n\n".join(out) or "No claims could be verified from the evidence."


# ---------------------------------------------------------------- publication
@dataclass(frozen=True)
class Publication:
    text: str
    downgraded: bool          # True if any claim stayed rejected
    attempts: int
    reasons: tuple


def publish(
    envelope: Any, packet: EvidencePacket,
    repair: Callable[[Sequence[tuple[str, str]]], Any] | None = None,
    max_repairs: int = 1,
) -> Publication:
    """Validate, optionally repair once with reason codes only, render.

    `repair` receives [(kind, reason_code), ...] (never prose) and returns a
    new envelope. The deterministic render is the floor: it is published even
    if every claim is rejected.
    """
    v = validate_claims(envelope, packet)
    attempts = 1
    while v.rejected and repair and attempts <= max_repairs:
        codes = [(str(r.claim.get("kind", "")), r.reason) for r in v.rejected]
        v = validate_claims(repair(codes), packet)
        attempts += 1
    if not v.envelope_ok:
        reasons = (v.envelope_reason,)
    else:
        reasons = tuple(sorted({r.reason for r in v.rejected}))
    return Publication(render_claims(v, packet),
                       bool(v.rejected or not v.envelope_ok), attempts, reasons)


# -------------------------------------------------------- v1 migration helper
def coverage_from_verified_window_reads(
    receipts: Sequence[Mapping[str, Any]],
) -> list[Coverage]:
    """Attest exact zero-result scope only from verified native read windows.

    This accepts positive checked pages, never asserts complete retention,
    and refuses unbounded/newest-N results or incomplete tool metadata.
    An empty source page is a narrow no-match result, not proof of an
    absent command at every upstream integration.
    """
    verified: list[Coverage] = []
    for receipt in receipts[:160]:
        if (not isinstance(receipt, Mapping)
                or receipt.get("tool") != "hub_read_devices"
                or receipt.get("sub_tool") != "hub_list_device_events"
                or receipt.get("success") is not True
                or receipt.get("mutates") is True
                or receipt.get("effect") not in (None, "read")
                or receipt.get("evidence_kind") not in {
                    "authoritative_device_event_history",
                    "authoritative_command_event_history",
                }):
            continue
        arguments = receipt.get("arguments")
        if not isinstance(arguments, Mapping):
            continue
        args = arguments.get("args")
        if not isinstance(args, Mapping):
            continue
        entity = str(args.get("deviceId") or "")
        kind = str(args.get("attribute") or "")
        start = str(args.get("since") or "")
        end = str(args.get("until") or "")
        if (not entity.isdecimal() or kind not in _ABSENCE_FILTERS
                or not _t(start) or not _t(end)
                or _t(start) >= _t(end)):
            continue
        details = receipt.get("details")
        if (not isinstance(details, Mapping)
                or details.get("windowVerified") is not True
                or str(details.get("deviceId") or "") != entity
                or str(details.get("attribute") or "") != kind
                or not isinstance(details.get("events"), list)):
            continue
        events = details["events"]
        if (not isinstance(details.get("eventCount"), int)
                or isinstance(details.get("eventCount"), bool)
                or details["eventCount"] != len(events)):
            continue
        verified.append(Coverage(
            coverage_id=f"{entity}|{kind}|{start}|{end}",
            entity=entity, source="verified native device-event page",
            window_start=start, window_end=end, pages_checked=1,
            complete=False, successful=True, matched_count=len(events),
            query_kind=kind,
        ))
    return verified


def packet_from_v1_ledger(
    ledger: Mapping[str, Any], *, coverage: Sequence[Coverage] = (),
    focal_event_keys: frozenset[str] = frozenset(),
    authorized_context_event_keys: frozenset[str] = frozenset(),
) -> EvidencePacket:
    """Translate actual v1 event classes, roles and source clock semantics.

    The existing v1 ledger contains no event_key and often no switch value:
    these may be derived from the source-attested class and timestamp. Focal
    membership remains a separate trust decision made by the host planner.
    A v1 coverage summary is not enough to attest checked zero-result pages.
    """
    if (not isinstance(ledger, Mapping)
            or ledger.get("schema") != "causal-witness-ledger.v1"):
        return EvidencePacket({})
    converted: dict[str, Witness] = {}
    switches = {
        "journal_source_switch_on": ("on", "source"),
        "journal_source_switch_off": ("off", "source"),
        "reported_switch_on": ("on", "source-reported"),
        "reported_switch_off": ("off", "source-reported"),
        "journal_received_switch_on": ("on", "collector-received"),
        "journal_received_switch_off": ("off", "collector-received"),
    }
    commands = {
        "issued_on": "command-on",
        "issued_off": "command-off",
        "issued_setlevel": "command-setlevel",
    }
    for row in (ledger.get("witnesses") or [])[:200]:
        if not isinstance(row, Mapping):
            continue
        witness_id = row.get("witness_id")
        entity = str(row.get("entity") or "")
        original_class = str(row.get("event_class") or "")
        clock = str(row.get("clock_basis") or "unknown")
        role = str(row.get("role") or "")
        instant = str(row.get("time") or "")
        value = str(row.get("value") or "")
        event_class = original_class
        if not isinstance(witness_id, str) or not witness_id or not entity:
            continue
        if original_class in switches and role == "state-report":
            event_class = "switch"
            value, expected_clock = switches[original_class]
            if clock != expected_clock:
                continue
            role = "reporter"
        elif original_class in commands and role == "issued-command":
            event_class = commands[original_class]
            role = "command-issuer"
        elif role == "input-report" and original_class in {
            "motion", "presence", "occupancy",
        }:
            if not value:
                continue
        elif role == "state-report" and original_class == "reported_level" and value:
            event_class = "level"
            role = "reporter"
        else:
            continue
        event_key = f"{entity}|{original_class}|{instant}"
        converted[witness_id] = Witness(
            witness_id=witness_id, entity=entity, event_class=event_class,
            role=role, time=instant, clock_basis=clock, value=value,
            event_key=event_key, app_issuer=str(row.get("app_issuer") or ""),
            unit=str(row.get("unit") or ""),
        )
    # The caller may supply only preverified read evidence, not arbitrary
    # v1 target_source_coverage summaries claiming historical completeness.
    return EvidencePacket(
        witnesses=converted,
        coverage={v.coverage_id: v for v in coverage
                  if isinstance(v, Coverage) and v.coverage_id},
        focal_event_keys=focal_event_keys,
        authorized_context_event_keys=authorized_context_event_keys,
        root_cause_verified=ledger.get("root_cause_verified") is True,
    )


def assess_claims_shadow(
    envelope: Any, ledger: Mapping[str, Any], *,
    coverage: Sequence[Coverage] = (),
    focal_event_keys: frozenset[str] = frozenset(),
    authorized_context_event_keys: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Offline/read-only, privacy-limited diagnostics; never publishes text."""
    packet = packet_from_v1_ledger(
        ledger, coverage=coverage, focal_event_keys=focal_event_keys,
        authorized_context_event_keys=authorized_context_event_keys,
    )
    verdict = validate_claims(envelope, packet)
    return {
        "schema": SCHEMA,
        "shadow_only": True,
        "witnesses": len(packet.witnesses),
        "claims": len(verdict.results),
        "supported": len(verdict.supported),
        "rejected": len(verdict.rejected),
        "envelope_valid": verdict.envelope_ok,
        "reason_codes": sorted(
            {r.reason for r in verdict.rejected if r.reason in REASONS}
            | ({verdict.envelope_reason} if not verdict.envelope_ok else set())
        ),
    }
