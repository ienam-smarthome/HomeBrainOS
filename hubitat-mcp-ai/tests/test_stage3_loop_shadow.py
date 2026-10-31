"""Stage 3C passive observer: no execution, no permissions, no output changes."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from mcp_agent_orchestrator import UnifiedMCPAgent
from stage3_loop_shadow import observe_stage3_model_round
from test_canonical_investigation_foundation import native_command, named_lookup


def schema(gateway="hub_read_apps_code", operations=("hub_get_app_config",)):
    return {
        "type": "function", "function": {
            "name": gateway,
            "description": "Untrusted human-readable description",
            "parameters": {"type": "object", "properties": {
                "tool": {"type": "string", "enum": list(operations)},
                "args": {"type": "object"},
            }},
        },
    }


def call(gateway="hub_read_apps_code", leaf="hub_get_app_config",
         args=None, *, as_json=False):
    value = {"tool": leaf, "args": args if args is not None else {"appId": "3001"}}
    return {"function": {"name": gateway,
                         "arguments": json.dumps(value) if as_json else value}}


def test_default_agent_constructor_keeps_stage3_observation_off():
    p = inspect.signature(UnifiedMCPAgent.__init__).parameters
    assert p["stage3_shadow_mode"].default == "off"


def test_positive_live_tool_schema_admits_source_qualified_read_only():
    receipts = [native_command()]
    calls = [call()]
    schemas = [schema()]
    before = deepcopy((receipts, calls, schemas))
    report = observe_stage3_model_round(receipts, calls, schemas)
    assert report["schema"] == "homebrain-stage3c-passive-round.v1"
    assert report["read_calls_with_positive_catalog_mapping"] == 1
    assert report["verified_new_candidate_count"] == 1
    assert report["affects_model_prompts"] is False
    assert report["affects_tool_choices"] is False
    assert report["affects_final_answer"] is False
    assert report["executes_tools"] is False
    assert (receipts, calls, schemas) == before


def test_no_authority_from_gateway_description_or_prior_success_alone():
    receipts = [native_command()]
    no_enum = schema()
    del no_enum["function"]["parameters"]["properties"]["tool"]["enum"]
    report = observe_stage3_model_round(receipts, [call()], [no_enum])
    assert report["read_calls_with_positive_catalog_mapping"] == 0
    assert report["verified_new_candidate_count"] == 0
    assert report["unsupported_gateway_or_operation_calls_skipped"] == 1


def test_unknown_leaf_mutation_and_unadvertised_gateway_are_ignored():
    rows = [native_command()]
    calls = [
        call(gateway="hub_manage_devices", leaf="hub_delete_device"),
        call(leaf="hub_get_app_config"),
        call(gateway="hub_read_devices", leaf="hub_get_app_config"),
    ]
    result = observe_stage3_model_round(rows, calls, [schema()])
    assert result["read_calls_with_positive_catalog_mapping"] == 1
    assert result["unsupported_gateway_or_operation_calls_skipped"] == 2
    assert result["verified_new_candidate_count"] == 1


def test_duplicate_exact_source_read_is_not_recommended_again():
    prior = {"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
             "success": False, "effect": "read",
             "arguments": {"args": {"appId": "3001"}}}
    report = observe_stage3_model_round([native_command(), prior],
                                       [call(as_json=True)], [schema()])
    assert report["previous_exact_attempts"] == 1
    assert report["verified_new_candidate_count"] == 0
    assert report["no_source_absence_or_causal_proof"] is True


def test_spoofed_app_ids_and_sensitive_fields_are_not_emitted():
    rows = [named_lookup()]
    calls = [
        call(args={"appId": "9999"}),
        call(args={"appId": "3001", "apiKey": "VERY-SECRET-TOKEN"}),
    ]
    report = observe_stage3_model_round(rows, calls, [schema()])
    assert report["verified_new_candidate_count"] == 0
    assert report["unattested_id_suppressed"] == 1
    assert report["invalid_scope_suppressed"] == 1
    rendered = json.dumps(report)
    assert "9999" not in rendered
    assert "VERY-SECRET" not in rendered
    assert "3001" not in rendered


def test_malformed_calls_are_nonfatal_and_never_echoed():
    calls = [{"function": {"name": "hub_read_apps_code",
                           "arguments": "{sensitive broken json"}},
             {"function": {"name": "hub_read_apps_code", "arguments": "[]"}},
             {"function": {"name": "hub_read_apps_code", "arguments": {"tool": "hub_get_app_config"}}}]
    report = observe_stage3_model_round([], calls, [schema()])
    assert report["verified_new_candidate_count"] == 0
    assert report["invalid_envelopes_skipped"] == 2
    assert report["unsupported_gateway_or_operation_calls_skipped"] == 1
    assert "sensitive" not in json.dumps(report)


def test_disabled_catalog_never_upgrades_model_choices():
    r = observe_stage3_model_round([native_command()], [call()], [])
    assert r["read_calls_with_positive_catalog_mapping"] == 0
    assert r["verified_new_candidate_count"] == 0
    assert r["no_source_absence_or_causal_proof"] is True


def test_more_than_sixteen_calls_are_bounded_without_claiming_complete_coverage():
    calls = [call() for _ in range(25)]
    r = observe_stage3_model_round([native_command()], calls, [schema()])
    assert r["model_calls_examined"] == 16
    assert r["model_calls_omitted"] == 9
    assert r["verified_new_candidate_count"] == 1
    assert r["no_source_absence_or_causal_proof"] is True


def test_unhashable_malformed_suboperation_is_skipped_not_crashed():
    calls = [call(leaf={"unexpected": "dict"})]
    report = observe_stage3_model_round([native_command()], calls, [schema()])
    assert report["verified_new_candidate_count"] == 0
    assert report["unsupported_gateway_or_operation_calls_skipped"] == 1


def test_privacy_safe_observer_metrics_are_pre_registered():
    from request_metrics import RequestMetrics
    counters = (
        "stage3_shadow_observed_round",
        "stage3_shadow_round_with_new_read",
        "stage3_shadow_round_with_exact_repeat",
        "stage3_shadow_observation_error",
    )
    assert set(counters).issubset(RequestMetrics.ALLOWED_COUNTERS)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        for key in counters:
            metrics.increment(key)
        assert all(metrics.snapshot()["counters"][key] == 1 for key in counters)
    finally:
        metrics.reset(token)
