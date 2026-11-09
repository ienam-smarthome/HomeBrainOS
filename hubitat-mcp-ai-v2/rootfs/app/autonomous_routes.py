"""HTTP API for synthetic autonomous MCP evaluations; no live hub client."""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StrictBool

from autonomous_lab import AutonomousLab

router=APIRouter(prefix="/api/autonomous")


def guard(request:Request):
    if request.headers.get("x-homebrain-request")!="1":
        raise HTTPException(403,"Open and refresh the current HomeBrainOS interface")


@router.get("/status")
async def status(request:Request):
    guard(request)
    return request.app.state.autolab.summary(request.app.state.autolab_progress)


@router.get("/case/{case_id}")
async def case(case_id:str,request:Request):
    guard(request)
    try:
        return request.app.state.autolab.case(case_id)
    except ValueError as exc:
        raise HTTPException(404,str(exc)) from None


class Start(BaseModel):
    case_id:str
    model_execution_consent:StrictBool
    cloud_transfer_consent:StrictBool
    retry_failed:StrictBool=False


async def _evaluate(app,case_id:str,retry_failed:bool=False):
    state=app.state.autolab_progress
    try:
        await app.state.autolab.run(case_id,app.state.model,retry_failed=retry_failed)
    except asyncio.CancelledError:
        state["error"]="Evaluation stopped; no completed result saved"
        raise
    except ValueError as exc:
        state["error"]=str(exc)
    except Exception:
        # Model errors can contain remote text; never send to the dashboard.
        state["error"]="Synthetic evaluation failed. Check model connection and credits."
    finally:
        state["running"]=False


@router.post("/run")
async def run(body:Start,request:Request):
    guard(request)
    app=request.app
    if not body.model_execution_consent:
        raise HTTPException(403,"Approve this synthetic model execution")
    if app.state.autolab_progress.get("running"):
        raise HTTPException(409,"Another synthetic evaluation is running")
    if (app.state.model is None or app.state.configuration_error):
        raise HTTPException(503,"Configure the model in add-on options")
    if body.case_id not in app.state.autolab.catalog:
        raise HTTPException(400,"Unknown synthetic lab case")
    path=app.state.autolab._answer_path(body.case_id)
    if path.exists():
        previous=app.state.autolab.case(body.case_id)
        if previous.get("success") or previous.get("ratings") is not None:
            raise HTTPException(409,"A completed or graded case cannot be overwritten")
        if not body.retry_failed:
            raise HTTPException(409,"Failed run retained; explicitly request a retry")
        if len(app.state.autolab._failed_archives(body.case_id))>=2:
            raise HTTPException(409,"Retry limit reached; use explicit reset")
    elif body.retry_failed:
        raise HTTPException(400,"No previous failed case to retry")
    options=app.state.options
    base=urlsplit(str(options["model_base_url"]))
    remote=(base.hostname not in ("localhost","127.0.0.1","::1")
            or "cloud" in str(options["model_name"]).lower())
    if remote and not body.cloud_transfer_consent:
        raise HTTPException(403,"Approve synthetic prompt transfer and possible cloud costs")
    if base.hostname=="ollama.com" and not str(options["model_api_key"]).strip():
        raise HTTPException(503,"Configure an Ollama Cloud API key")
    app.state.autolab_progress={"running":True,"case_id":body.case_id,
                                "started":True,"error":None}
    app.state.autolab_task=asyncio.create_task(_evaluate(app,body.case_id,body.retry_failed))
    return {"started":True,"case_id":body.case_id,
            "synthetic_only":True,"live_mcp_calls":0}


@router.post("/stop")
async def stop(request:Request):
    guard(request)
    task=request.app.state.autolab_task
    if task is not None and not task.done():
        task.cancel()
        return {"stop_requested":True}
    return {"stop_requested":False}


class Score(BaseModel):
    scores:dict[str,int|str]


@router.post("/case/{case_id}/score")
async def score(case_id:str,body:Score,request:Request):
    guard(request)
    if request.app.state.autolab_progress.get("running"):
        raise HTTPException(409,"Finish the evaluation before scoring")
    try:
        request.app.state.autolab.score(case_id,body.scores)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from None
    return {"saved":True}


@router.get("/report")
async def report(request:Request):
    guard(request)
    return request.app.state.autolab.report()


class Delete(BaseModel):
    confirm_delete:StrictBool


@router.post("/delete")
async def delete(body:Delete,request:Request):
    guard(request)
    if not body.confirm_delete:
        raise HTTPException(400,"Explicit deletion confirmation required")
    if request.app.state.autolab_progress.get("running"):
        raise HTTPException(409,"Stop the evaluation before deleting records")
    request.app.state.autolab.delete()
    request.app.state.autolab_progress={"running":False,"error":None}
    return {"deleted":True}
