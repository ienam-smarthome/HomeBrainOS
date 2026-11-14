"""Direct, paid Ollama Cloud transport for HomeBrainOS V2 (not local Ollama).

Fixed https://ollama.com/api/chat; no proxy, no redirects, no automatic
provider fallbacks or credential exposure to browser/Technical JSON.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx


_CLOUD_MODEL = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9._-]+)?$"
)


def ollama_cloud_model_name(name: str) -> str:
    """Accept a fixed Ollama model ID, not a URL, path or dynamic router.

    Direct ollama.com API model names are those listed by its /api/tags
    (e.g. nemotron-3-super, mimo-v2.6-flash, gemma4:31b). The server
    ultimately verifies whether the selected model is cloud-available.
    """
    value = str(name).strip()
    if len(value) > 160 or not _CLOUD_MODEL.fullmatch(value):
        raise ValueError("Ollama Cloud model must be a fixed model name from ollama.com/api/tags")
    return value


class OllamaCloudChat:
    """Native Ollama Cloud chat transport, paid and explicitly authorised."""

    ENDPOINT = "https://ollama.com/api/chat"

    def __init__(self, *, model: str, api_key: str, paid_consent: bool,
                 timeout: int):
        if paid_consent is not True:
            raise ValueError("Ollama Cloud paid mode requires explicit cloud_paid_consent=true")
        self.model = ollama_cloud_model_name(model)
        if not str(api_key).strip():
            raise ValueError("Configure the Ollama Cloud API key for paid Ollama inference")
        self.mode = "paid"
        self.timeout = max(10, int(timeout))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(self.timeout), connect=5.0),
            follow_redirects=False,
            trust_env=False,
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
            response = await asyncio.wait_for(
                self.client.post(
                    self.ENDPOINT,
                    json={
                        "model": self.model,
                        # Native Ollama tool-call conversation: original
                        # internal agent roles and tool_name receipts.
                        "messages": messages,
                        **({"tools": tools} if tools else {}),
                        "stream": False,
                    },
                ),
                timeout=min(float(self.timeout), float(remaining)),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # The provider's body can contain private home data.
            raise RuntimeError(
                f"Ollama Cloud model request returned HTTP {exc.response.status_code}"
            ) from None
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise RuntimeError("Ollama Cloud model request timed out") from None
        except httpx.RequestError:
            raise RuntimeError("Could not contact Ollama Cloud") from None
        except ValueError:
            raise RuntimeError("Ollama Cloud conversation format invalid") from None

        try:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("response is not an object")
            message = body["message"]
            if not isinstance(message, dict):
                raise ValueError("missing assistant message")
            calls = message.get("tool_calls") or []
            if not isinstance(calls, list):
                raise ValueError("invalid tool calls")
            normalized = []
            for call in calls:
                fun = call.get("function") if isinstance(call, dict) else None
                if not isinstance(fun, dict) or not isinstance(fun.get("name"), str):
                    raise ValueError("invalid function call")
                arguments = fun.get("arguments", {})
                if not isinstance(arguments, (str, dict)):
                    raise ValueError("invalid function arguments")
                normalized.append({"function": {
                    "name": fun["name"], "arguments": arguments,
                }})
            content = message.get("content") or ""
            if not isinstance(content, str):
                raise ValueError("invalid content")
            # Numeric-only Ollama counters. Native Ollama does not promise
            # a per-call USD bill amount, so never infer cost here.
            metrics: dict[str, Any] = {"provider_reported_model": self.model}
            reported = body.get("model")
            if isinstance(reported, str) and len(reported) < 200:
                metrics["provider_reported_model"] = reported
            for key in ("total_duration", "load_duration",
                        "prompt_eval_duration", "eval_duration"):
                val = body.get(key)
                if type(val) is int and val >= 0:
                    metrics[key.removesuffix("_duration") + "_ms"] = round(val / 1e6, 2)
            for key in ("prompt_eval_count", "eval_count"):
                val = body.get(key)
                if type(val) is int and val >= 0:
                    metrics[key] = val
            return {"content": content, "tool_calls": normalized,
                    "_inference_metrics": metrics}
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise RuntimeError("Ollama Cloud returned an invalid model response") from None
