"""Request-local evidence scope for single-device read-only investigations.

Admission policy for redundant *broad* reads only. Source-proven target history
allows focused investigation without whole-home device inventory sweeps.
Never deny source-linked device logs, driver source, broker evidence or specific
related-device reads. Explicit cross-device/inventory questions keep the
existing read surface.

This is a call-breadth guard, not a factual/causal verdict or an AI word router.
All conclusions remain the responsibility of the evidence-synthesis layer.
"""
from __future__ import annotations

import re
from typing import Any

from typed_device_history_evidence import normalize_target_device_history


_WIDER_SCOPE = re.compile(
    r"(?i)\b(?:compare|comparison|across|other|another|all|every|whole[- ](?:home|hub)|"
    r"system[- ]wide|hub[- ]wide|multiple|several|list\s+devices|inventory)\b"
)


def single_device_broad_read_reason(
    request: str,
    evidence: list[dict[str, Any]],
    tool_name: str,
    arguments: dict[str, Any],
    *,
    domain: str | None,
) -> str | None:
    """Return a fixed reason code only for positively scoped redundant reads.

    Requires a verified *single* target from an id-scoped mixed history and
    a matching targeted device-state receipt. Fails open when any identity,
    intent or source integrity requirement is not satisfied.
    """
    if domain != "device_telemetry" or _WIDER_SCOPE.search(str(request or "")):
        return None
    normalized = normalize_target_device_history(evidence)
    if not isinstance(normalized, dict):
        return None
    label = str(normalized.get("deviceLabel") or "").strip()
    target_id = str(normalized.get("deviceId") or "")
    reported = normalized.get("reportedDeviceState")
    if not isinstance(reported, dict) or not target_id.isdigit():
        return None
    if str(reported.get("deviceId") or "") != target_id:
        return None
    # The user asked about this precise device; don't restrict general
    # questions after an incidental target history read.
    if not label or label.casefold() not in str(request or "").casefold():
        return None

    if tool_name == "homebrain_home_snapshot":
        return "whole-home-snapshot-after-target-resolution"

    if tool_name == "hub_read_devices":
        if arguments.get("resource") == "hubitat://context":
            return "whole-home-context-after-target-resolution"
        if arguments.get("tool") == "hub_list_devices":
            args = arguments.get("args")
            if isinstance(args, dict) and not any(
                args.get(key) not in (None, "", [], {})
                for key in ("labelFilter", "roomFilter", "filter",
                            "capabilityFilter", "changedSince",
                            "attributeNames", "onlyOn", "cursor")
            ):
                return "unscoped-inventory-after-target-resolution"

    if tool_name == "homebrain_filter_devices":
        attr = str(arguments.get("attribute") or "").casefold()
        value = str(arguments.get("value") or "").strip()
        # A filter for the *known name* is harmless and can check the
        # target identity, but filtering unrelated names across the hub is
        # not a targeted connectivity read.
        if attr == "name" and value and value.casefold() not in label.casefold():
            return "unrelated-name-filter-after-target-resolution"

    return None


__all__ = ["single_device_broad_read_reason"]
