#!/usr/bin/env python3
"""Local-only Stage 3E trace audit. No network or file output.

Usage (on a trusted local machine only):
    python tools/stage3e_local_trace_report.py --input /private/replay.json --ack-local-sensitive-processing

The input contains {"cases": [...]} in the Stage 3D replay structure.
ONLY aggregate statistics are printed to stdout. This CLI does NOT prove
input provenance, collect live model calls, or make HomeBrain changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(_APP))

from stage3_trace_privacy_report import build_stage3e_private_trace_report  # noqa: E402

_MAX_INPUT_BYTES = 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True,
                        help="Path to locally held, sensitive Stage 3D replay JSON")
    parser.add_argument("--ack-local-sensitive-processing", action="store_true",
                        help="Confirm that this local process may read the sensitive input")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args(argv)
    if not args.ack_local_sensitive_processing:
        print("Refused: explicit local-sensitive-input acknowledgement required.",
              file=sys.stderr)
        return 2
    try:
        # Never log the path, JSON, exceptions, tokens or identifiers.
        with Path(args.input).open("rb") as handle:
            data = handle.read(_MAX_INPUT_BYTES + 1)
        if len(data) > _MAX_INPUT_BYTES:
            raise ValueError("oversized local input")
        parsed = json.loads(data)
        if not isinstance(parsed, dict) or set(parsed) != {"cases"}:
            raise ValueError("unexpected root structure")
        report = build_stage3e_private_trace_report(
            parsed["cases"], top_k=args.top_k)
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError,
            OverflowError, RecursionError, KeyError):
        print("Refused: invalid, unavailable or over-limit local trace input. "
              "No trace content has been printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
