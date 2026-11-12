"""Private offline paired review-pass experiment ledger. No model/Hubitat/network calls.

This tool does NOT run A/B arms or adjudicate correctness. The operator supplies
blind human ratings after independently replaying the same frozen evidence.
Never commit a populated manifest or private evidence to GitHub.

Usage: python hubitat-mcp-ai-v2/evaluation/review_pass_pairs.py private/manifest.json
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "homebrain-v2-review-pass-pairs.v1"
CRITERIA = ("factual_grounding", "source_completeness",
            "causal_calibration", "usefulness")
MODES = frozenset(("single_answer", "source_review_only", "final_audit_only",
                   "source_review_and_audit"))
MAX_CASES = 64
MAX_BYTES = 8 * 1024 * 1024

class ReviewError(ValueError):
    pass

def _fingerprint(root, filename):
    if not isinstance(filename, str) or not filename:
        raise ReviewError("Missing private capture")
    relative = Path(filename)
    if relative.is_absolute():
        raise ReviewError("Capture paths must be relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ReviewError("Capture escapes private directory")
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ReviewError("Missing, empty or oversized capture")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _score(raw):
    if not isinstance(raw, dict) or set(raw) != set(CRITERIA):
        raise ReviewError("Four explicit human scores required")
    if any(type(v) is not int or v not in (0, 1, 2)
           for k, v in raw.items() if not (k == "causal_calibration" and v is None)):
        raise ReviewError("Scores must be 0, 1, 2 or causal N/A")
    applicable = [v for v in raw.values() if v is not None]
    return sum(applicable), 2 * len(applicable)

def validate(manifest, root):
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ReviewError("Invalid experiment schema")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ReviewError("Expected 1-64 paired cases")
    results, ids = [], set()
    for case in cases:
        if not isinstance(case, dict):
            raise ReviewError("Invalid case")
        ident = case.get("id")
        if not isinstance(ident, str) or not ident.isascii() or not ident.replace("-", "").isalnum() or ident in ids:
            raise ReviewError("Case needs unique opaque ASCII identifier")
        ids.add(ident)
        if case.get("read_only") is not True:
            raise ReviewError("Only read-only cases are permitted")
        model = case.get("model")
        if not isinstance(model, str) or not model.strip() or len(model) > 120:
            raise ReviewError("Model must be recorded")
        # Both arms MUST have identical frozen evidence, not two live queries.
        evidence_hash = _fingerprint(root, case.get("frozen_evidence_file"))
        arms = case.get("arms")
        if not isinstance(arms, list) or len(arms) != 2:
            raise ReviewError("Exactly two blinded arms required")
        labels, parsed = set(), []
        for arm in arms:
            if not isinstance(arm, dict) or arm.get("label") not in ("A", "B"):
                raise ReviewError("Use blinded A/B labels")
            if arm["label"] in labels:
                raise ReviewError("Duplicate arm label")
            labels.add(arm["label"])
            mode = arm.get("mode")
            if mode not in MODES:
                raise ReviewError("Unknown review mode")
            if arm.get("evidence_sha256") != evidence_hash:
                raise ReviewError("Both arms must reference exact frozen evidence hash")
            elapsed = arm.get("elapsed_ms")
            rounds = arm.get("model_rounds")
            if type(elapsed) not in (int, float) or elapsed < 0:
                raise ReviewError("Nonnegative elapsed_ms required")
            if type(rounds) is not int or rounds < 1:
                raise ReviewError("Positive model rounds required")
            score = _score(arm.get("scores"))
            file_hash = _fingerprint(root, arm.get("answer_file"))
            if arm.get("unexpected_write") is not False:
                raise ReviewError("Unexpected writes must be absent for evaluated read-only trial")
            parsed.append({"label": arm["label"], "mode": mode, "score": score,
                           "elapsed_ms": elapsed, "model_rounds": rounds,
                           "answer_sha256": file_hash})
        if parsed[0]["mode"] == parsed[1]["mode"]:
            raise ReviewError("The paired conditions must differ")
        if parsed[0]["score"][1] != parsed[1]["score"][1]:
            raise ReviewError("Both arms must use the same applicable criteria")
        results.append({"id": ident, "model": model, "evidence_sha256": evidence_hash,
                        "arms": parsed,
                        "delta_B_minus_A": parsed[1]["score"][0] - parsed[0]["score"][0],
                        "latency_B_minus_A_ms": parsed[1]["elapsed_ms"] - parsed[0]["elapsed_ms"]})
    return {"schema": SCHEMA, "count": len(results),
            "fully_blinded_review_required": True, "cases": results,
            "note": "Human ratings only; experimental condition labels must remain hidden from reviewers. Identical hashes do not establish evidence sufficiency, correctness or randomization. Outputs contain no source text or device identities."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        path = args.manifest.resolve()
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ReviewError("Invalid manifest")
        report = validate(json.loads(path.read_text(encoding="utf-8")), path.parent)
    except (ReviewError, OSError, ValueError, TypeError):
        parser.exit(2, "Private review manifest rejected (no contents printed).\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
