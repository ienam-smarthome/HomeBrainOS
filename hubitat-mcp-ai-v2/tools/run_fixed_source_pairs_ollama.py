#!/usr/bin/env python3
"""Opt-in, tool-free Ollama runner for already frozen private v2 A/B pairs.

The default is OFFLINE DRY RUN (no network calls). Explicit --run, private-data
acknowledgment, and cloud/remote endpoint opt-in gates are required. This script
cannot replay MCP tools or connect to Hubitat. It never auto-grades answers.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import fixed_source_benchmark as benchmark


def _validate_endpoint(endpoint: str, allow_remote: bool) -> None:
    parsed = urlsplit(endpoint)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/api/chat"):
        raise ValueError("Expected an Ollama /api/chat endpoint without URL credentials")
    local = parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    if not local and not allow_remote:
        raise ValueError("Only loopback Ollama endpoints are allowed by default")
    if not local and parsed.scheme != "https":
        raise ValueError("Remote Ollama endpoints must use HTTPS")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ValueError("Invalid Ollama port")


def _is_cloud(model: str) -> bool:
    return "cloud" in model.lower()


def _read_pairs(folder: Path) -> list[tuple[str, dict, dict]]:
    manifest = json.loads((folder / "private_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != benchmark.SCHEMA:
        raise ValueError("Private manifest has an unsupported schema")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Private manifest contains no cases")
    result = []
    seen = set()
    for record in cases:
        case_id = record.get("case_id")
        if (not isinstance(case_id, str) or not case_id.startswith("case-")
                or not case_id[5:].isdigit() or case_id in seen):
            raise ValueError("Invalid or repeated case identifier")
        seen.add(case_id)
        a = json.loads((folder / (case_id + "-A.json")).read_text(encoding="utf-8"))
        b = json.loads((folder / (case_id + "-B.json")).read_text(encoding="utf-8"))
        mapping = record.get("condition_map", {})
        if (not isinstance(mapping, dict)
                or sorted(mapping.values()) != ["baseline", "role_notes"]):
            raise ValueError("Invalid private condition assignment")
        base = a if mapping.get("A") == "baseline" else b
        notes = b if mapping.get("A") == "baseline" else a
        if not benchmark._check_pair(base, notes, record.get("source_sha256")):
            raise ValueError("Frozen source SHA mismatch")
        result.append((case_id, a, b))
    return result


def _model_answer(model: str, endpoint: str, bundle: dict, timeout: float,
                  seed: int) -> tuple[str, float]:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": bundle["instructions"]},
            {"role": "user", "content": json.dumps({
                "recorded_user_question": bundle["recorded_user_question"],
                "native_tool_receipts": bundle["native_tool_receipts"],
            }, ensure_ascii=False)},
        ],
        "options": {"temperature": 0, "seed": seed},
    }
    request = Request(
        endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    start = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            response_json = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        # Do not echo server error bodies, which may include raw private input.
        raise ValueError("Ollama request failed: " + type(exc).__name__) from None
    elapsed_ms = (time.perf_counter() - start) * 1000
    message = response_json.get("message")
    if (not isinstance(message, dict) or message.get("tool_calls")
            or not isinstance(message.get("content"), str)
            or not message["content"].strip()):
        raise ValueError("Model did not return a standalone text answer")
    return message["content"], round(elapsed_ms, 3)


def _exclusive_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(value)
    if os.name == "posix":
        os.chmod(path, 0o600)


def _save_ratings_time(folder: Path, case_id: str, label: str,
                       elapsed_ms: float) -> None:
    path = folder / "blind_ratings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != benchmark.SCHEMA:
        raise ValueError("Blind rating template schema mismatch")
    record = data["cases"][case_id][label]
    if record.get("elapsed_ms") is not None:
        raise ValueError("Existing recorded model time; refusing to overwrite")
    record["elapsed_ms"] = elapsed_ms
    temp_path = folder / "blind_ratings.next-private.json"
    _exclusive_text(temp_path, json.dumps(data, indent=2) + "\n")
    os.replace(temp_path, path)
    if os.name == "posix":
        os.chmod(path, 0o600)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    folder = args.directory.resolve()
    _validate_endpoint(args.endpoint, args.allow_remote_endpoint)
    if not isinstance(args.model, str) or not args.model.strip():
        raise ValueError("Model must be named")
    if args.timeout <= 0 or args.timeout > 3600:
        raise ValueError("Timeout must be between 1 and 3600 seconds")
    if args.max_pairs < 1:
        raise ValueError("max-pairs must be at least one")
    pairs = _read_pairs(folder)
    if args.case:
        requested = set(args.case)
        available = {name for name, _, _ in pairs}
        if not requested.issubset(available):
            raise ValueError("A specified case is not in the private manifest")
        pairs = [p for p in pairs if p[0] in requested]
    pairs = pairs[:args.max_pairs]
    pending = [(case_id, label, bundle)
               for case_id, a, b in pairs
               for label, bundle in (("A", a), ("B", b))
               if not (folder / "answers" / (case_id + "-" + label + ".txt")).exists()]
    outcome = {
        "schema": "homebrain-v2-paired-ollama-runner.v1",
        "source_pairs_verified": len(pairs),
        "model_requests_pending": len(pending),
        "model_requests_completed_this_run": 0,
        "mode": "dry_run" if not args.run else "explicit_opt_in",
        "hubitat_or_mcp_calls": 0,
        "automated_quality_scores": 0,
    }
    if not args.run:
        return outcome
    if not args.acknowledge_private_mcp_data:
        raise ValueError("--run requires --acknowledge-private-mcp-data")
    if _is_cloud(args.model) and not args.allow_cloud_model:
        raise ValueError("Cloud model requires --allow-cloud-model")
    if not pending:
        return outcome
    ratings_file = json.loads((folder / "blind_ratings.json").read_text(encoding="utf-8"))
    if ratings_file.get("schema") != benchmark.SCHEMA:
        raise ValueError("Blind ratings schema mismatch")
    for case_id, label, _ in pending:
        if ratings_file["cases"][case_id][label].get("elapsed_ms") is not None:
            raise ValueError("Inconsistent answer/timing state; refusing to send data")
    random.Random(args.seed).shuffle(pending)
    for case_id, label, bundle in pending:
        answer, elapsed_ms = _model_answer(
            args.model, args.endpoint, bundle, args.timeout, args.seed
        )
        answer_file = folder / "answers" / (case_id + "-" + label + ".txt")
        _exclusive_text(answer_file, answer)
        _save_ratings_time(folder, case_id, label, elapsed_ms)
        outcome["model_requests_completed_this_run"] += 1
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--model", default="gemma4:31b-cloud")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-pairs", type=int, default=2,
                        help="Conservative pilot; use 10 to run all ten")
    parser.add_argument("--case", action="append",
                        help="Optional explicit case-XXX selection (repeatable)")
    parser.add_argument("--run", action="store_true",
                        help="Actually send raw private source bundles to the selected model")
    parser.add_argument("--acknowledge-private-mcp-data", action="store_true")
    parser.add_argument("--allow-cloud-model", action="store_true")
    parser.add_argument("--allow-remote-endpoint", action="store_true")
    args = parser.parse_args()
    try:
        outcome = execute(args)
    except (ValueError, KeyError, IndexError, TypeError, OSError) as exc:
        # Do not display raw model replies, source content, or server errors.
        parser.error("Paired Ollama run could not proceed: " + type(exc).__name__
                     + ". Check the private source folder and consent flags.")
    print(json.dumps(outcome, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
