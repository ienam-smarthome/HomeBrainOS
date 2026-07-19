from __future__ import annotations

import asyncio
import json
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


AnswerFactory = Callable[[], Awaitable[dict[str, Any]]]


class ActiveRequestRegistry:
    """Keep one active AI request per browser client and cancel the previous one."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def run(self, client_id: str, factory: AnswerFactory) -> dict[str, Any]:
        key = str(client_id or "default")[:160]
        async with self._lock:
            previous = self._tasks.get(key)
            if previous and not previous.done():
                previous.cancel()
            task = asyncio.create_task(factory(), name=f"hmcp-answer-{key}")
            self._tasks[key] = task

        try:
            return await task
        finally:
            async with self._lock:
                if self._tasks.get(key) is task:
                    self._tasks.pop(key, None)

    async def cancel_all(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def install_cancellable_ask(application: Any) -> ActiveRequestRegistry:
    """Replace the existing /api/ask route with a per-client cancellable wrapper."""
    api = application.app
    original_ask = application.ask
    registry = ActiveRequestRegistry()

    api.router.routes[:] = [
        route
        for route in api.router.routes
        if not (
            getattr(route, "path", None) == "/api/ask"
            and "POST" in (getattr(route, "methods", set()) or set())
        )
    ]

    @api.post("/api/ask", response_model=None)
    async def cancellable_ask(request: Request):
        try:
            payload = await request.json()
            body = application.AskRequest.model_validate(payload)
            client_id = request.headers.get("X-HMCP-Client")
            body_session = str(getattr(body, "session_id", "") or "").strip()
            if not client_id and body_session:
                client_id = body_session
            if not client_id and request.client:
                client_id = request.client.host
            if hasattr(body, "session_id") and not body_session:
                body.session_id = client_id or "default"
            return await registry.run(
                client_id or "default",
                lambda: original_ask(body),
            )
        except asyncio.CancelledError:
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "cancelled": True,
                    "route": "cancelled",
                    "message": "The previous question was stopped by a newer request.",
                },
            )
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "route": "server-error",
                    "intent": "api-exception",
                    "message": (
                        "HomeBrain returned a structured server error instead of a "
                        f"blank Internal Server Error: {type(exc).__name__}: {message}"
                    ),
                    "answered_by": "HomeBrain API error boundary",
                    "technical": json.dumps(
                        {
                            "exception_type": type(exc).__name__,
                            "error": message,
                            "traceback": traceback.format_exc(limit=12),
                        },
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                },
            )

    return registry


__all__ = ["ActiveRequestRegistry", "install_cancellable_ask"]
