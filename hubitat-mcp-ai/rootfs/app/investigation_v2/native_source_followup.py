"""Evidence-state advice for a model-chosen, read-only source investigation.

No MCP call, ID attestation, permission grant or routing based on question
words is performed here. An unverified driver ID is never guessed.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any


def source_path_followup(
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str],
    driver_ids: set[str],
) -> dict[str, Any] | None:
    """Suggest one discriminating model-chosen next step for a source gap."""
    focus = {str(x) for x in focus_ids}
    if len(focus) != 1:
        return None
    device_id = next(iter(focus))
    warning = any(
        w.get("operation") == "hub_get_logs"
        and any(
            isinstance(g, Mapping)
            and str(g.get("source_id")) == device_id
            for g in (w.get("source_data", {}).get("log_summary", {})
                      .get("warning_error_groups", []))
        )
        for w in witnesses
    )
    if not warning:
        return None
    source_reads = [
        w for w in witnesses if w.get("operation") == "hub_get_source"
    ]
    if any(w.get("source_data", {}).get("source_complete") is True
           for w in source_reads):
        return {
            "status": "complete_source_structure_available",
            "limits": "Static code does not establish callback execution or hub CPU contribution.",
        }
    if source_reads:
        return {
            "status": "source_read_already_attempted_without_complete_code",
            "limits": "Do not repeat the same metadata-only source read. A different "
                      "source endpoint, complete page or runtime profile is required.",
        }
    config_reads = [
        w for w in witnesses
        if w.get("operation") == "hub_get_device"
        and str(w.get("read_filters", {}).get("deviceId")) == device_id
        and w.get("source_data", {}).get("device_mode") == "configuration"
    ]
    for w in reversed(config_reads):
        identity = w.get("source_data", {}).get("device_identity", {})
        driver_id = str(identity.get("driverId") or "")
        if driver_id and driver_id in driver_ids:
            return {
                "status": "verified_driver_identity_available",
                "evidence_read": w.get("read"),
                "model_chosen_read": {
                    "operation": "hub_get_source",
                    "args": {"type": "driver", "id": driver_id},
                },
                "limits": "Gateway may return metadata only; source identity and "
                          "content coverage must be checked after the READ.",
            }
    if config_reads:
        return {
            "status": "driver_identity_missing_from_configuration",
            "limits": "No independently attested driver code ID; do not guess or "
                      "substitute the device ID or an issuing-app ID.",
        }
    return {
        "status": "driver_identity_not_yet_inspected",
        "model_chosen_read": {
            "operation": "hub_get_device",
            "args": {"deviceId": device_id, "mode": "configuration"},
        },
        "limits": "A read of configuration may expose a driver ID; do not assume "
                  "driver source exists or that its static structure proves runtime cause.",
    }


__all__ = ["source_path_followup"]
