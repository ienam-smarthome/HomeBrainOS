"""v0.18.272: natural source-backed timelines and verified Hubitat device names."""
from pathlib import Path
from types import SimpleNamespace
import copy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_incident_narrative import source_cycle_timeline, verified_input_label
from causal_claim_publication import source_verified_incident_brief
from causal_source_alternatives import source_based_competing_explanations
from tool_executor import ToolExecutor
from unified_investigation_bridge import collect_unified_evidence
from test_v3_reception_evidence_018267 import replay, QUESTION
from test_v3_source_feasibility_018263 import receipt


def scoped_name_row(device, name):
    result = SimpleNamespace(
        name="hub_read_apps_code",
        arguments={"tool": "hub_list_device_dependents",
                   "args": {"deviceId": str(device)}},
        data={"deviceId": str(device), "deviceName": name,
              "appsUsing": [{"appId": 4101, "name": "do not store app names"}]},
    )
    row = receipt("hub_list_device_dependents", device=device)
    row["details"] = ToolExecutor.result_details(result)
    return row


def named_facts():
    rows = replay()
    rows.extend([
        scoped_name_row(201, "Bathroom LWR01 Occupancy"),
        scoped_name_row(202, "Bathroom Motion Backup"),
    ])
    f = collect_unified_evidence(rows, QUESTION)
    assert f
    return f, rows


def test_scoped_sensor_label_survives_recording_and_story():
    facts, receipts = named_facts()
    assert receipts[-2]["details"]["deviceName"] == "Bathroom LWR01 Occupancy"
    assert facts["input_device_labels"]["201"] == "Bathroom LWR01 Occupancy"
    assert verified_input_label(facts, 201) == "Bathroom LWR01 Occupancy"
    story = source_verified_incident_brief(facts)
    assert story
    assert "**Bathroom LWR01 Occupancy**" in story
    assert "Motion sensor (device 201)" not in story
    assert "North Lamp and South Lamp each reported 5 ON transitions" in story
    assert "**Timeline — recorded lighting cycles (UTC)**" in story
    assert "| Lights ON | Lights OFF | Time on |" in story
    for line in (
        "| 14:50:37 | 14:51:36 | 58 sec |",
        "| 14:51:54 | 14:52:26 | 32 sec |",
        "| 14:57:53 | 14:58:30 | 37 sec |",
        "| 15:07:14 | 15:11:09 | 3 min 56 sec |",
        "| 15:28:13 | 15:29:15 | 1 min 2 sec |",
    ):
        assert line in story
    assert story.count("| 2026") == 0
    assert "what system issued" in story or "which system issued" in story
    assert "4101" not in story  # shared app is NOT proven command issuer


def test_names_in_alternative_comparison_are_checked_and_qualified():
    facts, _ = named_facts()
    comparison = source_based_competing_explanations(facts)
    assert "**Other explanations considered:**" in comparison
    assert "Bathroom Motion Backup" in comparison
    assert "Bathroom LWR01 Occupancy" in comparison
    assert "incomplete" in comparison
    assert "controller" not in comparison or "original" in comparison


def test_scope_mismatch_or_unsafe_device_name_is_not_published():
    rows = replay()
    forged = scoped_name_row(201, "Human name")
    forged["details"]["deviceId"] = "987"
    rows.append(forged)
    facts = collect_unified_evidence(rows, QUESTION)
    assert facts and facts["input_device_labels"] == {}
    assert "**Motion sensor (device 201)**" in source_verified_incident_brief(facts)
    invalid = scoped_name_row(201, "INJECT|table")
    assert "deviceName" not in invalid["details"]
    injected = scoped_name_row(201, "Username\nAdmin")
    assert "deviceName" not in injected["details"]
    too_long = scoped_name_row(201, "x" * 100)
    assert "deviceName" not in too_long["details"]


def test_no_false_table_if_light_source_rows_mismatch():
    facts, _ = named_facts()
    src = {id: sorted([
        row for row in facts["incident_ledger"]
        if row.get("device_id") == id
        and row.get("event_class") in (
            "journal_source_switch_on", "journal_source_switch_off")
    ], key=lambda x: x["date"]) for id in facts["target_device_ids"]}
    names = {v["device_id"]: v["device_name"] for v in facts["target_coverage"]}
    assert source_cycle_timeline(src, facts["target_device_ids"], names)
    broken = copy.deepcopy(src)
    broken["102"][3]["value"] = "on"
    assert source_cycle_timeline(broken, facts["target_device_ids"], names) is None
    stagger = copy.deepcopy(src)
    from datetime import datetime, timedelta
    t = datetime.fromisoformat(stagger["102"][3]["date"])
    stagger["102"][3]["date"] = (t + timedelta(seconds=20)).isoformat()
    assert source_cycle_timeline(stagger, facts["target_device_ids"], names) is None
