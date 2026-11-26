"""Run the HomeBrain-vs-Claude test sheet against a live add-on in one command.

Posts each question to /api/ask in its own conversation, then writes one JSON bundle with the
full Technical JSON of every answer plus a one-line-per-question scoreboard on stdout.

Nothing is sent to a device: every request asks the add-on to turn auto-approval off, and the
runner declines every approval card it sees (recording the proposed command). That is how
question 2, "scope only", can run. The runner first checks that the add-on supports this and
stops without asking anything if it does not.

    python scripts/run_test_sheet.py --base-url http://homeassistant.local:8789 --out sheet.json
    python scripts/run_test_sheet.py --base-url ... --profile both
    python scripts/run_test_sheet.py --base-url ... --only 1 5 --bathroom-time 14:08

--base-url is the add-on's own port (off by default; set it under the add-on's Network
settings). That port has no Home Assistant login, so switch it off again after the run.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

SHEET = (
    (1, "Which lights are on?"),
    (2, "Turn on bathroom lights"),
    (3, "What changed in the last hour?"),
    (4, "List the block devices"),
    (5, "Hub health and uptime"),
    (6, "Which batteries are low?"),
    (7, "Which devices have gone quiet?"),
)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "X-Homebrain-Request": "1"}
REQUIRED_ASK_OPTIONS = ("loop_profile", "disable_auto_approval")


def http_json(base_url: str, path: str, body: dict | None = None,
              timeout: float = 15) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        method="GET" if body is None else "POST", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def missing_ask_options(status: dict[str, Any]) -> list[str]:
    offered = status.get("ask_options") if isinstance(status, dict) else None
    offered = offered if isinstance(offered, list) else []
    return [name for name in REQUIRED_ASK_OPTIONS if name not in offered]


def decline_cards(base_url: str, request_id: str, done: threading.Event,
                  declined: list[dict], fetch=http_json, interval: float = 1.0) -> None:
    """Decline every approval card this request raises. Never approves anything.

    If polling or declining fails, the card stays pending and nothing is sent.
    """
    seen: set[str] = set()
    while not done.wait(interval):
        try:
            pending = fetch(base_url, f"/api/activity/{request_id}").get("pending")
            if not pending or pending.get("id") in seen:
                continue
            fetch(base_url, f"/api/activity/{request_id}/confirm",
                  {"id": pending["id"], "approved": False})
            seen.add(pending["id"])
            declined.append({"tool": pending.get("name"), "arguments": pending.get("arguments")})
        except (urllib.error.URLError, OSError, ValueError):
            continue


def ask_body(question: str, request_id: str, profile: str | None) -> dict[str, Any]:
    body = {"request_id": request_id, "conversation_id": str(uuid.uuid4()),
            "question": question, "disable_auto_approval": True}
    if profile:
        body["loop_profile"] = profile
    return body


def post_ask(base_url: str, question: str, timeout: float,
             profile: str | None = None) -> tuple[dict[str, Any], list[dict]]:
    request_id = str(uuid.uuid4())
    declined: list[dict] = []
    done = threading.Event()
    watcher = threading.Thread(target=decline_cards,
                               args=(base_url, request_id, done, declined), daemon=True)
    watcher.start()
    try:
        result = http_json(base_url, "/api/ask", ask_body(question, request_id, profile),
                           timeout=timeout)
    except urllib.error.HTTPError as exc:
        result = {"success": False, "answer": f"HTTP {exc.code}", "error": exc.read().decode(
            "utf-8", errors="replace")[:300], "tool_calls": [], "model_round_metrics": []}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        result = {"success": False, "answer": "Request failed", "error": str(exc)[:300],
                  "tool_calls": [], "model_round_metrics": []}
    finally:
        done.set()
        watcher.join(timeout=20)
    return result, declined


def scoreboard_row(number: int, question: str, result: dict[str, Any], wall_s: float,
                   declined: list[dict] | None = None) -> dict[str, Any]:
    metrics = result.get("model_round_metrics") or []
    calls = [c for c in result.get("tool_calls") or [] if isinstance(c, dict)]
    return {
        "q": number, "profile": result.get("loop_profile"), "question": question,
        "ok": bool(result.get("success")),
        "wall_s": round(wall_s, 1), "rounds": result.get("rounds", len(metrics)),
        "native_calls": len(calls), "failed_calls": sum(1 for c in calls if c.get("success") is False),
        "peak_prompt_tokens": max((m.get("prompt_eval_count") or 0 for m in metrics), default=0),
        "answer_chars": len(str(result.get("answer") or "")),
        "cards_declined": [json.dumps(card.get("arguments"), ensure_ascii=False)[:160]
                           for card in declined or []],
        "answer_head": " ".join(str(result.get("answer") or "").split())[:110],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--out", default="test-sheet-bundle.json")
    parser.add_argument("--only", nargs="*", type=int, help="question numbers to run")
    parser.add_argument("--bathroom-time", help="HH:MM for the causal question (question 8)")
    parser.add_argument("--profile", choices=("full", "plain", "both"),
                        help="loop profile for these requests; default is the add-on option")
    parser.add_argument("--timeout", type=float, default=330)
    args = parser.parse_args(argv)

    try:
        status = http_json(args.base_url, "/api/status")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"Cannot reach the add-on at {args.base_url}: {exc}", file=sys.stderr)
        return 2
    missing = missing_ask_options(status)
    if missing:
        print("Nothing was asked. This add-on does not support " + ", ".join(missing)
              + " (needs 2.0.0-alpha.210 or later), so a test question could switch a device.",
              file=sys.stderr)
        return 2

    questions = list(SHEET)
    if args.bathroom_time:
        questions.append((8, f"Why did the bathroom lights come on at {args.bathroom_time}?"))
    if args.only:
        questions = [q for q in questions if q[0] in args.only]
    # Both profiles run back to back per question, because the home is live.
    profiles = ("full", "plain") if args.profile == "both" else (args.profile,)

    bundle, rows = [], []
    for number, question in questions:
        for profile in profiles:
            started = time.monotonic()
            result, declined = post_ask(args.base_url, question, args.timeout, profile)
            wall = time.monotonic() - started
            rows.append(scoreboard_row(number, question, result, wall, declined))
            bundle.append({"q": number, "question": question, "requested_profile": profile,
                           "wall_s": round(wall, 1), "cards_declined": declined,
                           "response": result})
            print(json.dumps(rows[-1], ensure_ascii=False))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"sheet": "homebrain-vs-claude-no-writes",
                   "addon_version": status.get("version"), "results": bundle}, handle,
                  ensure_ascii=False, indent=1)
    print(f"bundle written to {args.out}", file=sys.stderr)
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
