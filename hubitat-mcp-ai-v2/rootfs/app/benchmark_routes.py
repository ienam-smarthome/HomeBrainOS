"""Private benchmark REST endpoints, isolated from live MCP and Agent.answer."""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool

from benchmark import BenchmarkError, MAX_ZIP_BYTES, run_pairs


router = APIRouter(prefix="/api/benchmark")


def guard(request: Request):
    if request.headers.get("x-homebrain-request") != "1":
        raise HTTPException(403, "Open the current HomeBrainOS interface and refresh")


def workspace(request: Request):
    return request.app.state.benchmark


@router.get("/status")
async def status(request: Request):
    guard(request)
    progress = request.app.state.benchmark_progress
    return workspace(request).summary(
        running=bool(progress.get("running")),
        error=progress.get("error"),
        progress={k: v for k, v in progress.items()
                  if k in ("completed_requests", "total_requests")},
    )


@router.post("/import")
async def upload(request: Request):
    guard(request)
    if request.app.state.benchmark_progress.get("running"):
        raise HTTPException(409, "Cannot import a benchmark while running")
    if request.headers.get("content-type", "").split(";")[0] != "application/zip":
        raise HTTPException(415, "Upload the private benchmark ZIP")
    try:
        stated_size = int(request.headers.get("content-length") or "0")
    except ValueError:
        raise HTTPException(400, "Invalid upload size") from None
    if stated_size > MAX_ZIP_BYTES:
        raise HTTPException(413, "Benchmark ZIP exceeds 8 MB")
    chunks = bytearray()
    async for block in request.stream():
        chunks.extend(block)
        if len(chunks) > MAX_ZIP_BYTES:
            raise HTTPException(413, "Benchmark ZIP exceeds 8 MB")
    try:
        pairs = workspace(request).import_zip(bytes(chunks))
    except BenchmarkError as exc:
        raise HTTPException(400, str(exc)) from None
    request.app.state.benchmark_progress = {"running": False, "error": None}
    return {"imported": True, "pairs": pairs, "model_calls": 0}


@router.get("/case/{case_id}")
async def case(case_id: str, request: Request):
    guard(request)
    try:
        return workspace(request).case(case_id)
    except BenchmarkError as exc:
        raise HTTPException(404, str(exc)) from None


class RunRequest(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=2)
    private_evidence_consent: StrictBool
    cloud_transfer_consent: StrictBool


async def _run(request_app, keys: list[str]):
    progress = request_app.state.benchmark_progress
    try:
        await run_pairs(
            request_app.state.benchmark, request_app.state.model, keys,
            float(request_app.state.options["model_timeout_seconds"]), progress
        )
    except asyncio.CancelledError:
        progress["error"] = "Run stopped; completed answers remain private"
        raise
    except BenchmarkError as exc:
        progress["error"] = str(exc)
    except Exception:
        # Error bodies can contain private evidence; never send them to UI.
        progress["error"] = "Model run failed; check connectivity and credits"
    finally:
        progress["running"] = False


@router.post("/run")
async def run(body: RunRequest, request: Request):
    guard(request)
    app = request.app
    if not body.private_evidence_consent:
        raise HTTPException(403, "Approve sending the private evidence to the model")
    if app.state.benchmark_progress.get("running"):
        raise HTTPException(409, "A benchmark is already running")
    if app.state.model is None or app.state.configuration_error:
        raise HTTPException(503, "Configure the AI model in add-on options")
    options = app.state.options
    base = urlsplit(str(options["model_base_url"]))
    remote_or_cloud = (base.hostname not in ("localhost", "127.0.0.1", "::1")
                       or "cloud" in str(options["model_name"]).lower())
    if remote_or_cloud and not body.cloud_transfer_consent:
        raise HTTPException(403, "Explicit cloud/remote evidence-transfer approval required")
    if base.hostname == "ollama.com" and not str(options["model_api_key"]).strip():
        raise HTTPException(503, "Ollama Cloud API key is not configured")
    try:
        pending = app.state.benchmark.pending(body.case_ids)
    except BenchmarkError as exc:
        raise HTTPException(400, str(exc)) from None
    if not pending:
        return {"started": False, "message": "These cases already have both answers"}
    app.state.benchmark_progress = {
        "running": True, "error": None, "total_requests": len(pending),
        "completed_requests": 0,
    }
    app.state.benchmark_task = asyncio.create_task(_run(app, body.case_ids))
    return {"started": True, "pending": len(pending)}


@router.post("/stop")
async def stop(request: Request):
    guard(request)
    task = request.app.state.benchmark_task
    if task is not None and not task.done():
        task.cancel()
        return {"stop_requested": True}
    return {"stop_requested": False}


class ScoringRequest(BaseModel):
    scores: dict[str, dict[str, int | str]]


@router.post("/case/{case_id}/score")
async def score(case_id: str, body: ScoringRequest, request: Request):
    guard(request)
    if request.app.state.benchmark_progress.get("running"):
        raise HTTPException(409, "Finish the active model run before scoring")
    try:
        workspace(request).score(case_id, body.scores)
    except BenchmarkError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"saved": True}


@router.get("/report")
async def report(request: Request):
    guard(request)
    try:
        return workspace(request).report()
    except BenchmarkError as exc:
        raise HTTPException(404, str(exc)) from None


class DeleteRequest(BaseModel):
    confirm_delete: StrictBool


@router.post("/delete")
async def delete(body: DeleteRequest, request: Request):
    guard(request)
    if not body.confirm_delete:
        raise HTTPException(400, "Deletion must be explicitly confirmed")
    if request.app.state.benchmark_progress.get("running"):
        raise HTTPException(409, "Stop the benchmark before deleting")
    workspace(request).clear()
    request.app.state.benchmark_progress = {"running": False, "error": None}
    return {"deleted": True}
