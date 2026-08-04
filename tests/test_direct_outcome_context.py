from __future__ import annotations

import asyncio
from contextvars import ContextVar

import pytest

from direct_outcome_context import DirectOutcomeContext
from evidence_recorder import EvidenceRecorder


def _context() -> tuple[
    DirectOutcomeContext,
    EvidenceRecorder,
    ContextVar[list[str] | None],
    ContextVar[bool],
    ContextVar[str],
]:
    evidence = EvidenceRecorder()
    choices: ContextVar[list[str] | None] = ContextVar("test_choices", default=None)
    mutation: ContextVar[bool] = ContextVar("test_mutation", default=False)
    request_class: ContextVar[str] = ContextVar("test_request_class", default="outer")
    return (
        DirectOutcomeContext(evidence, choices, mutation, request_class),
        evidence,
        choices,
        mutation,
        request_class,
    )


def test_direct_outcome_captures_request_local_state() -> None:
    coordinator, evidence, choices, mutation, request_class = _context()

    async def operation() -> str:
        assert request_class.get() == "write"
        assert mutation.get() is True
        choices.set(["Fan Boost"])
        evidence.record(
            "homebrain_control_devices",
            {"name": "fan"},
            success=True,
            elapsed_ms=4,
            summary="ok",
            evidence_kind="deterministic_device_control",
        )
        return "done"

    outcome = asyncio.run(coordinator.run(operation, request_class="write"))

    assert outcome.message == "done"
    assert outcome.request_class == "write"
    assert outcome.choices == ["Fan Boost"]
    assert len(outcome.evidence) == 1
    assert request_class.get() == "outer"
    assert mutation.get() is False
    assert choices.get() is None
    assert evidence.receipts() == []


def test_direct_outcome_restores_context_after_failure() -> None:
    coordinator, evidence, choices, mutation, request_class = _context()

    async def operation() -> str:
        choices.set(["Bedroom 1 Meter"])
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(coordinator.run(operation, request_class="live-read"))

    assert request_class.get() == "outer"
    assert mutation.get() is False
    assert choices.get() is None
    assert evidence.receipts() == []
