"""Provenance-specific regression contracts from v0.17.58 live answers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from causal_initiator_provenance_guard import (
    guard_unverified_initiator_claims,
)
from recorded_telemetry_freshness import reconcile_telemetry_answer


def _graph(*, scope="single-observed-event", command=None, external=False):
    return {
        "scope": scope,
        "focus": {"subject": "Livingroom Light 1",
                  "on": "2026-10-14T19:55:00.049+01:00"},
        "physicalStateBoundary": {
            "reporter": {"id": "7790", "type": "device",
                         "label": "Matter Hue Bridge Pro"},
        },
        "directCommand": command,
        "externalInitiatorVerified": external,
    }


def test_repaired_answer_cannot_promote_missing_command_into_external_cause():
    draft = (
        "The exact initiator remains unresolved.\n\n"
        "### Causal Analysis\n"
        "* **Command Provenance:** There is no record of a "
        "Hubitat-issued command to turn the light on.\n"
        "* **Downstream Effects:** The apps were notified of the state change "
        "as listeners, but they did not initiate the command.\n\n"
        "### Conclusion\n"
        "The timing correlates the FP400 event with the transition. However, "
        "because Hubitat did not issue the command and the reporting bridge "
        "is a Matter-integrated Hue bridge, the initiating logic likely "
        "resides in an external automation such as Hue-native motion."
    )
    focal_evidence = [{
        "tool": "homebrain_causal_secondary_correlation",
        "success": True,
        "details": {
            "subject": "Livingroom Light 1",
            "sensors": [{
                "label": "FP400 motion sensor",
                "relevantCorrelations": [{
                    "boundaryRole": "start",
                    "subjectTransition": "2026-10-14T19:55:00.049+01:00",
                    "sensorEvent": "2026-10-14T19:54:59.961+01:00",
                    "eventValue": "active",
                }],
            }],
        },
    }]
    revised, changed = guard_unverified_initiator_claims(
        draft, focal_evidence, "Why did the light turn on?", graph=_graph(),
    )
    assert changed
    assert "initiating logic likely" not in revised
    assert "because Hubitat did not issue" not in revised
    assert "they did not initiate the command" not in revised
    assert "No matching direct Hubitat command producer" in revised
    assert "An external automation or manual action remains possible" in revised
    assert "not identify them as initiators" in revised
    assert "FP400 motion sensor reported active" in revised
    assert "0.088 seconds before" in revised
    assert "not a confirmed command" in revised


def test_possibility_language_and_genuine_direct_commands_survive():
    benign = (
        "An external automation is possible, but the initiator is unverified.\n"
        "Matter Hue Bridge Pro reported the state event.\n"
    )
    assert guard_unverified_initiator_claims(
        benign, [], "Why?", graph=_graph(),
    ) == (benign, False)
    verified = (
        "The automation called on() at the observed transition; upstream "
        "logic remains unknown."
    )
    assert guard_unverified_initiator_claims(
        verified, [], "Why?", graph=_graph(command={
            "producer": {"id": "1251", "type": "app"}, "action": "on",
        }),
    ) == (verified, False)
    assert guard_unverified_initiator_claims(
        "An external automation is likely responsible.",
        [], "Why?", graph=_graph(external=True),
    )[1] is False


def test_unfocused_causal_question_is_never_rewritten_by_guard():
    original = "I suspect the external controller is most likely responsible."
    assert guard_unverified_initiator_claims(
        original, [], "Why were my lights flickering?",
        graph=_graph(scope="multiple-observed-events"),
    ) == (original, False)


def test_live_bedroom_mesh_summary_does_not_promote_bounded_events_to_packets():
    summary = {
        "storedDataAgeSeconds": {
            "value": "162325", "recordedAt": "2026-10-13T22:35:27+01:00",
        },
        "latestReturnedDeviceAttributedEventAt":
            "2026-10-13T22:35:38.773+01:00",
        "latestReturnedEventAttribute": "mqttStatus",
        "eventWithinPast24hOfRead": True,
        "fullHistoryVerified": False,
        "physicalTelemetryVerified": False,
    }
    source = (
        "### Investigation Summary: Bedroom 3 Mesh\n"
        "* **Health Status:** Offline.\n"
        "* **Last Device-Originated Event:** The last telemetry received "
        "from the device was on October 13 at 22:35:38.\n"
        "* **Freshness:** Stored dataAgeSeconds=162325 was recorded at "
        "2026-10-13T22:35:27+01:00; this is a historical driver value.\n"
        "* **Recent Hub Activity:** The hub sent several commands. "
        "However, no state-change events followed these commands, "
        "suggesting they may not have been received or executed.\n"
        "\n| Status | Conclusion | Evidence |\n"
        "| --- | --- | --- |\n"
        "| **Established** | **Telemetry is stale** | "
        "No device-originated events since Oct 13, 22:35. |\n"
        "| **Established** | **Commands are not triggering updates** | "
        "Multiple on() and refresh() commands sent today resulted "
        "in zero state changes. |\n"
        "| **Unverified** | **Command Reachability** | Not established. |\n"
    )
    reconciled, changed = reconcile_telemetry_answer(source, summary)
    assert changed
    assert "last telemetry received from the device" not in reconciled
    assert "no state-change events followed these commands" not in reconciled
    assert "No device-originated events since" not in reconciled
    assert "zero state changes" not in reconciled
    assert "Evidence-limited" in reconciled
    assert "physical telemetry" in reconciled
    assert "* **Health Status:** Offline." in reconciled
    assert "**Command Reachability**" in reconciled


def test_histories_unrelated_to_telemetry_are_preserved():
    msg = "* **Device Logs:** No log entries for this device in the last 30 minutes."
    snapshot = {
        "storedDataAgeSeconds": {"value": "162325",
                                 "recordedAt": "2026-10-13T22:35:27+01:00"},
        "latestReturnedDeviceAttributedEventAt":
            "2026-10-13T22:35:38+01:00",
        "latestReturnedEventAttribute": "mqttStatus",
    }
    assert reconcile_telemetry_answer(msg, snapshot) == (msg, False)
