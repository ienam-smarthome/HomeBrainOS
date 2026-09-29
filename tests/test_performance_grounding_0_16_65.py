import asyncio
from types import SimpleNamespace

from final_answer_coordinator import (
    FinalAnswerCoordinator,
    _broad_performance_recommendation_request,
    _performance_semantic_validation_needed,
)
from performance_live_semantic_guard import guard_live_performance_semantics


def _performance_evidence():
    return [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_performance_stats",
            "success": True,
            "evidence_kind": "tool_result",
            "arguments": {"tool": "hub_get_performance_stats"},
        }
    ]


def test_performance_semantic_validation_does_not_depend_on_logs():
    evidence = _performance_evidence()
    assert _performance_semantic_validation_needed(evidence) is True


def test_broad_performance_classifier_matches_live_proof_prompt():
    assert _broad_performance_recommendation_request(
        "Analyse my Hubitat performance and recommend improvements."
    ) is True


def test_live_01664_failure_phrases_are_repaired_without_log_evidence():
    draft = """### Hubitat Performance Analysis

* **Database:** Lean. At 168MB, your database is small and unlikely to be causing any performance drag.
* **Network Backup Failure:** The hub reports `NETWORK_BACKUP_FAILED`. This is the most urgent issue; verify backups to prevent data loss.
* *Hypothesis:* This is likely caused by the driver attempting to communicate with a TV that is asleep or unreachable, causing the thread to hang until a network timeout occurs.
* These recurring tasks increase the baseline CPU load.
* Review the app managing the `sessionTick` jobs. If possible, increase the `sessionTick` interval to reduce the total number of scheduled jobs.
"""
    corrected, changed = guard_live_performance_semantics(draft, _performance_evidence())
    assert changed is True
    assert "Database:** Lean" not in corrected
    assert "small and unlikely" not in corrected
    assert "most urgent issue" not in corrected
    assert "prevent data loss" not in corrected
    assert "likely caused by" not in corrected
    assert "increase the baseline CPU load" not in corrected
    assert "increase the `sessionTick` interval" not in corrected
    assert "168 MB" in corrected
    assert "does not establish which mechanism is responsible" in corrected
    assert "does not establish material CPU load" in corrected
    assert "Inspect the cited scheduler/app configuration first" in corrected


class _FakeExecutor:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = []

    async def execute(self, name, arguments, **kwargs):
        self.calls.append((name, arguments, kwargs))
        if name == "hub_manage_logs":
            self.evidence.append(
                {
                    "tool": name,
                    "sub_tool": "hub_get_logs",
                    "success": True,
                    "evidence_kind": "authoritative_recent_performance_logs",
                    "arguments": arguments,
                    "details": {"logs": []},
                }
            )
            return SimpleNamespace(
                success=True,
                result=object(),
                content='{"result":{"logs":[]}}',
            )
        return SimpleNamespace(success=False, result=None, content='{"error":"rejected"}')


class _FakeAgent:
    def __init__(self, evidence):
        self.executor = _FakeExecutor(evidence)

    async def chat(self, messages, tools):
        return {"content": "Measured performance summary."}


def test_host_enforces_bounded_log_read_before_broad_performance_synthesis():
    evidence = _performance_evidence()
    agent = _FakeAgent(evidence)
    coordinator = FinalAnswerCoordinator(agent.chat, evidence_supplier=lambda: evidence)
    messages = [
        {"role": "system", "content": "system"},
        {
            "role": "user",
            "content": "Analyse my Hubitat performance and recommend improvements.",
        },
    ]

    refreshed = asyncio.run(
        coordinator._ensure_broad_performance_logs(
            "Analyse my Hubitat performance and recommend improvements.",
            list(evidence),
            messages,
        )
    )

    assert any(row.get("sub_tool") == "hub_get_logs" for row in refreshed)
    assert agent.executor.calls[0][0] == "hub_manage_logs"
    assert agent.executor.calls[0][1] == {
        "tool": "hub_get_logs",
        "args": {"since": "30m", "limit": 100},
    }
    assert any(
        message.get("role") == "user"
        and "HOST BROAD PERFORMANCE LOG READ" in message.get("content", "")
        for message in messages
    )


def test_host_retries_diagnostics_gateway_if_manage_logs_rejects():
    evidence = _performance_evidence()

    class _FallbackExecutor:
        def __init__(self):
            self.calls = []

        async def execute(self, name, arguments, **kwargs):
            self.calls.append(name)
            if name == "hub_manage_logs":
                return SimpleNamespace(success=False, result=None, content='{"error":"rejected"}')
            evidence.append(
                {
                    "tool": name,
                    "sub_tool": "hub_get_logs",
                    "success": True,
                    "arguments": arguments,
                }
            )
            return SimpleNamespace(success=True, result=object(), content='{"result":{"logs":[]}}')

    agent = _FakeAgent(evidence)
    agent.executor = _FallbackExecutor()
    coordinator = FinalAnswerCoordinator(agent.chat, evidence_supplier=lambda: evidence)
    messages = [
        {"role": "user", "content": "Analyse my Hubitat performance and recommend improvements."},
    ]

    refreshed = asyncio.run(
        coordinator._ensure_broad_performance_logs(
            messages[0]["content"],
            list(evidence),
            messages,
        )
    )

    assert agent.executor.calls == ["hub_manage_logs", "hub_read_diagnostics"]
    assert any(row.get("sub_tool") == "hub_get_logs" for row in refreshed)
