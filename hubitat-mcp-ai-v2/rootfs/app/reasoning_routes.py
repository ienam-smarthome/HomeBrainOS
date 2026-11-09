"""Opt-in, isolated, blinded synthetic A/B HTTP routes.

Never reaches a real Hubitat/HA device. Uses only the configured model
endpoint and a fresh in-memory SyntheticMCP for each independent arm.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StrictBool

router=APIRouter(prefix="/api/reasoning-ab")


def guard(request:Request)->None:
    if request.headers.get("x-homebrain-request")!="1":
        raise HTTPException(403,"Open and refresh the current HomeBrainOS interface")


@router.get("/status")
async def status(request:Request):
    guard(request)
    return request.app.state.reasoning_lab.summary(request.app.state.reasoning_progress)


@router.get("/case/{case_id}")
async def case(case_id:str,request:Request):
    guard(request)
    try:
        return request.app.state.reasoning_lab.case(case_id)
    except ValueError as exc:
        raise HTTPException(404,str(exc)) from None


class Start(BaseModel):
    case_id:str
    model_execution_consent:StrictBool
    cloud_transfer_consent:StrictBool
    retry_failed:StrictBool=False


async def _evaluate(app,case_id:str,retry_failed:bool=False):
    state=app.state.reasoning_progress
    try:
        await app.state.reasoning_lab.run_pair(
            case_id,app.state.model,retry_failed=retry_failed,progress=state)
    except asyncio.CancelledError:
        state["error"]="Pair stopped. Existing completed arm retained; no device operations."
        raise
    except ValueError as exc:
        state["error"]=str(exc)
    except Exception:
        # Do not surface raw remote model text or errors in the dashboard.
        state["error"]="Synthetic pair failed. Check model connection and private case receipts."
    finally:
        state["running"]=False


@router.post("/run")
async def run(body:Start,request:Request):
    guard(request)
    app=request.app
    if not body.model_execution_consent:
        raise HTTPException(403,"Approve this fictional A/B model evaluation")
    if (app.state.reasoning_progress.get("running")
            or app.state.autolab_progress.get("running")
            or app.state.benchmark_progress.get("running")):
        raise HTTPException(409,"Another evaluation is already running")
    if app.state.model is None or app.state.configuration_error:
        raise HTTPException(503,"Configure the model in add-on options")
    try:
        app.state.reasoning_lab.can_run(body.case_id,body.retry_failed)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from None
    options=app.state.options
    base=urlsplit(str(options["model_base_url"]))
    remote=(base.hostname not in ("localhost","127.0.0.1","::1")
            or "cloud" in str(options["model_name"]).lower())
    if remote and not body.cloud_transfer_consent:
        raise HTTPException(403,"Approve fictional prompt transfer and possible cloud credits")
    if base.hostname=="ollama.com" and not str(options["model_api_key"]).strip():
        raise HTTPException(503,"Configure an Ollama Cloud API key")
    app.state.reasoning_progress={
        "running":True,"case_id":body.case_id,"arm":"A","error":None}
    app.state.reasoning_task=asyncio.create_task(
        _evaluate(app,body.case_id,body.retry_failed))
    return {"started":True,"case_id":body.case_id,
            "synthetic_only":True,"live_mcp_calls":0,"live_device_actions":0}


@router.post("/stop")
async def stop(request:Request):
    guard(request)
    task=request.app.state.reasoning_task
    if task is not None and not task.done():
        task.cancel()
        return {"stop_requested":True}
    return {"stop_requested":False}


class Score(BaseModel):
    scores:dict[str,dict[str,int|str]]


@router.post("/case/{case_id}/score")
async def score(case_id:str,body:Score,request:Request):
    guard(request)
    if request.app.state.reasoning_progress.get("running"):
        raise HTTPException(409,"Finish the pair before rating")
    try:
        request.app.state.reasoning_lab.score(case_id,body.scores)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from None
    return {"saved":True,"mapping_hidden":True}


@router.get("/report")
async def report(request:Request):
    guard(request)
    return request.app.state.reasoning_lab.report()


class Delete(BaseModel):
    confirm_delete:StrictBool


@router.post("/delete")
async def delete(body:Delete,request:Request):
    guard(request)
    if not body.confirm_delete:
        raise HTTPException(400,"Explicit deletion confirmation required")
    if request.app.state.reasoning_progress.get("running"):
        raise HTTPException(409,"Stop the paired experiment before deleting its records")
    request.app.state.reasoning_lab.delete()
    request.app.state.reasoning_progress={"running":False,"error":None}
    return {"deleted":True}
