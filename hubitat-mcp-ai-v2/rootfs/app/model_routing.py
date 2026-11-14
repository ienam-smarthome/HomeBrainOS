"""V2 local Ollama first; opt-in, free-model cloud backup on CONNECT failure only.

The model chooses every MCP tool. The router chooses only the inference host,
before a first successful model round. Once a request receives any local model
response, it stays local: never replay an ambiguous write or mix model
contexts mid-investigation. Cloud is explicit and leaks no key to the browser.
"""
from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from typing import Any

import httpx

from agent import Agent, ModelEndpointUnavailable


def free_model_name(name: str) -> str:
    """Free OpenRouter-only model IDs prevent accidentally selecting paid routes."""
    value = str(name).strip()
    if not value or not (value == "openrouter/free" or value.endswith(":free")):
        raise ValueError(
            "Cloud fallback accepts only openrouter/free or an explicit :free model"
        )
    if len(value) > 160 or any(char.isspace() for char in value):
        raise ValueError("Invalid cloud free-model identifier")
    return value


def openai_messages(original: list[dict]) -> list[dict]:
    """Map Ollama-style tool messages to OpenAI chat-completions tool pairing.

    Upstream model outputs can contain a list of tool calls without IDs. IDs
    are recreated deterministically at every model round from prior message
    positions. Each native tool receipt maps to the issuing assistant call;
    no content or tool arguments are invented or interpreted.
    """
    result: list[dict] = []
    waiting: list[tuple[str, str]] = []
    for index, entry in enumerate(original):
        role = entry.get("role") if isinstance(entry, dict) else None
        if role in ("system", "user"):
            result.append({"role": role, "content": entry.get("content", "")})
        elif role == "assistant":
            calls = entry.get("tool_calls")
            if not isinstance(calls, list) or not calls:
                result.append({"role": "assistant", "content": entry.get("content", "")})
                continue
            formatted = []
            for offset, call in enumerate(calls):
                fun = call.get("function") if isinstance(call, dict) else None
                if not isinstance(fun, dict) or not isinstance(fun.get("name"), str):
                    raise ValueError("Model tool call lacks a function name")
                call_id = f"hb_{index}_{offset}"
                raw = fun.get("arguments", {})
                arguments = raw if isinstance(raw, str) else json.dumps(raw)
                formatted.append({
                    "id": call_id,
                    "type": "function",
                    "function": {"name": fun["name"], "arguments": arguments},
                })
                waiting.append((fun["name"], call_id))
            result.append({
                "role": "assistant",
                "content": entry.get("content") or None,
                "tool_calls": formatted,
            })
        elif role == "tool":
            name = entry.get("tool_name")
            match = next((i for i, (tool_name, _) in enumerate(waiting)
                          if tool_name == name), -1)
            if match < 0:
                raise ValueError("Unpaired model tool result; cannot change providers")
            call_id = waiting.pop(match)[1]
            result.append({
                "role": "tool", "tool_call_id": call_id,
                "content": str(entry.get("content", "")),
            })
        else:
            raise ValueError("Unsupported model conversation role")
    if waiting:
        raise ValueError("Model tool calls lack matching source receipts")
    return result


class OpenRouterFree:
    """Explicit server-side key; only the provider's free model routes."""
    BASE = "https://openrouter.ai/api/v1"

    def __init__(self, *, model: str, api_key: str, timeout: int):
        self.model = free_model_name(model)
        if not str(api_key).strip():
            raise ValueError("Cloud fallback requires an OpenRouter API key")
        self.timeout = max(10, int(timeout))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(self.timeout), connect=5.0),
            follow_redirects=False, trust_env=False,
            headers={
                "Authorization": "Bearer " + str(api_key).strip(),
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def round(self, messages: list[dict], tools: list[dict],
                    remaining: float) -> dict:
        try:
            response = await asyncio.wait_for(self.client.post(
                self.BASE + "/chat/completions",
                json={
                    "model": self.model,
                    "messages": openai_messages(messages),
                    **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                    "stream": False,
                },
            ), timeout=min(float(self.timeout), remaining))
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # No provider response text: it can contain credentials or home data.
            raise RuntimeError(
                f"Cloud fallback returned HTTP {exc.response.status_code}"
            ) from None
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise RuntimeError("Cloud fallback model request timed out") from None
        except httpx.RequestError:
            raise RuntimeError("Could not contact the cloud fallback endpoint") from None
        except ValueError:
            raise RuntimeError("Cloud fallback conversation format invalid") from None
        try:
            body = response.json()
            choice = body["choices"][0]["message"]
            if not isinstance(choice, dict):
                raise ValueError("missing assistant response")
            function_calls = []
            for raw in (choice.get("tool_calls") or []):
                if not isinstance(raw, dict):
                    raise ValueError("invalid cloud tool call")
                fun = raw.get("function")
                if not isinstance(fun, dict) or not isinstance(fun.get("name"), str):
                    raise ValueError("invalid cloud tool call")
                arguments = fun.get("arguments", "{}")
                function_calls.append({"function": {
                    "name": fun["name"], "arguments": arguments,
                }})
            return {
                "content": choice.get("content") or "",
                "tool_calls": function_calls,
            }
        except (ValueError, KeyError, TypeError, IndexError):
            raise RuntimeError("Cloud fallback returned an invalid model response") from None


class RoutedAgent(Agent):
    """Drop-in V2 Agent, with inference routing isolated per Ask task."""

    def __init__(self, base_url: str, model: str, api_key: str, model_timeout: int,
                 cpu_cores: int = 4, *, cloud_fallback_enabled: bool = False,
                 cloud_fallback_model: str = "openrouter/free",
                 cloud_fallback_api_key: str = ""):
        super().__init__(base_url, model, api_key, model_timeout, cpu_cores=cpu_cores)
        self.cloud_enabled = bool(cloud_fallback_enabled)
        self.cloud = (
            OpenRouterFree(model=cloud_fallback_model,
                           api_key=cloud_fallback_api_key,
                           timeout=model_timeout)
            if self.cloud_enabled else None
        )
        self._route: ContextVar[dict | None] = ContextVar(
            f"homebrain_route_{id(self)}", default=None,
        )
        self.last_attempt: dict[str, Any] = {
            "provider": "not_used", "cloud_fallback_used": False,
        }

    async def close(self) -> None:
        await super().close()
        if self.cloud is not None:
            await self.cloud.close()

    def route_status(self) -> dict[str, Any]:
        return {
            "primary": "ollama", "primary_model": self.model,
            "fallback_enabled": self.cloud is not None,
            "fallback_provider": "openrouter" if self.cloud else None,
            "fallback_model": self.cloud.model if self.cloud else None,
            "last_attempt": dict(self.last_attempt),
            "status_basis": "last model attempt; no reachability check performed",
        }

    def _attempt(self, state: dict) -> dict:
        using_cloud = state["provider"] == "cloud"
        return {
            "provider": state["provider"],
            "model": self.cloud.model if using_cloud and self.cloud else self.model,
            "cloud_fallback_used": using_cloud,
            "reason": ("local_connect_failed" if using_cloud else None),
        }

    async def answer(self, *args, **kwargs) -> dict:
        state = {"provider": None}
        token = self._route.set(state)
        try:
            result = await super().answer(*args, **kwargs)
            # Only request-scope provenance; no secret or URL in Technical JSON.
            result["model_route"] = self._attempt(state)
            return result
        finally:
            self._route.reset(token)

    async def round(self, messages: list[dict], tools: list[dict],
                    remaining: float) -> dict:
        state = self._route.get()
        standalone = state is None
        if standalone:
            state = {"provider": None}
            token = self._route.set(state)
        try:
            if state["provider"] == "cloud":
                return await self.cloud.round(messages, tools, remaining)
            try:
                response = await super().round(messages, tools, remaining)
            except ModelEndpointUnavailable:
                if state["provider"] == "local":
                    raise ModelEndpointUnavailable(
                        "Local model disconnected mid-request; cloud handoff "
                        "was not attempted after a successful model round"
                    ) from None
                if self.cloud is None:
                    raise
                # Only a primary connect failure before the first completed
                # model round permits opt-in cloud transmission.
                state["provider"] = "cloud"
                self.last_attempt = self._attempt(state)
                return await self.cloud.round(messages, tools, remaining)
            state["provider"] = "local"
            self.last_attempt = self._attempt(state)
            return response
        finally:
            if standalone:
                self._route.reset(token)
