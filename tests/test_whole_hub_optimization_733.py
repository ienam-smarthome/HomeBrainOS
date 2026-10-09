from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_host_plan import (
    is_broad_performance_request,
    is_whole_hub_optimization_request,
    wants_scheduler_evidence,
)
from performance_api_finalizer import _normalize_recommendation_table


WHOLE_HUB = (
    "Review all devices, hub rules, apps, automations and all logs/events and "
    "suggest how to optimize and make the hub more efficient"
)


def test_exact_claude_comparison_prompt_reaches_scheduler_performance_review():
    assert is_whole_hub_optimization_request(WHOLE_HUB)
    assert is_broad_performance_request(WHOLE_HUB)
    assert wants_scheduler_evidence(WHOLE_HUB)
    assert not is_whole_hub_optimization_request("Run a full system check")
    assert not is_whole_hub_optimization_request("How can I optimize button 3 rule?")


def test_interleaved_guard_notes_are_moved_after_complete_markdown_table():
    original = """#### 6. Recommended Inspection Steps

| Priority | Target | Evidence | Recommended Action | Expected Benefit |
| :--- | :--- | :--- | :--- | :--- |
| **High** | App 4151 | 22.9% busy | Check logs | Unverified |
Collect target-scoped diagnostic evidence for this outlier before choosing a mechanism.
| **Medium** | App 4072 | stateSize 901843 | Inspect settings | Unknown |
Regular cadence; median interval 10.002 seconds; approximately every 10 seconds.
| **Low** | Job Cluster | 11:30 BST | Inspect schedules | Unknown |

### Repair status
No changes made.
"""
    repaired, changed = _normalize_recommendation_table(original)
    assert changed
    assert "| **High** |" in repaired
    assert repaired.index("| **High** |") < repaired.index("| **Medium** |")
    assert repaired.index("| **Medium** |") < repaired.index("| **Low** |")
    assert repaired.index("**Additional qualifications") > repaired.index("| **Low** |")
    assert repaired.index("**Additional qualifications") < repaired.index("### Repair status")
    assert "- Regular cadence; median interval" in repaired
    assert "No changes made." in repaired


def test_valid_markdown_table_is_unchanged():
    original = """| Priority | Target | Recommendation |
| --- | --- | --- |
| High | LG TV | Inspect |
| Low | Jobs | Review |
"""
    assert _normalize_recommendation_table(original) == (original, False)


def test_whole_hub_intent_preempts_health_audit_even_with_logs(monkeypatch, tmp_path):
    import importlib

    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    calls = []

    async def performance(agent, prompt):
        calls.append(("performance", prompt))
        return SimpleNamespace(message="Optimisation evidence collected.", route="unified-mcp-agent",
                               request_class="live-read", evidence=[], metrics={})

    async def finalize(agent, mcp, outcome, prompt):
        calls.append(("finalize", prompt))
        return outcome

    async def unexpected(*args, **kwargs):
        raise AssertionError("Generic health audit must not intercept optimisation intent")

    monkeypatch.setattr(module, "collect_broad_performance_outcome", performance)
    monkeypatch.setattr(module, "finalize_performance_api_outcome", finalize)
    monkeypatch.setattr(module, "run_comprehensive_chat_audit", unexpected)
    request = SimpleNamespace(message=WHOLE_HUB, history=[], session_id="test")
    result = asyncio.run(module._agent_request(request))
    assert result.message == "Optimisation evidence collected."
    assert calls == [("performance", WHOLE_HUB), ("finalize", WHOLE_HUB)]
