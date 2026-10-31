#!/usr/bin/env python3
"""Stage 4J: real Qwen2.5 3B semantic claim extraction on synthetic prose.

A fixed, pre-annotated constructed corpus holds expected atomic meanings
OUTSIDE all model prompts. JSON format limits response shape but does not
supply required claim count, category choices or answer key. Source
proofing of extracted atoms is independent of the model verdict.
No household data, network beyond local Ollama, or publication.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
from stage4_prose_atom_coverage import evaluate_stage4j_prose_claim_coverage  # noqa: E402
from stage4c_local_model_eval import LoopbackOllama  # noqa: E402
from stage4g_github_authored_answers import _synthetic_author_cases  # noqa: E402

_MODEL = "qwen2.5:3b"
_PROPS = (
    "recorded_event", "recorded_issuer", "recorded_clock", "recorded_gap",
    "packet_limit", "upstream_cause", "physical_effect", "absence_of_event",
    "complete_history",
)
_LIMITS = (
    "physical_ack_unverified", "root_cause_unverified",
    "history_incomplete", "absence_not_authorised",
)
_SYSTEM = (
    "Extract EVERY independently asserted factual proposition from the "
    "given sentence, including any implied physical effect, causal "
    "relationship, absence, or completeness claim. The evidence packet "
    "contains source records, NOT permission to disregard a proposition "
    "that the sentence states without evidence. Classify what the "
    "SENTENCE CLAIMS, not whether it is true. Use recorded_event for "
    "a claimed source observation or issued command, recorded_issuer "
    "for a claimed immediate controller issuer, recorded_clock for "
    "a claimed clock basis and timestamp, recorded_gap for an archived "
    "coverage gap, packet_limit for an explicit lack-of-proof caveat, "
    "upstream_cause for a claimed causal link between two cited facts, "
    "physical_effect for claimed physical operation, absence_of_event "
    "for an assertion that nothing occurred, and complete_history for "
    "claimed comprehensive coverage. Include multiple atoms when one "
    "sentence combines assertions. Only cite host fact IDs supplied in "
    "the packet; for packet_limit use no IDs and a named limit. "
    "Do not invent fact IDs or source statements. Return JSON only "
    "using homebrain-stage4j-atom-extraction.v1. Never infer a semantic "
    "claim solely because it might be true. This task is extraction, "
    "NOT a model-backed publication or semantic truth certification."
)


def _atom(prop: str, fids: list[str], limit=None) -> dict:
    return {"proposition": prop, "fact_ids": list(fids), "limit": limit}


def _synthetic_prose_cases() -> list[dict]:
    """Twelve curated constructed sentences, independent atomic labels."""
    sources = {c["domain"]: c["packet"] for c in _synthetic_author_cases()}
    l = sources["lighting"]["facts"][0]["fact_id"]
    h = sources["heating"]["facts"][0]["fact_id"]
    v = sources["ventilation"]["facts"][0]["fact_id"]
    hp = sources["history"]
    observed = next(f["fact_id"] for f in hp["facts"]
                    if f["kind"] == "reported_state")
    gap = next(f["fact_id"] for f in hp["facts"]
               if f["kind"] == "coverage_limit")
    rows = [
        ("lighting", "The source records a brightness command.",
         [_atom("recorded_event", [l])]),
        ("lighting", "The controlling application is recorded as the command issuer.",
         [_atom("recorded_issuer", [l])]),
        ("lighting", "That brightness command physically turned the light on.",
         [_atom("physical_effect", [l])]),
        ("heating", "A heating setpoint command was recorded, and the boiler fired.",
         [_atom("recorded_event", [h]), _atom("physical_effect", [h])]),
        ("heating", "The source records a heating setpoint command.",
         [_atom("recorded_event", [h])]),
        ("ventilation", "The fan OFF command means the fan motor stopped.",
         [_atom("recorded_event", [v]), _atom("physical_effect", [v])]),
        ("ventilation", "The evidence does not establish a physical fan-motor response.",
         [_atom("packet_limit", [], "physical_ack_unverified")]),
        ("history", "The contact reading uses the collector reception timestamp.",
         [_atom("recorded_clock", [observed])]),
        ("history", "The archive explicitly reports a coverage gap.",
         [_atom("recorded_gap", [gap])]),
        ("history", "The history is complete and covers every event.",
         [_atom("complete_history", [gap])]),
        ("history", "The history has a gap, so no other events occurred.",
         [_atom("recorded_gap", [gap]), _atom("absence_of_event", [gap])]),
        ("history", "The contact opening caused the later archive coverage gap.",
         [_atom("upstream_cause", [observed, gap])]),
    ]
    return [
        {"sentence": sentence, "packet": sources[domain],
         "reference_atoms": atoms}
        for domain, sentence, atoms in rows
    ]


def _json_schema(packet: dict) -> dict:
    """Constrain ATOMIC SHAPES, never choose which assertions are true.

    Ollama's JSON-schema output avoids malformed role/ref cardinalities
    observed in the first actual 3B run. Each branch permits both proven
    and unproven semantic roles. The model still decides the roles.
    """
    facts = packet["facts"]
    ids = [f["fact_id"] for f in facts]
    if not 1 <= len(ids) <= 8 or len(ids) != len(set(ids)):
        raise ValueError("unbounded synthetic IDs")
    events = [f["fact_id"] for f in facts
              if f["kind"] in ("issued_command", "reported_state", "input_report")]
    gaps = [f["fact_id"] for f in facts if f["kind"] == "coverage_limit"]
    issuer = [f["fact_id"] for f in facts
              if f["kind"] in ("issued_command", "reported_state", "input_report")
              and isinstance(f.get("issuer_app_id"), str)
              and bool(f["issuer_app_id"])]
    branches = []

    def add(prop: str, count: int, eligible: list[str], *,
            limits: bool = False) -> None:
        if count and len(eligible) < count:
            return
        branches.append({
            "type": "object", "additionalProperties": False,
            "properties": {
                "proposition": {"const": prop},
                "fact_ids": {
                    "type": "array", "minItems": count, "maxItems": count,
                    "uniqueItems": True,
                    "items": {"type": "string", "enum": eligible or ids},
                },
                "limit": (
                    {"type": "string", "enum": list(_LIMITS)} if limits
                    else {"type": "null"}
                ),
            },
            "required": ["proposition", "fact_ids", "limit"],
        })

    add("recorded_event", 1, events)
    add("recorded_issuer", 1, issuer)
    add("recorded_clock", 1, events)
    add("recorded_gap", 1, gaps)
    add("packet_limit", 0, ids, limits=True)
    add("upstream_cause", 2, ids)
    add("physical_effect", 1, events)
    add("absence_of_event", 1, ids)
    add("complete_history", 1, ids)
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "schema": {"const": "homebrain-stage4j-atom-extraction.v1"},
            "atoms": {
                "type": "array", "minItems": 0, "maxItems": 5,
                "uniqueItems": True,
                "items": {"anyOf": branches},
            },
        },
        "required": ["schema", "atoms"],
    }


class Stage4JLocalExtractor(LoopbackOllama):
    def __call__(self, model: str, request: dict) -> dict:
        if model != _MODEL or request.get("task") != "extract":
            raise ValueError("unapproved synthetic extractor")
        case_packet = request["packet"]
        prompt = json.dumps({
            "sentence": request["sentence"], "packet": case_packet,
            "required_schema": "homebrain-stage4j-atom-extraction.v1",
        }, separators=(",", ":"), ensure_ascii=True)
        if len(prompt) + len(_SYSTEM) > 96 * 1024:
            raise ValueError("local prompt too long")
        data = json.dumps({
            "model": model, "stream": False,
            "format": _json_schema(case_packet),
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0, "num_predict": 768},
        }, separators=(",", ":"), ensure_ascii=True).encode()
        call = Request(self._url, data=data, method="POST",
                       headers={"Content-Type": "application/json"})
        self.attempted += 1
        with self._opener.open(call, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError("local model response status invalid")
            body = response.read(32769)
        if len(body) > 32768:
            raise ValueError("model reply too long")
        outer = json.loads(body)
        if not isinstance(outer, dict) or not isinstance(outer.get("message"), dict):
            raise ValueError("invalid local model envelope")
        text = outer["message"].get("content")
        if not isinstance(text, str) or not 1 <= len(text) <= 24000:
            raise ValueError("invalid local response text")
        inner = json.loads(text)
        if not isinstance(inner, dict):
            raise ValueError("JSON object required")
        self.succeeded += 1
        return inner


def summary_markdown(output: dict) -> str:
    labels = [
        ("Synthetic sentences", "case_count"),
        ("Valid extractor responses", "valid_responses"),
        ("Total independently labelled atoms", "reference_atoms"),
        ("Reference high-risk implications", "reference_high_risk_atoms"),
        ("Missed high-risk implications", "missed_high_risk_atoms"),
        ("Correctly extracted atoms", "correctly_extracted_atoms"),
        ("Missed atoms", "missed_atoms"),
        ("Extra atoms", "extra_atoms"),
        ("Exact extraction cases", "exact_extraction_cases"),
        ("Extraction recall", "extraction_recall"),
        ("Extraction precision", "extraction_precision"),
        ("Host-unproven extracted atoms", "host_unproven_extracted_atoms"),
        ("Model invocation errors", "invocation_errors"),
    ]
    table = "\n".join(f"| {label} | {output[key]} |" for label, key in labels)
    return (
        "## Stage 4J — Real source-scoped prose implication extraction\n\n"
        "| Synthetic evaluation measure | Value |\n| --- | --- |\n"
        + table
        + "\n\nThese are host-curated, **constructed** sentences, "
        "not newly generated Stage 4G answers. Missed implications are "
        "unsafe for automated publication. Zero errors on this small "
        "corpus would not prove completeness on unseen prose. "
        "**The production publisher remains disabled for this path.**\n"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ack-github-synthetic-local-inference", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=120)
    args = p.parse_args(argv)
    if not args.ack_github_synthetic_local_inference:
        print("Refused: explicit synthetic-only model consent required.",
              file=sys.stderr)
        return 2
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("OLLAMA_NO_CLOUD") != "1"
            or os.environ.get("OLLAMA_HOST") != "127.0.0.1:11434"):
        print("Refused: isolated no-cloud GitHub loopback required.",
              file=sys.stderr)
        return 2
    try:
        client = Stage4JLocalExtractor(timeout_seconds=args.timeout_seconds)
        result = evaluate_stage4j_prose_claim_coverage(
            _synthetic_prose_cases(), model=_MODEL, invoke=client,
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(summary_markdown(result))
        if (client.attempted != result["invocation_attempts"]
                or result["valid_responses"] == 0):
            print("INCONCLUSIVE: model coverage could not be measured.",
                  file=sys.stderr)
            return 3
        return 0
    except Exception:
        print("Offline semantic extraction unavailable; sensitive details omitted.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
