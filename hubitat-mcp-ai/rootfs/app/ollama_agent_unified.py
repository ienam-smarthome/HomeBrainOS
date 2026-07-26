from __future__ import annotations

import json
import re
import time
from collections import Counter
from contextvars import ContextVar
from typing import Any

from device_intelligence_index import _attributes, _device_id, _device_rows, _label, _room_name
from mcp_client import MCPTool
from ollama_agent_quality import QualityNaturalHubitatOllamaAgent
from ollama_agent_claude import ClaudeStyleOllamaAgent
from ollama_agent_fast import OllamaUnavailable
from ollama_hybrid_http import HybridOllamaHTTPClient


_TARGETED_DEVICE_SEARCH = "homebrain_search_devices"
_DISCOVERY_TOOLS = {
    _TARGETED_DEVICE_SEARCH,
    "hub_search_tools",
    "hub_get_tool_guide",
    "hub_list_devices",
    "hub_read_devices",
}
_GENERIC_DEVICE_QUERY_WORDS = {
    "all",
    "any",
    "available",
    "device",
    "devices",
    "discover",
    "find",
    "get",
    "inventory",
    "list",
    "my",
    "please",
    "selected",
    "show",
    "the",
}
_TARGETED_DEVICE_LOOKUP = re.compile(
    r"^(?:please\s+)?(?:find|search(?:\s+for)?|locate|look\s+(?:up|for)|"
    r"show\s+(?:me\s+)?(?:matches\s+for\s+)?)(?:the\s+)?(?:device\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)


def _normalise_words(value: str) -> list[str]:
    return [item for item in re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split() if item]


_TARGET_LOCAL_MODEL_BILLIONS = 4.0

_CHAT_MODEL_USED: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_model_used",
    default=None,
)

_CHAT_PROVIDER_USED: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_provider_used",
    default=None,
)

_CHAT_CLOUD_ERROR: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_cloud_error",
    default=None,
)


_FINAL_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The complete user-facing answer only, with no analysis or hidden reasoning.",
        }
    },
    "required": ["answer"],
    "additionalProperties": False,
}

_REASONING_PATTERNS = (
    r"<think>",
    r"\bthe user (?:asked|wants|requested)\b",
    r"\bi have (?:the )?verified .* evidence\b",
    r"\bthe evidence (?:shows|contains|says|indicates)\b",
    r"\blet me (?:check|parse|think|tackle|analyse|analyze|work)\b",
    r"\bfirst,? i (?:need|should|will)\b",
    r"\bnext,? i (?:need|should|will)\b",
    r"\bwait,? (?:the user|i need|the evidence)\b",
    r"\bi should (?:answer|highlight|mention|focus|summarise|summarize)\b",
    r"\bso the key points\b",
    r"^analysis\s*:",
)


class UnifiedAdaptiveMCPAgent(QualityNaturalHubitatOllamaAgent):
    """AI-first Hubitat agent with structured device resolution."""

    def __init__(
        self,
        *args: Any,
        unified_tool_limit: int = 48,
        cloud_enabled: bool = False,
        cloud_model: str = "",
        local_fallback_model: str = "",
        cloud_fallback_local: bool = True,
        cloud_timeout_seconds: float = 25.0,
        direct_cloud_enabled: bool = False,
        direct_cloud_base_url: str = "https://ollama.com",
        direct_cloud_api_key: str = "",
        direct_cloud_model: str = "",
        direct_cloud_fallback_local_proxy: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.unified_tool_limit = max(
            16,
            min(96, int(unified_tool_limit)),
        )

        self.cloud_enabled = bool(cloud_enabled)
        self.cloud_model = str(cloud_model or "").strip()
        self.local_fallback_model = str(
            local_fallback_model or ""
        ).strip()
        self.cloud_fallback_local = bool(
            cloud_fallback_local
        )
        self.cloud_timeout_seconds = max(
            8.0,
            min(90.0, float(cloud_timeout_seconds)),
        )
        self._cloud_present_hint: bool | None = None

        existing_http = self._http
        self._http = HybridOllamaHTTPClient(
            local_base_url=self.base_url,
            cloud_model=self.cloud_model,
            direct_enabled=bool(direct_cloud_enabled),
            direct_base_url=str(
                direct_cloud_base_url or "https://ollama.com"
            ),
            direct_api_key=str(
                direct_cloud_api_key or ""
            ),
            direct_model=str(
                direct_cloud_model or ""
            ),
            fallback_local_proxy=bool(
                direct_cloud_fallback_local_proxy
            ),
            client=existing_http,
        )

    def _exact_model_present(model: str, installed_models: list[str]) -> bool:
        target = str(model or "").strip().lower()
        return bool(target) and any(
            str(name or "").strip().lower() == target for name in installed_models
        )

    def _cloud_model_present(self, installed_models: list[str]) -> bool:
        return bool(
            self.cloud_enabled
            and self.cloud_model
            and self._exact_model_present(self.cloud_model, installed_models)
        )

    async def health(self, force: bool = False) -> dict[str, Any]:
        status = await super().health(force=force)
        transport = self._http
        if not status.get("online"):
            result = dict(status)
            result.update(
                {
                    "direct_cloud_enabled": bool(transport.direct_enabled),
                    "direct_cloud_ready": bool(transport.direct_ready),
                    "direct_cloud_api_key_configured": bool(
                        transport.direct_api_key_configured
                    ),
                    "direct_cloud_model": transport.direct_model or None,
                    "direct_cloud_error": transport.last_direct_error,
                }
            )
            return result

        installed = list(status.get("models") or [])
        cloud_present = self._cloud_model_present(installed)
        local_present = self._exact_model_present(
            self.local_fallback_model,
            installed,
        )
        self._cloud_present_hint = cloud_present

        result = dict(status)
        result["model_present"] = bool(cloud_present or local_present)
        result["cloud_present"] = cloud_present
        result["local_fallback_present"] = local_present
        result["cloud_model"] = self.cloud_model or None
        result["local_fallback_model"] = self.local_fallback_model or None
        result["direct_cloud_enabled"] = bool(transport.direct_enabled)
        result["direct_cloud_ready"] = bool(transport.direct_ready)
        result["direct_cloud_api_key_configured"] = bool(
            transport.direct_api_key_configured
        )
        result["direct_cloud_base_url"] = transport.direct_base_url or None
        result["direct_cloud_model"] = transport.direct_model or None
        result["direct_cloud_error"] = transport.last_direct_error
        result["ollama_provider"] = transport.last_provider()
        return result

    async def runtime_status(self, force: bool = False) -> dict[str, Any]:
        status = await super().runtime_status(force=force)
        installed = list(status.get("installed_models") or [])
        cloud_present = self._cloud_model_present(installed)
        local_present = self._exact_model_present(
            self.local_fallback_model,
            installed,
        )
        transport = self._http
        status.update(
            {
                "cloud_enabled": self.cloud_enabled,
                "cloud_model": self.cloud_model or None,
                "cloud_present": cloud_present,
                "local_fallback_model": self.local_fallback_model or None,
                "local_fallback_present": local_present,
                "cloud_fallback_local": self.cloud_fallback_local,
                "direct_cloud_enabled": bool(transport.direct_enabled),
                "direct_cloud_ready": bool(transport.direct_ready),
                "direct_cloud_api_key_configured": bool(
                    transport.direct_api_key_configured
                ),
                "direct_cloud_base_url": transport.direct_base_url or None,
                "direct_cloud_model": transport.direct_model or None,
                "direct_cloud_fallback_local_proxy": bool(
                    transport.fallback_local_proxy
                ),
                "direct_cloud_error": transport.last_direct_error,
                "ollama_provider": transport.last_provider(),
                "preferred_response_model": (
                    self.cloud_model
                    if cloud_present
                    else self.local_fallback_model
                    if local_present
                    else self.model
                ),
            }
        )
        return status

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        model_token = _CHAT_MODEL_USED.set(None)
        provider_token = _CHAT_PROVIDER_USED.set(None)
        error_token = _CHAT_CLOUD_ERROR.set(None)
        try:
            result = dict(await super().answer(query, history or []))
            actual_model = _CHAT_MODEL_USED.get()
            provider = _CHAT_PROVIDER_USED.get()
            cloud_error = _CHAT_CLOUD_ERROR.get()
            if actual_model and str(result.get("route") or "").startswith("ollama"):
                result["model"] = actual_model
                if "response_model" in result:
                    result["response_model"] = actual_model
                result["ai_provider"] = provider
                if cloud_error:
                    result["cloud_fallback_error"] = cloud_error
            return result
        finally:
            _CHAT_MODEL_USED.reset(model_token)
            _CHAT_PROVIDER_USED.reset(provider_token)
            _CHAT_CLOUD_ERROR.reset(error_token)

    async def _final_answer_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
        temperature: float,
    ) -> dict[str, Any]:
        # Planning calls still need native tool_calls and therefore use the base
        # implementation unchanged. Only final user-facing synthesis is forced
        # through a strict answer schema.
        if tools:
            return await super()._chat(
                model=model,
                messages=messages,
                tools=tools,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )

        final_messages = self._final_only_messages(messages)
        try:
            body = await self._structured_final_chat(
                model=model,
                messages=final_messages,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=max(160, num_predict),
            )
            answer = self._extract_final_answer(body, require_json=True)
        except OllamaUnavailable as structured_error:
            # Older Ollama builds may not support JSON-schema output. Keep a
            # compatibility path, but still reject any visible chain-of-thought.
            try:
                body = await super()._chat(
                    model=model,
                    messages=final_messages,
                    tools=None,
                    timeout_seconds=timeout_seconds,
                    num_ctx=num_ctx,
                    num_predict=max(160, num_predict),
                    temperature=0.0,
                )
                answer = self._extract_final_answer(body, require_json=False)
            except Exception as fallback_error:
                raise OllamaUnavailable(
                    f"Final-answer generation failed: {structured_error}; {fallback_error}"
                ) from fallback_error

        clean_body = dict(body)
        message = dict(clean_body.get("message") or {})
        message["content"] = answer
        message.pop("thinking", None)
        clean_body["message"] = message
        return clean_body

    async def _structured_final_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": _FINAL_ANSWER_SCHEMA,
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": 0,
            },
        }
        try:
            response = await self._http.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise RuntimeError("Ollama returned a non-object response")
            return body
        except Exception as exc:
            text = str(exc) or exc.__class__.__name__
            if "timeout" in text.lower() or "timed out" in text.lower():
                raise OllamaUnavailable(
                    f"Ollama model {model} timed out after {timeout_seconds:g} seconds"
                ) from exc
            raise OllamaUnavailable(
                f"Ollama structured final answer failed for {model}: {text}"
            ) from exc

    def _final_only_messages(
        cls,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        instruction = (
            "/no_think\n"
            "Return only the final answer for the user. Do not reveal analysis, planning, "
            "evidence parsing, hidden reasoning, or phrases such as 'the user asked'. "
            "The response must match the supplied JSON schema exactly: "
            '{"answer":"complete user-facing answer"}.'
        )
        cleaned: list[dict[str, Any]] = []
        system_found = False
        for raw in messages:
            item = dict(raw)
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
            if role == "assistant" and cls._looks_like_reasoning(content):
                # Do not feed a leaked reasoning response back into the next turn.
                continue
            if role == "system":
                system_found = True
                item["content"] = (content.rstrip() + "\n\n" + instruction).strip()
            cleaned.append(item)
        if not system_found:
            cleaned.insert(0, {"role": "system", "content": instruction})
        return cleaned

    def _extract_final_answer(
        cls,
        body: dict[str, Any],
        *,
        require_json: bool,
    ) -> str:
        if str(body.get("done_reason") or "").lower() == "length":
            raise OllamaUnavailable("Ollama final answer was truncated")

        message = body.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise OllamaUnavailable("Ollama returned no final answer")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
        answer = ""
        try:
            decoded = json.loads(content)
            if isinstance(decoded, dict):
                answer = str(decoded.get("answer") or "").strip()
        except Exception:
            if require_json:
                raise OllamaUnavailable("Ollama did not follow the final-answer JSON schema")

        if not answer and not require_json:
            answer = cls._strip_thinking_blocks(content)

        if not answer:
            raise OllamaUnavailable("Ollama returned an empty final answer")
        if cls._looks_like_reasoning(answer):
            raise OllamaUnavailable("Ollama exposed internal reasoning instead of a final answer")
        if cls._looks_incomplete(answer):
            raise OllamaUnavailable("Ollama returned an incomplete final answer")
        return answer.strip()

    def _strip_thinking_blocks(value: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", value, flags=re.I | re.S).strip()
        if "</think>" in text.lower():
            text = re.split(r"</think>", text, flags=re.I)[-1].strip()
        final_match = re.search(
            r"(?:^|\n)(?:final answer|answer)\s*:\s*(.+)$",
            text,
            flags=re.I | re.S,
        )
        return final_match.group(1).strip() if final_match else text

    def _looks_like_reasoning(value: str) -> bool:
        text = str(value or "").strip().lower()
        return any(re.search(pattern, text, flags=re.I | re.S) for pattern in _REASONING_PATTERNS)

    def _looks_incomplete(value: str) -> bool:
        text = str(value or "").rstrip()
        if len(text) < 2:
            return True
        trailing = (
            ":",
            "-",
            "•",
            ",",
            " and",
            " or",
            " but",
            " because",
            " the",
            " a",
        )
        return any(text.lower().endswith(suffix) for suffix in trailing)

    async def _chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
        temperature: float,
    ) -> dict[str, Any]:
        requested_model = str(model or "").strip()
        cloud_requested = bool(
            self.cloud_enabled
            and self.cloud_model
            and requested_model.lower() == self.cloud_model.lower()
        )

        if not cloud_requested:
            body = await self._final_answer_chat(
                model=requested_model,
                messages=messages,
                tools=tools,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )
            result = dict(body)
            result["_homebrain_model_used"] = requested_model
            result["_homebrain_provider"] = self._http.last_provider("Local Ollama")
            _CHAT_MODEL_USED.set(requested_model)
            _CHAT_PROVIDER_USED.set(self._http.last_provider("Local Ollama"))
            return result

        cloud_error: Exception | None = None
        if self._cloud_present_hint is not False:
            cloud_timeout = min(
                self.cloud_timeout_seconds,
                max(8.0, float(timeout_seconds)),
            )
            try:
                body = await self._final_answer_chat(
                    model=requested_model,
                    messages=messages,
                    tools=tools,
                    timeout_seconds=cloud_timeout,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                    temperature=temperature,
                )
                provider = self._http.last_provider("Ollama Cloud")
                result = dict(body)
                result["_homebrain_model_used"] = requested_model
                result["_homebrain_provider"] = provider
                _CHAT_MODEL_USED.set(requested_model)
                _CHAT_PROVIDER_USED.set(provider)
                return result
            except Exception as exc:
                cloud_error = exc
        else:
            cloud_error = OllamaUnavailable(
                f"Ollama Cloud model {requested_model} is unavailable"
            )

        if (
            not self.cloud_fallback_local
            or not self.local_fallback_model
            or self.local_fallback_model.lower() == requested_model.lower()
        ):
            assert cloud_error is not None
            raise cloud_error

        body = await self._final_answer_chat(
            model=self.local_fallback_model,
            messages=messages,
            tools=tools,
            timeout_seconds=max(8.0, float(timeout_seconds)),
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
        )
        cloud_error_text = str(cloud_error) or cloud_error.__class__.__name__
        result = dict(body)
        result["_homebrain_model_used"] = self.local_fallback_model
        result["_homebrain_provider"] = "Local Ollama fallback"
        result["_homebrain_cloud_error"] = cloud_error_text
        _CHAT_MODEL_USED.set(self.local_fallback_model)
        _CHAT_PROVIDER_USED.set("Local Ollama fallback")
        _CHAT_CLOUD_ERROR.set(cloud_error_text)
        return result

    def _preferred_family_model(self, installed_models: list[str]) -> str:
        local_target = self.local_fallback_model or self.model
        response_family = local_target.split(":", 1)[0].lower()
        candidates = [
            name
            for name in installed_models
            if name
            and name.split(":", 1)[0].lower() == response_family
            and not name.lower().endswith("-cloud")
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
        ]
        if not candidates:
            return local_target

        def model_size(name: str) -> float:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            return float(match.group(1)) if match else 999.0

        def preference_key(name: str) -> tuple[float, int, float, str]:
            size = model_size(name)
            distance = abs(size - _TARGET_LOCAL_MODEL_BILLIONS)
            below_target = 1 if size < _TARGET_LOCAL_MODEL_BILLIONS else 0
            return distance, below_target, size, name.lower()

        candidates.sort(key=preference_key)
        return candidates[0]

    def _select_compact_tools(self, query: str, tools: list[MCPTool]) -> list[MCPTool]:
        unique: dict[str, MCPTool] = {}
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if name:
                unique.setdefault(name, tool)

        def priority(tool: MCPTool) -> tuple[int, str]:
            name = str(tool.name)
            if name == _TARGETED_DEVICE_SEARCH:
                return -1, name
            if name in _DISCOVERY_TOOLS:
                return 0, name
            if name.startswith("hub_read_"):
                return 1, name
            if name.startswith("hub_manage_"):
                return 2, name
            if name.startswith("hub_"):
                return 3, name
            return 4, name

        ordered = sorted(unique.values(), key=priority)
        return ordered[: self.unified_tool_limit]

    def _planner_prompt(self) -> str:
        return (
            super()._planner_prompt()
            + "\n\nUnified-agent rules: when the user names or describes a particular "
            "physical device, call homebrain_search_devices first with only the current "
            "request's natural description. Use hub_read_devices afterwards when more live "
            "detail is required. When the user asks broadly to list, find or show devices "
            "without a distinguishing name, room or capability, call hub_list_devices rather "
            "than hub_read_devices. Do not reuse an entity from conversation history unless "
            "the current request explicitly refers to it. Do not use hub_search_tools to find "
            "physical devices. Tool-catalogue discovery is never authoritative home data. ""discovery is never the final step for a live-home question. After discovery, ""call hub_list_devices, hub_read_devices, homebrain_search_devices, or another ""authoritative MCP tool before producing the final answer."
        )

    def _is_broad_device_inventory_request(self, query: str) -> bool:
        words = _normalise_words(query)
        if not words or not any(word in {"device", "devices", "inventory"} for word in words):
            return False
        distinguishing = [word for word in words if word not in _GENERIC_DEVICE_QUERY_WORDS]
        return not distinguishing

    @staticmethod
    def _targeted_device_lookup(query: str) -> str | None:
        """Return the requested device description for an explicit lookup request."""

        match = _TARGETED_DEVICE_LOOKUP.fullmatch(str(query or "").strip())
        if not match:
            return None
        requested = " ".join(match.group(1).strip(" .!?").split())
        requested = re.sub(
            r"^(?:the\s+)?(?:device\s+)?",
            "",
            requested,
            flags=re.IGNORECASE,
        ).strip()
        requested = re.sub(
            r"\s+device$",
            "",
            requested,
            flags=re.IGNORECASE,
        ).strip()
        if not requested:
            return None
        words = _normalise_words(requested)
        if not words or all(word in _GENERIC_DEVICE_QUERY_WORDS for word in words):
            return None
        return requested

    async def _execute_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        query: str,
    ) -> tuple[dict[str, Any], str]:
        """Repair a planner inventory call when the user requested one device.

        Small planning models occasionally choose ``hub_list_devices`` for requests such
        as "find front door". That tool is the authoritative inventory source but does not
        perform entity resolution. Redirect the call through HomeBrain's structured search
        broker before synthesis, keeping the model in the same multi-step agent loop.
        """

        requested = self._targeted_device_lookup(query)
        if name == "hub_list_devices" and requested:
            return await super()._execute_tool_call(
                _TARGETED_DEVICE_SEARCH,
                {"query": requested, "limit": 8},
                query,
            )
        return await super()._execute_tool_call(name, arguments, query)

    @staticmethod
    def _should_recover_with_inventory(error: Exception | str) -> bool:
        text = str(error or "").lower()
        return any(
            marker in text
            for marker in (
                "without authoritative home data",
                "did not execute an mcp tool for a live-home question",
                "tool request that could not be parsed",
            )
        )

    async def answer_with_planner(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        safe_history = history or []
        if self._is_broad_device_inventory_request(query):
            return await self._answer_from_device_inventory(query, safe_history)
        try:
            return await ClaudeStyleOllamaAgent.answer(self, query, safe_history)
        except OllamaUnavailable as exc:
            if not self._should_recover_with_inventory(exc):
                raise
            return await self._answer_from_targeted_device_search(query, safe_history, exc)

    async def _answer_from_device_inventory(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = await self.client.call_tool("hub_list_devices", {})
        if result.is_error:
            raise OllamaUnavailable(f"Device inventory failed: {result.text}")

        rows = _device_rows(result.data)
        room_counts: Counter[str] = Counter()
        devices: list[dict[str, Any]] = []
        for item in rows[:160]:
            room = _room_name(item) or "No room assigned"
            room_counts[room] += 1
            devices.append(
                {
                    "id": _device_id(item),
                    "label": _label(item),
                    "room": room,
                    "capabilities": item.get("capabilities") or [],
                    "currentStates": _attributes(item),
                    "disabled": bool(item.get("disabled") is True),
                }
            )

        payload = {
            "device_count": len(rows),
            "room_counts": dict(sorted(room_counts.items())),
            "devices": devices,
        }
        tool_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
        planner_messages = [
            {"role": "tool", "tool_name": "hub_list_devices", "content": tool_text}
        ]
        body = await self._chat(
            model=self.model,
            messages=self._synthesis_messages(
                query=query,
                history=history,
                planner_messages=planner_messages,
            ),
            tools=None,
            timeout_seconds=self.response_timeout_seconds,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            content = f"I found {len(rows)} selected Hubitat devices."
        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "device-inventory",
            "message": content,
            "model": self.model,
            "tools_used": [
                {
                    "name": "hub_list_devices",
                    "arguments": {},
                    "success": True,
                    "preview": tool_text[:700],
                    "evidence": {"device_count": len(rows)},
                }
            ],
            "selected_tools": ["hub_list_devices"],
            "device_count": len(rows),
            "elapsed_ms": elapsed,
        }

    async def _answer_from_targeted_device_search(
        self,
        query: str,
        history: list[dict[str, str]],
        planner_error: Exception,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        requested = self._targeted_device_lookup(query) or query
        result = await self.client.call_tool(
            _TARGETED_DEVICE_SEARCH,
            {"query": requested, "limit": 8},
        )
        if result.is_error:
            raise OllamaUnavailable(
                f"Planner ended without data and targeted device search failed: {result.text}"
            ) from planner_error

        tool_text = self._compact_tool_result(result)
        planner_messages: list[dict[str, Any]] = [
            {
                "role": "tool",
                "tool_name": _TARGETED_DEVICE_SEARCH,
                "content": tool_text,
            }
        ]
        body = await self._chat(
            model=self.model,
            messages=self._synthesis_messages(
                query=query,
                history=history,
                planner_messages=planner_messages,
            ),
            tools=None,
            timeout_seconds=self.response_timeout_seconds,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise OllamaUnavailable("Targeted device recovery returned no user-facing answer")

        elapsed = round((time.perf_counter() - started) * 1000)
        evidence = self._tool_evidence(result.data)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "unified-targeted-device-recovery",
            "message": content,
            "model": self.model,
            "planner_model": self._last_agent_status.get("planner_model"),
            "tools_used": [
                {
                    "name": _TARGETED_DEVICE_SEARCH,
                    "arguments": {"query": requested, "limit": 8},
                    "success": True,
                    "preview": tool_text[:700],
                    **({"evidence": evidence} if evidence else {}),
                }
            ],
            "selected_tools": [_TARGETED_DEVICE_SEARCH],
            "planner_error": str(planner_error),
            "authoritative_recovery": True,
            "targeted_device_search": True,
            "elapsed_ms": elapsed,
        }


__all__ = ["UnifiedAdaptiveMCPAgent"]
