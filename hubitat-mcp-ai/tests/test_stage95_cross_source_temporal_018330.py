"""Stage 9.5 source-linked, read-only cross-episode correlations."""
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from causal_temporal_correlations import (
    correlate_input_to_off_commands,
    reconcile_temporal_publication,
    render_temporal_evidence_for_synthesis,
)


PAIRS = [
    ("2026-11-01T15:43:46.781+0000", "2026-11-01T15:44:01.848+0000"),
    ("2026-11-01T15:47:43.288+0000", "2026-11-01T15:47:58.388+0000"),
    ("2026-11-01T15:51:27.183+0000", "2026-11-01T15:51:42.278+0000"),
    ("2026-11-01T15:58:01.507+0000", "2026-11-01T15:58:16.619+0000"),
]


def receipts():
    motion = [
        {"name": "motion", "value": "inactive", "date": before,
         "triggered": [{"appId": 4012, "handler": "motionHandler"}],
         "producedBy": {"type": "device", "id": "7718"}}
        for before, _ in PAIRS
    ]
    commands = [
        {"name": "command-off", "date": after,
         "producedBy": {"type": "app", "id": "4012"}}
        for _, after in PAIRS
    ]
    # Original historic command has no source-linked input in this bounded
    # page; later observed episodes are not proof of its upstream initiator.
    commands.append({
        "name": "command-off",
        "date": "2026-11-01T15:29:23.157+0000",
        "producedBy": {"type": "app", "id": "4012"},
    })
    return [
        {"tool": "homebrain_device_history", "success": True,
         "effect": "read", "arguments": {"name": "Synthetic Occupancy"},
         "details": {
             "label": "Synthetic Occupancy", "attribute": "motion",
             "boundaryEvents": motion,
             "observedEvents": list(reversed(motion)),
             "historySourceIntegrityVerified": False,
             "observedEventsTruncated": True,
         }},
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "effect": "read",
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "7829", "attribute": "command-off"}},
         "details": {"events": commands + commands}},
    ]


def test_stage95_four_episodes_yield_one_deduped_typed_pattern():
    report = correlate_input_to_off_commands(receipts())
    assert report["status"] == "repeated_source_linked_pattern"
    assert not report["causalDecisionVerified"]
    assert not report["historicalCoverageComplete"]
    assert not report["physicalExecutionVerified"]
    assert len(report["patterns"]) == 1
    pattern = report["patterns"][0]
    assert pattern["deviceId"] == "7829"
    assert pattern["appId"] == "4012"
    assert pattern["sensorLabel"] == "Synthetic Occupancy"
    assert pattern["inputAttribute"] == "motion"
    assert pattern["inputState"] == "inactive"
    assert pattern["repeatCount"] == 4
    assert 15.0 <= pattern["medianDelaySeconds"] <= 15.2
    assert len(pattern["pairs"]) == 4
    assert not any(
        pair["commandTimeUtc"].startswith("2026-11-01T15:29")
        for pair in pattern["pairs"]
    )


def test_stage95_synthesis_receives_directional_evidence_without_root_cause_claim():
    report = correlate_input_to_off_commands(receipts())
    brief = render_temporal_evidence_for_synthesis(report)
    assert "HOST CROSS-SOURCE TEMPORAL EVIDENCE" in brief
    assert "15.094" in brief or "15.095" in brief
    assert "NOT a root-cause verdict" in brief
    assert "different bounded history window" in brief
    assert "2026-11-01T15:43:46.781000+00:00" in brief
    assert "2026-11-01T15:44:01.848000+00:00" in brief
    assert "periodic heartbeat" in brief


def test_stage95_publication_reconciles_unsupported_keep_off_verdict():
    report = correlate_input_to_off_commands(receipts())
    draft = (
        "No motion events were found between 15:20 and 15:35. "
        "It was probably a periodic keep-off heartbeat."
    )
    final, modified = reconcile_temporal_publication(draft, report)
    assert modified
    assert "Additional cross-source evidence" in final
    assert "4 bounded reports" in final
    assert "15.095s median" in final
    assert "does not prove the timer branch" in final
    assert "periodic keep-off mechanism is not established" in final
    # No additional model or remote tool calls are necessary for this check.
    again, changed = reconcile_temporal_publication(final, report)
    assert not changed
    assert again == final


def test_stage95_original_focal_cause_not_verified_from_later_examples():
    report = correlate_input_to_off_commands(receipts())
    assert report["status"] == "repeated_source_linked_pattern"
    assert report["causalDecisionVerified"] is False
    assert all("15:29:23" not in p["commandTimeUtc"]
               for item in report["patterns"] for p in item["pairs"])


def test_stage95_missing_listener_connection_is_not_a_source_linked_pattern():
    sample = receipts()
    for event in sample[0]["details"]["observedEvents"]:
        event["triggered"] = []
    assert correlate_input_to_off_commands(sample)["patterns"] == []


def test_stage95_wrong_producer_is_not_a_command():
    sample = receipts()
    for row in sample[1]["details"]["events"]:
        row["producedBy"] = {"type": "device", "id": "4012"}
    assert correlate_input_to_off_commands(sample)["patterns"] == []


def test_stage95_rejects_command_earlier_than_sensor_and_naive_timestamps():
    sample = receipts()
    for event in sample[0]["details"]["observedEvents"]:
        event["date"] = "2026-11-01T15:59:01.507+0000"
    assert correlate_input_to_off_commands(sample)["patterns"] == []
    sample = receipts()
    for event in sample[0]["details"]["observedEvents"]:
        event["date"] = "2026-11-01T15:43:46.781"
    assert correlate_input_to_off_commands(sample)["patterns"] == []


def test_stage95_no_unrelated_sensor_or_periodicity_inferred():
    sample = receipts()
    sample[0]["details"]["attribute"] = "temperature"
    assert correlate_input_to_off_commands(sample)["patterns"] == []
    sample = receipts()
    sample[1]["arguments"]["args"]["deviceId"] = ""
    assert correlate_input_to_off_commands(sample)["patterns"] == []
    assert reconcile_temporal_publication(
        "Periodic automation is responsible.", {"patterns": []}
    ) == ("Periodic automation is responsible.", False)


def test_stage95_pre_synthesis_and_final_publication_both_use_same_projection():
    orchestrator = (APP / "mcp_agent_orchestrator.py").read_text()
    assert "render_temporal_evidence_for_synthesis(" in orchestrator
    assert "reconcile_temporal_publication(" in orchestrator
    assert '"crossSourceTemporalEvidence": correlations' in orchestrator
    assert "correlate_input_to_off_commands(self.evidence.receipts())" not in (
        ""  # deliberate; separate final and boundary scopes
    )
