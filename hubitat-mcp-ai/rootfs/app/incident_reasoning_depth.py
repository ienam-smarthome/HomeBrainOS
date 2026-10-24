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
    method_verified = False
    dependents_checked = False
    app_config_read = False
    controlling_app_link_verified = False
    upstream_observed = False
    upstream_probe_attempted = False
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
        if op == "hub_get_source" and str(args.get("type") or "").lower() == "driver":
            source_attempted = True
            if succeeded and detail.get("sourceRetrieved") is True:
                source = True
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
        if op == "hub_get_device_health":
            upstream_probe_attempted = True
            # A successful generic diagnostics call without its actual ping
            # observations does not prove reachability of this device.
            if succeeded and isinstance(detail.get("pingResults"), list) and detail.get("pingResults"):
                upstream_observed = True
        if (succeeded and receipt.get("supports_live_claim") is True and
                receipt.get("evidence_kind") in (
                    "physical_network_reachability", "mqtt_broker_packet_evidence",
                    "upstream_telemetry_confirmation",
                ) and detail.get("independentObservationVerified") is True):
            upstream_observed = True
    gaps = []
    if not source:
        gaps.append("installed driver implementation not retrieved")
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
        "driverMethodBehaviourVerified": method_verified,
        "deviceDependentAppsChecked": dependents_checked,
        "scopedAppConfigRead": app_config_read,
        "controllingAppLinkVerified": controlling_app_link_verified,
        "upstreamProbeAttempted": upstream_probe_attempted,
        "independentUpstreamObservationRetained": upstream_observed,
        "rootCauseEvidenceComplete": not gaps,
        "missingDiscriminators": gaps,
        "onlyReadReceiptsConsidered": True,
    }


__all__ = ["assess_incident_reasoning_depth"]
