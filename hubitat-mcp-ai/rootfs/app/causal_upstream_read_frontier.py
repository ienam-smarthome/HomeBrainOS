"""V3 source-witness-ranked, model-selectable upstream read frontier.

This is an advisory projection of currently recorded READ receipts, not a
planner that executes anything, grants permissions, interprets arbitrary
question words, or certifies causation. A sensor's collector-reception pattern
can nominate *which device dependency to inspect next*, never its origin time
or the app that historically switched on a light.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _id(value: Any) -> str:
    v = str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    return v if v.isdecimal() and int(v) > 0 else ""


def _args(row: Mapping[str, Any]) -> Mapping[str, Any]:
    args = row.get("arguments")
    if not isinstance(args, Mapping):
        return {}
    inner = args.get("args")
    return inner if isinstance(inner, Mapping) else args


def _leaf(row: Mapping[str, Any]) -> str:
    return str(row.get("sub_tool") or row.get("tool") or "")


def _read(row: Mapping[str, Any]) -> bool:
    return (row.get("mutates") is not True
            and row.get("effect") in ("read", None))


def _apps_using(row: Mapping[str, Any]) -> set[str]:
    """Only structured, verified app IDs under the explicit appsUsing key."""
    details = row.get("details")
    if not isinstance(details, Mapping):
        return set()
    apps = details.get("appsUsing")
    if not isinstance(apps, list):
        return set()
    ids: set[str] = set()
    for app in apps[:80]:
        if isinstance(app, Mapping):
            app_id = _id(app.get("appId") or app.get("id"))
        else:
            app_id = _id(app)
        if app_id:
            ids.add(app_id)
    return ids


def rank_upstream_read_frontier(
    facts: Mapping[str, Any] | None,
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Rank exact READ leads from a complete one-to-one collector pattern.

    The strongest input ID is authorized only when the same request contains
    a successful independently scoped native device-history read *and* an
    archive read for that ID, with an untruncated, full retained receipt page.
    Each subsequent leaf must already have succeeded somewhere in the active
    read-only catalog; failed exact attempts are never silently reissued.
    """
    if not isinstance(facts, Mapping):
        return None
    receiver = facts.get("same_receiver_evidence")
    if not isinstance(receiver, Mapping) or receiver.get("schema") != "collector-reception-evidence.v1":
        return None
    targets = {_id(i) for i in facts.get("target_device_ids") or []} - {""}
    if not targets:
        return None
    samples = {
        _id(x.get("device_id")): x
        for x in facts.get("archived_input_sample_coverage") or []
        if isinstance(x, Mapping) and _id(x.get("device_id"))
    }
    verified_read = [r for r in receipts[:160] if isinstance(r, Mapping) and _read(r)]
    successes = [r for r in verified_read if r.get("success") is True]
    available = {_leaf(r) for r in successes}

    ranked = []
    for c in (receiver.get("candidates") or [])[:8]:
        if not isinstance(c, Mapping):
            continue
        ident = _id(c.get("input_id"))
        count = c.get("input_returned_rows")
        entry = samples.get(ident)
        if (not ident or ident in targets
                or c.get("one_to_one_within_windows") is not True
                or c.get("receiver_clock_only") is not True
                or c.get("sensor_source_order_verified") is not False
                or c.get("initiator_verified") is not False
                or type(count) is not int or count < 6
                or type(c.get("matched_on")) is not int or c["matched_on"] < 3
                or type(c.get("matched_off")) is not int or c["matched_off"] < 3
                or not isinstance(entry, Mapping)
                or entry.get("query_truncated") is not False
                or entry.get("retained_receipt_observations") != count
                or entry.get("retrieved_observations") != count):
            continue
        native = any(
            _leaf(r) == "hub_list_device_events"
            and _id(_args(r).get("deviceId")) == ident
            for r in successes
        )
        archive = any(
            r.get("tool") == "homebrain_evidence_journal"
            and r.get("evidence_kind") == "group_archived_input_history"
            and _id(_args(r).get("device_id")) == ident
            for r in successes
        )
        if native and archive:
            ranked.append(c)
    if not ranked:
        return None

    ranked.sort(key=lambda c: (
        -(c["matched_on"] + c["matched_off"]),
        -c["input_returned_rows"],
        int(_id(c["input_id"])),
    ))
    lead = ranked[0]
    ident = _id(lead["input_id"])
    dependents_attempts = [
        r for r in verified_read
        if _leaf(r) == "hub_list_device_dependents"
        and _id(_args(r).get("deviceId")) == ident
    ]
    successes_input = [r for r in dependents_attempts if r.get("success") is True]
    choices: list[dict[str, Any]] = []
    # The native target source's own app dependencies are not enough to
    # establish historical input->app->light execution.
    if not dependents_attempts and "hub_list_device_dependents" in available:
        choices.append({
            "source_category": "strongest-receiver-input-current-dependencies",
            "leaf": "hub_list_device_dependents",
            "args": {"deviceId": ident},
            "priority": "evidence-ranked",
            "reason": "All input active/inactive receptions uniquely paired with source-qualified target switch receptions; inspect this verified input's current app subscriptions before additional low-signal logs.",
            "cannot_prove": "historical app execution, sensor source clock, or original ON-command origin",
        })
    # Only if BOTH ends' actual dependency lists expose explicit app IDs.
    # The tool receipt summary ('appsUsing' in a field list) is NOT enough.
    target_apps: set[str] = set()
    for row in successes:
        if (_leaf(row) == "hub_list_device_dependents"
                and _id(_args(row).get("deviceId")) in targets):
            target_apps.update(_apps_using(row))
    candidate_apps: set[str] = set()
    for row in successes_input:
        candidate_apps.update(_apps_using(row))
    shared = sorted(target_apps & candidate_apps, key=int)
    configured = {
        _id(_args(r).get("appId")) for r in successes
        if _leaf(r) == "hub_get_app_config"
    }
    attempted_config = {
        _id(_args(r).get("appId")) for r in verified_read
        if _leaf(r) == "hub_get_app_config"
    }
    if "hub_get_app_config" in available:
        for app_id in shared[:4]:
            if app_id not in attempted_config:
                choices.append({
                    "source_category": "source-attested-shared-input-target-app",
                    "leaf": "hub_get_app_config",
                    "args": {"appId": app_id},
                    "priority": "evidence-ranked",
                    "reason": "The current input and target dependency lists share this explicit app ID; its configuration is a next historical execution lead, not evidence of past command issuance.",
                    "cannot_prove": "the app ran at the incident time or initiated the original ON",
                })

    return {
        "schema": "causal-upstream-read-frontier.v1",
        "advisory_only": True,
        "lead": {
            "input_id": ident,
            "target_id": _id(lead.get("target_id")),
            "matched_active_to_on": lead["matched_on"],
            "matched_inactive_to_off": lead["matched_off"],
            "input_reception_rows": count,
            "one_to_one_receiver_pattern": True,
            "source_order_verified": False,
            "command_initiator_verified": False,
        },
        "dependency_read_status": (
            "source-observed" if successes_input
            else "attempted-no-success" if dependents_attempts
            else "not-attempted"
        ),
        "shared_current_app_ids": shared[:8],
        "checked_shared_app_configs": [i for i in shared if i in configured][:8],
        "candidate_reads": choices[:4],
        "no_new_permissions_granted": True,
    }


__all__ = ["rank_upstream_read_frontier"]
