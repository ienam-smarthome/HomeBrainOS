"""Read-only source-ID and clock-conflict verification for vNext.

Synthetic fixtures only; no live device modifications or production accuracy
claims. Source code identity is not evidence of endpoint/broker operation.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from driver_source_identity_guard import (
    verified_driver_configuration_metadata, _linked_driver_source_ids,
)
from source_authority_packet import (
    pending_verified_driver_source_read, telemetry_source_authority,
)
from model_first_publication import admit_model_first_telemetry_answer
from model_first_draft_provenance import PrivateModelDraft
from test_vnext_source_authority import receipts, QUESTION


def with_config(device_id="9911", source_id="3686"):
    source = receipts()
    source.append({
        "tool": "hub_read_devices", "sub_tool": "hub_get_device",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_device",
                      "args": {"deviceId": device_id, "mode": "configuration"}},
        "details": {"deviceId": device_id,
                    "driverSource": {"sourceCodeId": source_id}},
    })
    return source


def test_read_only_driver_code_read_needs_unique_verified_target_linkage():
    src = with_config()
    assert pending_verified_driver_source_read(QUESTION, src) == {
        "type": "driver", "id": "3686", "offset": 0, "length": 8000,
    }
    src.append({
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_source",
        "success": False,
        "arguments": {"tool": "hub_get_source",
                      "args": {"type": "driver", "id": "3686"}},
    })
    assert pending_verified_driver_source_read(QUESTION, src) is None
    assert pending_verified_driver_source_read(
        "Compare Test Relay and all outlets", with_config(),
    ) is None


def test_identity_absent_wrong_device_ambiguous_or_non_driver_never_admitted():
    assert pending_verified_driver_source_read(QUESTION, receipts()) is None
    assert pending_verified_driver_source_read(
        QUESTION, with_config(device_id="7777"),
    ) is None
    src = with_config()
    src[-1]["details"]["driverSource"]["sourceCodeId"] = "9911"
    src[-1]["details"]["id"] = "7777"
    assert pending_verified_driver_source_read(QUESTION, src) is None
    src = with_config()
    src[-1]["details"]["driverSource"] = {"sourceCodeId": "3686",
                                            "driverCodeId": "9999"}
    assert _linked_driver_source_ids(src, "9911") == {"3686", "9999"}
    assert pending_verified_driver_source_read(QUESTION, src) is None
    src = with_config()
    src[-1]["success"] = False
    assert pending_verified_driver_source_read(QUESTION, src) is None


def test_config_metadata_extractor_never_admits_unlinked_or_generic_code_id():
    data = {
        "id": "9911", "driverSource": {"sourceCodeId": "3686"},
        "app": {"sourceCodeId": "9999"}, "deviceTypeId": "1111",
    }
    expected = {"deviceId": "9911", "driverSource": {"sourceCodeId": "3686"}}
    assert verified_driver_configuration_metadata(data, "9911") == expected
    assert verified_driver_configuration_metadata(data, "9999") is None
    assert verified_driver_configuration_metadata(
        {"id": "9911", "driverCodeId": "3686"}, "9911",
    ) == {"deviceId": "9911", "driverSourceCodeIdentity": "unverified"}
    assert verified_driver_configuration_metadata(
        {"id": "9911", "driverSource": {"sourceCodeId": "3686",
                                      "driverCodeId": "9999"}}, "9911",
    ) == {"deviceId": "9911", "driverSourceCodeIdentity": "unverified"}


def test_only_source_chunk_linked_to_target_counts_not_method_causation():
    src = with_config()
    src.append({
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_source",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_source",
                      "args": {"type": "driver", "id": "3686"}},
        "details": {"sourceRetrieved": True, "sourceCodeId": "3686",
                    "chunkLength": 8000, "totalLength": 30000},
    })
    packet = telemetry_source_authority(QUESTION, src, clock=None)
    assert packet["linkedDriverSourceChunkRetrieved"] is True
    assert packet["verifiedInstalledDriverBehaviour"] is False
    src[-1]["arguments"]["args"]["id"] = "7777"
    assert telemetry_source_authority(
        QUESTION, src, clock=None,
    )["linkedDriverSourceChunkRetrieved"] is False


def test_conflicting_unresolved_source_clocks_use_bounded_fallback_not_prose():
    text = (
        "Hubitat reports the device offline. Its MQTT status is connected, "
        "although that does not verify live messages. The current driver "
        "timestamps disagree, and the physical cause is unknown. Next read "
        "only the verified source, then compare actual broker packets."
    )
    trace = PrivateModelDraft(
        raw_first=text, coordinator_result=text,
        final_answer=text, no_tools_final_stage=True,
    )
    state = {"deviceId": "9911", "commandCount": 0, "truncated": False,
             "reportedDeviceState": {
                 "deviceId": "9911", "source": "targeted-hubitat-device-state",
                 "isPhysicalConnectivityProof": False,
                 "reportedAttributes": {
                     "healthStatus": "offline", "mqttStatus": "connected",
                 },
             }}
    coverage = {
        "rootCauseVerified": False,
        "sourceAuthority": {"temporalClocks": {"sourcesAgree": False},
                            "independentBrokerPacketsVerified": False,
                            "verifiedInstalledDriverBehaviour": False},
    }
    result, reason = admit_model_first_telemetry_answer(
        text, trace, state, coverage,
    )
    assert result is None and reason == "unresolved-source-clock-conflict"
    coverage["sourceAuthority"]["temporalClocks"]["sourcesAgree"] = True
    result, reason = admit_model_first_telemetry_answer(
        text, trace, state, coverage,
    )
    assert result == text and reason == "model-authored-bounded-telemetry"
