"""Bound absolute zero-state claims to typed, source-complete aggregates.

A complete device-list snapshot and a successful ON-filter are different
from proof every eligible device supplied an ON/OFF state. This guard uses
only safe current-request aggregate receipt counts; it never re-reads Hubitat,
reconstructs device names, or infers physical device connectivity.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_ZEROS = {
    "lights": re.compile(
        r"(?i)\b(?:no\s+(?:recognised\s+|recognized\s+)?lights?\s+"
        r"(?:are\s+)?(?:currently\s+)?on"
        r"|(?:all|every)\s+lights?\s+(?:are\s+)?(?:currently\s+)?off"
        r"|none\s+of\s+(?:the\s+)?lights?\s+(?:are\s+)?(?:currently\s+)?on)\b[.!]?"
    ),
    "non_light_switches": re.compile(
        r"(?i)\b(?:no\s+(?:non[- ]light\s+)?switches\s+"
        r"(?:are\s+)?(?:currently\s+)?on"
        r"|(?:all|every)\s+switches\s+(?:are\s+)?(?:currently\s+)?off"
        r"|none\s+of\s+(?:the\s+)?switches\s+(?:are\s+)?(?:currently\s+)?on)\b[.!]?"
    ),
}
_TOOLS = {
    "homebrain_active_lights": "lights",
    "homebrain_active_switches": "non_light_switches",
}


def _typed_aggregate(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    kind = _TOOLS.get(row.get("tool"))
    if (
        kind is None or row.get("success") is not True
        or row.get("supports_live_claim") is not True
        or row.get("effect") != "read"
        or row.get("mutates") is not False
    ):
        return None
    details = row.get("details")
    state = details.get("aggregateState") if isinstance(details, Mapping) else None
    if not isinstance(state, Mapping) or state.get("category") != kind:
        return None
    nums = ("onCount", "candidateCount", "unknownStateCount", "totalScanned")
    if not all(type(state.get(k)) is int and 0 <= state[k] <= 100000 for k in nums):
        return None
    if not all(type(state.get(k)) is bool for k in (
        "scopeVerified", "inventoryComplete", "stateCoverageComplete"
    )):
        return None
    if state.get("scope") not in {"whole-home", "room", "unresolved-room"}:
        return None
    if state["onCount"] + state["unknownStateCount"] > state["candidateCount"]:
        return None
    if state["stateCoverageComplete"] != (state["unknownStateCount"] == 0):
        return None
    return dict(state)


def guard_aggregate_zero_claims(
    message: str, evidence: Sequence[Mapping[str, Any]],
) -> tuple[str, list[str]]:
    """Calibrate only absolute ON=0 claims, preserving other model prose.

    A verified complete inventory may contain recognized devices with an
    unknown switch value. Such devices cannot be silently called OFF.
    Unrelated results, ambiguous or missing receipts are never promoted to
    evidence. One useful read is enough: no additional source calls.
    """
    original = str(message or "")
    if not original.strip():
        return original, []
    scoped: dict[str, list[dict[str, Any]]] = {}
    for receipt in evidence:
        data = _typed_aggregate(receipt)
        if data is not None:
            scoped.setdefault(data["category"], []).append(data)
    corrected = original
    issues: list[str] = []
    for category, pattern in _ZEROS.items():
        if pattern.search(corrected) is None:
            continue
        options = scoped.get(category) or []
        if len(options) != 1:
            # Conflicting separate reads are not a complete zero proof.
            continue
        info = options[0]
        verified_scope = (
            info["scopeVerified"] and info["inventoryComplete"]
            and info["scope"] in {"whole-home", "room"}
        )
        # An aggregate can be complete for a verified requested room as
        # well as for the whole house. The original user intent sets scope;
        # the guard must not silently broaden a valid room-specific answer.
        category_name = ("recognised light devices" if category == "lights"
                         else "recognised non-light switches")
        if not verified_scope:
            replacement = (
                f"The requested {category_name} inventory was "
                "not verified; a zero-active conclusion is not established."
            )
            issue = "aggregate_inventory_scope_unverified"
        elif info["onCount"] > 0:
            replacement = (
                f"The checked snapshot reports {info['onCount']} "
                f"{category_name} ON; the zero-active claim is not supported."
            )
            issue = "aggregate_zero_contradicted"
        elif info["candidateCount"] == 0:
            replacement = (
                f"No {category_name} were recognised in the checked inventory; "
                "that does not prove every physical device is OFF."
            )
            issue = "aggregate_no_eligible_candidates"
        elif not info["stateCoverageComplete"]:
            replacement = (
                f"No {category_name} reported ON in the checked snapshot, "
                f"but {info['unknownStateCount']} candidate(s) lacked a usable "
                "ON/OFF state. A complete zero-active conclusion is unverified."
            )
            issue = "aggregate_state_coverage_gap"
        else:
            # The claim is supported as a source-reported aggregate result,
            # not as an independent test of physical light output.
            continue
        corrected, changed = pattern.subn(replacement, corrected)
        if changed:
            issues.append(issue)
    return corrected, list(dict.fromkeys(issues))


__all__ = ["guard_aggregate_zero_claims"]
