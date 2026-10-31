"""Stage 3 evidence frontier: offline regression and authorization boundaries."""
from copy import deepcopy
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from stage3_evidence_frontier import build_stage3_read_frontier
from test_canonical_investigation_foundation import named_lookup, native_command
from test_v3_reception_evidence_018267 import replay, QUESTION
from unified_investigation_bridge import collect_unified_evidence


CATALOG = ("hub_list_device_events", "hub_list_device_dependents",
           "hub_get_app_config")


def propose(leaf, **args):
    return {"leaf": leaf, "args": args, "priority": "model-high"}


def test_source_attested_model_proposal_and_exact_history_repeat():
    receipts = [named_lookup(), native_command()]
    candidate = propose("hub_list_device_events", deviceId="101")
    narrowed = propose("hub_list_device_events", deviceId="101",
                       since="2026-10-30T14:00:00+00:00",
                       until="2026-10-30T15:00:00Z", attribute="switch")
    packet = build_stage3_read_frontier(
        receipts, model_proposals=[candidate, narrowed],
        available_read_tools=CATALOG)
    assert packet["shadow_only"] is True
    assert packet["executes_tools"] is False
    assert packet["candidate_count"] == 1
    assert packet["candidate_reads"][0]["leaf"] == "hub_list_device_events"
    assert packet["candidate_reads"][0]["args"]["since"].startswith("2026-10-30T14:00")
    assert packet["rejected_candidate_counts"]["exact-read-already-attempted"] == 1


def test_verified_app_issuer_never_mistaken_for_notified_listener():
    receipts = [named_lookup(), native_command()]
    packet = build_stage3_read_frontier(
        receipts, available_read_tools=CATALOG,
        model_proposals=[propose("hub_get_app_config", appId="3001"),
                         propose("hub_get_app_config", appId="3999"),
                         propose("hub_get_app_config", appId="9090")])
    assert [x["args"]["appId"] for x in packet["candidate_reads"]] == ["3001"]
    assert packet["candidate_reads"][0]["score"] == 60
    assert packet["rejected_candidate_counts"]["identifier-not-source-attested"] == 2
    assert packet["source_order_or_root_cause_proven"] is False


def test_failed_attempt_is_not_automatically_reissued():
    receipts = [named_lookup(), {
        "tool": "hub_read_apps_code", "sub_tool": "hub_list_device_dependents",
        "effect": "read", "success": False,
        "arguments": {"args": {"deviceId": "101"}},
    }]
    packet = build_stage3_read_frontier(
        receipts, available_read_tools=CATALOG,
        model_proposals=[propose("hub_list_device_dependents", deviceId="101")])
    assert not packet["candidate_reads"]
    assert packet["rejected_candidate_counts"]["exact-read-already-attempted"] == 1
    assert packet["next_action"] == "model-discover-new-read-or-report-limits"
    assert packet["no_verified_new_candidate_is_not_source_absence"] is True


def test_missing_authorized_catalog_blocks_all_candidates():
    packet = build_stage3_read_frontier(
        [named_lookup()], model_proposals=[
            propose("hub_list_device_dependents", deviceId="101")])
    assert packet["current_catalog_validated"] is False
    assert packet["candidate_reads"] == []
    assert packet["rejected_candidate_counts"]["not-in-current-validated-read-catalog"] == 1


def test_rejects_unverified_ids_broad_scopes_and_mutating_leaves():
    proposals = [
        propose("hub_list_device_events", deviceId="999"),
        propose("hub_list_device_events", deviceId="101", until="2026-10-31T00:00:00Z"),
        propose("hub_list_device_events", deviceId="101", length=100000),
        propose("hub_list_device_events", deviceId="101", api_key="SHOULD_NOT_SURVIVE"),
        propose("hub_get_app_config", appId="999"),
        propose("hub_delete_device", deviceId="101"),
        propose("hub_list_device_events", deviceId="101",
                since="2026-01-01T00:00:00Z", until="2026-10-31T00:00:00Z"),
        propose("hub_list_device_dependents", deviceId="101"),
    ]
    report = build_stage3_read_frontier(
        [named_lookup()], model_proposals=proposals,
        available_read_tools=(*CATALOG, "hub_delete_device"))
    assert len(report["candidate_reads"]) == 1
    assert report["candidate_reads"][0]["leaf"] == "hub_list_device_dependents"
    assert "SHOULD_NOT_SURVIVE" not in json.dumps(report)
    assert report["rejected_candidate_counts"]["identifier-not-source-attested"] == 2
    assert report["rejected_candidate_counts"]["invalid-or-unbounded-scope"] == 4


def test_legacy_evidence_ranked_lead_is_reused_not_rebuilt():
    rows = replay()
    facts = collect_unified_evidence(rows, QUESTION)
    assert facts is not None
    # The existing feasibility module will expose only currently possible
    # reads. Stage 3 must not invent tools or IDs from the five-cycle story.
    report = build_stage3_read_frontier(
        rows, facts=facts,
        available_read_tools=CATALOG)
    assert report["existing_feasibility_available"] is True
    assert report["source_order_or_root_cause_proven"] is False
    assert report["candidate_is_not_new_permission"] is True
    assert report["no_arbitrary_five_call_limit"] is True


def test_not_five_calls_and_stable_ranking_and_bounded_output():
    receipts = [named_lookup()]
    proposals = []
    for n in range(22):
        proposals.append(propose("hub_list_device_events", deviceId="101",
                                 since=f"2026-10-30T{n:02d}:00:00Z",
                                 until=f"2026-10-30T{n+1:02d}:00:00Z"))
    report = build_stage3_read_frontier(
        receipts, model_proposals=proposals,
        available_read_tools=CATALOG, max_choices=10)
    assert report["candidate_count"] == 22
    assert len(report["candidate_reads"]) == 10
    assert report["candidate_count_omitted"] == 12
    assert report["no_arbitrary_five_call_limit"] is True
    again = build_stage3_read_frontier(
        receipts, model_proposals=proposals,
        available_read_tools=CATALOG, max_choices=10)
    assert report == again


def test_heating_source_command_can_nominate_app_configuration():
    receipts = [native_command("701", issuer="501", label="Heating Coordinator",
                               attribute="command-setHeatingSetpoint")]
    report = build_stage3_read_frontier(
        receipts, available_read_tools=CATALOG,
        model_proposals=[propose("hub_get_app_config", appId="501")])
    assert report["candidate_reads"][0]["args"] == {"appId": "501"}
    assert report["candidate_reads"][0]["score"] == 60
    assert report["source_order_or_root_cause_proven"] is False


def test_no_receipt_mutation_even_with_duplicates():
    rows = [named_lookup(), native_command()]
    before = deepcopy(rows)
    result = build_stage3_read_frontier(
        rows, model_proposals=[propose("hub_list_device_events", deviceId="101"),
                               propose("hub_list_device_dependents", deviceId="101")],
        available_read_tools=CATALOG)
    assert rows == before
    assert result["next_action"] == "model-select-validated-read"
    assert result["candidate_is_not_new_permission"] is True
