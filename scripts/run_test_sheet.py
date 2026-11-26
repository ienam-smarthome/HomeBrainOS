"""Run the HomeBrain-vs-Claude read-only test sheet against a live add-on in one command.

Posts each question to /api/ask in its own conversation, then writes one JSON bundle with the
full Technical JSON of every answer plus a one-line-per-question scoreboard on stdout.
Read-only: write questions (lights on/off, blocks) need the in-app approval card and are not run.

    python scripts/run_test_sheet.py --base-url http://homeassistant.local:8099 --out sheet.json
    python scripts/run_test_sheet.py --base-url ... --only 1 5 --bathroom-time 14:08
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

SHEET = (
    (1, "Which lights are on?"),
    (3, "What changed in the last hour?"),
    (4, "List the block devices"),
    (5, "Hub health and uptime"),
    (6, "Which batteries are low?"),
    (7, "Which devices have gone quiet?"),
)


def post_ask(base_url: str, question: str, timeout: float) -> dict[str, Any]:
    body = json.dumps({"request_id": str(uuid.uuid4()), "conversation_id": str(uuid.uuid4()),
                       "question": question}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/ask", data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "X-Homebrain-Request": "1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"success": False, "answer": f"HTTP {exc.code}", "error": exc.read().decode(
            "utf-8", errors="replace")[:300], "tool_calls": [], "model_round_metrics": []}


def scoreboard_row(number: int, question: str, result: dict[str, Any], wall_s: float) -> dict[str, Any]:
    metrics = result.get("model_round_metrics") or []
    calls = [c for c in result.get("tool_calls") or [] if isinstance(c, dict)]
    return {
        "q": number, "question": question, "ok": bool(result.get("success")),
        "wall_s": round(wall_s, 1), "rounds": result.get("rounds", len(metrics)),
        "native_calls": len(calls), "failed_calls": sum(1 for c in calls if c.get("success") is False),
        "peak_prompt_tokens": max((m.get("prompt_eval_count") or 0 for m in metrics), default=0),
        "answer_chars": len(str(result.get("answer") or "")),
        "answer_head": " ".join(str(result.get("answer") or "").split())[:110],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--out", default="test-sheet-bundle.json")
    parser.add_argument("--only", nargs="*", type=int, help="question numbers to run")
    parser.add_argument("--bathroom-time", help="HH:MM for the causal question (question 8)")
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args(argv)

    questions = list(SHEET)
    if args.bathroom_time:
        questions.append((8, f"Why did the bathroom lights come on at {args.bathroom_time}?"))
    if args.only:
        questions = [q for q in questions if q[0] in args.only]

    bundle, rows = [], []
    for number, question in questions:
        started = time.monotonic()
        result = post_ask(args.base_url, question, args.timeout)
        wall = time.monotonic() - started
        rows.append(scoreboard_row(number, question, result, wall))
        bundle.append({"q": number, "question": question, "wall_s": round(wall, 1), "response": result})
        print(json.dumps(rows[-1], ensure_ascii=False))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"sheet": "homebrain-vs-claude-read-only", "results": bundle}, handle,
                  ensure_ascii=False, indent=1)
    print(f"bundle written to {args.out}", file=sys.stderr)
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
