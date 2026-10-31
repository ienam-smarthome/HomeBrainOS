#!/usr/bin/env python3
"""Local-only Stage 4D paired answer audit, NO model/MCP/network calls.

Usage on a trusted machine:
  python tools/stage4d_local_answer_compare.py \
    --input /private/paired-answers.json --ack-private-offline-input

The private input JSON root is {"cases": [...]} and each case follows
docs/INVESTIGATION-STAGE-4D-OFFLINE-ANSWER-COMPARISON.md. This tool
prints only fixed-key aggregate statistics; no raw source observations,
identifiers or answer prose are printed, uploaded or written to disk.
Do NOT put raw household records in a GitHub issue, PR or chat.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(_APP))
from stage4_offline_answer_comparison import (  # noqa: E402
    compare_stage4d_offline_answers,
)

_MAX_FILE_SIZE = 512 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True,
                        help="Locally held private paired-answer JSON file")
    parser.add_argument("--ack-private-offline-input", action="store_true",
                        help="Confirm sensitive source and answer text may be read locally")
    args = parser.parse_args(argv)
    if not args.ack_private_offline_input:
        print("Refused: local private-input acknowledgement required.",
              file=sys.stderr)
        return 2
    try:
        with Path(args.input).open("rb") as stream:
            raw = stream.read(_MAX_FILE_SIZE + 1)
        if len(raw) > _MAX_FILE_SIZE:
            raise ValueError("oversized input")
        source = json.loads(raw)
        if not isinstance(source, dict) or set(source) != {"cases"}:
            raise ValueError("invalid top level")
        report = compare_stage4d_offline_answers(source["cases"])
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        # Untrusted parse/model/source values or absolute paths are NEVER
        # included in stderr, even if an exception itself contains them.
        print("Refused: invalid, unavailable, or over-limit local input. "
              "No private source text was printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
