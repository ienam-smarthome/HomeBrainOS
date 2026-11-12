#!/usr/bin/env python3
"""Summarise PRIVATE V2 Technical JSON completion stages without printing drafts.

Usage: python inspect_answer_stages.py /path/to/private-technical-json.json
       python inspect_answer_stages.py /path/to/private-technical-json.json --json

This is descriptive diagnostics, not a causal adjudicator or a model evaluation
score. It does not connect to Hubitat, the cloud model or any network.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def stage_summary(payload: dict[str, Any]) -> dict[str, Any]:
    response = payload.get("response", payload)
    if not isinstance(response, dict):
        raise ValueError("Technical JSON must contain an object response")
    stages = response.get("answer_stage_trace")
    if not isinstance(stages, list):
        raise ValueError("No answer_stage_trace; install V2 alpha.58 or later")
    summary = []
    prior_text = None
    prior_reads = None
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        text = stage.get("answer", "")
        if not isinstance(text, str):
            text = ""
        read_count = stage.get("tool_receipts_seen")
        if type(read_count) is not int:
            read_count = None
        summary.append({
            "stage": stage.get("stage"),
            "model_round": stage.get("after_model_round"),
            "tool_receipts_seen": read_count,
            "successful_tool_receipts_seen":
                stage.get("successful_tool_receipts_seen"),
            "failed_tool_receipts_seen": stage.get("failed_tool_receipts_seen"),
            "additional_tool_receipts_since_prior":
                read_count - prior_reads if read_count is not None
                and prior_reads is not None else None,
            "answer_changed_since_prior":
                text != prior_text if prior_text is not None else None,
            "draft_truncated": stage.get("answer_truncated") is True,
        })
        prior_text, prior_reads = text, read_count
    return {
        "ui_version": payload.get("ui_version"),
        "model": payload.get("model"),
        "source_review_invoked": response.get("source_review_invoked"),
        "final_claim_audit_invoked": response.get("final_claim_audit_invoked"),
        "final_claim_audit_status": response.get("final_claim_audit_status"),
        "model_rounds": response.get("rounds"),
        "total_tool_receipts": len(response.get("tool_calls", []))
            if isinstance(response.get("tool_calls"), list) else None,
        "stages": summary,
        "interpretation": (
            "Observational only: changed prose with unchanged receipt counts "
            "identifies a same-record revision, not whether it is more accurate. "
            "Score each stage against original successful source receipts, "
            "especially source gaps, positive issuers and counterexamples."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("technical_json", type=Path)
    parser.add_argument("--json", action="store_true",
                        help="Print compact metadata-only JSON")
    args = parser.parse_args()
    payload = json.loads(args.technical_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Technical JSON root must be an object")
    result = stage_summary(payload)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("Version:", result["ui_version"], " Model:", result["model"])
    print("Model rounds:", result["model_rounds"],
          " Source review:", result["source_review_invoked"],
          " Final audit:", result["final_claim_audit_status"])
    for stage in result["stages"]:
        print(f"  {stage['stage']}: round {stage['model_round']}, "
              f"receipts {stage['tool_receipts_seen']}, "
              f"new receipts {stage['additional_tool_receipts_since_prior']}, "
              f"text changed {stage['answer_changed_since_prior']}")
    print(result["interpretation"])


if __name__ == "__main__":
    main()
