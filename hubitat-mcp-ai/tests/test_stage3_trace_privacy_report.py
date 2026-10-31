"""Stage 3E privacy and provenance boundary regression.

The suite uses CONSTRUCTED calls; it does not assert genuine captures exist.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "rootfs" / "app"))

from stage3_trace_privacy_report import build_stage3e_private_trace_report
from test_stage3_controlled_replay import replay_suite

CLI = PACKAGE / "tools" / "stage3e_local_trace_report.py"


def test_constructed_six_domain_replay_is_scored_but_never_live_verified():
    cases = replay_suite()
    before = deepcopy(cases)
    result = build_stage3e_private_trace_report(cases, top_k=2)
    assert result["schema"] == "homebrain-stage3e-private-aggregate.v1"
    assert result["source_case_count"] == 6
    assert result["round_count"] == 6
    assert result["independently_scored_rounds"] == 6
    assert result["origins"]["constructed_fixture"] == 6
    assert result["small_domain_case_counts_suppressed"] == 6
    assert result["domains_with_at_least_three_cases"] == {}
    assert result["live_quality_improvement_verified"] is False
    assert result["independently_authenticated_genuine_traces"] == 0
    assert result["can_trigger_live_activation"] is False
    assert result["end_to_end_latency_measured"] is False
    assert cases == before


def test_shareable_report_never_contains_private_source_or_model_fields():
    cases = replay_suite()
    cases[-1]["rounds"][0]["model_tool_calls"][0]["function"][
        "arguments"] = json.dumps({
            "tool": "hub_list_device_dependents",
            "args": {"deviceId": "741", "secret": "SECRET-SENTINEL-DO-NOT-ECHO"},
        })
    cases[1]["rounds"][0]["receipts_before"][0]["name"] = (
        "MySecretHomeAndBedroomLocation")
    report = build_stage3e_private_trace_report(cases)
    output = json.dumps(report)
    for forbidden in ("SECRET-SENTINEL", "MySecretHome", "deviceId",
                      "appId", "hub_read_apps_code", "hub_read_devices",
                      "model_tool_calls", "receipts_before", "741",
                      "Heat Coordinator", "2026-10-30"):
        assert forbidden not in output
    assert report["raw_input_saved_or_transmitted"] is False


def test_provenance_labels_do_not_create_authentication_or_unlock():
    cases = replay_suite()
    cases[0]["trace_origin"] = "user-labelled-redacted-trace"
    cases[1]["trace_origin"] = "anonymised-reconstruction"
    result = build_stage3e_private_trace_report(cases)
    assert result["origins"]["user_labelled_redacted_trace"] == 1
    assert result["origins"]["anonymised_reconstruction"] == 1
    assert result["independently_authenticated_genuine_traces"] == 0
    assert result["enablement_decision"] == "blocked-pending-independent-trace-verification"
    assert result["data_provenance"] == "user-supplied-not-independently-authenticated"


def test_domains_are_bucketed_and_small_cells_suppressed():
    base = replay_suite()[0]
    base["domain"] = "lighting"
    cases = [deepcopy(base) for _ in range(3)]
    report = build_stage3e_private_trace_report(cases)
    assert report["domains_with_at_least_three_cases"] == {"lighting": 3}
    assert report["small_domain_case_counts_suppressed"] == 0
    cases.append(deepcopy(replay_suite()[1]))
    next_result = build_stage3e_private_trace_report(cases)
    assert next_result["domains_with_at_least_three_cases"] == {"lighting": 3}
    assert next_result["small_domain_case_counts_suppressed"] == 1


def test_missing_oracle_is_null_and_not_invented_as_zero_or_success():
    case = replay_suite()[1]
    del case["rounds"][0]["expected_reads"]
    report = build_stage3e_private_trace_report([case])
    assert report["independently_scored_rounds"] == 0
    assert report["unscored_rounds"] == 1
    assert report["model_original"]["macro_recall_at_k"] is None
    assert report["stage3_frontier"]["macro_recall_at_k"] is None


@pytest.mark.parametrize("mutation", [
    lambda cases: cases.extend([deepcopy(cases[0]) for _ in range(25)]),
    lambda cases: cases[0].update({"trace_origin": "verified-live"}),
    lambda cases: cases[0].update({"domain": "Bedroom 1"}),
    lambda cases: cases[0]["rounds"][0].update({"receipts_before":
                                               [deepcopy(cases[0]["rounds"][0]["receipts_before"][0])] * 161}),
    lambda cases: cases[0]["rounds"][0].update({"model_tool_calls":
                                               [deepcopy(cases[0]["rounds"][0]["model_tool_calls"][0])] * 17}),
    lambda cases: cases[0].update({"rounds": [deepcopy(cases[0]["rounds"][0])] * 13}),
])
def test_invalid_or_truncating_capture_is_rejected(mutation):
    cases = replay_suite()
    mutation(cases)
    with pytest.raises(ValueError):
        build_stage3e_private_trace_report(cases)


def test_cli_requires_explicit_ack_before_accessing_input(tmp_path):
    path = tmp_path / "sensitive-sentinel.json"
    path.write_text("SENSITIVE-PRIVATE-SECRET", encoding="utf8")
    run = subprocess.run([sys.executable, str(CLI), "--input", str(path)],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 2
    assert run.stdout == ""
    assert "acknowledgement required" in run.stderr
    assert "PRIVATE-SECRET" not in run.stderr


def test_cli_produces_private_counts_no_input_values(tmp_path):
    cases = replay_suite()
    cases[0]["trace_origin"] = "user-labelled-redacted-trace"
    path = tmp_path / "unshared-replay.json"
    path.write_text(json.dumps({"cases": cases}), encoding="utf8")
    run = subprocess.run(
        [sys.executable, str(CLI), "--input", str(path),
         "--ack-local-sensitive-processing"],
        capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    report = json.loads(run.stdout)
    assert report["source_case_count"] == 6
    assert report["origins"]["user_labelled_redacted_trace"] == 1
    assert report["can_trigger_live_activation"] is False
    for field in ("appId", "deviceId", "Heat Coordinator",
                  "hub_read_devices", "741", "model_tool_calls"):
        assert field not in run.stdout


def test_cli_invalid_input_never_leaks_secret(tmp_path):
    path = tmp_path / "secret-input.json"
    path.write_text('{"cases": "VERY-SECRET-SENTINEL"', encoding="utf8")
    run = subprocess.run(
        [sys.executable, str(CLI), "--input", str(path),
         "--ack-local-sensitive-processing"], capture_output=True,
        text=True, check=False)
    assert run.returncode == 2
    assert run.stdout == ""
    assert "VERY-SECRET-SENTINEL" not in run.stderr
