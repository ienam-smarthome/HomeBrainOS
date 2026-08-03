from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evidence_recorder import EvidenceRecorder
from grounding_policy import GroundingAction, GroundingDecision, GroundingPolicy


class LiveEvidenceAuthority:
    """Combine request evidence receipts with bounded grounding decisions.

    The authority is request-local. It does not execute tools, inspect prompt
    wording, or mutate receipts. It only answers whether a model response may
    be accepted, must retry once, or must fail closed.
    """

    def __init__(
        self,
        recorder: EvidenceRecorder,
        *,
        logs_requested: bool,
        conversational: bool,
        record_metric: Callable[[str], None] | None = None,
    ) -> None:
        self.recorder = recorder
        self.policy = GroundingPolicy.default(
            logs_requested=logs_requested,
            conversational=conversational,
        )
        self._record_metric = record_metric

    @property
    def has_live_evidence(self) -> bool:
        return self.recorder.has_live_evidence()

    @property
    def logs_checked(self) -> bool:
        return self.policy.logs_checked

    def record_tool_outcome(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
    ) -> None:
        self.policy.record_tool_outcome(name, arguments, success=success)

    def decide_no_tool_calls(
        self,
        *,
        has_live_evidence: bool | None = None,
    ) -> GroundingDecision:
        """Decide from the recorder, ignoring any stale external evidence flag."""

        del has_live_evidence
        decision = self.policy.decide_no_tool_calls(
            has_live_evidence=self.has_live_evidence
        )
        if self._record_metric is not None:
            if decision.action is GroundingAction.RETRY:
                self._record_metric("evidence_retries")
            elif decision.action is GroundingAction.REFUSE:
                self._record_metric("grounding_refusals")
        return decision


__all__ = ["LiveEvidenceAuthority"]
