"""V3: model-guided upstream dependency selection follows typed evidence, not names."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from test_v3_reception_evidence_018267 import replay, QUESTION
from test_v3_source_feasibility_018263 import receipt
from causal_upstream_read_frontier import rank_upstream_read_frontier
from causal_source_feasibility import build_source_feasibility_choices
from investigation_evidence_cycle import cross_source_discovery_checkpoint
from unified_investigation_bridge import collect_unified_evidence


def feed(ids=(101, 102, 201, 202, 203)):
    reads = replay(ids)
    # Only observed successful READ leaf operations may be suggested.
    reads.append(receipt("hub_list_device_dependents", device=ids[0]))
    reads.append(receipt("hub_get_app_config", app=9001))
    return reads


def facts(rows):
    f = collect_unified_evidence(rows, QUESTION)
    assert f is not None
    return f


def test_full_reception_pairing_proposes_sensor_dependents_before_target_config():
    rows = feed()
    f = facts(rows)
    plan = build_source_feasibility_choices(f, rows)
    top = plan["candidate_reads"][0]
    assert top["source_category"] == "strongest-receiver-input-current-dependencies"
    assert top["priority"] == "evidence-ranked"
    assert top["leaf"] == "hub_list_device_dependents"
    assert top["args"] == {"deviceId": "201"}
    assert top["cannot_prove"].startswith("historical")
    upstream = plan["evidence_ranked_upstream_lead"]
    assert upstream["lead"]["input_id"] == "201"
    assert upstream["lead"]["matched_active_to_on"] == 5
    assert upstream["lead"]["matched_inactive_to_off"] == 5
    assert upstream["lead"]["command_initiator_verified"] is False
    assert upstream["dependency_read_status"] == "not-attempted"
    prompt = cross_source_discovery_checkpoint(rows, QUESTION)
    assert prompt and '"highestPriorityUpstreamRead":{"source_category":"strongest-receiver' in prompt
    assert '"deviceId":"201"' in prompt
    assert "original input" not in json.dumps(upstream).lower() or "cannot_prove" in str(top)
    assert "Choose only available, authorized READ tools" in prompt


def test_after_sensor_dependency_read_shared_app_is_next_not_repeated_sensor():
    rows = feed()
    rows[-2]["details"] = {"appsUsing": [{"appId": 4321}, {"appId": 4330}]}
    rows.append(receipt("hub_list_device_dependents", device=201))
    rows[-1]["details"] = {"appsUsing": [{"id": 4321}, {"id": 5000}]}
    frontier = rank_upstream_read_frontier(facts(rows), rows)
    assert frontier["dependency_read_status"] == "source-observed"
    assert frontier["shared_current_app_ids"] == ["4321"]
    assert frontier["candidate_reads"][0]["leaf"] == "hub_get_app_config"
    assert frontier["candidate_reads"][0]["args"] == {"appId": "4321"}
    assert all(c["args"].get("deviceId") != "201" for c in frontier["candidate_reads"])
    # A checked current config cannot be suggested twice.
    rows.append(receipt("hub_get_app_config", app=4321))
    refreshed = rank_upstream_read_frontier(facts(rows), rows)
    assert refreshed["candidate_reads"] == []
    assert refreshed["checked_shared_app_configs"] == ["4321"]


def test_rejected_input_dependents_read_is_attempted_not_retried():
    rows = feed()
    rows.append(receipt("hub_list_device_dependents", device=201, success=False))
    lead = rank_upstream_read_frontier(facts(rows), rows)
    assert lead["dependency_read_status"] == "attempted-no-success"
    assert lead["candidate_reads"] == []


def test_no_phantom_leaf_no_guessed_sensors_or_apps():
    rows = replay()
    lead = rank_upstream_read_frontier(facts(rows), rows)
    assert lead is not None and lead["candidate_reads"] == []
    assert lead["no_new_permissions_granted"] is True
    # Inventing a candidate ID into a projection does not authorize the read.
    f = facts(rows)
    f["same_receiver_evidence"]["candidates"][0]["input_id"] = "999999"
    assert rank_upstream_read_frontier(f, rows) is None
    # A dependent summary field is not the structured appsUsing list.
    rows = feed()
    rows.append(receipt("hub_list_device_dependents", device=201))
    rows[-1]["details"] = {"fields": ["appsUsing"], "count": 2}
    lead = rank_upstream_read_frontier(facts(rows), rows)
    assert lead["shared_current_app_ids"] == []
    assert lead["candidate_reads"] == []


def test_truncated_input_and_no_source_clock_pair_do_not_create_frontier():
    rows = feed()
    rows[9]["details"]["truncated"] = True  # noisy input is already incomplete
    assert rank_upstream_read_frontier(facts(rows), rows) is not None
    rows[10]["details"]["truncated"] = True  # complete input becomes incomplete
    f = facts(rows)
    assert rank_upstream_read_frontier(f, rows) is None
    rows = feed()
    for row in rows:
        if row.get("evidence_kind") == "group_archived_switch_history":
            row["details"]["observations"] = [
                x for x in row["details"]["observations"]
                if x.get("timestamp_basis") == "source"]
    assert rank_upstream_read_frontier(facts(rows), rows) is None


def test_renaming_numbers_does_not_change_choice_or_causal_certainty():
    ids = (701, 702, 803, 804, 805)
    rows = feed(ids)
    lead = rank_upstream_read_frontier(facts(rows), rows)
    assert lead and lead["candidate_reads"][0]["args"] == {"deviceId": "803"}
    assert lead["lead"]["command_initiator_verified"] is False
    assert "7895" not in json.dumps(lead)
