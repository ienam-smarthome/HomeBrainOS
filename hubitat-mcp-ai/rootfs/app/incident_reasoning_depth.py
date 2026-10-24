"""Evidence-depth accounting for focused device fault investigations.

Source reads, interpreted method behaviour, identified controlling apps and
independent broker/physical observations are separate proof dimensions.
Nothing here routes by keywords, selects tools, or authorises a write.
"""
from __future__ import annotations

from typing import Any


def _args(receipt: dict[str, Any]) -> dict[str, Any]:
    args = receipt.get("arguments") or {}
    for _ in range(3):
        if not isinstance(args, dict):
            return {}
        inner = args.get("args")
        if not isinstance(inner, dict):
            return args
        args = inner
    return args if isinstance(args, dict) else {}


def assess_incident_reasoning_depth(
    evidence: list[dict[str, Any]], target_device_id: str,
) -> dict[str, Any]:
    ident = str(target_device_id or "")
    source = False
    source_attempted = False
    source_ids: set[str] = set()
    verified_target_driver_ids: set[str] = set()
    method_verified = False
    dependents_checked = False
    app_config_read = False
    controlling_app_link_verified = False
    upstream_observed = False
    upstream_probe_attempted = False
    scoped_app_logs_checked: set[str] = set()
    scoped_app_logs_empty: set[str] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("mutates") is True or receipt.get("effect") == "write":
            continue
        op = str(receipt.get("sub_tool") or "")
        args = _args(receipt)
        detail = receipt.get("details") or {}
        detail = detail if isinstance(detail, dict) else {}
        succeeded = receipt.get("success") is True
        if op == "hub_get_device" and succeeded and str(args.get("deviceId") or "") == ident:
            # Only a typed mapping from a target-scoped device record can
            # establish that a separately retrieved source is installed here.
            mapped = detail.get("verifiedInstalledDriverCodeId")
            if str(mapped or "").isdigit():
                verified_target_driver_ids.add(str(mapped))
        if op == "hub_get_source" and str(args.get("type") or "").lower() == "driver":
            source_attempted = True
            if succeeded and detail.get("sourceRetrieved") is True:
                source = True
                code_id = str(detail.get("sourceCodeId") or args.get("id") or "")
                if code_id.isdigit():
                    source_ids.add(code_id)
                method_verified = (method_verified or
                    detail.get("methodBehaviourVerified") is True)
        if op == "hub_list_device_dependents" and succeeded and str(args.get("deviceId") or "") == ident:
            dependents_checked = True
            if detail.get("verifiedDeviceTargetLinks") is True:
                controlling_app_link_verified = True
        if op == "hub_get_app_config" and succeeded and args.get("appId") not in (None, ""):
            app_config_read = True
            if detail.get("verifiedControlsDeviceId") is not None and (
                str(detail.get("verifiedControlsDeviceId")) == ident
            ):
                controlling_app_link_verified = True
        if op == "hub_get_logs" and succeeded:
            # A bounded zero-row app log is evidence that a query returned no
            # rows; it is NOT evidence that this app controls the device, nor
            # that the app did not execute outside this log window.
            app_id = str(args.get("appId") or args.get("app_id") or "")
            if app_id.isdigit():
                scoped_app_logs_checked.add(app_id)
                if detail.get("logCount") == 0 and detail.get("logs") == []:
                    scoped_app_logs_empty.add(app_id)
        if op == "hub_get_device_health":
            upstream_probe_attempted = True
            # A successful generic diagnostics call without its actual ping
            # observations does not prove reachability of this device.
            if (succeeded and isinstance(detail.get("pingResults"), list)
                    and detail.get("pingResults")
                    and str(detail.get("verifiedForDeviceId") or "") == ident):
                upstream_observed = True
        if (succeeded and receipt.get("supports_live_claim") is True and
                receipt.get("evidence_kind") in (
                    "physical_network_reachability", "mqtt_broker_packet_evidence",
                    "upstream_telemetry_confirmation",
                ) and detail.get("independentObservationVerified") is True):
            upstream_observed = True
    driver_link_verified = bool(source_ids & verified_target_driver_ids)
    gaps = []
    if not source:
        gaps.append("driver implementation source not retrieved")
    if source and not driver_link_verified:
        gaps.append("retrieved driver code ID not independently mapped to this device")
    if not method_verified:
        gaps.append("watchdog timer and last-data update paths not source-traced")
    if not (controlling_app_link_verified and app_config_read):
        gaps.append("controlling automation link, stored settings and execution not corroborated")
    if not upstream_observed:
        gaps.append("independent device/network/broker observation not retained")
    return {
        "targetDeviceId": ident,
        "driverSourceAttempted": source_attempted,
        "driverSourceRetrieved": source,
        "driverSourceLinkedToTarget": driver_link_verified,
        "driverMethodBehaviourVerified": method_verified,
        "deviceDependentAppsChecked": dependents_checked,
        "scopedAppConfigRead": app_config_read,
        "controllingAppLinkVerified": controlling_app_link_verified,
        "scopedAppLogIdsChecked": sorted(scoped_app_logs_checked),
        "scopedAppLogIdsEmpty": sorted(scoped_app_logs_empty),
        "appLogAbsenceProvesNoExecution": False,
        "upstreamProbeAttempted": upstream_probe_attempted,
        "independentUpstreamObservationRetained": upstream_observed,
        "keyDiscriminatorsCovered": not gaps,
        "rootCauseEstablishedByThisAssessment": False,
        "missingDiscriminators": gaps,
        "onlyReadReceiptsConsidered": True,
    }


__all__ = ["assess_incident_reasoning_depth"]
