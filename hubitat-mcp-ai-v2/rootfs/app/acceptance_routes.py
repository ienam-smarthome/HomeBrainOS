"""Private, operator-driven alpha.150 acceptance under the V2 UI boundary."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, StrictBool

from prospective_routes import guard
from prospective_source_ab import ReadOnlyMCP, verify_read_only_client

router = APIRouter()
STUDY = Path("/data/homebrain-v2-alpha150-acceptance")
PRIVATE = {"Cache-Control": "no-store"}
PACKAGE_VERSION = os.environ.get("HOMEBRAIN_PACKAGE_VERSION") or "development"


class Labels(BaseModel):
    labels: dict[str, str]


class CaptureConsent(BaseModel):
    model_and_private_evidence_consent: StrictBool


def _study(request: Request) -> Path:
    guard(request)
    # The production location is fixed. An injected location supports isolated tests.
    return getattr(request.app.state, "acceptance_directory", STUDY)


def _case_path(directory: Path, case_id: str) -> tuple[dict, Path]:
    from source_real_acceptance import _load_manifest, EXPORT_DIRECTORY

    if not directory.exists():
        raise HTTPException(404, "Seal the study first")
    manifest, _ = _load_manifest(directory)
    case = next((row for row in manifest["cases"] if row["id"] == case_id), None)
    if case is None:
        raise HTTPException(404, "Unknown case")
    return case, directory / EXPORT_DIRECTORY / (case_id + ".json")


@router.get("/acceptance")
async def acceptance_page():
    return FileResponse(Path(__file__).with_name("acceptance.html"), headers=PRIVATE)


@router.post("/api/acceptance/prepare")
async def prepare(body: Labels, request: Request):
    from source_real_acceptance import ALPHA150_PACK, AcceptanceError, init_labels

    directory = _study(request)
    if directory.exists():
        raise HTTPException(409, "The study has already been sealed")
    # Make the parent private before the CLI helper writes labels or prompts.
    directory.mkdir(mode=0o700)
    try:
        result = init_labels(body.labels, directory, pack=ALPHA150_PACK)
    except AcceptanceError as exc:
        if not any(directory.iterdir()):
            directory.rmdir()
        raise HTTPException(400, str(exc)) from None
    return JSONResponse(result, headers=PRIVATE)


@router.get("/api/acceptance/status")
async def status(request: Request):
    from source_real_acceptance import AcceptanceError, _load_manifest, EXPORT_DIRECTORY

    directory = _study(request)
    if not directory.exists():
        return JSONResponse({"cases": [], "package_version": PACKAGE_VERSION}, headers=PRIVATE)
    try:
        manifest, seal = _load_manifest(directory)
    except AcceptanceError as exc:
        raise HTTPException(409, str(exc)) from None
    cases = []
    for row in manifest["cases"]:
        path = directory / EXPORT_DIRECTORY / (row["id"] + ".json")
        state = "captured" if path.is_file() else (
            "attempted" if path.with_suffix(".attempt").is_file() else "ready"
        )
        cases.append({"id": row["id"], "question": row["question"], "state": state})
    return JSONResponse({"manifest_sha256": seal, "cases": cases,
                         "package_version": PACKAGE_VERSION}, headers=PRIVATE)


@router.get("/api/acceptance/{case_id}/export")
async def export(case_id: str, request: Request):
    from source_real_acceptance import AcceptanceError

    directory = _study(request)
    try:
        _, path = _case_path(directory, case_id)
    except AcceptanceError as exc:
        raise HTTPException(409, str(exc)) from None
    if not path.is_file():
        raise HTTPException(404, "No original capture is available")
    return FileResponse(path, filename=path.name, media_type="application/json",
                        headers=PRIVATE)


@router.post("/api/acceptance/{case_id}/capture")
async def capture(case_id: str, body: CaptureConsent, request: Request):
    from source_real_acceptance import ALPHA150_VERSION, AcceptanceError

    directory = _study(request)
    if not body.model_and_private_evidence_consent:
        raise HTTPException(400, "Confirm use of the configured model with private evidence")
    app = request.app
    if app.version != ALPHA150_VERSION:
        raise HTTPException(409, "This study requires exactly V2 Preview alpha.150")
    state = app.state
    if state.configuration_error or state.model is None or state.mcp is None:
        raise HTTPException(503, "Configure the V2 model and dedicated read-only MCP client")

    try:
        case, path = _case_path(directory, case_id)
    except AcceptanceError as exc:
        raise HTTPException(409, str(exc)) from None

    async with state.ask_lock:
        marker = path.with_suffix(".attempt")
        if marker.exists() or path.exists():
            raise HTTPException(409, "This case already has a first attempt")
        try:
            await verify_read_only_client(state.mcp)
        except Exception:
            # A permission preflight failure is outside the sealed investigation.
            raise HTTPException(403, "A dedicated per-client Read ON / Write OFF grant could not be verified") from None

        # Exclusive creation protects the first attempt across concurrent requests.
        try:
            with marker.open("x", encoding="utf-8"):
                pass
        except FileExistsError:
            raise HTTPException(409, "This case already has a first attempt") from None

        started = monotonic()
        request_id = str(uuid4())
        monitor = getattr(state, "device_monitor", None)
        try:
            answer = await state.model.answer(
                case["question"], [], ReadOnlyMCP(state.mcp),
                int(state.options["investigation_timeout_seconds"]),
                **({"device_monitor": monitor} if monitor is not None else {}),
            )
        except Exception:
            # Exceptions without a completed response provide no original receipts.
            answer = {
                "success": False, "answer": "Investigation failed before returning an export.",
                "error": "acceptance_capture_failed", "tool_calls": [],
            }

        document = {
            "ui_version": app.version,
            "package_version": PACKAGE_VERSION,
            "model": state.model.model,
            "request_id": request_id,
            "question": case["question"],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "server_elapsed_ms": round((monotonic() - started) * 1000),
            "response": answer,
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
    return JSONResponse({"id": case_id, "captured": True, "response_success": answer.get("success") is True},
                        headers=PRIVATE)


@router.get("/api/acceptance/report")
async def report(request: Request):
    from source_real_acceptance import AcceptanceError, verify

    directory = _study(request)
    if not directory.exists():
        raise HTTPException(404, "Seal the study first")
    try:
        result = verify(directory)
    except AcceptanceError as exc:
        raise HTTPException(409, str(exc)) from None
    result["capture_workflow"] = "in_addon_read_only_catalog"
    result["verification_package_version"] = PACKAGE_VERSION
    return JSONResponse(result, headers=PRIVATE)
