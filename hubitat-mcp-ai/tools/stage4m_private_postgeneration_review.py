#!/usr/bin/env python3
"""Stage 4M: privately annotate frozen Stage 4L prose, then source-proof labels.

No model inference, HTTP, HomeBrain runtime imports, automatic annotations,
evidence retrieval, or raw prose in stdout. This can only measure claims
actually labelled by a reviewer, never prove exhaustive understanding.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage4k_frozen_answer_audit import freeze_stage4k_answer  # noqa: E402
from stage4_narrative_contract import build_stage4_evidence_packet  # noqa: E402
from stage4_atomic_proof_obligations import (  # noqa: E402
    _host_packet, evaluate_stage4i_proof_obligations,
)
from stage4_prose_atom_coverage import _atom, _proof_claim, _UNSUPPORTED  # noqa: E402

MAX_FILE = 512 * 1024
MAX_CASES = 4


def _load_private(path: str) -> dict:
    source = Path(path)
    if not source.is_absolute() or source.is_symlink() or not source.is_file():
        raise ValueError("private input must be an existing absolute regular file")
    with source.open("rb") as f:
        raw = f.read(MAX_FILE + 1)
    if not raw or len(raw) > MAX_FILE:
        raise ValueError("private input size invalid")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError("invalid private JSON")
    return doc


def _write_private(path: str, doc: dict) -> None:
    dest = Path(path)
    if not dest.is_absolute() or dest.is_symlink():
        raise ValueError("new absolute private path required")
    payload = json.dumps(doc, sort_keys=True, ensure_ascii=True).encode()
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def _bound_cases(bundle: dict) -> list[dict]:
    if (set(bundle) != {"schema", "cases"}
            or bundle["schema"] != "homebrain-stage4l-private-bundle.v1"
            or not isinstance(bundle["cases"], list)
            or not 1 <= len(bundle["cases"]) <= MAX_CASES):
        raise ValueError("invalid private frozen bundle")
    seen = set()
    for case in bundle["cases"]:
        if (not isinstance(case, dict)
                or set(case) != {"domain", "receipts", "draft", "frozen"}
                or case["domain"] not in ("lighting", "heating", "ventilation", "history")
                or case["domain"] in seen):
            raise ValueError("unknown or duplicated domain")
        seen.add(case["domain"])
        expected = freeze_stage4k_answer(case["receipts"], case["draft"])
        if expected != case["frozen"]:
            raise ValueError("frozen answer and source mismatch")
    return bundle["cases"]


def make_review_template(bundle: dict) -> dict:
    result = []
    for case in _bound_cases(bundle):
        frozen = case["frozen"]
        result.append({
            "domain": case["domain"],
            "draft_sha256": frozen["draft_sha256"],
            "packet_sha256": frozen["packet_sha256"],
            "sentences": [{
                "sentence_sha256": digest,
                "reference_atoms": [],
                "clarity_score": None,
                "usefulness_score": None,
            } for digest in frozen["sentence_sha256"]],
        })
    return {"schema": "homebrain-stage4m-review.v1", "cases": result}


def assess_independently_labelled_bundle(bundle: dict, review: dict) -> dict:
    """Labels must be created by a separate reviewer after prose is frozen.

    This procedure checks referential consistency, not reviewer independence.
    No missing claims can be inferred from review labels.
    """
    cases = _bound_cases(bundle)
    if (not isinstance(review, dict) or set(review) != {"schema", "cases"}
            or review["schema"] != "homebrain-stage4m-review.v1"
            or not isinstance(review["cases"], list)
            or len(review["cases"]) != len(cases)):
        raise ValueError("review coverage invalid")
    counts = Counter()
    for case, entry in zip(cases, review["cases"]):
        frozen = case["frozen"]
        if (not isinstance(entry, dict)
                or set(entry) != {"domain", "draft_sha256", "packet_sha256", "sentences"}
                or entry["domain"] != case["domain"]
                or entry["draft_sha256"] != frozen["draft_sha256"]
                or entry["packet_sha256"] != frozen["packet_sha256"]
                or not isinstance(entry["sentences"], list)
                or len(entry["sentences"]) != frozen["sentence_count"]):
            raise ValueError("review packet binding failed")
        packet = build_stage4_evidence_packet(case["receipts"])
        facts = _host_packet(packet)
        for index, annotation in enumerate(entry["sentences"]):
            if (not isinstance(annotation, dict)
                    or set(annotation) != {
                        "sentence_sha256", "reference_atoms",
                        "clarity_score", "usefulness_score"}
                    or annotation["sentence_sha256"] != frozen["sentence_sha256"][index]
                    or not isinstance(annotation["reference_atoms"], list)
                    or not 1 <= len(annotation["reference_atoms"]) <= 5
                    or any(type(annotation[score]) is not int
                           or not 1 <= annotation[score] <= 5
                           for score in ("clarity_score", "usefulness_score"))):
                raise ValueError("missing or incomplete sentence review")
            atoms = [_atom(atom, facts) for atom in annotation["reference_atoms"]]
            if len(atoms) != len(set(atoms)):
                raise ValueError("duplicate reviewed atomic proposition")
            counts["sentences"] += 1
            counts["clarity_total"] += annotation["clarity_score"]
            counts["usefulness_total"] += annotation["usefulness_score"]
            for atom in atoms:
                proof = evaluate_stage4i_proof_obligations(
                    packet, {"schema": "homebrain-stage4i-proof-bundle.v1",
                             "claims": [_proof_claim(atom, facts)]})
                counts["labelled_atoms"] += 1
                counts["host_proven"] += proof["host_proven_atomic_claims"]
                counts["host_unproven"] += proof["unproven_atomic_claims"]
                if atom[0] in _UNSUPPORTED:
                    counts["high_risk_labelled"] += 1
                    counts["high_risk_unproven"] += proof["unproven_atomic_claims"]
    return {
        "schema": "homebrain-stage4m-private-annotation-audit.v1",
        "constructed_cases": len(cases),
        "reviewed_sentences": counts["sentences"],
        "reviewed_atomic_claims": counts["labelled_atoms"],
        "host_proven_labelled_claims": counts["host_proven"],
        "host_unproven_labelled_claims": counts["host_unproven"],
        "high_risk_labelled_claims": counts["high_risk_labelled"],
        "high_risk_unproven_claims": counts["high_risk_unproven"],
        "mean_reviewer_clarity_score": round(counts["clarity_total"] / counts["sentences"], 2),
        "mean_reviewer_usefulness_score": round(counts["usefulness_total"] / counts["sentences"], 2),
        "post_generation_reviewer_independence_authenticated": False,
        "source_truth_authenticated": False,
        "unlabelled_prose_implications_excluded": True,
        "semantic_exhaustiveness_proven": False,
        "publisher_approval": False,
        "live_device_actions": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline private Stage 4M review")
    p.add_argument("--bundle", required=True, help="absolute private Stage 4L JSON")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", help="write new absolute private review template")
    mode.add_argument("--review", help="absolute completed private annotation JSON")
    args = p.parse_args(argv)
    try:
        bundle = _load_private(args.bundle)
        if args.template:
            _write_private(args.template, make_review_template(bundle))
            print('{"template_created":true,"cloud_calls":0}')
        else:
            review = _load_private(args.review)
            print(json.dumps(assess_independently_labelled_bundle(bundle, review),
                             sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError):
        p.exit(1, "Private review invalid or incomplete; no model or device calls made.\n")


if __name__ == "__main__":
    raise SystemExit(main())
