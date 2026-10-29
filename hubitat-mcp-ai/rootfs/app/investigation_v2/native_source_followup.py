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
    *, failures: Sequence[Mapping[str, Any]] = (),
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
            # Only source for this specific device's independently identified
            # driver qualifies. An app source, or a driver used by another
            # device, cannot close the device-driver execution-path gap.
            matching_reads = [
                item for item in witnesses
                if item.get("operation") == "hub_get_source"
                and item.get("source_data", {}).get("requested_source_type") == "driver"
                and str(item.get("source_data", {}).get("requested_source_id")) == driver_id
            ]
            if any(item.get("source_data", {}).get("source_complete") is True
                   for item in matching_reads):
                return {
                    "status": "complete_source_structure_available",
                    "limits": "Static code does not establish callback execution "
                              "or hub CPU contribution.",
                }
            if matching_reads:
                return {
                    "status": "source_read_already_attempted_without_complete_code",
                    "limits": "Do not repeat the same metadata-only driver read. "
                              "A complete page or runtime profile is required.",
                }
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
        latest = config_reads[-1]
        metadata = latest.get("source_data", {}).get(
            "driver_source_metadata", {})
        metadata = metadata if isinstance(metadata, Mapping) else {}
        unavailable = str(metadata.get("status") or "").lower() in (
            "unavailable", "unsupported", "missing", "not_found",
        )
        return {
            "status": ("driver_source_unavailable_no_attested_id"
                       if unavailable else
                       "driver_identity_missing_from_configuration"),
            "evidence_read": latest.get("read"),
            "limits": (
                "Device configuration reports driver source unavailable "
                "and supplies no independently attested driver code ID. "
                "Do not guess an ID or claim driver implementation was inspected."
                if unavailable else
                "No independently attested driver code ID; do not guess or "
                "substitute the device ID or an issuing-app ID."
            ),
        }
    # A failed model-chosen configuration read IS an attempted inspection.
    # Do not present it as "not yet inspected" or suggest the exact failed
    # call again. A successful default device read is not a configuration
    # inspection; require the documented mode and verified subject in the
    # failure receipt before attributing this specific blocker.
    for failed in reversed(failures):
        if not isinstance(failed, Mapping) or failed.get("operation") != "hub_get_device":
            continue
        filters = failed.get("read_filters")
        if (isinstance(filters, Mapping)
                and str(filters.get("deviceId")) == device_id
                and filters.get("mode") == "configuration"
                and failed.get("code") in (
                    "mcp_tool_reported_error", "read_timeout",
                    "response_too_large", "repeated_target_read_error")):
            return {
                "status": "driver_configuration_read_failed",
                "failed_operation": "hub_get_device",
                "failed_device_id": device_id,
                "failure_code": failed["code"],
                "limits": (
                    "A verified-device configuration read was attempted "
                    "but did not return usable configuration. The driver "
                    "ID/source are unverified; do not claim they were "
                    "inspected or repeat the same failed scope."),
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
