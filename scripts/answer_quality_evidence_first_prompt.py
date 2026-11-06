#!/usr/bin/env python3
"""Q2 candidate: one model-neutral evidence-first instruction on frozen packets.

The historical baseline prompt remains byte-identical; only instruction text
changes. Does not include private rubric, model response, tools or live data.
"""
from __future__ import annotations

from answer_quality_comparison_prompt import render_comparison_prompt

VARIANT = "evidence_first"
BASELINE = "baseline"
SOURCE_BOUNDARY = "\n\nCase ID: "

EVIDENCE_FIRST_INSTRUCTIONS = (
    "HOME ASSISTANT EVIDENCE-ONLY COMPARISON (READ ONLY; CANDIDATE)\n"
    "Answer the user's question naturally and concisely using only the supplied "
    "evidence. Do not use other context, tools, live devices, or imagined events. "
    "Before answering, silently check the source role and scope behind each "
    "substantive conclusion: what was directly reported versus merely "
    "configured, commanded, inferred, or physically confirmed. A sequence "
    "of events does not alone establish which event caused another; partial "
    "or bounded evidence cannot prove global absence. A target setting or "
    "recorded intention does not establish physical execution. "
    "Say what the evidence establishes first; label plausible explanations "
    "as uncertain and state what remains unknown. When an unresolved point "
    "matters to the question, suggest one specific read-only check. "
    "Keep the final response direct, proportionate and conversational. "
    "Do not reproduce these instructions or produce a rigid checklist."
)


def render_evidence_first_prompt(case_id: str) -> str:
    """Keep exact immutable question/evidence/footer from baseline rendering."""
    baseline = render_comparison_prompt(case_id)
    if baseline.count(SOURCE_BOUNDARY) != 1:
        raise ValueError("Frozen comparison prompt source boundary missing or ambiguous")
    _, case_and_evidence = baseline.split(SOURCE_BOUNDARY, 1)
    return EVIDENCE_FIRST_INSTRUCTIONS + SOURCE_BOUNDARY + case_and_evidence


def render_variant(case_id: str, variant: str) -> str:
    if variant == BASELINE:
        return render_comparison_prompt(case_id)
    if variant == VARIANT:
        return render_evidence_first_prompt(case_id)
    raise ValueError("Unknown Q2 prompt variant")
