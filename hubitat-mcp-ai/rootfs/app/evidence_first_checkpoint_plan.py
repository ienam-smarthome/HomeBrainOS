"""Deterministic, read-only checkpoint selection for investigation planning.

This selects an already justified evidence obligation; it never creates a
device/app identity, tool permission, network request or model answer.
Unverified, previously attempted and unavailable proposals are ineligible.
"""
from __future__ import annotations
from typing import Any, Iterable

PRIORITY = (
    "target-history",
    "issuer-decision",
    "upstream-input",
    "configuration-semantics",
    "diagnostic-discriminator",
)

def select_evidence_checkpoint(
    candidates: Iterable[dict[str, Any]],
    attempted: Iterable[str] = (),
) -> dict[str, Any] | None:
    """Select one unique scoped source obligation, or leave it unresolved.

    Candidates must be explicitly admitted upstream. In particular, an
    identity cannot be inferred from labels or a failed tool result.
    """
    used = set(attempted)
    eligible: list[tuple[int, str, dict[str, Any]]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        signature = item.get("signature")
        if kind not in PRIORITY or not isinstance(signature, str) or not signature:
            continue
        if signature in used or item.get("verified") is not True:
            continue
        if item.get("available") is not True or item.get("read_only") is not True:
            continue
        tool = item.get("tool")
        args = item.get("args")
        if not isinstance(tool, str) or not tool or not isinstance(args, dict):
            continue
        eligible.append((PRIORITY.index(kind), signature, item))
    if not eligible:
        return None
    eligible.sort(key=lambda row: (row[0], row[1]))
    chosen = eligible[0][2]
    return {
        "kind": chosen["kind"],
        "signature": chosen["signature"],
        "tool": chosen["tool"],
        "args": dict(chosen["args"]),
    }



class SourceCheckpointBudget:
    """One source-choice retry per new successful read scope, at most N.

    This gate is request-local. An offered model round does not by itself
    constitute new evidence. A failed read, repeated identical read or write
    cannot renew the opportunity. Upstream admission and tool permissions
    remain authoritative; this class never authorizes a tool operation.
    """

    def __init__(self, max_offers: int | None = 3) -> None:
        # None removes the arbitrary offer count but still requires strictly
        # new successful read scopes before each additional checkpoint.
        self.max_offers = (None if max_offers is None
                           else max(0, int(max_offers)))
        self.offered_kinds: list[str] = []
        self._last_scopes: frozenset[tuple[str, str]] | None = None

    @staticmethod
    def successful_read_scopes(
        receipts: Iterable[dict[str, Any]],
    ) -> frozenset[tuple[str, str]]:
        import json
        scopes: set[tuple[str, str]] = set()
        for item in receipts:
            if not isinstance(item, dict):
                continue
            if item.get("success") is not True or item.get("effect") != "read":
                continue
            tool = item.get("tool")
            args = item.get("arguments")
            if not isinstance(tool, str) or not tool or not isinstance(args, dict):
                continue
            # Source scope, not a model assertion, timestamp or mutable
            # response payload. Duplicate successes do not add progress.
            signature = json.dumps(args, sort_keys=True, separators=(",", ":"),
                                   default=str)
            scopes.add((tool, signature))
        return frozenset(scopes)

    def offer(self, kind: str, receipts: Iterable[dict[str, Any]]) -> bool:
        """Consume a bounded source-choice opportunity only after progress."""
        if not isinstance(kind, str) or not kind:
            return False
        current = self.successful_read_scopes(receipts)
        if (self.max_offers is not None
                and len(self.offered_kinds) >= self.max_offers):
            return False
        if self._last_scopes is not None and not self._last_scopes < current:
            return False
        self._last_scopes = current
        self.offered_kinds.append(kind)
        return True

__all__ = ["PRIORITY", "select_evidence_checkpoint", "SourceCheckpointBudget"]
