"""V3 feasibility-aware causal source choices for the ORIGINAL model tool loop.

This module never performs MCP calls, grants tool permission, or invents
upstream source capabilities. Choices use only source-attested device IDs,
observed command-app IDs, and READ leaf operations already successfully
executed in this request. A successful empty response does not prove no
historical commands existed. Suggestions remain model-selectable, not routes.
"""
from __future__ import annotations

from collections import Counter
import json
from typing import Any, Mapping, Sequence


def _id(x: Any) -> str:
    value = str(x or "")
    return value if value.isdecimal() and int(value) > 0 else ""


def _args(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    outer = receipt.get("arguments")
    if not isinstance(outer, Mapping):
        return {}
    inner = outer.get("args")
    return inner if isinstance(inner, Mapping) else outer


def _leaf(receipt: Mapping[str, Any]) -> str:
    value = receipt.get("sub_tool") or receipt.get("tool")
    return str(value or "")[:90]


def _signature(receipt: Mapping[str, Any]) -> str:
    """Stable signature, not a log of source contents or credentials."""
    args = _args(receipt)
    allowed = {}
    for key in ("deviceId", "appId", "since", "until",
                "attribute", "includeSettings", "offset", "length"):
        val = args.get(key)
        if isinstance(val, (str, int, bool)):
            allowed[key] = str(val)[:80]
    return _leaf(receipt) + ":" + json.dumps(allowed, sort_keys=True)


def build_source_feasibility_choices(
    facts: Mapping[str, Any] | None,
    receipts: Sequence[Mapping[str, Any]],
    *,
    max_options: int = 3,
) -> dict[str, Any] | None:
    """List bounded *potentially useful* already-authorized read leaves.

    An observed successful read proves this leaf was previously usable; it
    cannot promise access on the next model round. The agent's tool catalog
    and permissions remain authoritative. All candidate IDs must come from
    the target/source witness ledger, not free-text, word routing or rooms.
    """
    ledger = facts.get("v3_witness_ledger") if isinstance(facts, Mapping) else None
    if not isinstance(ledger, Mapping) or ledger.get("schema") != "causal-witness-ledger.v1":
        return None
    max_options = max(1, min(int(max_options), 6))
    targets = sorted({_id(x) for x in facts.get("target_device_ids") or []} - {""}, key=int)[:12]
    source_apps = sorted({
        _id(x) for x in facts.get("target_observed_command_app_ids") or []
    } - {""}, key=int)[:12]
    # In-scope successful read receipts are the capability evidence.
    successes: list[Mapping[str, Any]] = [
        r for r in receipts[:160] if isinstance(r, Mapping)
        and r.get("success") is True and r.get("mutates") is not True
        and r.get("effect") in (None, "read")
    ]
    available_leaves = {_leaf(r) for r in successes}
    checked_dependents = {
        _id(_args(r).get("deviceId")) for r in successes
        if _leaf(r) == "hub_list_device_dependents"
    }
    checked_configs = {
        _id(_args(r).get("appId")) for r in successes
        if _leaf(r) == "hub_get_app_config"
    }
    target_history_ids = {
        _id(_args(r).get("deviceId")) for r in successes
        if _leaf(r) == "hub_list_device_events"
    }
    # A failed leaf may be repaired and later succeed. Only successful exact
    # duplicate signatures are redundant reads.
    repeats = Counter(_signature(r) for r in successes)
    duplicate_success_count = sum(max(0, n - 1) for n in repeats.values())

    # These candidate operations are read-only and demonstrably executed
    # successfully in the request. The original model decides whether/when
    # to call them, with *its* active catalog authorization.
    choices: list[dict[str, Any]] = []
    if "hub_list_device_dependents" in available_leaves:
        for ident in targets:
            if ident not in checked_dependents:
                choices.append({
                    "source_category": "current-target-app-dependencies",
                    "leaf": "hub_list_device_dependents",
                    "args": {"deviceId": ident},
                    "priority": "potentially-useful",
                    "reason": "This verified target lacks a scoped dependency read; current app associations can nominate further source checks.",
                    "cannot_prove": "historical application execution or original ON-command initiator",
                })
    if "hub_get_app_config" in available_leaves:
        for app in source_apps:
            if app not in checked_configs:
                choices.append({
                    "source_category": "observed-command-app-current-config",
                    "leaf": "hub_get_app_config",
                    "args": {"appId": app},
                    "priority": "potentially-useful",
                    "reason": "This app actually issued a target command, but its current configuration has not been checked.",
                    "cannot_prove": "historical execution or the initiating cause of an earlier state",
                })
    # The absence of a dedicated command-origin tool in observed receipts
    # does NOT show it doesn't exist; one model-led catalog discovery is
    # reasonable if not performed. Never fabricate a leaf name here.
    # A tool search about Groovy source is not evidence that an original
    # command-history provider was searched. Do not infer absence from any
    # unrelated successful discovery attempt.
    discovery_attempted = any(
        r.get("tool") == "hub_search_tools" and r.get("success") is True
        for r in receipts[:160]
    )
    known_issuer_matches = list(
        ledger.get("immediate_hubitat_on_command_matches") or [])
    remaining_issuer_gap = (
        int(ledger.get("issuer_verified_target_count") or 0)
        < int(ledger.get("target_count") or 0)
    )
    options = choices[:max_options]
    # It is accurate to state what the inspected *receipts* did not attest,
    # not to assert that a historical command or external source did not exist.
    open_sources: list[dict[str, Any]] = []
    if remaining_issuer_gap:
        open_sources.append({
            "required": "original-ON-command-issuer",
            "status": "not-witnessed-in-retained-sources",
            "discovery": (
                "No prior catalog discovery in these receipts; the model may check the live read-only catalog"
                if not discovery_attempted
                else "A catalog search occurred, but its topic may differ; only current authorized tools can confirm command-origin access"
            ),
            "not_equivalent_to": [
                "source-timed switch state", "later setLevel command",
                "notified app", "sensor reception coincidence",
                "current app source code",
            ],
        })
    if (facts.get("archived_input_collector_observations") or 0) > 0:
        open_sources.append({
            "required": "original-input-event-timestamps",
            "status": "only-collector-reception-available-for-some-inputs",
            "not_equivalent_to": ["source event chronology", "command origin"],
        })
    return {
        "schema": "causal-source-feasibility.v1",
        "advisory_only": True,
        "verified_target_count": len(targets),
        "target_scoped_history_reads": sum(x in target_history_ids for x in targets),
        "already_checked_dependency_targets": sorted(checked_dependents - {""}, key=int)[:12],
        "already_checked_command_app_configs": sorted(checked_configs - {""}, key=int)[:12],
        "successful_exact_duplicate_read_count": duplicate_success_count,
        "candidate_reads": options,
        "additional_candidates_omitted": max(0, len(choices) - len(options)),
        "unresolved_sources": open_sources[:3],
        "recorded_immediate_command_matches": len(known_issuer_matches),
        "no_further_concrete_read_in_verified_receipts": not bool(choices),
        "has_independently_verified_upstream_origin": False,
        "source_absence_proven": False,
        "no_new_permissions_granted": True,
    }


__all__ = ["build_source_feasibility_choices"]
