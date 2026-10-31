"""Stage 3: evidence-grounded next-read frontier (OFFLINE SHADOW ONLY).

An adapter over the existing causal source-feasibility and canonical evidence
modules, not another evidence graph or an alternative MCP agent. The model may
propose discriminating READs, but every candidate is gated by independently
scoped source IDs, an explicitly supplied current read-tool catalog, and
the exact-attempt ledger. Nothing here dispatches tools, grants permission,
writes to a device, or publishes a causal claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping, Sequence

from canonical_investigation_evidence import build_canonical_evidence_view
from causal_source_feasibility import build_source_feasibility_choices


# Only schemas for which we can *validate* source-scoped arguments are accepted
# in this shadow stage. Tool authorization is checked separately and afresh by
# the production model/host; catalog membership is not access permission.
_READ_SCOPES = {
    "hub_list_device_events": ("deviceId",),
    "hub_list_device_dependents": ("deviceId",),
    "hub_get_app_config": ("appId",),
}
_HISTORY_FILTERS = frozenset(("since", "until", "attribute", "offset", "length"))
_COMMANDS = frozenset(("on", "off", "toggle", "setLevel",
                       "setHeatingSetpoint", "setThermostatMode",
                       "open", "close", "setPosition"))


def _id(value: Any) -> str | None:
    if type(value) not in (str, int):
        return None
    value = str(value)
    if not 0 < len(value) <= 16 or not value.isdecimal():
        return None
    number = int(value)
    return str(number) if number > 0 else None


def _args(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    outer = receipt.get("arguments")
    if not isinstance(outer, Mapping):
        return {}
    inner = outer.get("args")
    return inner if isinstance(inner, Mapping) else outer


def _read(receipt: Any) -> bool:
    return (isinstance(receipt, Mapping)
            and receipt.get("mutates") is not True
            and receipt.get("effect") in (None, "read")
            and receipt.get("supports_live_claim") is not False)


def _time(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat() if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _leaf(row: Mapping[str, Any]) -> str:
    return str(row.get("sub_tool") or row.get("tool") or "")


def _scope(leaf: str, args: Any) -> dict[str, Any] | None:
    """Reject unknown keys, secrets, absent targets and unbounded filters."""
    if leaf not in _READ_SCOPES or not isinstance(args, Mapping):
        return None
    required = _READ_SCOPES[leaf][0]
    allowed = {required}
    if leaf == "hub_list_device_events":
        allowed |= _HISTORY_FILTERS
    if set(args) - allowed or required not in args:
        return None
    ident = _id(args[required])
    if ident is None:
        return None
    result: dict[str, Any] = {required: ident}
    if leaf != "hub_list_device_events":
        return result
    for key in ("since", "until"):
        if key in args:
            stamp = _time(args[key])
            if stamp is None:
                return None
            result[key] = stamp
    if ("since" in result) != ("until" in result):
        return None
    if "since" in result:
        start = datetime.fromisoformat(result["since"])
        end = datetime.fromisoformat(result["until"])
        if not 0 < (end - start).total_seconds() <= 90 * 86400:
            return None
    if "attribute" in args:
        attr = args["attribute"]
        if not isinstance(attr, str) or not attr or len(attr) > 60:
            return None
        if any(not (x.isalnum() or x in "_-") for x in attr):
            return None
        result["attribute"] = attr
    for key in ("offset", "length"):
        if key in args:
            value = args[key]
            if type(value) is not int or not 0 <= value <= (5000 if key == "offset" else 200):
                return None
            result[key] = value
    return result


def _signature(leaf: str, args: Mapping[str, Any]) -> str:
    return json.dumps([leaf, args], sort_keys=True, separators=(",", ":"))


def _discovered_ids(receipts: Sequence[Mapping[str, Any]]) -> tuple[set[str], set[str], set[str]]:
    """IDs admitted only from successful scoped receipts / command producers."""
    view = build_canonical_evidence_view(receipts)
    devices = {i.entity_id for i in view.identities if i.kind == "device"}
    apps = {i.entity_id for i in view.identities if i.kind == "app"}
    command_apps = {e.issuer_app_id for e in view.events
                    if e.role == "issued-command" and e.issuer_app_id}
    apps.update(command_apps)
    for row in receipts[:160]:
        if not _read(row) or row.get("success") is not True:
            continue
        leaf = _leaf(row)
        args = _args(row)
        if leaf == "hub_list_device_events":
            ident = _id(args.get("deviceId"))
            if ident:
                devices.add(ident)
        elif leaf == "hub_list_device_dependents":
            ident = _id(args.get("deviceId"))
            detail = row.get("details")
            if ident and isinstance(detail, Mapping) and _id(detail.get("deviceId")) == ident:
                devices.add(ident)
                # A current dependency is an investigation lead, not an
                # independently witnessed historical command.
                dependencies = detail.get("appsUsing")
                if not isinstance(dependencies, list):
                    dependencies = []
                for app in dependencies[:60]:
                    app_id = (_id(app.get("appId") or app.get("id"))
                              if isinstance(app, Mapping) else _id(app))
                    if app_id:
                        apps.add(app_id)
    return devices, apps, command_apps


def build_stage3_read_frontier(
    receipts: Sequence[Mapping[str, Any]],
    *,
    facts: Mapping[str, Any] | None = None,
    model_proposals: Sequence[Mapping[str, Any]] = (),
    available_read_tools: Sequence[str] = (),
    max_choices: int = 12,
) -> dict[str, Any]:
    """Score model- and existing-frontier-proposed reads, never execute them.

    No call-count stop rule: only an exact-attempt fingerprint suppresses a
    previously attempted operation. A different bounded history window is a
    different read; identical failed calls are suppressed rather than retried.
    """
    max_choices = max(1, min(int(max_choices), 24))
    known = frozenset(t for t in available_read_tools
                      if isinstance(t, str) and t in _READ_SCOPES)
    devices, apps, command_apps = _discovered_ids(receipts)
    attempts: dict[str, str] = {}
    duplicate_attempts = 0
    for receipt in receipts[:160]:
        if not _read(receipt):
            continue
        leaf = _leaf(receipt)
        scoped = _scope(leaf, _args(receipt))
        if scoped is None:
            continue
        signature = _signature(leaf, scoped)
        if signature in attempts:
            duplicate_attempts += 1
        status = "succeeded" if receipt.get("success") is True else "failed-or-unavailable"
        attempts[signature] = status

    # Existing source-feasibility module already implements the specialised
    # receiver-pattern and current app-dependency logic. Reuse its candidates;
    # no independent hardcoded sensor/room causal inference.
    prior = build_source_feasibility_choices(facts, receipts, max_options=6)
    existing = prior.get("candidate_reads") or [] if isinstance(prior, Mapping) else []
    candidates: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    seen: set[str] = set()

    def discard(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for source, proposals in (("existing-source-frontier", existing[:12]),
                              ("model", model_proposals[:48])):
        for suggestion in proposals:
            if not isinstance(suggestion, Mapping):
                discard("invalid-proposal")
                continue
            leaf = suggestion.get("leaf")
            args = suggestion.get("args")
            if not isinstance(leaf, str) or leaf not in known:
                discard("not-in-current-validated-read-catalog")
                continue
            scoped = _scope(leaf, args)
            if scoped is None:
                discard("invalid-or-unbounded-scope")
                continue
            ident = scoped["deviceId"] if "deviceId" in scoped else scoped["appId"]
            if ident not in (devices if "deviceId" in scoped else apps):
                discard("identifier-not-source-attested")
                continue
            sig = _signature(leaf, scoped)
            if sig in attempts:
                discard("exact-read-already-attempted")
                continue
            if sig in seen:
                discard("duplicate-frontier-candidate")
                continue
            seen.add(sig)
            priority = suggestion.get("priority")
            score = 90 if source == "existing-source-frontier" and priority == "evidence-ranked" else (
                68 if source == "existing-source-frontier" else 50)
            if leaf == "hub_get_app_config" and ident in command_apps:
                score += 10
            if leaf == "hub_list_device_events" and "since" in scoped:
                score += 6
            # A model-supplied self-assessed score is deliberately ignored;
            # untrusted model text cannot manufacture evidence authority.
            candidates.append({
                "leaf": leaf, "args": scoped, "score": score,
                "origin": source, "source_attested_id": ident,
                "advisory_only": True,
                "reason": (
                    str(suggestion.get("reason") or "Model-proposed bounded evidence discriminator")[:180]
                    if source == "existing-source-frontier"
                    else "Model-proposed read; scope and leaf validated, relevance still for model to judge"
                ),
                "cannot_prove": "causal initiator, physical acknowledgement, or complete historical coverage",
            })
    candidates.sort(key=lambda c: (-c["score"], c["leaf"], _signature(c["leaf"], c["args"])))
    selected = candidates[:max_choices]
    return {
        "schema": "homebrain-stage3-read-frontier.v1",
        "shadow_only": True, "executes_tools": False,
        "current_catalog_validated": bool(known),
        "candidate_reads": selected,
        "candidate_count": len(candidates),
        "candidate_count_omitted": max(0, len(candidates) - max_choices),
        "attempt_count": len(attempts), "duplicate_attempt_count": duplicate_attempts,
        "rejected_candidate_counts": rejected,
        "existing_feasibility_available": isinstance(prior, Mapping),
        "unresolved_source_questions": (prior.get("unresolved_sources") or [])[:3]
                                       if isinstance(prior, Mapping) else [],
        "next_action": ("model-select-validated-read" if selected
                        else "model-discover-new-read-or-report-limits"),
        "no_verified_new_candidate_is_not_source_absence": True,
        "no_arbitrary_five_call_limit": True,
        "candidate_is_not_new_permission": True,
        "source_order_or_root_cause_proven": False,
    }


__all__ = ["build_stage3_read_frontier"]
