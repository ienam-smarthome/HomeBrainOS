"""Offline replay scorecards for Investigation V2.

Measured checks only: canonical evidence retention, link validity, atomic
rejections, and caller-provided tool/latency counts. External V1/Claude texts
are optional and evaluated only for LITERAL timestamp appearances; this is
NOT a semantic quality judgment or fabricated model comparison.

No service calls, no benchmark-specific production routing, no writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .evidence import CaseFile
from .synthesis import GroundedAnswer


@dataclass(frozen=True)
class ReplayScore:
    label: str
    evidence_records: int
    command_records: int
    commands_retained: int
    command_retention_fraction: float
    states_retained: int
    invalid_citations: int
    validator_flags: tuple[str, ...]
    source_complete_proven: bool
    reads_executed: int | None = None
    elapsed_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalTextObservation:
    label: str
    provided: bool
    commands_with_exact_source_clock_mention: int | None
    total_command_records: int
    note: str = ("Literal source timestamps mentioned in supplied output; "
                 "not proof of correct command/state semantics or causality.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_grounded_replay(
    case: CaseFile, answer: GroundedAnswer, *, label: str = "V2",
    reads_executed: int | None = None, elapsed_ms: int | None = None,
) -> ReplayScore:
    """Score source-ID preservation without assuming explanation quality."""
    valid = {r.record_id for r in case.records}
    displayed = set(answer.displayed_record_ids)
    commands = {r.record_id for r in case.records if r.stage == "command_issued"}
    states = {r.record_id for r in case.records if r.stage == "state_reported"}
    n = len(commands)
    return ReplayScore(
        label=label,
        evidence_records=len(case.records),
        command_records=n,
        commands_retained=len(commands & displayed),
        command_retention_fraction=(len(commands & displayed) / n if n else 1.0),
        states_retained=len(states & displayed),
        invalid_citations=len(displayed - valid),
        validator_flags=tuple(answer.validation_issues),
        source_complete_proven=any(c.source_complete is True for c in case.coverage),
        reads_executed=reads_executed,
        elapsed_ms=elapsed_ms,
    )


def inspect_external_text(case: CaseFile, label: str,
                          captured_answer: str | None) -> ExternalTextObservation:
    """No V1/Claude benchmark value exists until an actual output is supplied."""
    commands = [r for r in case.records if r.stage == "command_issued"]
    if captured_answer is None:
        return ExternalTextObservation(label, False, None, len(commands))
    if not isinstance(captured_answer, str):
        raise TypeError("Captured answer must be a string or None")
    return ExternalTextObservation(
        label, True,
        sum(r.timestamp_original in captured_answer for r in commands),
        len(commands),
    )


def replay_scorecard(
    case: CaseFile, answer: GroundedAnswer, *,
    existing_v1_answer: str | None = None,
    reference_answer: str | None = None,
    reads_executed: int | None = None,
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    score = score_grounded_replay(
        case, answer, reads_executed=reads_executed, elapsed_ms=elapsed_ms)
    return {
        "v2_measured": score.to_dict(),
        "v1_external": inspect_external_text(case, "V1", existing_v1_answer).to_dict(),
        "reference_external": inspect_external_text(
            case, "External reference", reference_answer).to_dict(),
        "causal_accuracy_comparison_completed": False,
        "external_text_scores_are_semantic": False,
    }


__all__ = [
    "ReplayScore", "ExternalTextObservation", "score_grounded_replay",
    "inspect_external_text", "replay_scorecard",
]
