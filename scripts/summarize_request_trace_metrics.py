from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("traces", "requests", "items", "history"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("Trace export must be a JSON list or contain traces/requests/items/history.")


def _number(record: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    performance = record.get("performance")
    if isinstance(performance, dict):
        for key in keys:
            value = performance.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def summarize(payload: Any) -> dict[str, Any]:
    records = _records(payload)
    mcp_calls = [value for item in records if (value := _number(item, "mcp_calls")) is not None]
    mcp_ms = [
        value
        for item in records
        if (value := _number(item, "mcp_duration_ms", "mcp_busy_ms")) is not None
    ]
    elapsed_ms = [value for item in records if (value := _number(item, "elapsed_ms")) is not None]
    return {
        "request_count": len(records),
        "mean_mcp_calls": mean(mcp_calls) if mcp_calls else None,
        "total_mcp_calls": sum(mcp_calls) if mcp_calls else None,
        "mean_mcp_duration_ms": mean(mcp_ms) if mcp_ms else None,
        "total_mcp_duration_ms": sum(mcp_ms) if mcp_ms else None,
        "mean_elapsed_ms": mean(elapsed_ms) if elapsed_ms else None,
    }


def compare(before: Any, after: Any) -> dict[str, Any]:
    before_summary = summarize(before)
    after_summary = summarize(after)
    delta: dict[str, Any] = {}
    for key in ("mean_mcp_calls", "total_mcp_calls", "mean_mcp_duration_ms", "total_mcp_duration_ms", "mean_elapsed_ms"):
        old = before_summary.get(key)
        new = after_summary.get(key)
        delta[key] = None if old is None or new is None else new - old
    return {"before": before_summary, "after": after_summary, "delta_after_minus_before": delta}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare live HomeBrain request trace metrics.")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = compare(_load(args.before), _load(args.after))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
