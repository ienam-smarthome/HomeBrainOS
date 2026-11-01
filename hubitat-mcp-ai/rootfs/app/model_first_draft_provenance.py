"""Private request-scoped provenance for the *actual* no-tools model draft.

A final-model completion differs from an assistant's intermediate tool-call
narration, synthesis-repaired text, and the host-published answer. This module
preserves only a request-local reference; no answer text, hashes, source IDs,
user text or credentials are written to the API metrics/coverage/logs.

This is provenance, NOT evidence attestation, claim validation, a publication
switch, or a source of write authorization.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PrivateModelDraft:
    raw_first: str | None = None
    coordinator_result: str | None = None
    final_answer: str | None = None
    # No guessed serving model identity or provider proof.
    no_tools_final_stage: bool = False


_ACTIVE: ContextVar[PrivateModelDraft | None] = ContextVar(
    "homebrain_private_model_draft", default=None,
)


def begin_private_model_draft() -> Token:
    return _ACTIVE.set(PrivateModelDraft())


def reset_private_model_draft(token: Token) -> None:
    _ACTIVE.reset(token)


def record_first_no_tools_draft(value: Any) -> None:
    current = _ACTIVE.get()
    if current is not None and current.raw_first is None and isinstance(value, str):
        current.raw_first = value
        current.no_tools_final_stage = True


def record_coordinator_result(value: Any) -> None:
    current = _ACTIVE.get()
    if current is not None and isinstance(value, str):
        current.coordinator_result = value


def record_final_answer(value: Any) -> None:
    current = _ACTIVE.get()
    if current is not None and isinstance(value, str):
        current.final_answer = value


def private_snapshot() -> PrivateModelDraft | None:
    current = _ACTIVE.get()
    if current is None or not current.no_tools_final_stage:
        return None
    # Decouple from ContextVar lifespan and prevent later mutation.
    return PrivateModelDraft(
        raw_first=current.raw_first,
        coordinator_result=current.coordinator_result,
        final_answer=current.final_answer,
        no_tools_final_stage=current.no_tools_final_stage,
    )


def public_boundary_shape(
    trace: PrivateModelDraft | None,
    *,
    incoming: str,
    published: str,
) -> dict[str, Any]:
    """Privacy-safe facts about boundary transitions, never claim quality."""
    valid = isinstance(trace, PrivateModelDraft) and trace.no_tools_final_stage
    raw = trace.raw_first if valid else None
    coordinator = trace.coordinator_result if valid else None
    terminal = trace.final_answer if valid else None
    return {
        "schema": "homebrain-model-first-draft-boundary.v1",
        "firstNoToolsDraftCaptured": isinstance(raw, str) and bool(raw.strip()),
        "coordinatorResultCaptured": isinstance(coordinator, str),
        "finalAuthorAnswerCaptured": isinstance(terminal, str),
        "draftUnchangedAtCoordinator": (
            raw == coordinator if isinstance(raw, str)
            and isinstance(coordinator, str) else None
        ),
        "coordinatorUnchangedAtAuthorBoundary": (
            coordinator == terminal if isinstance(coordinator, str)
            and isinstance(terminal, str) else None
        ),
        "authorAnswerUnchangedAtSharedBoundary": (
            terminal == incoming if isinstance(terminal, str) else None
        ),
        "publishedIsFirstModelDraft": (
            published == raw if isinstance(raw, str) else False
        ),
        "rawDraftSourceClaimsAttested": False,
        "modelProseAuthorizedForPublication": False,
        "containsAnswerText": False,
        "containsSourceIds": False,
    }


__all__ = [
    "PrivateModelDraft", "begin_private_model_draft",
    "reset_private_model_draft", "record_first_no_tools_draft",
    "record_coordinator_result", "record_final_answer", "private_snapshot",
    "public_boundary_shape",
]
