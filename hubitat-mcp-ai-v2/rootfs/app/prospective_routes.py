"""Deliberate, opt-in source-real read-only blinded A/B endpoints.

No scheduler, no device control, no persistent household evidence. Both
conditions run the existing model-led Agent loop with independent contexts.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool

from prospective_source_ab import (
    ProspectiveError, ProspectiveWorkspace,
    SourceLedgerExperimentalAgent, verify_read_only_client,
)

router = APIRouter(prefix="/api/prospective-ab")


def guard(request: Request):
    if request.headers.get("x-homebrain-request") != "1":
        raise HTTPException(403, "Open and refresh the current v2 interface")


@router.get("/status")
async def status(request: Request):
    guard(request)
    return request.app.state.prospective.summary()


class FreezeQuestions(BaseModel):
    questions: list[str] = Field(min_length=2, max_length=10)
    causal_mode: StrictBool = False
    target_check_attested: StrictBool = False


@router.post("/prepare")
async def prepare(body: FreezeQuestions, request: Request):
    guard(request)
    try:
        return request.app.state.prospective.prepare(
            body.questions, body.causal_mode, body.target_check_attested
        )
    except ProspectiveError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/permission")
async def permission(request: Request):
    guard(request)
    mcp = request.app.state.mcp
    if mcp is None or request.app.state.configuration_error:
        raise HTTPException(503, "Configure the Hubitat MCP endpoint")
    try:
        # A single read-only upstream hub_get_info, no model call.
        return await verify_read_only_client(mcp)
    except (ProspectiveError, RuntimeError) as exc:
        raise HTTPException(
            403, "The configured token has not established per-client Read ON / Write OFF "
                 "access. Check the private v2 MCP endpoint/token and server clientAccess."
        ) from None


class RunRequest(BaseModel):
    case_id: str
    model_execution_consent: StrictBool
    private_evidence_consent: StrictBool
    cloud_transfer_consent: StrictBool


async def _run_pair(app, case_id: str):
    candidate = None
    workspace: ProspectiveWorkspace = app.state.prospective
    try:
        options = app.state.options
        candidate = SourceLedgerExperimentalAgent(
            str(options["model_base_url"]),
            str(options["model_name"]),
            str(options["model_api_key"]),
            int(options["model_timeout_seconds"]),
        )
        # Shares the normal Ask lock: source verification and A/B runs do not
        # overlap an unrelated live operation in the same add-on instance.
        async with app.state.ask_lock:
            await workspace.run(
                case_id, app.state.model, candidate, app.state.mcp,
                int(options["investigation_timeout_seconds"]),
            )
    except asyncio.CancelledError:
        workspace.error = "Paired run cancelled; first answers already captured remain immutable"
        raise
    except Exception:
        # Original MCP text/model messages may contain sensitive household data.
        workspace.error = "Paired run stopped. Check token, read-only schemas and model configuration."
    finally:
        workspace.active_case = None
        if candidate is not None:
            await candidate.close()


@router.post("/run")
async def run(body: RunRequest, request: Request):
    guard(request)
    app = request.app
    workspace: ProspectiveWorkspace = app.state.prospective
    if not body.model_execution_consent or not body.private_evidence_consent:
        raise HTTPException(403, "Explicit model and private evidence consent required")
    if not body.cloud_transfer_consent:
        base = urlsplit(str(app.state.options["model_base_url"]))
        remote = (base.hostname not in ("localhost", "127.0.0.1", "::1")
                  or "cloud" in str(app.state.options["model_name"]).lower())
        if remote:
            raise HTTPException(403, "Explicit cloud/remote model consent required")
    if app.state.configuration_error or app.state.mcp is None or app.state.model is None:
        raise HTTPException(503, "Configure the model and Hubitat MCP endpoint")
    if (app.state.prospective_task and not app.state.prospective_task.done()) or any(
        (task is not None and not task.done())
        for task in (
            getattr(app.state, "benchmark_task", None),
            getattr(app.state, "autolab_task", None),
            getattr(app.state, "reasoning_task", None),
        )
    ):
        raise HTTPException(409, "Another evaluation is active")
    try:
        workspace.can_run(body.case_id)
    except ProspectiveError as exc:
        raise HTTPException(409, str(exc)) from None
    # PRE-FLIGHT before starting any model calls. The worker checks AGAIN
    # before each arm, including after a token/config change.
    try:
        await verify_read_only_client(app.state.mcp)
    except (ProspectiveError, RuntimeError):
        raise HTTPException(403,
             "This v2 connection has not verified its own read-only clientAccess grant."
        ) from None
    app.state.prospective_task = asyncio.create_task(_run_pair(app, body.case_id))
    return {
        "started": True, "case_id": body.case_id,
        "arms_planned": 2, "source": "live_read_only_mcp",
        "model_calls_may_incur_cost": True,
    }


@router.post("/stop")
async def stop(request: Request):
    guard(request)
    task = request.app.state.prospective_task
    if task and not task.done():
        task.cancel()
        return {"stop_requested": True}
    return {"stop_requested": False}


@router.get("/case/{case_id}")
async def case(case_id: str, request: Request):
    guard(request)
    try:
        return request.app.state.prospective.case(case_id)
    except ProspectiveError as exc:
        raise HTTPException(404, str(exc)) from None


class Score(BaseModel):
    scores: dict[str, dict[str, int | str]]
    causal_review: dict[str, Any] | None = None


@router.post("/case/{case_id}/score")
async def score(case_id: str, body: Score, request: Request):
    guard(request)
    try:
        request.app.state.prospective.rate(
            case_id, body.scores, body.causal_review
        )
    except ProspectiveError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"saved": True, "mapping_hidden_until_all_rated": True}


@router.get("/report")
async def report(request: Request):
    guard(request)
    return request.app.state.prospective.report()


class Delete(BaseModel):
    confirm_delete: StrictBool


@router.post("/delete")
async def delete(body: Delete, request: Request):
    guard(request)
    if body.confirm_delete is not True:
        raise HTTPException(403, "Explicit deletion confirmation required")
    try:
        request.app.state.prospective.delete()
    except ProspectiveError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"deleted": True}
