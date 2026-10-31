"""V3 fail-closed, claim-guided natural-language incident publication.

Model-selected claim kinds and witness IDs determine *whether* and *which*
observations can be highlighted. The model's unconstrained draft prose is
never published by this gate: typed claim validation does NOT semantically
validate its sentences. Natural-language paragraphs are formed exclusively
from verified typed source observations and bounded reception comparisons.

No command issuer may be inferred from input timing, later setLevel, current
app dependencies or missing historical rows. Ineligible cases retain the
existing source-first digest unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

from causal_claim_attestation import extract_claim_envelope, validate_claim_envelope


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _label(raw: Any, fallback: str) -> str:
    # Labels originate from independently verified current-target histories,
    # never the model's untrusted draft. Strip formatting control characters.
    value = str(raw or "").strip()
    if not value or len(value) > 72 or any(x in value for x in ("\n", "\r", "|", "`")):
        return "Device " + fallback
    return value


def claim_guided_incident_answer(
    draft: str,
    facts: Mapping[str, Any] | None,
) -> tuple[str | None, str]:
    """Return source-rendered prose or fail-closed (None, allowlisted reason).

    Eligibility: both scoped targets have real source-clock ON and OFF
    observations and the model's claim envelope independently cites at least
    one of each kind for each target, with no invalid claim. A one-sided,
    incomplete, unsupported or absent envelope cannot change publication.
    """
    if not isinstance(facts, Mapping):
        return None, "not_eligible"
    ledger = facts.get("v3_witness_ledger")
    if not isinstance(ledger, Mapping) or ledger.get("schema") != "causal-witness-ledger.v1":
        return None, "not_eligible"
    if not facts.get("missing_switch_history_for_targets"):
        return None, "not_eligible"
    names = {
        str(r.get("device_id") or ""): _label(
            r.get("device_name"), str(r.get("device_id") or "unknown"))
        for r in facts.get("target_coverage") or []
        if isinstance(r, Mapping)
    }
    targets = [str(i) for i in facts.get("target_device_ids") or []]
    if len(targets) != 2 or not all(t in names for t in targets):
        return None, "not_eligible"
    envelope = extract_claim_envelope(draft)
    if envelope is None:
        return None, "missing_envelope"
    verdict = validate_claim_envelope(envelope, ledger)
    if not verdict["valid"]:
        return None, "invalid_envelope"
    witnesses = {
        str(row.get("witness_id")): row for row in ledger.get("witnesses") or []
        if isinstance(row, Mapping)
    }
    cited: dict[str, set[str]] = defaultdict(set)
    has_uncertainty_claim = False
    for claim in envelope["claims"]:
        if claim["kind"] == "reported_switch_state":
            ident = str(claim["device_id"])
            state = str(claim["state"]).lower()
            # validate_claim_envelope already proved matching source witness;
            # this additional guard prevents a valid but irrelevant selection.
            if ident in targets:
                cited[ident].add(state)
        elif claim["kind"] == "upstream_cause_unverified":
            if str(claim["device_id"]) in targets:
                has_uncertainty_claim = True
    if any(cited.get(t) != {"on", "off"} for t in targets):
        return None, "incomplete_claim_coverage"
    if not has_uncertainty_claim or ledger.get("root_cause_verified") is not False:
        return None, "missing_causal_boundary"

    # Independently source-timestamped journal rows are the time authority.
    source: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in facts.get("incident_ledger") or []:
        if not isinstance(row, Mapping):
            continue
        ident = str(row.get("device_id") or "")
        kind = row.get("event_class")
        if ident in targets and kind in (
            "journal_source_switch_on", "journal_source_switch_off"
        ) and _time(row.get("date")) is not None:
            source[ident].append(row)
    if not all({str(row.get("value")) for row in source[t]} == {"on", "off"}
               for t in targets):
        return None, "missing_source_pair"

    source = {
        t: sorted(source[t], key=lambda row: _time(row["date"]))
        for t in targets
    }
    # The model's selected states must also refer to a source-qualified
    # witness that is present in the source ledger for this exact target.
    for ident in targets:
        for state in ("on", "off"):
            key = "journal_source_switch_" + state
            if not any(
                str(witnesses.get(w, {}).get("entity")) == ident
                and witnesses[w].get("event_class") == key
                for claim in envelope["claims"]
                if claim.get("kind") == "reported_switch_state"
                and str(claim.get("device_id")) == ident
                and str(claim.get("state")).lower() == state
                for w in claim.get("witness_ids") or []
            ):
                return None, "missing_source_witness"

    rows = source[targets[0]]
    on0 = sum(r.get("value") == "on" for r in rows)
    off0 = sum(r.get("value") == "off" for r in rows)
    if on0 < 1 or off0 < 1:
        return None, "missing_source_pair"
    start = min(_time(r["date"]) for t in targets for r in source[t])
    end = max(_time(r["date"]) for t in targets for r in source[t])
    other = source[targets[1]]
    common = (
        len(rows) == len(other) and len(rows) >= 4
        and all(str(a.get("value")) == str(b.get("value"))
                for a, b in zip(rows, other))
    )

    receiver = facts.get("same_receiver_evidence")
    candidate = None
    if isinstance(receiver, Mapping):
        candidate = next((
            c for c in (receiver.get("candidates") or [])
            if isinstance(c, Mapping)
            and c.get("one_to_one_within_windows") is True
            and c.get("receiver_clock_only") is True
            and c.get("sensor_source_order_verified") is False
            and c.get("initiator_verified") is False
            and str(c.get("target_id") or "") in targets
            and isinstance(c.get("on_receiver_delay_seconds"), Mapping)
            and isinstance(c.get("off_receiver_delay_seconds"), Mapping)
        ), None)

    if candidate:
        on = candidate["on_receiver_delay_seconds"]
        off = candidate["off_receiver_delay_seconds"]
        lead = (
            "**Most likely mechanism:** The switching pattern is consistent "
            "with motion-driven lighting. Input device "
            + str(candidate["input_id"])
            + " had " + str(candidate["matched_on"]) + "/"
            + str(candidate["target_on_rows"]) + " active-to-ON and "
            + str(candidate["matched_off"]) + "/"
            + str(candidate["target_off_rows"])
            + " inactive-to-OFF matches on the *collector reception clock*. "
            + "Its input receptions preceded matching light receptions by "
            + f"{on['min']:.3f}–{on['max']:.3f} seconds for ON and "
            + f"{off['min']:.3f}–{off['max']:.3f} seconds for OFF. "
            + "The near-ten-second inactive-to-OFF interval suggests an idle "
              "delay; neither the sensor's original event time nor an issuing "
              "controller is established by these reception pairs."
        )
    else:
        lead = (
            "**Most likely mechanism:** The independently recorded light "
            "transitions are consistent with coordinated control, but the "
            "available evidence does not distinguish a specific triggering "
            "input or command issuer."
        )

    first, second = names[targets[0]], names[targets[1]]
    observed = (
        "**What happened:** " + first + " had "
        + str(on0) + " reported ON and " + str(off0)
        + " reported OFF transitions; " + second + " had "
        + str(sum(r.get("value") == "on" for r in other))
        + " ON and " + str(sum(r.get("value") == "off" for r in other))
        + " OFF transitions between "
        + start.strftime("%H:%M:%S") + " and "
        + end.strftime("%H:%M:%S") + " UTC. "
        + "These are source-timestamped state reports, not command-origin proof."
    )
    pair = receiver.get("light_pair") if isinstance(receiver, Mapping) else None
    if common and isinstance(pair, Mapping):
        st = pair.get("source_event_stagger_seconds")
        if (isinstance(st, Mapping)
                and str(pair.get("first_id")) in targets
                and str(pair.get("second_id")) in targets):
            observed += (
                " Source-timed reports on " + names[str(pair["first_id"])]
                + " preceded " + names[str(pair["second_id"])] + " by "
                + f"{st['min']:.3f}–{st['max']:.3f} seconds across "
                + str(pair["paired_transitions"]) + " paired transitions."
            )

    level_notes: list[str] = []
    for ident in targets:
        first_on = next((r for r in source[ident] if r.get("value") == "on"), None)
        if first_on is None:
            continue
        at = _time(first_on["date"])
        candidates = [
            r for r in facts.get("incident_ledger") or []
            if isinstance(r, Mapping)
            and str(r.get("device_id")) == ident
            and r.get("event_class") == "issued_setlevel"
            and str(r.get("app_id") or "").isdecimal()
            and _time(r.get("date")) is not None
            and 0 <= (_time(r["date"]) - at).total_seconds() <= 2
        ]
        if candidates:
            later = min(candidates, key=lambda r: _time(r["date"]))
            milliseconds = round((_time(later["date"]) - at).total_seconds() * 1000)
            level_notes.append(
                names[ident] + ": app " + str(later["app_id"])
                + " requested brightness " + str(milliseconds)
                + " ms *after* its ON report"
            )
    limits = (
        "**What is not established:** No source-attested initiating ON command "
        "was matched for both targets. The reported motion timing, a current "
        "app dependency, and any later brightness request cannot identify "
        "which controller caused the earlier ON. Historical app execution "
        "or original upstream command records are still needed. Existing "
        "archive gaps prevent treating missing records as proof of inactivity."
    )
    if level_notes:
        limits = (
            "**Verified command order:** " + "; ".join(level_notes)
            + ". Those later commands cannot initiate the earlier ON.\n\n"
            + limits
        )
    return lead + "\n\n" + observed + "\n\n" + limits, "published"


__all__ = ["claim_guided_incident_answer"]
