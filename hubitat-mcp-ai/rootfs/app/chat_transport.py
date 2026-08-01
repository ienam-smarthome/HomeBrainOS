from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx


logger = logging.getLogger("HomeBrainOS.ChatTransport")


class ChatTransport:
    """Own the Ollama HTTP client and assemble native chat responses."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemma4:31b",
        *,
        base_url: str = "https://ollama.com",
        timeout_seconds: float = 60,
        stream_idle_timeout_seconds: float = 20,
        client: Any | None = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.model_name = str(model_name or "").strip()
        if self.model_name.lower().endswith("-cloud"):
            self.model_name = self.model_name[:-6]
        self.base_url = str(base_url or "https://ollama.com").rstrip("/")
        self.timeout_seconds = max(3.0, float(timeout_seconds))
        self.stream_idle_timeout_seconds = max(
            1.0, float(stream_idle_timeout_seconds)
        )
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model_name and self.base_url)

    async def close(self) -> None:
        close = getattr(self.client, "aclose", None)
        if callable(close):
            await close()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Ollama Online API key is not configured")
        if callable(getattr(self.client, "stream", None)):
            return await self._chat_stream(messages, tools)
        return await self._chat_post(messages, tools)

    def _request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "messages": messages,
            "tools": tools or None,
            "stream": stream,
            "options": {"temperature": 0.1},
        }

    async def _chat_post(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.monotonic()
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=self._request(messages, tools, stream=False),
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama round completed in %.3fs with %d declared tools",
            time.monotonic() - started,
            len(tools),
        )
        return message

    async def _chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.monotonic()
        first_chunk_at: float | None = None
        chunk_count = 0
        content: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=self._request(messages, tools, stream=True),
        ) as response:
            response.raise_for_status()
            lines = response.aiter_lines()
            while True:
                try:
                    line = await asyncio.wait_for(
                        anext(lines), timeout=self.stream_idle_timeout_seconds
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError as exc:
                    elapsed = time.monotonic() - started
                    logger.warning(
                        "Ollama stream stalled after %.3fs and %d chunks",
                        elapsed,
                        chunk_count,
                    )
                    raise TimeoutError(
                        "Ollama stream produced no data for "
                        f"{self.stream_idle_timeout_seconds:g}s "
                        f"after {elapsed:.1f}s and {chunk_count} chunks"
                    ) from exc
                if not line.strip():
                    continue
                chunk_count += 1
                if first_chunk_at is None:
                    first_chunk_at = time.monotonic()
                    logger.info(
                        "Ollama first stream chunk arrived in %.3fs",
                        first_chunk_at - started,
                    )
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Ollama returned invalid streamed JSON") from exc
                if payload.get("error"):
                    raise RuntimeError(str(payload["error"]))
                message = payload.get("message")
                if not isinstance(message, dict):
                    continue
                if message.get("content"):
                    content.append(str(message["content"]))
                calls = message.get("tool_calls")
                if isinstance(calls, list):
                    tool_calls.extend(
                        call for call in calls if isinstance(call, dict)
                    )
        if not content and not tool_calls:
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama streamed round completed in %.3fs with %d chunks and %d declared tools",
            time.monotonic() - started,
            chunk_count,
            len(tools),
        )
        message = {"role": "assistant", "content": "".join(content)}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
