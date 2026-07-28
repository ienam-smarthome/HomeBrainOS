from __future__ import annotations

import json
import logging
import time
from typing import Any

from mcp_agent_orchestrator import UnifiedMCPAgent


logger = logging.getLogger("HomeBrainOS.StreamingAgent")


class StreamingUnifiedMCPAgent(UnifiedMCPAgent):
    """Unified agent using Ollama's incremental NDJSON chat transport.

    Tool-call and text chunks are accumulated into the same assistant-message shape
    expected by the existing orchestration loop. This changes transport only; the
    evidence, confirmation and refusal decisions remain in the parent class.
    """

    @staticmethod
    def _merge_message(target: dict[str, Any], chunk: dict[str, Any]) -> None:
        role = chunk.get("role")
        if role and not target.get("role"):
            target["role"] = role
        content = chunk.get("content")
        if content:
            target["content"] = str(target.get("content") or "") + str(content)
        calls = chunk.get("tool_calls")
        if isinstance(calls, list) and calls:
            target.setdefault("tool_calls", []).extend(calls)

    async def _chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Ollama Online API key is not configured")

        stream_factory = getattr(self.ai_client, "stream", None)
        if not callable(stream_factory):
            # Compatibility for small test doubles and alternate clients. Production
            # httpx.AsyncClient always supplies stream(), so live traffic uses NDJSON.
            return await super()._chat(messages, tools)

        started = time.monotonic()
        assistant: dict[str, Any] = {"role": "assistant", "content": ""}
        async with stream_factory(
            "POST",
            f"{self.base_url}/api/chat",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model_name,
                "messages": messages,
                "tools": tools or None,
                "stream": True,
                "options": {"temperature": 0.1},
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                text = str(line or "").strip()
                if not text:
                    continue
                payload = json.loads(text)
                message = payload.get("message")
                if isinstance(message, dict):
                    self._merge_message(assistant, message)
                error = payload.get("error")
                if error:
                    raise RuntimeError(str(error))

        if not assistant.get("content") and not assistant.get("tool_calls"):
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama streaming round completed in %.3fs with %d declared tools",
            time.monotonic() - started,
            len(tools),
        )
        return assistant


__all__ = ["StreamingUnifiedMCPAgent"]
