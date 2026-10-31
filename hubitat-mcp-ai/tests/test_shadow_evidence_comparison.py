"""Stage 2.5 shadow parity checks; no agent/live API invocation."""
from copy import deepcopy
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from canonical_investigation_evidence import build_canonical_evidence_view
from shadow_evidence_comparison import (
    benchmark_shadow_replay, compare_shadow_evidence,
)
from unified_investigation_bridge import collect_unified_evidence
from test_canonical_investigation_foundation import named_lookup, native_command
from test_v3_reception_evidence_018267 import QUESTION, replay


def _facts(rows):
    facts = collect_unified_evidence(rows, QUESTION)
    assert facts and facts["v3_witness_ledger"]
    return facts


def test_five_cycle_shadow_preserves_source_and_collector_clocks():
    rows = replay()
    facts = _facts(rows)
    report = compare_shadow_evidence(rows, facts)
    assert report["schema"] == "homebrain-shadow-comparison.v1"
    assert report["shadow_only"] is True
    assert report["writes_performed"] == 0
    assert report["legacy_witness_available"] is True
    assert report["canonical_counts"]["source_clock_records"] == 20
    assert report["canonical_counts"]["collector_clock_records"] >= 20
    assert report["source_coverage_proven_complete"] is False
    assert report["physical_ack_verified"] is False
    assert report["root_cause_verified_by_comparison"] is False
    assert report["legacy_counts"]["matched_witness_keys"] > 0
    # Legacy lookup fixture lacks a typed source qualifier. The shadow view
    # records the identity gap instead of silently accepting a weaker label.
    assert set(report["target_ids_missing_canonical_verified_names"]) == {"101", "102"}


def test_independently_scoped_names_survive_shadow_without_promoting_listeners():
    rows = [named_lookup("101", "North Lamp"),
            named_lookup("102", "South Lamp"),
            native_command("101", issuer="3001", label="Test Controller"),
            *replay()]
    facts = _facts(rows)
    report = compare_shadow_evidence(rows, facts)
    assert report["target_ids_missing_canonical_verified_names"] == []
    assert "3001" in report["issuer_ids_with_name_lost_in_legacy_ledger"]
    assert "3999" not in report["issuer_ids_with_name_lost_in_legacy_ledger"]
    assert report["physical_ack_verified"] is False


def test_missing_legacy_witness_is_reported_and_bounded():
    rows = replay()
    facts = deepcopy(_facts(rows))
    witness = facts["v3_witness_ledger"]
    witness["witnesses"].append({
        "entity": "101", "role": "state-report",
        "event_class": "journal_source_switch_on",
        "time": "2026-10-30T15:20:00+00:00", "clock_basis": "source",
    })
    report = compare_shadow_evidence(rows, facts, max_examples=0)
    assert report["status"] == "divergence"
    assert report["legacy_counts"]["missing_witness_keys"] >= 1
    assert report["missing_canonical_witnesses"] == []
    assert report["missing_canonical_witnesses_omitted"] >= 1


def test_not_comparable_is_not_a_negative_or_absence_claim():
    rows = [native_command("701", issuer="501", label="Heating Coordinator",
                           attribute="command-setHeatingSetpoint")]
    report = compare_shadow_evidence(rows, None, legacy_graph={"scope": "ambiguous"})
    view = build_canonical_evidence_view(rows)
    assert report["status"] == "not-comparable"
    assert report["legacy_graph_scope"] == "ambiguous"
    assert report["legacy_counts"]["available_witness_keys"] == 0
    assert view.verified_label("app", "501") == "Heating Coordinator"
    assert report["root_cause_verified_by_comparison"] is False


def test_query_gap_counts_remain_query_counts_not_outage_counts():
    rows = replay()
    facts = deepcopy(_facts(rows))
    facts["target_coverage"][0]["journal_gaps"] += 7
    report = compare_shadow_evidence(rows, facts)
    assert len(report["journal_query_gap_disagreements"]) == 1
    gap = report["journal_query_gap_disagreements"][0]
    assert gap["device_id"] == str(facts["target_coverage"][0]["device_id"])
    assert gap["legacy_query_gaps"] - gap["canonical_query_gaps"] == 7


def test_truncated_legacy_witness_presentation_is_explicitly_partial():
    rows = [named_lookup("101", "North Lamp"),
            named_lookup("102", "South Lamp"), *replay()]
    facts = deepcopy(_facts(rows))
    facts["v3_witness_ledger"]["witnesses_omitted"] = 9
    report = compare_shadow_evidence(rows, facts)
    assert report["legacy_counts"]["witnesses_omitted"] == 9
    assert report["status"] in ("partial", "divergence")
    assert report["source_coverage_proven_complete"] is False


def test_offline_benchmark_never_runs_tools_or_changes_receipts():
    rows = replay()
    before = json.dumps(rows, sort_keys=True)
    benchmark = benchmark_shadow_replay(rows, QUESTION, iterations=2)
    assert benchmark["iterations"] == 2
    assert benchmark["baseline_compute_median_ms"] >= 0
    assert benchmark["shadow_comparison_median_ms"] >= 0
    assert benchmark["includes_mcp_or_model_latency"] is False
    assert benchmark["changes_production_latency"] is False
    assert json.dumps(rows, sort_keys=True) == before
