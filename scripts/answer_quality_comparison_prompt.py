#!/usr/bin/env python3
"""Render a frozen, identical, read-only source packet for Claude/Gemma.

No tools, model API, uploads, benchmark scoring or real device access. Private
review rubrics are never present. The prompt is model-neutral; the packet hash
comes from the already versioned curated fixture.
"""
from __future__ import annotations

import argparse
from answer_quality_fixed_packets import build_fixed_packets


def render_comparison_prompt(case_id: str) -> str:
    packets = {item["case_id"]: item for item in build_fixed_packets()}
    if case_id not in packets:
        raise ValueError("Unknown frozen source packet")
    p = packets[case_id]
    evidence = "\n".join(f"- {x}" for x in p["available_evidence"])
    return (
        "HOME ASSISTANT EVIDENCE-ONLY COMPARISON (READ ONLY)\n"
        "Answer the question naturally and concisely using only the exact "
        "evidence below. Do not call MCP, browse, inspect a live hub, "
        "invent events, or rely on earlier conversation context. "
        "Separate confirmed observations, possible explanations and what "
        "is still unknown. State the most useful next read-only check if "
        "evidence is insufficient. Avoid long audit checklists.\n\n"
        f"Case ID: {p['case_id']}\n"
        f"Frozen packet SHA-256: {p['packet_sha256']}\n"
        f"Question: {p['question']}\n\n"
        "Available evidence (the entire fixed source packet):\n"
        f"{evidence}\n\n"
        "Write only the user-facing answer. "
        "The packet hash is an input identifier, not a source fact."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args(argv)
    print(render_comparison_prompt(args.case_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
