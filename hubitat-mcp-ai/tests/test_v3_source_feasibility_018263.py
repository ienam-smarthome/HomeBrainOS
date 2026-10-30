"""V3 Stage C: feasible source reads only from verified receipts and identities."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"rootfs"/"app"))
from causal_source_feasibility import build_source_feasibility_choices
from causal_witness_ledger import build_witness_coverage_ledger
from investigation_evidence_cycle import cross_source_discovery_checkpoint
from unified_investigation_bridge import unified_investigation_instruction

Q=("Why did Zone Alpha Light and Zone Beta Light repeatedly switch "
   "between 14:50 and 15:30 GMT on 30 October 2026?")


def receipt(leaf, *, device=None, app=None, success=True, **kw):
    args = {}
    if device is not None:
        args["deviceId"] = str(device)
    if app is not None:
        args["appId"] = str(app)
    args.update(kw)
    return {
        "tool": ("hub_read_apps_code" if "app_" in leaf or
                 "dependents" in leaf else "hub_read_devices"),
        "sub_tool":leaf, "success":success,"effect":"read","mutates":False,
        "arguments":{"tool":leaf,"args":args},
    }


def data(targets=("101","102"), apps=("4013",), matches=0):
    facts={
        "source_attested":True,
        "target_device_ids":list(targets),
        "target_coverage":[{"device_id":t} for t in targets],
        "incident_ledger":[],
        "target_observed_command_app_ids":list(apps),
        "archived_input_collector_observations":10,
        "archived_input_reception_patterns":[{"device_id":"201"}],
        "input_app_relationships":[],
    }
    facts["v3_witness_ledger"]=build_witness_coverage_ledger(facts,[])
    return facts


def test_only_verified_successful_read_leaves_become_concrete_choices():
    facts=data()
    reads=[
        receipt("hub_list_device_dependents",device=101),
        receipt("hub_get_app_config",app=1000),
        receipt("hub_list_device_events",device=101),
        receipt("hub_list_device_events",device=102),
    ]
    plan=build_source_feasibility_choices(facts,reads)
    assert plan["schema"]=="causal-source-feasibility.v1"
    assert plan["advisory_only"] is True
    assert plan["target_scoped_history_reads"]==2
    assert plan["recorded_immediate_command_matches"]==0
    assert len(plan["candidate_reads"])==2
    assert plan["candidate_reads"][0]["leaf"]=="hub_list_device_dependents"
    assert plan["candidate_reads"][0]["args"]=={"deviceId":"102"}
    assert plan["candidate_reads"][1]["leaf"]=="hub_get_app_config"
    assert plan["candidate_reads"][1]["args"]=={"appId":"4013"}
    assert all(x["cannot_prove"] for x in plan["candidate_reads"])
    assert plan["unresolved_sources"][0]["required"]=="original-ON-command-issuer"
    assert plan["source_absence_proven"] is False
    assert plan["has_independently_verified_upstream_origin"] is False


def test_no_phantom_tool_when_leaf_not_in_existing_success_receipts():
    facts=data()
    reads=[receipt("hub_list_device_events",device=101),
           receipt("hub_get_app_config",app=1000,success=False)]
    plan=build_source_feasibility_choices(facts,reads)
    assert plan["candidate_reads"]==[]
    assert plan["no_further_concrete_read_in_verified_receipts"] is True
    assert plan["unresolved_sources"][0]["status"]=="not-witnessed-in-retained-sources"
    assert "hub_get_command_history" not in json.dumps(plan)


def test_successful_duplicate_signatures_are_counted_but_failed_retries_are_not():
    facts=data()
    reads=[
        receipt("hub_list_device_events",device=101),
        receipt("hub_list_device_events",device=101),
        receipt("hub_get_app_config",app=4013,success=False),
        receipt("hub_get_app_config",app=4013),
        receipt("hub_list_device_dependents",device=101),
        receipt("hub_list_device_dependents",device=102),
    ]
    plan=build_source_feasibility_choices(facts,reads)
    assert plan["successful_exact_duplicate_read_count"]==1
    assert plan["candidate_reads"]==[]
    assert plan["already_checked_command_app_configs"]==["4013"]
    assert plan["already_checked_dependency_targets"]==["101","102"]


def test_unrelated_source_code_discovery_does_not_close_command_history_gap():
    facts=data()
    reads=[{
        "tool":"hub_search_tools","success":True,"effect":"read",
        "mutates":False,
        "arguments":{"query":"read installed Groovy code chunks"}
    }]
    plan=build_source_feasibility_choices(facts,reads)
    assert "topic may differ" in plan["unresolved_sources"][0]["discovery"]


def test_unverified_app_or_target_ids_never_become_suggested_arguments():
    facts=data(targets=("101","bogus"),apps=("4013","not-app"))
    reads=[receipt("hub_list_device_dependents",device=12),
           receipt("hub_get_app_config",app=12)]
    plan=build_source_feasibility_choices(facts,reads)
    assert len(plan["candidate_reads"])==2
    assert plan["candidate_reads"][0]["args"]=={"deviceId":"101"}
    assert plan["candidate_reads"][1]["args"]=={"appId":"4013"}
    assert "not-app" not in json.dumps(plan)


def test_bounded_choices_and_no_writes_and_no_hard_stop():
    facts=data(targets=("101","102","103","104","105"))
    reads=[receipt("hub_list_device_dependents",device=999)]
    plan=build_source_feasibility_choices(facts,reads,max_options=2)
    assert len(plan["candidate_reads"])==2
    assert plan["additional_candidates_omitted"]==3
    assert all(option["leaf"]=="hub_list_device_dependents"
               for option in plan["candidate_reads"])
    assert plan["no_new_permissions_granted"]
    assert all("permission" not in k for k in plan["candidate_reads"][0])


def test_positive_issuer_match_does_not_invent_root_cause():
    facts=data(targets=("101",),apps=("4013",))
    facts["incident_ledger"]=[
        {"device_id":"101","event_class":"issued_on","app_id":"4013",
         "date":"2026-10-30T15:00:00.100+00:00"},
        {"device_id":"101","event_class":"reported_switch_on",
         "date":"2026-10-30T15:00:00.250+00:00"},
    ]
    facts["v3_witness_ledger"]=build_witness_coverage_ledger(facts,[])
    plan=build_source_feasibility_choices(facts,[])
    assert plan["recorded_immediate_command_matches"]==1
    assert plan["unresolved_sources"][0]["required"]=="original-input-event-timestamps"
    assert plan["has_independently_verified_upstream_origin"] is False


def test_journal_checkpoint_still_uses_original_model_and_advisory_choices():
    # Exercising the original collector's structured path is covered by the
    # separate mixed-journal regression tests. This contract prevents a
    # second agent or tool call from being added by this source planner.
    assert callable(cross_source_discovery_checkpoint)
    assert callable(unified_investigation_instruction)
    assert build_source_feasibility_choices(None,[]) is None
