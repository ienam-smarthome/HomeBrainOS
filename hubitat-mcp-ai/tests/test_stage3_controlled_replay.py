"""Stage 3D controlled replay: original-model-shaped calls versus Stage 3A.

No real model/hub is called. This replay deliberately labels constructed
scenario calls as constructed, not as captured live agent output.
"""
from copy import deepcopy
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from stage3_controlled_replay import evaluate_stage3d_replay
from test_stage3_planning_evaluation import domain_suite, candidate, window, scoped_read
from test_stage3_loop_shadow import schema, call
from test_canonical_investigation_foundation import named_lookup, native_command

DEVICE = schema("hub_read_devices",
                ("hub_list_device_events", "hub_list_device_dependents"))
APP = schema("hub_read_apps_code", ("hub_get_app_config",))
CATALOG = [DEVICE, APP]


def recorded_shape(leaf, *, gateway=None, **kwargs):
    if gateway is None:
        gateway = "hub_read_apps_code" if leaf == "hub_get_app_config" else "hub_read_devices"
    return call(gateway=gateway, leaf=leaf, args=kwargs, as_json=True)


def sample(case_id, domain, receipts, calls, expected=None, facts=None,
           origin="constructed-fixture", schemas=None):
    round_row = {
        "receipts_before": receipts,
        "declared_tool_schemas": CATALOG if schemas is None else schemas,
        "model_tool_calls": calls,
    }
    if facts is not None:
        round_row["facts"] = facts
    if expected is not None:
        round_row["expected_reads"] = expected
    return {"case_id": case_id, "domain": domain,
            "trace_origin": origin, "rounds": [round_row]}


def replay_suite():
    cases = domain_suite()
    return [
        sample("lights-five-cycle", "lighting", cases[0]["receipts"], [
            recorded_shape("hub_list_device_dependents", deviceId="999"),
            recorded_shape("hub_list_device_dependents", deviceId="201"),
        ], [candidate("hub_list_device_dependents", deviceId="201")],
               facts=cases[0]["facts"], origin="anonymised-reconstruction"),
        sample("heat-source-issuer", "heating", cases[1]["receipts"], [
            recorded_shape("hub_get_app_config", appId="3999"),
            recorded_shape("hub_get_app_config", appId="501"),
        ], [candidate("hub_get_app_config", appId="501")]),
        sample("fan-humidity-bound", "ventilation", cases[2]["receipts"], [
            recorded_shape("hub_get_app_config", appId="551"),
            recorded_shape("hub_list_device_events", **window("711", "humidity")["args"]),
        ], [candidate("hub_get_app_config", appId="551"),
            window("711", "humidity")]),
        sample("power-empty-native-history", "power", cases[3]["receipts"], [
            recorded_shape("hub_list_device_events", deviceId="721"),
            recorded_shape("hub_list_device_events", **window("721", "power")["args"]),
        ], [window("721", "power")]),
        sample("history-failed-native-read", "history", cases[4]["receipts"], [
            recorded_shape("hub_list_device_events", deviceId="731"),
            recorded_shape("hub_list_device_events", **window("731", "contact")["args"]),
        ], [window("731", "contact")]),
        sample("security-adversarial-catalog", "security", cases[5]["receipts"], [
            recorded_shape("hub_delete_device", gateway="hub_manage_devices", deviceId="741"),
            recorded_shape("hub_list_device_dependents", deviceId="741",
                           secret="NEVER-LEAK-THIS-TOKEN"),
            recorded_shape("hub_list_device_dependents", deviceId="741"),
        ], [candidate("hub_list_device_dependents", deviceId="741")]),
    ]


def test_six_domain_model_vs_shadow_scorecard():
    cases = replay_suite()
    report = evaluate_stage3d_replay(cases, top_k=2)
    assert report["schema"] == "homebrain-stage3d-controlled-replay.v1"
    assert report["case_count"] == 6
    assert report["round_count"] == 6
    assert report["oracle_scored_rounds"] == 6
    assert report["oracle_unscored_rounds"] == 0
    assert report["model_calls_replayed_not_executed"] is True
    assert report["no_agent_tool_or_publisher_change"] is True
    assert report["total_duplicate_attempts_suppressed"] >= 2
    assert report["total_unattested_ids_suppressed"] >= 2
    assert report["total_invalid_scopes_suppressed"] >= 1
    assert report["shadow_macro_oracle_recall_at_k"] is not None
    assert report["input_trace_provenance_not_verified"] is True
    assert report["causal_initiator_verified"] is False
    assert "NEVER-LEAK" not in json.dumps(report)


def test_model_top1_differs_from_filtered_shadow_with_bad_first_issuer():
    report = evaluate_stage3d_replay([replay_suite()[1]], top_k=1)
    one = report["cases"][0]["rounds"][0]
    assert one["model_oracle"]["oracle_recall_at_k"] == 0.0
    assert one["shadow_oracle"]["oracle_recall_at_k"] == 1.0
    assert one["unattested_ids_suppressed"] == 1
    assert one["effect_on_live_tool_calls"] is False


def test_repeated_success_empty_or_failed_is_not_recommended():
    for which in (3, 4):
        result = evaluate_stage3d_replay([replay_suite()[which]], top_k=1)
        one = result["cases"][0]["rounds"][0]
        assert one["model_oracle"]["oracle_recall_at_k"] == 0.0
        assert one["shadow_oracle"]["oracle_recall_at_k"] == 1.0
        assert one["duplicate_exact_attempts_suppressed"] == 1


def test_nonreplayed_mcp_io_cannot_claim_latency_or_root_cause():
    result = evaluate_stage3d_replay(replay_suite())
    assert result["offline_only"]
    assert result["no_live_speed_or_quality_claim"]
    assert result["historical_completeness_proven"] is False
    assert result["physical_ack_verified"] is False
    assert result["model_calls_replayed_not_executed"] is True
    assert all(not row["effect_on_live_answer"]
               for case in result["cases"] for row in case["rounds"])


def test_missing_independent_oracle_is_not_fabricated_as_success_or_failure():
    case = replay_suite()[1]
    del case["rounds"][0]["expected_reads"]
    report = evaluate_stage3d_replay([case])
    assert report["oracle_scored_rounds"] == 0
    assert report["oracle_unscored_rounds"] == 1
    assert report["model_macro_oracle_recall_at_k"] is None
    assert report["shadow_macro_oracle_recall_at_k"] is None
    row = report["cases"][0]["rounds"][0]
    assert row["model_oracle"] is None and row["shadow_oracle"] is None


def test_oracle_is_never_shared_with_model_or_shadow():
    case = replay_suite()[1]
    before = deepcopy(case)
    alt = deepcopy(case)
    alt["rounds"][0]["expected_reads"] = [
        candidate("hub_list_device_dependents", deviceId="701")]
    r1 = evaluate_stage3d_replay([case])["cases"][0]["rounds"][0]
    r2 = evaluate_stage3d_replay([alt])["cases"][0]["rounds"][0]
    assert r1["shadow_read_candidates"] == r2["shadow_read_candidates"]
    assert r1["model_reads_with_declared_mapping"] == r2["model_reads_with_declared_mapping"]
    assert r1["shadow_oracle"]["useful_at_k"] == 1
    assert r2["shadow_oracle"]["useful_at_k"] == 0
    assert case == before


def test_oracle_rejects_unattested_identifier_and_undeclared_leaf():
    original = replay_suite()[1]
    case = deepcopy(original)
    case["rounds"][0]["expected_reads"] = [candidate("hub_get_app_config", appId="9999")]
    with pytest.raises(ValueError, match="receipt evidence"):
        evaluate_stage3d_replay([case])
    case["rounds"][0]["expected_reads"] = [candidate("hub_delete_device", deviceId="701")]
    with pytest.raises(ValueError, match="declared"):
        evaluate_stage3d_replay([case])


def test_rejects_fake_provenance_and_unbounded_evidence():
    case = replay_suite()[1]
    case["trace_origin"] = "live-proven"
    with pytest.raises(ValueError, match="trace_origin"):
        evaluate_stage3d_replay([case])
    case = replay_suite()[1]
    case["rounds"][0]["receipts_before"] = [named_lookup("701")] * 161
    with pytest.raises(ValueError, match="bounded"):
        evaluate_stage3d_replay([case])


def test_redacted_model_trace_user_label_is_explicitly_unverified():
    case = replay_suite()[1]
    case["trace_origin"] = "user-labelled-redacted-trace"
    result = evaluate_stage3d_replay([case])
    assert result["cases"][0]["trace_origin"] == "user-labelled-redacted-trace"
    assert result["cases"][0]["provenance_independently_authenticated"] is False


def test_read_catalog_absent_does_not_approve_unadvertised_calls():
    case = replay_suite()[1]
    case["rounds"][0]["declared_tool_schemas"] = []
    del case["rounds"][0]["expected_reads"]
    one = evaluate_stage3d_replay([case])["cases"][0]["rounds"][0]
    assert one["model_reads_with_declared_mapping"] == 0
    assert one["shadow_read_candidates"] == 0
    assert one["unsupported_operations_skipped"] == 2


def test_cumulative_rounds_use_only_receipts_before_each_round():
    base = replay_suite()[1]
    first = deepcopy(base["rounds"][0])
    first["expected_reads"] = [candidate("hub_get_app_config", appId="501")]
    second = deepcopy(first)
    second["receipts_before"] = [
        *second["receipts_before"],
        {"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
         "arguments": {"args": {"appId": "501"}},
         "success": True, "effect": "read", "details": {}},
    ]
    second["expected_reads"] = []
    case = {**base, "rounds": [first, second]}
    result = evaluate_stage3d_replay([case])
    round_one, round_two = result["cases"][0]["rounds"]
    assert round_one["shadow_read_candidates"] == 1
    assert round_two["duplicate_exact_attempts_suppressed"] >= 1
    assert round_two["shadow_read_candidates"] == 0
    assert result["round_count"] == 2


def test_bounded_calls_and_cases_report_omissions_without_source_absence():
    case = replay_suite()[1]
    case["rounds"][0]["model_tool_calls"] = [recorded_shape("hub_get_app_config", appId="501")] * 18
    report = evaluate_stage3d_replay([case] * 26)
    assert report["case_count"] == 24 and report["cases_omitted"] == 2
    row = report["cases"][0]["rounds"][0]
    assert row["input_model_calls"] == 16
    assert row["model_calls_omitted"] == 2
    assert report["historical_completeness_proven"] is False


def test_all_result_fields_are_pii_safe_counts_and_safe_identifiers():
    case = replay_suite()[-1]
    result = evaluate_stage3d_replay([case])
    blob = json.dumps(result)
    for sensitive in ("NEVER-LEAK", '"deviceId"', '"appId"', "741", "hub_manage_devices"):
        assert sensitive not in blob
    assert result["no_agent_tool_or_publisher_change"]


def test_deterministic_offline_replay_and_input_immutability():
    cases = replay_suite()
    backup = deepcopy(cases)
    one = evaluate_stage3d_replay(cases)
    two = evaluate_stage3d_replay(cases)
    assert cases == backup
    assert one == two
