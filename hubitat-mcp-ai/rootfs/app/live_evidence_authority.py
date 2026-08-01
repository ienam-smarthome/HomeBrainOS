from __future__ import annotations

from typing import Any

from evidence_recorder import EvidenceRecorder
from grounding_policy import GroundingDecision, GroundingPolicy


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
    ) -> None:
        self.recorder = recorder
        self.policy = GroundingPolicy(
            logs_requested=logs_requested,
            conversational=conversational,
        )

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

    def decide_no_tool_calls(self) -> GroundingDecision:
        return self.policy.decide_no_tool_calls(
            has_live_evidence=self.has_live_evidence
        )


__all__ = ["LiveEvidenceAuthority"]
