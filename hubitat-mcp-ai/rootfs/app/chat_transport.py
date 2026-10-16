from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from reasoning_policy import observe_assistant_message, prepare_reasoning_turn
from household_ollama_accounts import (
    HouseholdCloudAccount, permissible_cloud_failover,
)
from request_metrics import increment_active_metric


logger = logging.getLogger("HomeBrainOS.ChatTransport")


class EmptyOllamaAssistantMessage(RuntimeError):
    """The provider completed a round without final text or native tool calls."""

# Ollama's native `think` field is model-family-specific. Keep the allow-list
# deliberately conservative: these are reasoning families HomeBrain currently
# uses or explicitly supports. Unknown/local models retain their prior request
# shape rather than risking an unsupported option.
_THINKING_MODEL_PREFIXES = (
    "gemma4",
    "qwen3",
    "deepseek-r1",
    "gpt-oss",
)


class ChatTransport:
    """Owns the Ollama HTTP client and assemble native chat responses.

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

    Reasoning-capable model families receive Ollama's native `think=true`.
    Provider reasoning traces are never returned to the orchestrator: only
    final content and structured tool calls survive response normalization.

    Before each provider round, the generic reasoning policy reinforces the
    current-turn evidence boundary and can remove callable tools once a
    read-only investigation has spent its soft reasoning budget. This keeps
    the orchestration policy generic and applies equally to local/cloud models.
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
        thinking_enabled: bool = True,
        household_cloud_accounts: tuple[HouseholdCloudAccount, ...] = (),
        household_cloud_failover_enabled: bool = False,
        cloud_first: bool = False,
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
        self.thinking_enabled = bool(thinking_enabled)
        self.household_cloud_accounts = (
            tuple(household_cloud_accounts)
            if household_cloud_failover_enabled else ()
        )
        self.household_cloud_failover_enabled = bool(household_cloud_failover_enabled)
        self.cloud_first = bool(cloud_first)
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

    @staticmethod
    def _supports_thinking(model_name: str) -> bool:
        normalized = str(model_name or "").strip().casefold()
        return normalized.startswith(_THINKING_MODEL_PREFIXES)

    @staticmethod
    def _normalized_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
        """Keep only final assistant content and native tool calls.

        Ollama reasoning models may return a separate `thinking` field. It is
        useful inside the provider for tool selection but is intentionally not
        copied into HomeBrain's conversation, logs, evidence, or API response.
        """

        normalized: dict[str, Any] = {
            "role": str(message.get("role") or "assistant"),
            "content": str(message.get("content") or ""),
        }
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            kept = [call for call in calls if isinstance(call, dict)]
            if kept:
                normalized["tool_calls"] = kept
        return normalized

    async def _try_local(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._chat_round(
            messages, tools,
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

    async def _try_cloud_accounts(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Ollama Online API key is not configured")
        account_keys = [("primary", self.api_key)]
        if self.household_cloud_failover_enabled:
            account_keys.extend(
                (acct.account_id, acct.api_key)
                for acct in self.household_cloud_accounts
            )
        for index, (alias, key) in enumerate(account_keys):
            try:
                result = await self._chat_round(
                    messages, tools,
                    base_url=self.base_url,
                    model_name=self.model_name,
                    api_key=key,
                    timeout=httpx.Timeout(self.timeout_seconds),
                    read_timeout=self.timeout_seconds,
                    keep_alive=None,
                )
                if index:
                    increment_active_metric("ollama_authorized_cloud_failover")
                return result
            except Exception as exc:
                # No 429/account-quota bypass. Never replay a request after a
                # response timeout or partial stream. Only pre-response
                # connect failures and 502/503/504 are failover candidates.
                if (
                    index == len(account_keys)-1
                    or not permissible_cloud_failover(exc)
                ):
                    raise
                increment_active_metric("ollama_cloud_failover_eligible")
                logger.warning(
                    "Cloud account %s encountered a retryable infrastructure "
                    "failure; attempting explicitly authorised secondary account",
                    alias,
                )
        raise RuntimeError("No authorised Ollama Cloud account is available")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.local_configured and not self.cloud_first:
            try:
                return await self._try_local(messages, tools)
            except Exception:
                logger.warning(
                    "Local Ollama unavailable; attempting configured cloud",
                    exc_info=False,
                )
        try:
            return await self._try_cloud_accounts(messages, tools)
        except Exception:
            if self.local_configured and self.cloud_first:
                # Final fallback is the locally configured Ollama model.
                # This is independent of household cloud-account usage.
                try:
                    result = await self._try_local(messages, tools)
                    increment_active_metric("ollama_cloud_to_local_fallback")
                    return result
                except Exception:
                    logger.warning("Local Ollama fallback also unavailable")
            raise

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
        prepared_messages, prepared_tools = prepare_reasoning_turn(messages, tools)
        streamed = callable(getattr(self.client, "stream", None))
        try:
            if streamed:
                return await self._chat_stream(
                    prepared_messages,
                    prepared_tools,
                    base_url=base_url,
                    model_name=model_name,
                    api_key=api_key,
                    timeout=timeout,
                    read_timeout=read_timeout,
                    keep_alive=keep_alive,
                )
            return await self._chat_post(
                prepared_messages,
                prepared_tools,
                base_url=base_url,
                model_name=model_name,
                api_key=api_key,
                timeout=timeout,
                keep_alive=keep_alive,
            )
        except EmptyOllamaAssistantMessage:
            # A completed provider round with neither content nor tool calls
            # has NOT executed any MCP tool. Recover this exact model round
            # once, without streaming and without optional reasoning. Never
            # retry timeouts, malformed JSON, status errors or cancelled calls.
            increment_active_metric("ollama_empty_message_recovery")
            logger.warning(
                "Ollama returned no assistant message; retrying one "
                "non-streamed round with thinking disabled (model=%s, "
                "streamed=%s)",
                model_name, streamed,
            )
            try:
                return await self._chat_post(
                    prepared_messages,
                    prepared_tools,
                    base_url=base_url,
                    model_name=model_name,
                    api_key=api_key,
                    timeout=timeout,
                    keep_alive=keep_alive,
                    disable_thinking=True,
                )
            except EmptyOllamaAssistantMessage as exc:
                increment_active_metric("ollama_empty_message_recovery_failed")
                raise EmptyOllamaAssistantMessage(
                    "Ollama returned no assistant message after one "
                    "non-streamed recovery attempt"
                ) from exc
            except Exception:
                increment_active_metric("ollama_empty_message_recovery_failed")
                raise

    def _request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model_name: str,
        *,
        stream: bool,
        keep_alive: float | None,
        disable_thinking: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "tools": tools or None,
            "stream": stream,
            "options": {"temperature": 0.1},
        }
        if disable_thinking and self._supports_thinking(model_name):
            payload["think"] = False
        elif self.thinking_enabled and self._supports_thinking(model_name):
            payload["think"] = True
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
        disable_thinking: bool = False,
    ) -> dict[str, Any]:
        started = time.monotonic()
        response = await self.client.post(
            f"{base_url}/api/chat",
            headers=self._headers(api_key),
            json=self._request(
                messages, tools, model_name, stream=False,
                keep_alive=keep_alive, disable_thinking=disable_thinking
            ),
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise EmptyOllamaAssistantMessage("Ollama returned no assistant message")
        normalized = self._normalized_assistant_message(message)
        if not normalized["content"] and not normalized.get("tool_calls"):
            raise EmptyOllamaAssistantMessage("Ollama returned no assistant message")
        observe_assistant_message(normalized)
        logger.info(
            "Ollama round completed in %.3fs with %d declared tools (%s)",
            time.monotonic() - started,
            len(tools),
            base_url,
        )
        return normalized

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
                # Deliberately ignore message['thinking']; only final content
                # and structured tool calls are retained by HomeBrain.
                if message.get("content"):
                    content.append(str(message["content"]))
                calls = message.get("tool_calls")
                if isinstance(calls, list):
                    tool_calls.extend(
                        call for call in calls if isinstance(call, dict)
                    )
        if not content and not tool_calls:
            raise EmptyOllamaAssistantMessage("Ollama returned no assistant message")
        logger.info(
            "Ollama streamed round completed in %.3fs with %d chunks and "
            "%d declared tools (%s)",
            time.monotonic() - started,
            chunk_count,
            len(tools),
            base_url,
        )
        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        observe_assistant_message(message)
        return message
