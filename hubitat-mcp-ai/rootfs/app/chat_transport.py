from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx


logger = logging.getLogger("HomeBrainOS.ChatTransport")


class ChatTransport:
    """Own the Ollama HTTP client and assemble native chat responses.

    Supports an optional local Ollama instance (e.g. a machine on the same
    network running `ollama serve`) as a first-choice target, with automatic
    fallback to the cloud endpoint whenever the local instance is not
    configured, unreachable, or errors. This is a plain try-then-fallback --
    there is no persistent "local is down" state -- so if local comes back
    online, the very next request uses it again without any restart.

    The local attempt uses a *split* timeout rather than one flat number:
    `local_connect_timeout_seconds` bounds how long we wait to even reach
    the local instance (fails fast if it's off or unreachable), while
    `local_timeout_seconds` bounds how long we wait for a response *after*
    connecting -- generously, because Ollama loads a model into memory on
    first use after it has been idle, and that cold load alone can take
    several seconds. A single flat timeout would either be too long for the
    "nothing is listening" case or too short for the "just woke up and is
    loading the model" case; splitting it avoids that tradeoff.

    `local_keep_alive_seconds` is sent as Ollama's own `keep_alive` option
    on local requests only, so the local model unloads from memory after
    that many idle seconds instead of relying on Ollama's undocumented-here
    default. It is never sent to the cloud endpoint, which doesn't manage
    memory this way.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemma4:31b-cloud",
        *,
        base_url: str = "https://ollama.com",
        timeout_seconds: float = 60,
        stream_idle_timeout_seconds: float = 20,
        client: Any | None = None,
        local_base_url: str = "",
        local_model_name: str = "",
        local_timeout_seconds: float = 12,
        local_connect_timeout_seconds: float = 3,
        local_keep_alive_seconds: float = 120,
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
        self.local_base_url = str(local_base_url or "").rstrip("/")
        self.local_model_name = str(local_model_name or "").strip()
        self.local_timeout_seconds = max(1.0, float(local_timeout_seconds))
        self.local_connect_timeout_seconds = max(
            0.5, float(local_connect_timeout_seconds)
        )
        self.local_keep_alive_seconds = float(local_keep_alive_seconds)
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model_name and self.base_url)

    @property
    def local_configured(self) -> bool:
        return bool(self.local_base_url and self.local_model_name)

    async def close(self) -> None:
        close = getattr(self.client, "aclose", None)
        if callable(close):
            await close()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.local_configured:
            try:
                return await self._chat_round(
                    messages,
                    tools,
                    base_url=self.local_base_url,
                    model_name=self.local_model_name,
                    api_key="",
                    timeout=httpx.Timeout(
                        self.local_timeout_seconds,
                        connect=self.local_connect_timeout_seconds,
                    ),
                    read_timeout=self.local_timeout_seconds,
                    keep_alive=self.local_keep_alive_seconds,
                )
            except Exception:
                logger.warning(
                    "Local Ollama at %s unreachable or failed; falling back "
                    "to cloud",
                    self.local_base_url,
                    exc_info=True,
                )
        if not self.configured:
            raise RuntimeError("Ollama Online API key is not configured")
        return await self._chat_round(
            messages,
            tools,
            base_url=self.base_url,
            model_name=self.model_name,
            api_key=self.api_key,
            timeout=httpx.Timeout(self.timeout_seconds),
            read_timeout=self.timeout_seconds,
            keep_alive=None,
        )

    async def _chat_round(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        base_url: str,
        model_name: str,
        api_key: str,
        timeout: httpx.Timeout,
        read_timeout: float,
        keep_alive: float | None,
    ) -> dict[str, Any]:
        if callable(getattr(self.client, "stream", None)):
            return await self._chat_stream(
                messages,
                tools,
                base_url=base_url,
                model_name=model_name,
                api_key=api_key,
                timeout=timeout,
                read_timeout=read_timeout,
                keep_alive=keep_alive,
            )
        return await self._chat_post(
            messages,
            tools,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            timeout=timeout,
            keep_alive=keep_alive,
        )

    def _request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model_name: str,
        *,
        stream: bool,
        keep_alive: float | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "tools": tools or None,
            "stream": stream,
            "options": {"temperature": 0.1},
        }
        if keep_alive is not None:
            # Ollama accepts a plain number of seconds here; 0 unloads
            # immediately after the response, a positive number keeps the
            # model warm for that long after last use.
            payload["keep_alive"] = keep_alive
        return payload

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def _chat_post(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        base_url: str,
        model_name: str,
        api_key: str,
        timeout: httpx.Timeout,
        keep_alive: float | None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        response = await self.client.post(
            f"{base_url}/api/chat",
            headers=self._headers(api_key),
            json=self._request(
                messages, tools, model_name, stream=False, keep_alive=keep_alive
            ),
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama round completed in %.3fs with %d declared tools (%s)",
            time.monotonic() - started,
            len(tools),
            base_url,
        )
        return message

    async def _chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        base_url: str,
        model_name: str,
        api_key: str,
        timeout: httpx.Timeout,
        read_timeout: float,
        keep_alive: float | None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        first_chunk_at: float | None = None
        chunk_count = 0
        content: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        idle_timeout = min(self.stream_idle_timeout_seconds, read_timeout)
        async with self.client.stream(
            "POST",
            f"{base_url}/api/chat",
            headers=self._headers(api_key),
            json=self._request(
                messages, tools, model_name, stream=True, keep_alive=keep_alive
            ),
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            lines = response.aiter_lines()
            while True:
                try:
                    line = await asyncio.wait_for(
                        anext(lines), timeout=idle_timeout
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError as exc:
                    elapsed = time.monotonic() - started
                    logger.warning(
                        "Ollama stream stalled after %.3fs and %d chunks (%s)",
                        elapsed,
                        chunk_count,
                        base_url,
                    )
                    raise TimeoutError(
                        "Ollama stream produced no data for "
                        f"{idle_timeout:g}s "
                        f"after {elapsed:.1f}s and {chunk_count} chunks"
                    ) from exc
                if not line.strip():
                    continue
                chunk_count += 1
                if first_chunk_at is None:
                    first_chunk_at = time.monotonic()
                    logger.info(
                        "Ollama first stream chunk arrived in %.3fs (%s)",
                        first_chunk_at - started,
                        base_url,
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
            "Ollama streamed round completed in %.3fs with %d chunks and "
            "%d declared tools (%s)",
            time.monotonic() - started,
            chunk_count,
            len(tools),
            base_url,
        )
        message = {"role": "assistant", "content": "".join(content)}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
