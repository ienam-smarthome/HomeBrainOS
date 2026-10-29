"""Source-grounded READ scope contract for model-native investigations.

A device-scoped diagnosis may contain unrelated hub/location evidence, but
an unscoped history query must not silently become evidence for a previously
resolved target. This validator never executes or rewrites a tool call.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence


def target_history_scope_problem(
    operation: str | None,
    args: Mapping[str, Any],
    focused_ids: Sequence[str],
    witnesses: Sequence[Mapping[str, Any]],
) -> str | None:
    if operation != "hub_list_device_events" or len(focused_ids) != 1:
        return None
    if args.get("deviceId") is not None or args.get("appId") is not None:
        return None
    # An explicitly requested hub/location event mode is a different
    # investigation; do not prohibit intentional hub-wide source discovery.
    if args.get("mode") is not None:
        return None
    # A uniquely verified target has been selected, but the proposal has
    # neither a target nor an explicit hub/location mode. Even before a
    # target WARN is fetched, this read would silently return unrelated
    # hub-wide activity. Never infer device history from such a result.
    # This rejects the proposal only; a deliberate scoped or mode-specific
    # model-selected READ remains available after the normal host guards.
    return "target_device_history_scope_missing"
