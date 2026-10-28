#!/usr/bin/env python3
"""Offline, deterministic Investigation V2 golden replay.

Input is a sanitised, USER-REPORTED scenario fixture, not an archived live
MCP transaction. This gate verifies structural evidence retention and causal
boundaries, not quality of a new LLM explanation or historical truth.
No network, Hubitat writes, model calls, credentials, or live operations.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai" / "rootfs" / "app"))

from investigation_v2.evidence import build_case_file  # noqa: E402
from investigation_v2.causal_evidence import causal_evidence_bundle  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures"
FIXTURES = (FIXTURE_DIR / "investigation_v2_light2_2026_10_28_golden.json",)


def _event_matches(record: Any, expectation: dict[str, Any]) -> bool:
    if (record.stage != expectation["stage"]
            or record.action != expectation["action"]
            or record.producer_id != expectation["producer_id"]):
        return False
    if "value" in expectation and record.value != expectation["value"]:
        return False
    expected = datetime.fromisoformat(expectation["timestamp"].replace("Z", "+00:00"))
    actual = datetime.fromisoformat(record.timestamp_utc)
    return expected == actual


def replay_fixture(path: Path) -> dict[str, Any]:
    if path.parent != FIXTURE_DIR or path not in FIXTURES:
        raise ValueError("Only version-controlled, reviewed golden fixtures may execute")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported fixture version")
    target = data["target_id"]
    receipts = data["receipts"]
    if not isinstance(receipts, list) or not 0 < len(receipts) <= 12:
        raise ValueError("Invalid replay receipt count")
    for receipt in receipts:
        if (receipt.get("mutates") is not False
                or receipt.get("effect") != "read"
                or receipt.get("sub_tool") != "hub_list_device_events"
                or receipt.get("arguments", {}).get("args", {}).get("deviceId") != target):
            raise ValueError("Replay fixture may contain only same-device READ history")
    case = build_case_file(data["question"], receipts)
    evidence = causal_evidence_bundle(case, target)
    assertions = [
        {"name": expected["name"],
         "present_in_fixture_records": any(
             _event_matches(row, expected) for row in case.records)}
        for expected in data["source_assertions"]
    ]
    pair_expected = data["expected_pair"]
    pair_found = any(
        pair["issuer_app_id"] == pair_expected["issuer_app_id"]
        and pair["state_reporter_id"] == pair_expected["state_reporter_id"]
        and pair["device_id"] == pair_expected["target_id"]
        and pair["interval_ms"] == pair_expected["interval_ms"]
        and pair["physical_action_verified"] is False
        and pair["internal_rule_decision_verified"] is False
        for pair in evidence["command_state_pairs"]
    )
    filter_only = build_case_file(data["question"], receipts[:1])
    gap = causal_evidence_bundle(filter_only, target)["command_history"]
    gap_detected = (
        "command_events_excluded_by_filter" in gap["issues"]
        and gap["observed_command_records"] == 0
        and gap["no_command_proven"] is False
    )
    reference_only = data.get("reference_only_not_yet_source_verified", [])
    expected_unverified = (len(reference_only) > 0
                           and all("needed" in item for item in reference_only))
    ok = (all(row["present_in_fixture_records"] for row in assertions)
          and pair_found and gap_detected and expected_unverified
          and evidence["causal_verdict"] == "not_established"
          and not evidence["physical_action_verified"])
    return {
        "case_id": data["case_id"],
        "fixture_provenance": data["provenance"],
        "replay_structural_gate_passed": bool(ok),
        "source_assertions": assertions,
        "command_report_temporal_pair_in_fixture": pair_found,
        "filtered_command_history_gap_detected": gap_detected,
        "reference_only_facts_unverified": len(reference_only),
        "live_hub_claims_verified": False,
        "llm_explanation_quality_evaluated": False,
    }


def main() -> int:
    results = [replay_fixture(path) for path in FIXTURES]
    print(json.dumps({"schema_version": 1, "golden_replays": results},
                     indent=2, sort_keys=True))
    return 0 if all(r["replay_structural_gate_passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
