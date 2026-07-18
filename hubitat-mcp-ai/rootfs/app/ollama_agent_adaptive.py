from __future__ import annotations

import re
from typing import Any

from ollama_agent_final_answer import FinalAnswerNaturalAgent
from ollama_agent_fast import OllamaUnavailable


_TARGET_LOCAL_MODEL_BILLIONS = 4.0


class AdaptiveFinalAnswerAgent(FinalAnswerNaturalAgent):
    """Hybrid Ollama agent tuned for the user's 16 GB shared-memory PC.

    Qwen 3.5 4B remains the local model and MCP planner. When Ollama Cloud is
    enabled and its model tag is available, analytical response synthesis uses
    the stronger cloud model. A cloud request that fails is retried once through
    the local model before HomeBrain falls back to deterministic Hubitat output.

    The cloud is never the source of device state and is not used for ordinary
    exact reads or controls. Those routes remain deterministic and local.
    """

    def __init__(
        self,
        *args: Any,
        cloud_enabled: bool = False,
        cloud_model: str = "",
        cloud_fallback_local: bool = True,
        cloud_timeout_seconds: float = 25.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.cloud_enabled = bool(cloud_enabled)
        self.cloud_model = str(cloud_model or "").strip()
        self.cloud_fallback_local = bool(cloud_fallback_local)
        self.cloud_timeout_seconds = max(8.0, min(90.0, float(cloud_timeout_seconds)))

    @staticmethod
    def _exact_model_present(model: str, installed_models: list[str]) -> bool:
        target = str(model or "").strip().lower()
        return bool(target) and any(str(name or "").strip().lower() == target for name in installed_models)

    def _cloud_model_present(self, installed_models: list[str]) -> bool:
        return bool(
            self.cloud_enabled
            and self.cloud_model
            and self._exact_model_present(self.cloud_model, installed_models)
        )

    def _resolve_routine_model(self, installed_models: list[str]) -> str:
        # An explicit routine model remains an administrator override.
        if getattr(self, "configured_routine_model", ""):
            return super()._resolve_routine_model(installed_models)
        if self._cloud_model_present(installed_models):
            return self.cloud_model
        return super()._resolve_routine_model(installed_models)

    def _resolve_response_model(
        self,
        installed_models: list[str],
        *,
        deep_reasoning: bool,
    ) -> str:
        if self._cloud_model_present(installed_models):
            return self.cloud_model
        return super()._resolve_response_model(
            installed_models,
            deep_reasoning=deep_reasoning,
        )

    async def runtime_status(self, force: bool = False) -> dict[str, Any]:
        status = await super().runtime_status(force=force)
        installed = list(status.get("installed_models") or [])
        status.update(
            {
                "local_model": self.model,
                "cloud_enabled": self.cloud_enabled,
                "cloud_model": self.cloud_model or None,
                "cloud_present": self._cloud_model_present(installed),
                "cloud_fallback_local": self.cloud_fallback_local,
                "preferred_response_model": self._resolve_response_model(
                    installed,
                    deep_reasoning=True,
                ),
            }
        )
        return status

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
            return result

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
            return result
        except Exception as cloud_error:
            if not self.cloud_fallback_local or not self.model or self.model == requested_model:
                raise

            body = await super()._chat(
                model=self.model,
                messages=messages,
                tools=tools,
                timeout_seconds=max(8.0, float(timeout_seconds)),
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )
            result = dict(body)
            result["_homebrain_model_used"] = self.model
            result["_homebrain_provider"] = "Local Ollama fallback"
            result["_homebrain_cloud_error"] = str(cloud_error) or cloud_error.__class__.__name__
            return result

    def _preferred_family_model(self, installed_models: list[str]) -> str:
        response_family = self.model.split(":", 1)[0].lower()
        candidates = [
            name
            for name in installed_models
            if name
            and name.split(":", 1)[0].lower() == response_family
            and not name.lower().endswith("-cloud")
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
        ]
        if not candidates:
            return self.model

        def model_size(name: str) -> float:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            return float(match.group(1)) if match else 999.0

        def preference_key(name: str) -> tuple[float, int, float, str]:
            size = model_size(name)
            # Prefer the exact 4B target. On a tie, avoid going below 4B before
            # choosing a larger model, then prefer the smaller memory footprint.
            distance = abs(size - _TARGET_LOCAL_MODEL_BILLIONS)
            below_target = 1 if size < _TARGET_LOCAL_MODEL_BILLIONS else 0
            return distance, below_target, size, name.lower()

        candidates.sort(key=preference_key)
        return candidates[0]


__all__ = ["AdaptiveFinalAnswerAgent", "OllamaUnavailable"]
