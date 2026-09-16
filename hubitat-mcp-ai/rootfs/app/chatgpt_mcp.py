from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse, Response

import app as core

logger = logging.getLogger("HomeBrainOS.ChatGPTMCP")

DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "homebrainos"


def _enabled() -> bool:
    return core._bool(core.OPTIONS.get("chatgpt_mcp_enabled"), False)


def _configured_token() -> str:
    return str(core.OPTIONS.get("chatgpt_mcp_token") or "").strip()


def _require_bearer_auth() -> bool:
    return core._bool(core.OPTIONS.get("chatgpt_mcp_require_bearer_auth"), True)


def _authorised(request: Request) -> bool:
    if not _require_bearer_auth():
        return True
    token = _configured_token()
    if not token:
        return False
    value = request.headers.get("authorization", "")
    if not value.lower().startswith("bearer "):
        return False
    supplied = value[7:].strip()
    return hashlib.sha256(supplied.encode()).digest() == hashlib.sha256(token.encode()).digest()


def _session_id(request: Request) -> str:
    value = request.headers.get("mcp-session-id", "").strip()
    if value:
        return value[:160]
    return f"mcp-{uuid.uuid4().hex}"


def _jsonrpc_result(request_id: Any, result: Any, *, session_id: str | None = None) -> JSONResponse:
    headers = {"Mcp-Session-Id": session_id} if session_id else None
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result}, headers=headers)


def _jsonrpc_error(
    request_id: Any,
    code: int,
    message: str,
    *,
    session_id: str | None = None,
) -> JSONResponse:
    headers = {"Mcp-Session-Id": session_id} if session_id else None
    return JSONResponse(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
        headers=headers,
    )


def _tool_result(
    text: str,
    structured: Any | None = None,
    *,
    is_error: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }
    if structured is not None:
        result["structuredContent"] = structured
    return result


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "homebrain_status",
            "description": (
                "Read HomeBrainOS, Hubitat MCP and model-provider health. "
                "Use this before troubleshooting connectivity."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "homebrain_dashboard",
            "description": (
                "Read the current HomeBrainOS dashboard snapshot: device count, lights, motion, "
                "switches, low batteries, rooms and hub information."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "homebrain_ask",
            "description": (
                "Send a smart-home request through HomeBrainOS' existing verified agent and safety layer. "
                "Use this for live Hubitat reads, device control, history, automation/rule work and other "
                "HomeBrainOS capabilities. Sensitive changes may return a confirmation request; after the "
                "user explicitly confirms, call this tool again in the same MCP session with that confirmation."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 2000,
                        "description": "Natural-language smart-home request to execute through HomeBrainOS.",
                    }
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            },
        },
    ]


async def _call_tool(
    name: str,
    arguments: dict[str, Any],
    request: Request,
    session_id: str,
) -> dict[str, Any]:
    if name == "homebrain_status":
        status = await core.health()
        return _tool_result(json.dumps(status, ensure_ascii=False), status)

    if name == "homebrain_dashboard":
        dashboard = await core.dashboard()
        return _tool_result(json.dumps(dashboard, ensure_ascii=False), dashboard)

    if name == "homebrain_ask":
        prompt = str(arguments.get("prompt") or "").strip()
        if not prompt:
            return _tool_result(
                "prompt is required",
                {"success": False, "error": "prompt is required"},
                is_error=True,
            )
        chat_request = core.ChatRequest(prompt=prompt, session_id=session_id)
        started = time.perf_counter()
        outcome = await core._answer_result(chat_request, request)
        structured = core.build_agent_response(
            outcome,
            model=core.agent.model_name,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            version=core.VERSION,
        )
        return _tool_result(outcome.message, structured)

    return _tool_result(
        f"Unknown tool: {name}",
        {"success": False, "error": f"Unknown tool: {name}"},
        is_error=True,
    )


@core.app.get("/mcp")
async def mcp_get() -> Response:
    # Streamable HTTP servers may decline the optional SSE GET stream.
    return Response(status_code=405, headers={"Allow": "POST"})


@core.app.post("/mcp")
async def mcp_post(request: Request) -> Response:
    if not _enabled():
        return JSONResponse({"error": "ChatGPT MCP is disabled"}, status_code=503)
    if _require_bearer_auth() and not _configured_token():
        return JSONResponse(
            {"error": "ChatGPT MCP token is not configured"},
            status_code=503,
        )
    if not _authorised(request):
        return JSONResponse(
            {"error": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_id = _session_id(request)
    try:
        payload = await request.json()
    except Exception:
        return _jsonrpc_error(None, -32700, "Parse error", session_id=session_id)

    if not isinstance(payload, dict):
        return _jsonrpc_error(None, -32600, "Invalid Request", session_id=session_id)

    request_id = payload.get("id")
    method = str(payload.get("method") or "")
    params = payload.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _jsonrpc_error(
            request_id,
            -32602,
            "Invalid params",
            session_id=session_id,
        )

    if method == "initialize":
        requested = str(params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION)
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": core.VERSION},
                "instructions": (
                    "HomeBrainOS provides verified Hubitat reads and guarded smart-home actions. "
                    "Use homebrain_ask for smart-home work; preserve the MCP session so sensitive "
                    "confirmations remain isolated to this conversation."
                ),
            },
            session_id=session_id,
        )

    if method == "notifications/initialized":
        return Response(status_code=202, headers={"Mcp-Session-Id": session_id})

    if method == "ping":
        return _jsonrpc_result(request_id, {}, session_id=session_id)

    if method == "tools/list":
        return _jsonrpc_result(
            request_id,
            {"tools": _tool_definitions()},
            session_id=session_id,
        )

    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _jsonrpc_error(
                request_id,
                -32602,
                "Tool arguments must be an object",
                session_id=session_id,
            )
        try:
            result = await _call_tool(name, arguments, request, session_id)
        except Exception as exc:
            logger.exception("ChatGPT MCP tool call failed: %s", name)
            result = _tool_result(
                "HomeBrainOS could not complete the request.",
                {"success": False, "error": str(exc)},
                is_error=True,
            )
        return _jsonrpc_result(request_id, result, session_id=session_id)

    if request_id is None:
        return Response(status_code=202, headers={"Mcp-Session-Id": session_id})

    return _jsonrpc_error(
        request_id,
        -32601,
        "Method not found",
        session_id=session_id,
    )


if __name__ == "__main__":
    uvicorn.run(
        core.app,
        host="0.0.0.0",
        port=8788,
        log_level="info",
        proxy_headers=True,
    )
