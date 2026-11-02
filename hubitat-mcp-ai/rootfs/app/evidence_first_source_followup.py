"""One source-backed proposal at a time for the model's early no-tool recovery.

The existing candidate generators determine whether a source obligation exists.
This coordinator only orders those admitted candidates and consumes the shared
request-local evidence-progress budget. It does not execute MCP tools, infer
device identities, expand permission sets or author a final explanation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

EARLY_SOURCE_ORDER = ("target-history", "upstream-input", "inventory-evidence")
READ_ONLY_GATEWAYS = frozenset({
    "hub_read_devices", "hub_read_apps_code", "hub_read_rules",
    "hub_read_diagnostics", "hub_search_tools",
})


@dataclass(frozen=True)
class ModelSourceFollowup:
    kind: str
    admitted: Callable[[], bool]
    render: Callable[[], str | None]
    read_gateways: tuple[str, ...]
    metric: str
    hide_inventory: bool = False


def choose_model_source_followup(
    candidates: Iterable[ModelSourceFollowup],
    *,
    offer: Callable[[str], bool],
) -> tuple[ModelSourceFollowup, str] | None:
    """Choose the highest-priority *admitted* source, preserving legacy order.

    Check candidates lazily: lower-priority generators are not called after a
    higher-priority source is accepted. Only the existing checkpoint budget
    decides whether a further read-choice model round is justified.
    """
    ordered = sorted(
        (candidate for candidate in candidates
         if isinstance(candidate, ModelSourceFollowup)
         and candidate.kind in EARLY_SOURCE_ORDER),
        key=lambda candidate: EARLY_SOURCE_ORDER.index(candidate.kind),
    )
    for candidate in ordered:
        if (not candidate.read_gateways
                or not set(candidate.read_gateways) <= READ_ONLY_GATEWAYS
                or not candidate.metric):
            continue
        if not candidate.admitted():
            continue
        prompt = candidate.render()
        if not isinstance(prompt, str) or not prompt.strip():
            continue
        if offer(candidate.kind):
            return candidate, prompt
    return None


__all__ = ["EARLY_SOURCE_ORDER", "READ_ONLY_GATEWAYS", "ModelSourceFollowup",
           "choose_model_source_followup"]
