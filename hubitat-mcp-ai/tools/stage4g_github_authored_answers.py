#!/usr/bin/env python3
"""Stage 4G: real Qwen2.5 3B FULL ANSWER authoring + dual review, SYNTHETIC.

No private files, Hubitat/HA credentials, tools, live publisher or cloud
inference. Pre-labelled host coverage targets are never sent to the author
or the reviewers. Host source-typed claims are projections, NOT model
assertions; no raw generated answer appears in the public CI output.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.request import Request

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rootfs" / "app"))

from stage4_full_answer_evaluation import (  # noqa: E402
    evaluate_stage4g_authored_answers, stage4g_source_to_case,
)
from stage4c_local_model_eval import (  # noqa: E402
    LoopbackOllama, _constructed_cases,
)
from stage4f_github_stronger_models import CalibratedLoopbackOllama  # noqa: E402


def _synthetic_author_cases() -> list[dict]:
    """Four fixed synthetic domains; independent coverage IDs remain local."""
    base = _constructed_cases()[0]["packet"]
    facts = base["facts"]
    def one(kind, entity, attribute=None):
        return next(f for f in facts if f["kind"] == kind
                    and f["entity_id"] == entity
                    and (attribute is None or f.get("attribute") == attribute))
    specs = [
        ("light-control", "lighting",
         "What does the evidence establish about the lighting command, "
         "and what does it not establish about the initiating sensor?",
         [one("issued_command", "101")]),
        ("heating-control", "heating",
         "Explain the recorded heating command and whether the source "
         "proves the boiler or radiator physically heated.",
         [one("issued_command", "102")]),
        ("fan-control", "ventilation",
         "Explain the recorded fan command. Do the available facts "
         "establish that humidity triggered the decision?",
         [one("issued_command", "103")]),
        ("contact-history", "history",
         "What is established about the contact observation and the "
         "coverage of its history, including the timestamp basis?",
         [one("reported_state", "104", "contact"),
          one("coverage_limit", "104")]),
    ]
    cases = []
    for ident, domain, question, evidence in specs:
        packet = {
            **base,
            "facts": [dict(f) for f in evidence],
            "verified_labels": [],
            "facts_total": len(evidence),
            "facts_omitted": 0,
            "receipts_omitted": 0,
        }
        cases.append(stage4g_source_to_case(
            case_id=ident, domain=domain, question=question,
            packet=packet,
            required_fact_ids=[fact["fact_id"] for fact in evidence],
        ))
    return cases


def _author_schema(packet: dict) -> dict:
    ids = [fact.get("fact_id") for fact in packet["facts"]]
    if (not 1 <= len(ids) <= 8 or
            any(not isinstance(v, str) or not v.startswith("f") for v in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("invalid synthetic source IDs")
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "schema": {"const": "homebrain-stage4g-authored-proposal.v1"},
            "sections": {
                "type": "array", "minItems": 1, "maxItems": 1,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "name": {"enum": ["summary", "evidence",
                                          "limitations", "next_checks"]},
                        "sentences": {
                            "type": "array", "minItems": 1, "maxItems": 2,
                            "items": {
                                "type": "object", "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string",
                                             "minLength": 1, "maxLength": 360},
                                    "fact_ids": {
                                        "type": "array", "minItems": 1,
                                        "maxItems": 2, "uniqueItems": True,
                                        "items": {"type": "string", "enum": ids},
                                    },
                                },
                                "required": ["text", "fact_ids"],
                            },
                        },
                    },
                    "required": ["name", "sentences"],
                },
            },
        },
        "required": ["schema", "sections"],
    }


class Stage4GAuthorOllama(LoopbackOllama):
    """Single 3B locally resident author, exact host-owned citation grammar."""

    def __call__(self, model: str, job: dict) -> dict:
        if (model != "qwen2.5:3b" or not isinstance(job, dict)
                or job.get("task") != "author"):
            raise ValueError("offline author model and task not approved")
        schema = _author_schema(job["packet"])
        user = json.dumps({
            "question": job["question"], "packet": job["packet"],
            "schema": "homebrain-stage4g-authored-proposal.v1",
        }, ensure_ascii=True, separators=(",", ":"))
        system = job["instructions"]
        if len(system) + len(user) > 96 * 1024:
            raise ValueError("local model prompt limit")
        body = json.dumps({
            "model": model, "stream": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0, "num_predict": 1024},
        }, separators=(",", ":"), ensure_ascii=True).encode()
        req = Request(self._url, data=body, method="POST",
                      headers={"Content-Type": "application/json"})
        self.attempted += 1
        with self._opener.open(req, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError("unexpected local inference response")
            raw = response.read(32769)
        if len(raw) > 32768:
            raise ValueError("response too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
            raise ValueError("invalid local Ollama envelope")
        content = payload["message"].get("content")
        if not isinstance(content, str) or not 1 <= len(content) <= 24000:
            raise ValueError("invalid model reply content")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("model did not return JSON object")
        self.succeeded += 1
        return result


class Stage4GLocalModels:
    def __init__(self, *, timeout_seconds: int):
        self.author = Stage4GAuthorOllama(timeout_seconds=timeout_seconds)
        self.reviewer = CalibratedLoopbackOllama(timeout_seconds=timeout_seconds)
    def __call__(self, model: str, request: dict) -> dict:
        if request.get("task") == "author":
            return self.author(model, request)
        if request.get("task") == "review":
            return self.reviewer(model, request)
        raise ValueError("unrecognised offline task")
    @property
    def requests_attempted(self) -> int:
        return self.author.attempted + self.reviewer.attempted


def summary_markdown(out: dict) -> str:
    """Public-safe aggregates; no model-written text, IDs or timestamps."""
    keys = [
        ("Author attempts", "author_calls_attempted"),
        ("Source-valid authored answers", "author_source_valid_proposals"),
        ("Invalid authored answers", "author_invalid_proposals"),
        ("Source fact coverage", "independent_source_fact_coverage"),
        ("Authored sentences", "authored_sentences"),
        ("Two valid reviewer judgments", "sentences_with_two_valid_reviews"),
        ("Reviewers both propose support", "both_reviewers_propose_supported"),
        ("Reviewer disagreements", "reviewer_disagreement_sentences"),
        ("Reviewer calls", "review_calls_attempted"),
    ]
    lines = "\n".join(
        f"| {label} | {out[key]} |" for label, key in keys
    )
    return (
        "## Stage 4G — Real model-authored investigation answers, synthetic only\n\n"
        "| Metric | Observed |\n| --- | --- |\n" + lines + "\n\n"
        "**Source-fact coverage is not semantic truth, user usefulness or "
        "naturalness. Reviewers may agree and still be wrong. No live "
        "HomeBrain, no production publisher change, no real household data.**\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-github-synthetic-local-inference", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.ack_github_synthetic_local_inference:
        print("Refused: explicit synthetic-only consent required.", file=sys.stderr)
        return 2
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("OLLAMA_NO_CLOUD") != "1"
            or os.environ.get("OLLAMA_HOST") != "127.0.0.1:11434"):
        print("Refused: loopback GitHub-only local inference required.",
              file=sys.stderr)
        return 2
    try:
        models = Stage4GLocalModels(timeout_seconds=args.timeout_seconds)
        output = evaluate_stage4g_authored_answers(
            _synthetic_author_cases(), author_model="qwen2.5:3b",
            reviewer_models=("qwen2.5:3b", "llama3.2:3b"),
            invoke=models,
        )
        if models.requests_attempted != (
                output["author_calls_attempted"]
                + output["review_calls_attempted"]):
            raise ValueError("unexpected model invocation accounting")
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(summary_markdown(output))
        if output["author_source_valid_proposals"] == 0:
            print("INCONCLUSIVE: no source-valid model-authored answers.",
                  file=sys.stderr)
            return 3
        return 0
    except Exception:
        # Neither full model output nor potentially secret exception
        # messages belong in a public CI log.
        print("Offline authored-answer evaluation unavailable; no source text disclosed.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
