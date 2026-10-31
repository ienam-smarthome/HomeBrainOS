"""Stage 3B cross-domain planning utility, safety, and parity tests.

All fixtures are local, anonymised, source-scoped retained read receipts.
Reference expected reads are authored independently and supplied only to
the evaluator, never to the frontier itself.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from stage3_planning_evaluation import evaluate_stage3_fixture_suite
from stage3_evidence_frontier import build_stage3_read_frontier
from test_canonical_investigation_foundation import named_lookup, native_command
from test_v3_reception_evidence_018267 import QUESTION, replay
from unified_investigation_bridge import collect_unified_evidence

CATALOG = ("hub_list_device_events", "hub_list_device_dependents",
           "hub_get_app_config")


def candidate(leaf, **args):
    return {"leaf": leaf, "args": args}


def scoped_read(device, success=True, events=None):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": success, "effect": "read",
        "arguments": {"args": {"deviceId": device}},
        "details": {"observedEvents": list(events or [])},
    }


def window(device, attribute="switch"):
    return candidate("hub_list_device_events", deviceId=device,
                     since="2026-10-30T14:00:00Z",
                     until="2026-10-30T15:00:00+00:00",
                     attribute=attribute)


def domain_suite():
    lights = replay()
    facts = collect_unified_evidence(lights, QUESTION)
    assert facts is not None
    return [
        {
            "case_id": "paired-lights-journal", "domain": "lighting",
            "receipts": lights, "facts": facts,
            "available_read_tools": CATALOG,
            "model_proposals": [candidate("hub_list_device_dependents", deviceId="201"),
                                candidate("hub_list_device_dependents", deviceId="999")],
            "expected_reads": [candidate("hub_list_device_dependents", deviceId="201")],
        },
        {
            "case_id": "thermostat-command", "domain": "heating",
            "receipts": [named_lookup("701", "Heating Source"),
                         native_command("701", issuer="501", label="Heat Coordinator",
                                        attribute="command-setHeatingSetpoint")],
            "available_read_tools": CATALOG,
            "model_proposals": [candidate("hub_get_app_config", appId="501"),
                                candidate("hub_get_app_config", appId="3999")],
            "expected_reads": [candidate("hub_get_app_config", appId="501")],
        },
        {
            "case_id": "humidity-fan", "domain": "ventilation",
            "receipts": [named_lookup("711", "Extractor"),
                         native_command("711", issuer="551", label="Humidity Scheduler",
                                        attribute="command-off")],
            "available_read_tools": CATALOG,
            "model_proposals": [candidate("hub_get_app_config", appId="551"),
                                window("711", "humidity")],
            "expected_reads": [candidate("hub_get_app_config", appId="551"),
                               window("711", "humidity")],
        },
        {
            "case_id": "offline-power-device", "domain": "power",
            "receipts": [named_lookup("721", "Freezer"),
                         scoped_read("721", success=True, events=[])],
            "available_read_tools": CATALOG,
            "model_proposals": [candidate("hub_list_device_dependents", deviceId="721"),
                                window("721", "power")],
            "expected_reads": [candidate("hub_list_device_dependents", deviceId="721"),
                               window("721", "power")],
        },
        {
            "case_id": "failed-history-recovery", "domain": "history",
            "receipts": [named_lookup("731", "Room Sensor"),
                         scoped_read("731", success=False)],
            "available_read_tools": CATALOG,
            "model_proposals": [candidate("hub_list_device_events", deviceId="731"),
                                window("731", "contact")],
            "expected_reads": [window("731", "contact")],
        },
        {
            "case_id": "spoofed-app-and-secret", "domain": "security",
            "receipts": [named_lookup("741", "Plug")],
            "available_read_tools": (*CATALOG, "hub_delete_device"),
            "model_proposals": [
                candidate("hub_delete_device", deviceId="741"),
                candidate("hub_get_app_config", appId="9999"),
                candidate("hub_list_device_dependents", deviceId="741",
                          token="SENSITIVE-DO-NOT-REPEAT"),
                candidate("hub_list_device_dependents", deviceId="741"),
            ],
            "expected_reads": [candidate("hub_list_device_dependents", deviceId="741")],
        },
    ]


def test_six_domain_suite_recovers_independent_oracle_leads():
    suite = domain_suite()
    result = evaluate_stage3_fixture_suite(suite, top_k=3)
    assert result["schema"] == "homebrain-stage3b-offline-scorecard.v1"
    assert result["suite_count"] == 6
    assert result["total_expected_reads"] == 8
    assert result["total_stage3_useful_reads_at_k"] == 8
    assert result["stage3_macro_oracle_recall_at_k"] == 1.0
    assert result["total_invalid_or_unauthorized_stage3_offers"] == 0
    assert result["legacy_comparable_cases"] == 1
    assert result["total_suppressed_exact_repeats"] >= 1
    assert result["total_suppressed_unverified_ids"] >= 2
    assert result["total_suppressed_invalid_scopes"] >= 1
    assert result["total_suppressed_unsupported_leaves"] >= 1
    assert result["no_runtime_quality_or_latency_claim"] is True
    assert "SENSITIVE-DO-NOT-REPEAT" not in json.dumps(result)


def test_all_domains_report_no_causal_proof_and_case_summaries_are_small():
    result = evaluate_stage3_fixture_suite(domain_suite())
    assert {row["domain"] for row in result["cases"]} == {
        "lighting", "heating", "ventilation", "power", "history", "security"}
    assert all(row["source_absence_proven"] is False
               and row["root_cause_proven"] is False for row in result["cases"])
    assert all(row["new_frontier"]["invalid_or_unauthorized_offered"] == 0
               for row in result["cases"])


def test_oracle_is_independent_of_frontier_plan():
    items = domain_suite()
    base = build_stage3_read_frontier(
        items[1]["receipts"],
        model_proposals=items[1]["model_proposals"],
        available_read_tools=items[1]["available_read_tools"])
    mutated = deepcopy(items)
    mutated[1]["expected_reads"] = [candidate("hub_list_device_dependents", deviceId="701")]
    changed = build_stage3_read_frontier(
        mutated[1]["receipts"],
        model_proposals=mutated[1]["model_proposals"],
        available_read_tools=mutated[1]["available_read_tools"])
    assert base == changed
    score = evaluate_stage3_fixture_suite(mutated)["cases"][1]
    assert score["new_frontier"]["useful"] == 0


def test_reception_clock_is_not_source_clock_or_proof():
    data = domain_suite()[0]
    result = evaluate_stage3_fixture_suite([data])
    assert result["cases"][0]["source_absence_proven"] is False
    assert result["cases"][0]["root_cause_proven"] is False
    assert result["total_stage3_useful_reads_at_k"] == 1


def test_missing_oracle_and_no_available_catalog_cannot_claim_success():
    data = domain_suite()[1]
    data = deepcopy(data)
    data["available_read_tools"] = ()
    data["expected_reads"] = []
    report = evaluate_stage3_fixture_suite([data])
    assert report["total_stage3_useful_reads_at_k"] == 0
    assert report["stage3_macro_oracle_recall_at_k"] is None
    assert report["cases"][0]["new_frontier"]["offered"] == 0


def test_failed_exact_repeat_is_suppressed_without_source_absence_verdict():
    rows = domain_suite()[4:5]
    result = evaluate_stage3_fixture_suite(rows)
    assert result["total_suppressed_exact_repeats"] >= 1
    assert result["cases"][0]["new_frontier"]["useful"] == 1
    assert result["cases"][0]["source_absence_proven"] is False


def test_reference_oracle_rejects_malformed_unauthorised_and_duplicate_reads():
    data = deepcopy(domain_suite()[1])
    data["expected_reads"] = [candidate("hub_get_app_config", appId="501")] * 2
    with pytest.raises(ValueError, match="unique"):
        evaluate_stage3_fixture_suite([data])
    data["expected_reads"] = [candidate("hub_delete_device", deviceId="701")]
    with pytest.raises(ValueError, match="catalog-scoped"):
        evaluate_stage3_fixture_suite([data])


def test_case_id_cannot_expose_source_text_or_markup():
    data = domain_suite()[1]
    data["case_id"] = "<script>secret</script>"
    with pytest.raises(ValueError, match="case_id"):
        evaluate_stage3_fixture_suite([data])


def test_existing_frontier_not_applicable_is_reported_as_null_not_zero():
    result = evaluate_stage3_fixture_suite(domain_suite()[1:])
    assert result["legacy_comparable_cases"] == 0
    assert result["existing_macro_precision_at_k"] is None
    assert result["existing_macro_oracle_recall_at_k"] is None


def test_suite_limit_does_not_infer_historical_completeness():
    data = domain_suite()[1]
    result = evaluate_stage3_fixture_suite([data] * 41)
    assert result["suite_count"] == 40
    assert result["suite_cases_omitted"] == 1
    assert result["zero_unsupported_causal_claims_asserted"] is True


def test_input_receipts_unchanged_and_deterministic_scores():
    cases = domain_suite()
    before = deepcopy(cases)
    first = evaluate_stage3_fixture_suite(cases, top_k=2)
    second = evaluate_stage3_fixture_suite(cases, top_k=2)
    assert cases == before
    assert first == second
    assert first["total_invalid_or_unauthorized_stage3_offers"] == 0


@pytest.mark.parametrize("bad_apps", [42, "not-a-list", {"appId": "9"}, True])
def test_malformed_dependency_metadata_cannot_crash_or_attest_app(bad_apps):
    receipts = [named_lookup("721", "Freezer"),
                {"tool": "hub_read_apps_code",
                 "sub_tool": "hub_list_device_dependents",
                 "success": True, "effect": "read",
                 "arguments": {"args": {"deviceId": "721"}},
                 "details": {"deviceId": "721", "appsUsing": bad_apps}}]
    packet = build_stage3_read_frontier(
        receipts, available_read_tools=CATALOG,
        model_proposals=[candidate("hub_get_app_config", appId="9"),
                         candidate("hub_list_device_events", deviceId="721",
                                   since="2026-10-30T14:00:00Z",
                                   until="2026-10-30T15:00:00Z")])
    assert packet["candidate_count"] == 1
    assert packet["candidate_reads"][0]["leaf"] == "hub_list_device_events"
    assert packet["rejected_candidate_counts"]["identifier-not-source-attested"] == 1
