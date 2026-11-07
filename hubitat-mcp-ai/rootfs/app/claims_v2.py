"""homebrain-claims.v2: claim-first answer contract (draft, pure functions, no I/O).

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
})

REASONS = frozenset({
    "malformed_envelope", "unknown_claim_kind", "claim_limit_exceeded",
    "missing_witness", "witness_count", "target_mismatch", "wrong_witness_role",
    "clock_unverified", "value_mismatch", "app_mismatch", "bad_time_order",
    "not_numeric", "unknown_operation", "out_of_scope_event",
    "missing_coverage", "coverage_target_mismatch", "cause_already_verified",
    "correlation_window", "coverage_unverified", "invalid_event_pair", "unit_mismatch",
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
        if first.event_class != second.event_class or first.unit != second.unit:
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
    if (not cov.successful or cov.pages_checked < 1
            or cov.matched_count != 0
            or cov.query_kind not in _ABSENCE_FILTERS
            or c.get("what") != cov.query_kind
            or not _t(cov.window_start) or not _t(cov.window_end)
            or _t(cov.window_start) >= _t(cov.window_end)):
        return "coverage_unverified", {}
    return "", {"what": cov.query_kind, "coverage": cov}


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
    return p.labels.get(entity, f"device {entity}")


def _line(r: ClaimResult, p: EvidencePacket) -> tuple[str, str]:
    """Return (section, text) for a supported claim."""
    k, f = r.claim["kind"], r.facts
    ctx = r.claim.get("scope") == "context"
    sec = "context" if ctx else "verified"
    if k == "observed_value":
        return sec, (f"{_name(p, f['entity'])} reported {f['attribute']}="
                     f"{f['value']} at {f['time']}.")
    if k == "observed_interval":
        return sec, (f"{_name(p, f['entity'])}: {_dur(f['seconds'])} between "
                     f"recorded events {f['start']} and {f['end']}.")
    if k == "calculation" and f["op"] == "elapsed":
        return sec, (f"{_name(p, f['entity'])}: {_dur(f['seconds'])} elapsed "
                     f"({f['start']} to {f['end']}).")
    if k == "calculation":
        return sec, (f"{_name(p, f['entity'])} {f['attribute']} changed from "
                     f"{f['from']} to {f['to']} (delta {f['delta']:+g}).")
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
            f"{_name(p, a.entity)} {a.event_class}={a.value} ({a.time}) and "
            f"{_name(p, b.entity)} {b.event_class}={b.value} ({b.time}) are "
            f"{_dur(f['lag_s'])} apart. This is a correlation, not shown to "
            f"be the cause.")
    if k == "absent_in_scope":
        cv = f["coverage"]
        scope = (f"{cv.pages_checked} page(s) of {cv.source}"
                 + (f", {cv.window_start} to {cv.window_end}"
                    if cv.window_start else ""))
        tail = "" if cv.complete else " Coverage is incomplete, so this is not proof it never happened."
        return "scope", (f"No {f['what']} found for {_name(p, cv.entity)} "
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
    if not p.root_cause_verified:       # derived, not model-controlled
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
def packet_from_v1_ledger(
    ledger: Mapping[str, Any], *, coverage: Sequence[Coverage] = (),
    focal_event_keys: frozenset = frozenset(),
) -> EvidencePacket:
    """Adapt causal-witness-ledger.v1 rows. Missing fields fail closed."""
    ws: dict[str, Witness] = {}
    for w in ledger.get("witnesses") or []:
        if isinstance(w, Mapping) and isinstance(w.get("witness_id"), str):
            ws[w["witness_id"]] = Witness(
                witness_id=w["witness_id"], entity=str(w.get("entity", "")),
                event_class=str(w.get("event_class", "")),
                role=str(w.get("role", "")), time=str(w.get("time", "")),
                clock_basis=str(w.get("clock_basis", "unknown")),
                value=str(w.get("value", "")),
                event_key=str(w.get("event_key", "")),
                app_issuer=str(w.get("app_issuer", "")))
    return EvidencePacket(
        witnesses=ws, coverage={c.coverage_id: c for c in coverage},
        focal_event_keys=focal_event_keys,
        root_cause_verified=ledger.get("root_cause_verified") is True)