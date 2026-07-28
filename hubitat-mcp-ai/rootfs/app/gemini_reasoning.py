from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _gemini_request(payload: dict[str, Any]) -> dict[str, Any]:
    system_parts: list[dict[str, str]] = []
    contents: list[dict[str, Any]] = []
    for message in list(payload.get("messages") or []):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user").strip().lower()
        content = _text(message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append({"text": content})
            continue
        gemini_role = "model" if role == "assistant" else "user"
        if role == "tool":
            tool_name = str(message.get("tool_name") or "MCP tool").strip()
            content = f"{tool_name} result:\n{content}"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})

    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    generation: dict[str, Any] = {
        "temperature": float(options.get("temperature") or 0),
        "maxOutputTokens": max(1, int(options.get("num_predict") or 240)),
    }
    schema = payload.get("format")
    if isinstance(schema, dict):
        generation["responseMimeType"] = "application/json"
        generation["responseJsonSchema"] = schema
    elif str(schema or "").strip().lower() == "json":
        generation["responseMimeType"] = "application/json"

    request: dict[str, Any] = {
        "contents": contents or [{"role": "user", "parts": [{"text": "Respond briefly."}]}],
        "generationConfig": generation,
        # Explicitly avoid server-side interaction storage where the API supports it.
        "store": False,
    }
    if system_parts:
        request["systemInstruction"] = {"parts": system_parts}
    return request


def _response_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        feedback = payload.get("promptFeedback")
        raise RuntimeError(
            "Gemini returned no candidate"
            + (f": {_text(feedback)}" if feedback else "")
        )
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else {}
    parts = content.get("parts") if isinstance(content, dict) else []
    text = "\n".join(
        str(part.get("text") or "").strip()
        for part in parts or []
        if isinstance(part, dict) and str(part.get("text") or "").strip()
    ).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return text


async def post_gemini_chat(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    payload: dict[str, Any],
    timeout: Any,
) -> httpx.Response:
    if payload.get("tools"):
        raise RuntimeError("Gemini reasoning transport does not execute MCP tools")
    model_path = quote(str(model or "").strip(), safe="._-")
    url = f"{str(base_url).rstrip('/')}/models/{model_path}:generateContent"
    response = await client.post(
        url,
        json=_gemini_request(payload),
        headers={"x-goog-api-key": str(api_key)},
        timeout=timeout,
    )
    response.raise_for_status()
    text = _response_text(response.json())
    return httpx.Response(
        200,
        json={
            "model": model,
            "message": {"role": "assistant", "content": text},
            "done": True,
        },
        request=httpx.Request("POST", url),
    )


__all__ = ["_gemini_request", "_response_text", "post_gemini_chat"]
