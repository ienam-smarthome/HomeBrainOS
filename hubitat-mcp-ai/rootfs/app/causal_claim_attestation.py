"""V3 typed claim-to-witness attestation, without keyword-based causal routing.

A valid structured claim means ONLY that the proposed claim's typed role,
target, event and witness IDs match the source-attested evidence packet.
It does not validate any unrelated free-form prose in the model's draft, prove
a physical ACK, or establish an upstream cause from temporal correlation.

Stage D1: shadow-only. Never change publication or grant tool permissions.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


_ALLOWED = frozenset({
    "reported_switch_state", "reported_input_state", "hubitat_issued_command",
    "matched_hubitat_on_command", "upstream_cause_unverified",
})
_COMMAND = {"on": "issued_on", "off": "issued_off",
            "setlevel": "issued_setlevel"}
_STATE = {"on": {"journal_source_switch_on", "reported_switch_on"},
          "off": {"journal_source_switch_off", "reported_switch_off"}}
_INPUT = {"motion", "occupancy", "presence"}
_REJECT = frozenset({
    "malformed_envelope", "unknown_claim_kind", "missing_witness",
    "wrong_witness_role", "target_mismatch", "state_mismatch",
    "app_mismatch", "clock_unverified", "command_pair_not_attested",
    "unknown_target", "unsupported_unverified_claim", "claim_limit_exceeded",
})


def _id(value: Any) -> str:
    val = str(value) if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
    return val if val.isdecimal() and int(val) > 0 else ""


def _reason(value: str) -> str:
    return value if value in _REJECT else "malformed_envelope"



def source_witness_aliases(
    ledger: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Deterministic short aliases for *existing* source-timed switch witnesses.

    A language model need not transcribe long SHA-derived witness IDs. Aliases
    are assigned from independently constructed source ledger entries, never
    from user text or the model's envelope. They do not weaken role/clock
    checks, and an unknown alias remains an invalid witness.
    """
    if not isinstance(ledger, Mapping) or ledger.get("schema") != "causal-witness-ledger.v1":
        return {}
    witnesses = ledger.get("witnesses") or []
    targets = sorted({
        str(item.get("device_id")) for item in
        ledger.get("target_source_coverage") or []
        if isinstance(item, Mapping) and _id(item.get("device_id"))
    }, key=int)[:16]
    result: dict[str, str] = {}
    for i, target in enumerate(targets, start=1):
        for state in ("on", "off"):
            eligible = [
                w for w in witnesses
                if isinstance(w, Mapping)
                and str(w.get("entity")) == target
                and w.get("event_class") == "journal_source_switch_" + state
                and w.get("clock_basis") == "source"
                and isinstance(w.get("witness_id"), str)
            ]
            if eligible:
                first = min(eligible, key=lambda row: str(row.get("time") or ""))
                result[f"w_t{i}_{state}"] = first["witness_id"]
    return result


def resolve_source_witness_aliases(
    envelope: Any, ledger: Mapping[str, Any] | None,
) -> Any:
    """Resolve only known source aliases; leave unrecognised IDs untouched."""
    if not isinstance(envelope, Mapping) or not isinstance(envelope.get("claims"), list):
        return envelope
    aliases = source_witness_aliases(ledger)
    normalized = dict(envelope)
    claims: list[Any] = []
    for claim in envelope["claims"]:
        if not isinstance(claim, Mapping):
            claims.append(claim)
            continue
        item = dict(claim)
        keys = item.get("witness_ids")
        if isinstance(keys, list):
            item["witness_ids"] = [
                aliases.get(k, k) if isinstance(k, str) else k
                for k in keys
            ]
        claims.append(item)
    normalized["claims"] = claims
    return normalized


def _validate_one(
    claim: Mapping[str, Any], witnesses: Mapping[str, Mapping[str, Any]],
    ledger: Mapping[str, Any],
) -> str | None:
    """Return a reason code, or None for supported typed claim."""
    kind = str(claim.get("kind") or "")
    if kind not in _ALLOWED:
        return "unknown_claim_kind"
    ident = _id(claim.get("device_id"))
    targets = {str(r.get("device_id")) for r in
               (ledger.get("target_source_coverage") or [])
               if isinstance(r, Mapping)}
    if not ident or (kind != "reported_input_state" and ident not in targets):
        return "unknown_target"
    keys = claim.get("witness_ids")
    if not isinstance(keys, list) or len(keys) > 4 or any(
        not isinstance(x, str) or not x.startswith("w_") for x in keys
    ):
        return "malformed_envelope"
    if kind == "upstream_cause_unverified":
        if keys:
            return "wrong_witness_role"
        if ledger.get("root_cause_verified") is not False:
            return "unsupported_unverified_claim"
        # Even a matched Hubitat command does not attest the upstream reason.
        return None
    if not keys:
        return "missing_witness"
    entries = [witnesses.get(key) for key in keys]
    if any(row is None for row in entries):
        return "missing_witness"
    if any(str(row.get("entity")) != ident for row in entries):
        return "target_mismatch"

    if kind == "reported_switch_state":
        expected = _STATE.get(str(claim.get("state") or "").casefold())
        if not expected:
            return "state_mismatch"
        if len(entries) != 1 or entries[0].get("event_class") not in expected:
            return "wrong_witness_role"
        if entries[0].get("clock_basis") not in ("source", "source-reported"):
            return "clock_unverified"
        return None

    if kind == "reported_input_state":
        if len(entries) != 1 or entries[0].get("role") != "input-report":
            return "wrong_witness_role"
        if (entries[0].get("event_class") != claim.get("attribute")
                or str(entries[0].get("value") or "") != str(claim.get("value") or "")):
            return "state_mismatch"
        if entries[0].get("clock_basis") not in ("source", "source-reported"):
            return "clock_unverified"
        return None

    if kind == "hubitat_issued_command":
        command = _COMMAND.get(str(claim.get("command") or "").casefold())
        if not command:
            return "state_mismatch"
        if len(entries) != 1 or entries[0].get("event_class") != command:
            return "wrong_witness_role"
        app = _id(claim.get("app_id"))
        if not app or entries[0].get("app_issuer") != app:
            return "app_mismatch"
        return None

    if kind == "matched_hubitat_on_command":
        if len(set(keys)) != 2 or len(keys) != 2:
            return "command_pair_not_attested"
        app = _id(claim.get("app_id"))
        if not app:
            return "app_mismatch"
        candidates = ledger.get("immediate_hubitat_on_command_matches") or []
        for pair in candidates:
            if (not isinstance(pair, Mapping)
                    or str(pair.get("device_id")) != ident
                    or str(pair.get("hubitat_app_id")) != app):
                continue
            if set(keys) == {
                pair.get("command_witness_id"), pair.get("state_witness_id")
            }:
                return None
        return "command_pair_not_attested"
    return "unknown_claim_kind"


def validate_claim_envelope(
    envelope: Any, ledger: Mapping[str, Any] | None,
    *, max_claims: int = 16,
) -> dict[str, Any]:
    """Validate only structured claims; never attest surrounding model prose.

    The result contains no raw natural language, device names, access tokens
    or event clock values. Rejection reason identifiers are allowlisted.
    """
    if (not isinstance(envelope, Mapping)
            or envelope.get("schema") != "homebrain-claims.v1"
            or not isinstance(envelope.get("claims"), list)
            or not isinstance(ledger, Mapping)
            or ledger.get("schema") != "causal-witness-ledger.v1"):
        return {"present": isinstance(envelope, Mapping), "valid": False,
                "total": 0, "supported": 0, "rejected": 0,
                "reasons": ["malformed_envelope"], "prose_verified": False}
    envelope = resolve_source_witness_aliases(envelope, ledger)
    claims = envelope["claims"]
    max_claims = max(1, min(32, int(max_claims)))
    if not claims or len(claims) > max_claims:
        return {"present": True, "valid": False,
                "total": min(len(claims), max_claims), "supported": 0,
                "rejected": len(claims), "reasons": ["claim_limit_exceeded"],
                "prose_verified": False}
    witnesses = {
        str(w["witness_id"]): w
        for w in (ledger.get("witnesses") or [])[:200]
        if isinstance(w, Mapping) and isinstance(w.get("witness_id"), str)
    }
    rejected: list[str] = []
    supported = 0
    for claim in claims:
        reason = (_validate_one(claim, witnesses, ledger)
                  if isinstance(claim, Mapping) else "malformed_envelope")
        if reason is None:
            supported += 1
        else:
            rejected.append(_reason(reason))
    return {"present": True, "valid": not rejected,
            "total": len(claims), "supported": supported,
            "rejected": len(rejected), "reasons": sorted(set(rejected))[:8],
            "prose_verified": False}


def extract_claim_envelope(draft: str, *, max_bytes: int = 8192) -> Any:
    """Extract an OPTIONAL fenced machine attestation from a model draft.

    No language heuristic or claim inference: only the exact versioned
    machine envelope is parsed. No embedded code, external links or writes.
    A missing fence is None; a malformed one is an explicit invalid object.
    """
    text = str(draft or "")
    start = "\x60\x60\x60homebrain-claims"
    pos = text.find(start)
    if pos < 0:
        return None
    a = pos + len(start)
    close = text.find("\x60\x60\x60", a)
    if close < 0 or close - a > max_bytes:
        return {"schema": "invalid", "claims": []}
    body = text[a:close].strip()
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return {"schema": "invalid", "claims": []}


__all__ = [
    "validate_claim_envelope", "extract_claim_envelope",
    "source_witness_aliases", "resolve_source_witness_aliases",
]
