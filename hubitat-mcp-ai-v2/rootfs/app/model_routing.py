"""HomeBrainOS V2 cloud-only routing: OpenRouter free/paid or paid Ollama Cloud.

The native MCP agent owns investigation and native write approvals.
The user selects exactly one provider for each installed config. No LAN Ollama,
automatic free-to-paid conversion, cross-provider retry or billing switch.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

import httpx

from agent import Agent
from ollama_cloud import OllamaCloudChat

_FREE_MODEL = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._:-]+$")
_PAID_MODEL = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._:-]+$")


def free_model_name(name: str) -> str:
    """Reject every non-free model route in free mode."""
    value = str(name).strip()
    if (not _FREE_MODEL.fullmatch(value) or len(value) > 160
            or not (value == "openrouter/free" or value.endswith(":free"))):
        raise ValueError("Free cloud mode accepts only openrouter/free or a :free model")
    return value


def paid_model_name(name: str) -> str:
    """Paid inference requires a fixed named model, not an auto router."""
    value = str(name).strip()
    if (not _PAID_MODEL.fullmatch(value) or len(value) > 160
            or value.endswith(":free") or value in (
                "openrouter/free", "openrouter/auto", "openrouter/auto-beta",
            )):
        raise ValueError("Paid mode requires a fixed named chargeable model ID")
    return value


def cloud_configuration(*, mode: str, free_model: str,
                        paid_model: str, paid_consent: bool, api_key: str) -> dict:
    """Validate explicit provider & billing selection before constructing a client."""
    if mode not in ("free", "paid"):
        raise ValueError("Cloud mode must be free or paid")
    if type(paid_consent) is not bool:
        raise ValueError("Paid model consent must be a boolean")
    model = (free_model_name(free_model) if mode == "free"
             else paid_model_name(paid_model))
    if mode == "paid" and not paid_consent:
        raise ValueError("Paid cloud mode requires explicit cloud_paid_consent=true")
    if not str(api_key).strip():
        raise ValueError("Configure an OpenRouter API key for cloud-only V2")
    return {"mode": mode, "model": model}


def openai_messages(original: list[dict]) -> list[dict]:
    """Pair Ollama-format *agent internal* messages with OpenAI tool call IDs.

    This is an internal conversation format, not local model execution.
    Each MCP receipt is matched to an issuing assistant tool call. Nothing
    selects, reorders or executes a native tool and original text stays intact.
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
                    "id": call_id, "type": "function",
                    "function": {"name": fun["name"], "arguments": arguments},
                })
                waiting.append((fun["name"], call_id))
            result.append({
                "role": "assistant", "content": entry.get("content") or None,
                "tool_calls": formatted,
            })
        elif role == "tool":
            name = entry.get("tool_name")
            match = next((i for i, (tool_name, _) in enumerate(waiting)
                          if tool_name == name), -1)
            if match < 0:
                raise ValueError("Unpaired model tool result")
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


class OpenRouterChat:
    """Fixed HTTPS OpenRouter transport; no other model endpoints are reachable."""
    BASE = "https://openrouter.ai/api/v1"

    def __init__(self, *, mode: str, free_model: str, paid_model: str,
                 paid_consent: bool, api_key: str, timeout: int):
        selection = cloud_configuration(
            mode=mode, free_model=free_model, paid_model=paid_model,
            paid_consent=paid_consent, api_key=api_key)
        self.mode = selection["mode"]
        self.model = selection["model"]
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
            # Never return the provider body: it may contain private home data.
            raise RuntimeError(
                f"OpenRouter model request returned HTTP {exc.response.status_code}"
            ) from None
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise RuntimeError("OpenRouter model request timed out") from None
        except httpx.RequestError:
            raise RuntimeError("Could not contact OpenRouter") from None
        except ValueError:
            raise RuntimeError("OpenRouter conversation format invalid") from None
        try:
            body = response.json()
            choice = body["choices"][0]["message"]
            if not isinstance(choice, dict):
                raise ValueError("missing assistant response")
            calls = []
            for raw in (choice.get("tool_calls") or []):
                fun = raw.get("function") if isinstance(raw, dict) else None
                if not isinstance(fun, dict) or not isinstance(fun.get("name"), str):
                    raise ValueError("invalid cloud tool call")
                arguments = fun.get("arguments", "{}")
                if not isinstance(arguments, (str, dict)):
                    raise ValueError("invalid cloud tool arguments")
                calls.append({"function": {
                    "name": fun["name"], "arguments": arguments,
                }})
            # Expose only provider-returned numeric usage, not guessed cost,
            # raw messages, hidden reasoning or credential-bearing response.
            metrics: dict[str, Any] = {}
            usage = body.get("usage") if isinstance(body, dict) else None
            if isinstance(usage, dict):
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    v = usage.get(key)
                    if type(v) is int and v >= 0:
                        metrics[key] = v
                cost = usage.get("cost")
                if type(cost) in (int, float) and 0 <= cost < 1000:
                    metrics["provider_reported_cost_usd"] = round(float(cost), 8)
            reported_model = body.get("model") if isinstance(body, dict) else None
            if isinstance(reported_model, str) and len(reported_model) < 200:
                metrics["provider_reported_model"] = reported_model
            return {
                "content": choice.get("content") or "",
                "tool_calls": calls,
                **({"_inference_metrics": metrics} if metrics else {}),
            }
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise RuntimeError("OpenRouter returned an invalid model response") from None


class CloudAgent(Agent):
    """V2 Agent orchestration with an explicitly selected cloud provider."""

    def __init__(self, *, mode: str = "free",
                 free_model: str = "openrouter/free",
                 paid_model: str = "google/gemini-3.1-flash-lite",
                 paid_consent: bool = False, api_key: str = "",
                 paid_provider: str = "openrouter",
                 ollama_model: str = "nemotron-3-super",
                 ollama_api_key: str = "",
                 model_timeout: int = 120, cpu_cores: int = 4):
        if mode not in ("free", "paid"):
            raise ValueError("Cloud mode must be free or paid")
        if paid_provider not in ("openrouter", "ollama"):
            raise ValueError("Paid provider must be openrouter or ollama")
        if type(paid_consent) is not bool:
            raise ValueError("Paid model consent must be a boolean")
        if mode == "paid" and not paid_consent:
            raise ValueError("Paid cloud mode requires explicit cloud_paid_consent=true")
        # Free ALWAYS remains OpenRouter free, regardless of stored paid
        # provider or key. Only the chosen provider/client is constructed.
        self.provider = "ollama" if mode == "paid" and paid_provider == "ollama" else "openrouter"
        if self.provider == "ollama":
            self.cloud = OllamaCloudChat(
                model=ollama_model, api_key=ollama_api_key,
                paid_consent=paid_consent, timeout=model_timeout,
            )
        else:
            self.cloud = OpenRouterChat(
                mode=mode, free_model=free_model, paid_model=paid_model,
                paid_consent=paid_consent, api_key=api_key,
                timeout=model_timeout,
            )
        self.model = self.cloud.model
        self.timeout = max(10, int(model_timeout))
        self.cpu_cores = max(1, min(64, int(cpu_cores)))
        self.last_attempt: dict[str, Any] = {
            "provider": "not_used", "mode": self.cloud.mode,
        }

    async def close(self) -> None:
        await self.cloud.close()

    def route_status(self) -> dict[str, Any]:
        return {
            "primary": self.provider,
            "primary_model": self.model,
            "mode": self.cloud.mode,
            "paid_mode": self.cloud.mode == "paid",
            "automatic_paid_fallback": False,
            "last_attempt": dict(self.last_attempt),
            "status_basis": "selected model only; no live connectivity probe",
        }

    async def answer(self, *args, **kwargs) -> dict:
        # Existing agent chooses native MCP reads/writes and enforces approvals.
        result = await super().answer(*args, **kwargs)
        result["model_route"] = {
            "provider": "cloud",
            "attempted_provider": self.provider,
            "mode": self.cloud.mode,
            "model": self.model,
            "status": ("completed_model_round" if result.get("rounds", 0) > 0
                       else "no_completed_model_round"),
            "cloud_fallback_used": False,
        }
        return result

    async def round(self, messages: list[dict], tools: list[dict],
                    remaining: float) -> dict:
        # No fallback, retries, or changes of paid/free status.
        self.last_attempt = {"provider": self.provider, "mode": self.cloud.mode}
        return await self.cloud.round(messages, tools, remaining)


_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "fixture_read_state",
        "description": "Return the reported state of a fictional test switch. READ ONLY.",
        "parameters": {
            "type": "object",
            "properties": {
                "fixture_id": {"type": "string", "enum": ["DEMO_SWITCH"]},
            },
            "required": ["fixture_id"],
            "additionalProperties": False,
        },
    },
}


async def probe_cloud_tool_call(agent: CloudAgent) -> dict:
    """Explicit one-shot model-only test; no Hubitat, MCP or home data."""
    started = time.monotonic()
    response = await agent.round([
        {"role": "system", "content": (
            "You are testing function calls. Use the offered read-only "
            "fixture_read_state tool for the fictional switch, not prose."
        )},
        {"role": "user", "content": (
            "Call fixture_read_state with fixture_id DEMO_SWITCH. "
            "Do not guess its state and do not perform any real action."
        )},
    ], [_PROBE_TOOL], min(agent.timeout, 60))
    calls = response.get("tool_calls") or []
    verified = False
    for call in calls:
        fun = call.get("function") if isinstance(call, dict) else None
        if not isinstance(fun, dict) or fun.get("name") != "fixture_read_state":
            continue
        args = fun.get("arguments", {})
        try:
            args = json.loads(args) if isinstance(args, str) else args
        except (ValueError, TypeError):
            continue
        verified = isinstance(args, dict) and args == {"fixture_id": "DEMO_SWITCH"}
        if verified:
            break
    return {
        "tool_call_test_passed": verified,
        "model": agent.model,
        "provider": agent.provider,
        "mode": agent.cloud.mode,
        "model_rounds": 1,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "usage": response.get("_inference_metrics", {}),
        "note": "Synthetic tool request only; no actual tool executed or Hubitat state checked",
    }
