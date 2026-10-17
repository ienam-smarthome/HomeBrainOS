"""Opt-in Anthropic Messages adapter for HomeBrain's native MCP tool loop.

Claude and Ollama have distinct wire protocols. All tool execution remains
exclusively in the existing HomeBrain executor, including confirmation gates.
No provider call is made unless the request expressly selects Claude.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from reasoning_policy import observe_assistant_message
from request_metrics import record_active_provider_model

_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"

# Never echo provider error bodies. Anthropic error messages may include
# snippets of model-input instructions, tool arguments, or private content.
_KNOWN_ERROR_TYPES = frozenset({
    "invalid_request_error", "authentication_error", "permission_error",
    "not_found_error", "rate_limit_error", "api_error", "overloaded_error",
    "billing_error",
})


def describe_anthropic_http_error(
    exc: httpx.HTTPStatusError,
) -> tuple[int, str, str | None, str, str]:
    """Return actionable, redacted status and a stable diagnostic category.

    Only the upstream HTTP status and allowlisted error *type* are ever echoed.
    A limited keyword classification may improve 400 diagnostics, but the
    upstream message body itself is never surfaced or logged.
    """
    response = exc.response
    status = response.status_code
    error_type = "unknown"
    hint = ""
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                supplied_type = str(error.get("type") or "")
                if supplied_type in _KNOWN_ERROR_TYPES:
                    error_type = supplied_type
                hint = str(error.get("message") or "")[:2048].casefold()
    except (ValueError, TypeError, UnicodeError):
        pass

    reason = "provider-http-error"
    if status == 400:
        if "tool_use" in hint or "tool_result" in hint:
            reason = "tool-result-format"
            detail = "Claude rejected the tool-call/result transcript."
        elif "input_schema" in hint or "tools" in hint:
            reason = "tool-schema"
            detail = "Claude rejected a tool definition or schema."
        elif "message" in hint or "assistant" in hint or "prefill" in hint:
            reason = "message-format"
            detail = "Claude rejected the conversation message format."
        elif "model" in hint:
            reason = "model-parameter"
            detail = "Claude rejected the model or model parameters."
        else:
            reason = "invalid-request"
            detail = "Claude rejected the API request format."
    elif status == 401:
        reason, detail = "authentication", "Claude rejected the Anthropic API key."
    elif status == 402:
        reason, detail = "billing", "Claude API billing or credits are unavailable."
    elif status == 403:
        reason, detail = "permission", "Claude API access is not permitted for this key."
    elif status == 404:
        reason, detail = "model-unavailable", "Claude model or API endpoint is unavailable to this account."
    elif status == 413:
        reason, detail = "request-too-large", "Claude request is too large for the API."
    elif status == 429:
        reason, detail = "rate-limit", "Claude API rate limit or token quota was reached."
    elif status in (500, 502, 503, 504, 529):
        reason, detail = "provider-unavailable", "Claude API is temporarily unavailable."
    else:
        detail = "Claude API request failed."

    retry_after = str(response.headers.get("retry-after") or "").strip()
    retry_after = retry_after if retry_after.isdigit() and int(retry_after) <= 86400 else None
    # Do not treat the Anthropic response as a Hubitat or MCP error.
    safe = (
        f"{detail} (Anthropic HTTP {status}; type={error_type}; "
        f"category={reason}). No Ollama/Free fallback was attempted."
    )
    return status, safe, retry_after, error_type, reason


def _string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, default=str)


def _tool_calls(value: Any) -> list[dict[str, Any]]:
    return [c for c in (value if isinstance(value, list) else [])
            if isinstance(c, dict) and isinstance(c.get("function"), dict)]


def convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert declared Ollama/OpenAI tool schemas without broadening them."""
    translated = []
    for row in tools:
        if not isinstance(row, dict) or row.get("type") != "function":
            continue
        fn = row.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        parameters = fn.get("parameters")
        schema = parameters if isinstance(parameters, dict) else {
            "type": "object", "properties": {},
        }
        translated.append({
            "name": name,
            "description": str(fn.get("description") or "")[:8192],
            "input_schema": schema,
        })
    return translated


def convert_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Map request-scoped Ollama transcript to Anthropic tool_use/result pairs.

    For host-collected reads with no preceding model tool call, include their
    output as labelled text, NOT invented tool_result/tool_use provenance.
    If a proposed call did not execute, pass a bounded error result rather
    than making the API or the model assume successful tool execution.
    """
    system: list[str] = []
    converted: list[dict[str, Any]] = []
    pending: list[dict[str, str]] = []

    def missing_results() -> None:
        nonlocal pending
        if pending:
            blocks = [
                {"type": "tool_result", "tool_use_id": item["id"],
                 "content": "HomeBrain did not execute this proposed tool.",
                 "is_error": True}
                for item in pending
            ]
            if converted and converted[-1]["role"] == "user" and isinstance(
                converted[-1]["content"], list
            ) and all(b.get("type") == "tool_result"
                      for b in converted[-1]["content"]):
                converted[-1]["content"].extend(blocks)
            else:
                converted.append({"role": "user", "content": blocks})
            pending = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        text = _string(message.get("content"))
        if role == "system":
            if text:
                system.append(text)
            continue
        if role == "tool":
            tool_name = str(message.get("tool_name") or "")
            index = next((i for i, item in enumerate(pending)
                          if item["name"] == tool_name), None)
            if index is not None:
                item = pending.pop(index)
                result = {"type": "tool_result", "tool_use_id": item["id"],
                          "content": text or "(empty tool output)"}
                if converted and converted[-1]["role"] == "user" and isinstance(
                    converted[-1]["content"], list
                ) and all(b.get("type") == "tool_result"
                          for b in converted[-1]["content"]):
                    converted[-1]["content"].append(result)
                else:
                    converted.append({"role": "user", "content": [result]})
            else:
                missing_results()
                converted.append({
                    "role": "user",
                    "content": f"HOST-REPORTED TOOL EVIDENCE ({tool_name or 'unnamed'}):\n{text}",
                })
            continue
        if role not in {"assistant", "user"}:
            continue
        missing_results()
        if role == "assistant":
            calls = _tool_calls(message.get("tool_calls"))
            blocks: list[dict[str, Any]] = []
            if text:
                blocks.append({"type": "text", "text": text})
            for call in calls:
                fn = call["function"]
                name = str(fn.get("name") or "")
                tool_id = str(call.get("id") or "")
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (ValueError, TypeError):
                        args = {}
                if not (name and tool_id.startswith("toolu_") and isinstance(args, dict)):
                    blocks.append({"type": "text", "text":
                                   f"Prior model proposed {name or 'a tool'}; no authenticated tool-use ID."})
                    continue
                blocks.append({"type": "tool_use", "id": tool_id, "name": name,
                               "input": args})
                pending.append({"name": name, "id": tool_id})
            if blocks:
                converted.append({"role": "assistant", "content": blocks})
        else:
            converted.append({"role": "user", "content": text or "(empty input)"})
    missing_results()
    if not converted:
        converted = [{"role": "user", "content": "Please answer the request."}]
    return "\n\n".join(system), converted


class AnthropicMessagesTransport:
    """One explicit Claude round. No retries, key rotation or model fallback."""

    def __init__(self, client: Any, *, api_key: str, model: str, timeout: float):
        self.client = client
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip() and self.model.strip())

    async def chat(
        self, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Claude API key and model must be configured in add-on options")
        system, converted = convert_messages(messages)
        tool_declarations = convert_tools(tools)
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": converted,
        }
        if system:
            request["system"] = system
        if tool_declarations:
            request["tools"] = tool_declarations
        started = time.monotonic()
        response = await self.client.post(
            _ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=request,
            timeout=httpx.Timeout(max(3.0, self.timeout)),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise RuntimeError("Claude API response was missing structured content")
        text_parts: list[str] = []
        calls: list[dict[str, Any]] = []
        for block in payload["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                name, tool_id, arguments = (
                    block.get("name"), block.get("id"), block.get("input"),
                )
                if not (isinstance(name, str) and isinstance(tool_id, str)
                        and tool_id.startswith("toolu_") and isinstance(arguments, dict)):
                    raise RuntimeError("Claude API returned an invalid tool-use block")
                calls.append({
                    "id": tool_id,
                    "function": {"name": name, "arguments": arguments},
                })
        if not text_parts and not calls:
            raise RuntimeError("Claude API returned no final text or tool calls")
        normalized: dict[str, Any] = {
            "role": "assistant",
            "content": "\n".join(text_parts),
        }
        if calls:
            normalized["tool_calls"] = calls
        observe_assistant_message(normalized)
        record_active_provider_model(self.model, "anthropic")
        # Never log prompts, HTTP bodies, tool arguments, or credentials.
        return normalized
