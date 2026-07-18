from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any

from ollama_agent_final_answer import FinalAnswerNaturalAgent
from ollama_agent_fast import OllamaUnavailable


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


class AdaptiveFinalAnswerAgent(FinalAnswerNaturalAgent):
    """Hybrid Ollama agent for Cloud synthesis with a local 4B safety net.

    The configured primary response model may be an Ollama Cloud tag such as
    ``gemma4:31b-cloud``. Qwen 3.5 4B remains the local MCP planner and is retried
    automatically when Cloud is unavailable, rate-limited or out of Free usage.

    Exact device reads and controls never reach this class; they remain local,
    deterministic Hubitat routes. Cloud therefore receives only the compact live
    evidence needed for questions that genuinely benefit from AI wording/reasoning.
    """

    def __init__(
        self,
        *args: Any,
        cloud_enabled: bool = False,
        cloud_model: str = "",
        local_fallback_model: str = "",
        cloud_fallback_local: bool = True,
        cloud_timeout_seconds: float = 25.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.cloud_enabled = bool(cloud_enabled)
        self.cloud_model = str(cloud_model or "").strip()
        self.local_fallback_model = str(local_fallback_model or "").strip()
        self.cloud_fallback_local = bool(cloud_fallback_local)
        self.cloud_timeout_seconds = max(8.0, min(90.0, float(cloud_timeout_seconds)))
        self._cloud_present_hint: bool | None = None

    @staticmethod
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
        if not status.get("online"):
            return status

        installed = list(status.get("models") or [])
        cloud_present = self._cloud_model_present(installed)
        local_present = self._exact_model_present(
            self.local_fallback_model,
            installed,
        )
        self._cloud_present_hint = cloud_present

        result = dict(status)
        # Allow HomeBrain to remain usable when the cloud tag is missing but the
        # explicitly configured local safety model is installed.
        result["model_present"] = bool(cloud_present or local_present)
        result["cloud_present"] = cloud_present
        result["local_fallback_present"] = local_present
        result["cloud_model"] = self.cloud_model or None
        result["local_fallback_model"] = self.local_fallback_model or None
        return result

    async def runtime_status(self, force: bool = False) -> dict[str, Any]:
        status = await super().runtime_status(force=force)
        installed = list(status.get("installed_models") or [])
        cloud_present = self._cloud_model_present(installed)
        local_present = self._exact_model_present(
            self.local_fallback_model,
            installed,
        )
        status.update(
            {
                "cloud_enabled": self.cloud_enabled,
                "cloud_model": self.cloud_model or None,
                "cloud_present": cloud_present,
                "local_fallback_model": self.local_fallback_model or None,
                "local_fallback_present": local_present,
                "cloud_fallback_local": self.cloud_fallback_local,
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
            body = await super()._chat(
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
            result["_homebrain_provider"] = "Local Ollama"
            _CHAT_MODEL_USED.set(requested_model)
            _CHAT_PROVIDER_USED.set("Local Ollama")
            return result

        cloud_error: Exception | None = None
        if self._cloud_present_hint is not False:
            cloud_timeout = min(
                self.cloud_timeout_seconds,
                max(8.0, float(timeout_seconds)),
            )
            try:
                body = await super()._chat(
                    model=requested_model,
                    messages=messages,
                    tools=tools,
                    timeout_seconds=cloud_timeout,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                    temperature=temperature,
                )
                result = dict(body)
                result["_homebrain_model_used"] = requested_model
                result["_homebrain_provider"] = "Ollama Cloud"
                _CHAT_MODEL_USED.set(requested_model)
                _CHAT_PROVIDER_USED.set("Ollama Cloud")
                return result
            except Exception as exc:
                cloud_error = exc
        else:
            cloud_error = OllamaUnavailable(
                f"Ollama Cloud model {requested_model} is not installed or signed in"
            )

        if (
            not self.cloud_fallback_local
            or not self.local_fallback_model
            or self.local_fallback_model.lower() == requested_model.lower()
        ):
            assert cloud_error is not None
            raise cloud_error

        body = await super()._chat(
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


__all__ = ["AdaptiveFinalAnswerAgent", "OllamaUnavailable"]
