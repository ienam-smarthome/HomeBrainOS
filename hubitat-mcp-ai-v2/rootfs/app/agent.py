"""Direct Ollama <-> native MCP tool loop. The model owns investigation strategy."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from mcp import MCPError, ReadOnlyMCP, redact


_SKILL = (Path(__file__).parent / "skills" / "hubitat" / "SKILL.md").read_text(
    encoding="utf-8"
)
_SKILL = _SKILL.split("---", 2)[-1].strip() if _SKILL.startswith("---") else _SKILL


def model_tools(catalog: list[dict]) -> list[dict]:
    return [{
        "type": "function",
        "function": {
            "name": item["name"],
            "description": str(item.get("description") or item["name"]),
            "parameters": item.get("inputSchema") or {
                "type": "object", "properties": {},
            },
        },
    } for item in catalog]


def arguments_of(call: dict) -> dict:
    raw = call.get("function", {}).get("arguments", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {"_invalid_arguments": "Model returned invalid JSON arguments"}
    if not isinstance(raw, dict):
        return {"_invalid_arguments": "Model arguments were not an object"}
    return raw


def compact_tool_result(value: dict, max_chars: int = 90000) -> str:
    content = json.dumps(redact(value), ensure_ascii=False, default=str)
    if len(content) <= max_chars:
        return content
    # Memory bound on model context, never pretend the full source was inspected.
    return json.dumps({
        "truncated": True, "returned_characters": len(content),
        "visible_prefix": content[:max_chars],
        "note": "The original MCP source was larger than the context transport limit. Re-query with a narrower tool scope.",
    }, ensure_ascii=False)


class Agent:
    def __init__(self, base_url: str, model: str, api_key: str, model_timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model.removesuffix("-cloud")
        self.timeout = max(10, int(model_timeout))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(self.timeout)),
            follow_redirects=False,
            trust_env=False,
            headers={
                **({"Authorization": "Bearer " + api_key.strip()} if api_key.strip() else {}),
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def round(self, messages: list[dict], tools: list[dict], remaining: float) -> dict:
        try:
            response = await asyncio.wait_for(
                self.client.post(
                    self.base_url + "/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "tools": tools,
                        "stream": False,
                    },
                ),
                timeout=min(self.timeout, remaining),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Model API returned HTTP {exc.response.status_code}") from None
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise RuntimeError("Model request timed out") from None
        except httpx.RequestError:
            raise RuntimeError("Could not contact the model endpoint") from None
        try:
            data = response.json()
        except ValueError:
            raise RuntimeError("Model returned invalid JSON") from None
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, dict):
            raise RuntimeError("Model response contained no assistant message")
        return message

    async def answer(
        self, question: str, history: list[dict], mcp: ReadOnlyMCP,
        deadline_seconds: int,
    ) -> dict[str, Any]:
        started = time.monotonic()
        deadline = started + max(30, int(deadline_seconds))
        catalog = await mcp.list_tools()
        tools = model_tools(catalog)
        history = [
            {"role": row["role"], "content": row["content"][:10000]}
            for row in history[-16:]
            if isinstance(row, dict)
            and row.get("role") in ("user", "assistant")
            and isinstance(row.get("content"), str)
        ]
        messages: list[dict] = [
            {"role": "system", "content": _SKILL},
            *history, {"role": "user", "content": question},
        ]
        receipts: list[dict] = []
        rounds = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {
                    "success": False,
                    "answer": "Investigation deadline reached. Available read receipts are listed below; no unverified conclusion was substituted.",
                    "error": "deadline",
                    "tool_calls": receipts,
                    "rounds": rounds,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }
            message = await self.round(messages, tools, remaining)
            rounds += 1
            calls = message.get("tool_calls") or []
            text = str(message.get("content") or "").strip()
            if not isinstance(calls, list):
                calls = []
            clean_message: dict = {"role": "assistant", "content": text}
            if calls:
                clean_message["tool_calls"] = calls
            messages.append(clean_message)

            if not calls:
                return {
                    "success": bool(text),
                    "answer": text or "The model returned an empty answer.",
                    "tool_calls": receipts,
                    "rounds": rounds,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }

            for call in calls:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                name = str(function.get("name") or "")
                args = arguments_of(call) if isinstance(call, dict) else {}
                started_call = time.monotonic()
                try:
                    if deadline - time.monotonic() <= 0:
                        raise MCPError("Investigation deadline reached before this read")
                    if "_invalid_arguments" in args:
                        raise MCPError(args["_invalid_arguments"])
                    result = await asyncio.wait_for(mcp.call(name, args), timeout=max(0.1, deadline - time.monotonic()))
                    tool_error = bool(result.get("isError"))
                    record = {
                        "name": name, "arguments": redact(args),
                        "success": not tool_error,
                        "elapsed_ms": round((time.monotonic() - started_call) * 1000),
                    }
                    if tool_error:
                        record["error"] = "MCP tool reported isError"
                    content = compact_tool_result(result)
                    record["response_characters"] = len(content)
                except (MCPError, ValueError, asyncio.TimeoutError) as exc:
                    record = {
                        "name": name, "arguments": redact(args), "success": False,
                        "elapsed_ms": round((time.monotonic() - started_call) * 1000),
                        "error": (str(redact(str(exc))) or "Tool deadline exceeded")[:240],
                    }
                    content = json.dumps({"error": record["error"]})
                receipts.append(record)
                messages.append({
                    "role": "tool", "tool_name": name, "content": content,
                })
