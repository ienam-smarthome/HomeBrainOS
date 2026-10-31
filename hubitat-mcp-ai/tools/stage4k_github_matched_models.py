#!/usr/bin/env python3
"""Stage 4K: matched 3B vs 7B real Ollama extraction plus a held-out corpus.

Both models use EXACT Stage 4J prompt, JSON schema, temperature, context,
source witness checker, reference labels and semantic scoring. The only
controlled input that varies is the model tag. A separate, pre-curated
synthetic holdout checks whether the result generalises past twelve
familiar Stage 4J sentences. No model-written live HomeBrain answers here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
from stage4_prose_atom_coverage import evaluate_stage4j_prose_claim_coverage  # noqa: E402
from stage4j_github_prose_coverage import (  # noqa: E402
    Stage4JLocalExtractor, _atom, _synthetic_prose_cases,
)

_MODELS = ("qwen2.5:3b", "qwen2.5:7b")
_CORPUS_NAMES = ("stage4j-baseline", "stage4k-holdout")


def _heldout_cases() -> list[dict]:
    """Eight novel, curated, constructed sentences (not model-generated).

    Reference atoms are never sent to a model. Every instance uses an
    existing synthetic Stage 4A packet; no private event or device data.
    """
    source = _synthetic_prose_cases()
    packet_by = {
        "light": source[0]["packet"],
        "heat": source[3]["packet"],
        "fan": source[5]["packet"],
        "history": source[7]["packet"],
    }
    light = packet_by["light"]["facts"][0]["fact_id"]
    heat = packet_by["heat"]["facts"][0]["fact_id"]
    fan = packet_by["fan"]["facts"][0]["fact_id"]
    observed = next(f["fact_id"] for f in packet_by["history"]["facts"]
                    if f["kind"] == "reported_state")
    gap = next(f["fact_id"] for f in packet_by["history"]["facts"]
               if f["kind"] == "coverage_limit")
    items = [
        ("light", "The source shows a lighting command, and the lamp certainly illuminated.",
         [_atom("recorded_event", [light]),
          _atom("physical_effect", [light])]),
        ("light", "A controller application was recorded as the command issuer.",
         [_atom("recorded_issuer", [light])]),
        ("heat", "The source contains a thermostat setpoint command, but no verified boiler response.",
         [_atom("recorded_event", [heat]),
          _atom("packet_limit", [], "physical_ack_unverified")]),
        ("heat", "A setpoint command was logged, proving that the radiators became hot.",
         [_atom("recorded_event", [heat]),
          _atom("physical_effect", [heat])]),
        ("fan", "The recorded OFF command proves that the extractor's motor stopped.",
         [_atom("recorded_event", [fan]),
          _atom("physical_effect", [fan])]),
        ("history", "The contact report was timestamped upon collection, despite incomplete history.",
         [_atom("recorded_clock", [observed]),
          _atom("packet_limit", [], "history_incomplete")]),
        ("history", "The journal reports a gap, so there were no additional contact events.",
         [_atom("recorded_gap", [gap]),
          _atom("absence_of_event", [gap])]),
        ("history", "A contact observation caused the archive to develop its recorded gap.",
         [_atom("upstream_cause", [observed, gap])]),
    ]
    cases = [
        {
            "sentence": sentence,
            "packet": packet_by[domain],
            "reference_atoms": ref_atoms,
        }
        for domain, sentence, ref_atoms in items
    ]
    assert len(cases) == 8
    return cases


def _aggregate(result: dict) -> dict:
    """No source text, case IDs, model replies or host fact content."""
    fields = (
        "case_count", "invocation_attempts", "responses_received",
        "invocation_errors", "valid_responses", "invalid_responses",
        "reference_atoms", "reference_high_risk_atoms",
        "extracted_atoms", "correctly_extracted_atoms", "missed_atoms",
        "extra_atoms", "missed_high_risk_atoms", "exact_extraction_cases",
        "extraction_recall", "extraction_precision",
        "host_proven_extracted_atoms", "host_unproven_extracted_atoms",
        "host_unproven_high_risk_atoms", "proof_errors",
    )
    return {k: result[k] for k in fields}


def evaluate_matched_models(*, invoke, baseline=None, holdout=None) -> dict:
    """Match BOTH model settings on both immutable constructed corpora."""
    source_cases = (
        _synthetic_prose_cases() if baseline is None else baseline,
        _heldout_cases() if holdout is None else holdout,
    )
    if len(source_cases[0]) != 12 or len(source_cases[1]) != 8:
        raise ValueError("Stage 4K requires exact fixed 12+8 corpus sizes")
    fingerprints = [
        json.dumps(cases, sort_keys=True, separators=(",", ":"))
        for cases in source_cases
    ]
    reports = {}
    for model in _MODELS:
        reports[model] = {}
        for name, cases in zip(_CORPUS_NAMES, source_cases):
            output = evaluate_stage4j_prose_claim_coverage(
                cases, model=model, invoke=invoke,
            )
            reports[model][name] = _aggregate(output)
    if [json.dumps(c, sort_keys=True, separators=(",", ":"))
            for c in source_cases] != fingerprints:
        raise ValueError("a model mutated or contaminated the benchmark source")
    # Positive delta means 7B found more correct atoms; negative risk
    # delta means 7B missed fewer unsupported high-risk implications.
    differences = {}
    for name in _CORPUS_NAMES:
        a, b = [reports[model][name] for model in _MODELS]
        differences[name] = {
            "delta_correctly_extracted_7b_minus_3b":
                b["correctly_extracted_atoms"] - a["correctly_extracted_atoms"],
            "delta_high_risk_misses_7b_minus_3b":
                b["missed_high_risk_atoms"] - a["missed_high_risk_atoms"],
            "delta_extra_atoms_7b_minus_3b":
                b["extra_atoms"] - a["extra_atoms"],
            "delta_valid_responses_7b_minus_3b":
                b["valid_responses"] - a["valid_responses"],
        }
    return {
        "schema": "homebrain-stage4k-matched-local-3b-7b.v1",
        "models": list(_MODELS),
        "matched_settings": True,
        "controlled_difference": "model_tag_only",
        "corpora": list(_CORPUS_NAMES),
        "model_results": reports,
        "model_differences": differences,
        "comparison_of_created_answers": False,
        "independent_human_adjudication_of_generated_answers": False,
        "reference_labels_are_curated_synthetic": True,
        "benchmark_accuracy_not_production_accuracy": True,
        "publisher_approval": False,
        "homeassistant_or_hubitat_connected": False,
    }


def summary_markdown(output: dict) -> str:
    lines = ["## Stage 4K — Actual matched Qwen2.5 3B vs 7B extraction",
             "", "| Corpus / metric | Qwen 3B | Qwen 7B |",
             "| --- | ---: | ---: |"]
    for corpus in _CORPUS_NAMES:
        for field in (
            "case_count", "valid_responses", "correctly_extracted_atoms",
            "reference_atoms", "missed_high_risk_atoms",
            "reference_high_risk_atoms", "extra_atoms",
            "extraction_precision", "extraction_recall",
        ):
            a = output["model_results"][_MODELS[0]][corpus][field]
            b = output["model_results"][_MODELS[1]][corpus][field]
            lines.append(f"| {corpus} / {field} | {a} | {b} |")
    lines.extend([
        "", "Both models received identical synthetic evidence, prompt, "
        "JSON schema and generation settings. No real household data.",
        "The held-out eight sentences have separately authored, unverified "
        "synthetic labels. **These measurements do not certify unseen "
        "model-authored prose or permit production publication.**",
    ])
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ack-github-synthetic-local-inference", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=180)
    args = p.parse_args(argv)
    if not args.ack_github_synthetic_local_inference:
        print("Refused: explicit synthetic-only consent required.", file=sys.stderr)
        return 2
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("OLLAMA_NO_CLOUD") != "1"
            or os.environ.get("OLLAMA_HOST") != "127.0.0.1:11434"):
        print("Refused: local no-cloud GitHub inference only.", file=sys.stderr)
        return 2
    try:
        client = Stage4JLocalExtractor(timeout_seconds=args.timeout_seconds)
        data = evaluate_matched_models(invoke=client)
        output = json.dumps(data, separators=(",", ":"), sort_keys=True)
        print(output)
        dest = os.environ.get("GITHUB_STEP_SUMMARY")
        if dest:
            with Path(dest).open("a", encoding="utf-8") as fp:
                fp.write(summary_markdown(data))
        stats = [data["model_results"][model][corpus]
                 for model in _MODELS for corpus in _CORPUS_NAMES]
        if (client.attempted != 40
                or any(r["invocation_attempts"] != r["case_count"]
                       or r["valid_responses"] == 0 for r in stats)):
            print("INCONCLUSIVE: model requests missing or no valid review "
                  "in one comparison arm.", file=sys.stderr)
            return 3
        return 0
    except Exception as error:
        # Safe diagnostics: exception class and last internal code line ONLY.
        # Never emit the exception message, path, source facts or model text.
        current = error.__traceback__
        line = 0
        while current is not None:
            if current.tb_frame.f_code.co_filename.endswith(
                    ("stage4k_github_matched_models.py",
                     "stage4j_github_prose_coverage.py",
                     "stage4_prose_atom_coverage.py")):
                line = current.tb_lineno
            current = current.tb_next
        print("Offline matched comparison failed; sanitized diagnostic "
              f"type={type(error).__name__} code_line={line}; raw data withheld.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
