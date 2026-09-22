from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from chat_transport import ChatTransport  # noqa: E402
from semantic_agent_core import SemanticAgentCore  # noqa: E402
from semantic_plan import SemanticPlan  # noqa: E402
from semantic_planner import SemanticPlanner  # noqa: E402


CASES_PATH = ROOT / "tests" / "fixtures" / "semantic_control_eval.json"


def _normalized_name(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _actual(plan: SemanticPlan) -> dict[str, Any]:
    target = plan.target
    action = plan.action
    return {
        "domain": plan.domain,
        "timing": plan.timing,
        "target_scope": target.scope if target is not None else None,
        "target_name": _normalized_name(target.name) if target is not None else None,
        "operation": action.operation if action is not None else None,
        "value": action.value if action is not None else None,
        "delta": action.delta if action is not None else None,
        "direction": action.direction if action is not None else None,
        "magnitude": action.magnitude if action is not None else None,
        "needs_clarification": plan.needs_clarification,
    }


def _matches(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for key, wanted in expected.items():
        got = actual.get(key)
        if key == "target_name":
            wanted = _normalized_name(wanted)
        if got != wanted:
            mismatches.append(f"{key}: expected {wanted!r}, got {got!r}")
    return mismatches


async def main() -> int:
    api_key = (
        os.getenv("HOMEBRAIN_SEMANTIC_EVAL_API_KEY")
        or os.getenv("HMCP_OLLAMA_DIRECT_CLOUD_API_KEY")
        or ""
    ).strip()
    base_url = (
        os.getenv("HOMEBRAIN_SEMANTIC_EVAL_BASE_URL")
        or os.getenv("HMCP_OLLAMA_DIRECT_CLOUD_BASE_URL")
        or "https://ollama.com"
    ).strip()
    model = (
        os.getenv("HOMEBRAIN_SEMANTIC_EVAL_MODEL")
        or os.getenv("HMCP_OLLAMA_DIRECT_CLOUD_MODEL")
        or "gemma4:31b-cloud"
    ).strip()
    if not api_key:
        print(
            "Set HOMEBRAIN_SEMANTIC_EVAL_API_KEY (or "
            "HMCP_OLLAMA_DIRECT_CLOUD_API_KEY) before running this model eval.",
            file=sys.stderr,
        )
        return 2

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    transport = ChatTransport(
        api_key,
        model,
        base_url=base_url,
        timeout_seconds=60,
        stream_idle_timeout_seconds=20,
    )
    planner = SemanticPlanner(transport.chat)
    core = SemanticAgentCore(planner)
    passed = 0
    failures: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases, start=1):
            prompt = str(case["prompt"])
            expected = dict(case["expected"])
            try:
                world_context = str(case.get("world_context") or "")
                plan = await planner.plan(
                    prompt,
                    world_context=world_context,
                )
                plan = core.ground_plan_target(
                    prompt,
                    plan,
                    world_context,
                )
                actual = _actual(plan)
                mismatches = _matches(expected, actual)
            except Exception as exc:
                actual = {}
                mismatches = [f"{type(exc).__name__}: {exc}"]

            if mismatches:
                failures.append(
                    {
                        "index": index,
                        "prompt": prompt,
                        "mismatches": mismatches,
                        "actual": actual,
                    }
                )
                print(f"FAIL {index:02d}: {prompt}")
                for mismatch in mismatches:
                    print(f"  - {mismatch}")
            else:
                passed += 1
                print(f"PASS {index:02d}: {prompt}")
    finally:
        await transport.close()

    total = len(cases)
    accuracy = (passed / total * 100.0) if total else 0.0
    print(
        f"\nSemantic interpretation eval: "
        f"{passed}/{total} passed ({accuracy:.1f}%)."
    )
    if failures:
        print(json.dumps({"failures": failures}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
