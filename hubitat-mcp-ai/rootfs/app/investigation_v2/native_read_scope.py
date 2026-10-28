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
    target = str(focused_ids[0])
    # Require independently source-attested target warning evidence, rather
    # than inferring scope or causality from a keyword in the user question.
    target_warned = any(
        w.get("operation") == "hub_get_logs"
        and isinstance(w.get("source_data"), Mapping)
        and isinstance(w["source_data"].get("log_summary"), Mapping)
        and any(
            isinstance(group, Mapping)
            and str(group.get("source_id")) == target
            for group in w["source_data"]["log_summary"].get(
                "warning_error_groups", [])
        )
        for w in witnesses
    )
    return "target_device_history_scope_missing" if target_warned else None
