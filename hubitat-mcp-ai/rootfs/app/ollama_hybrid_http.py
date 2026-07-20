from __future__ import annotations

import asyncio
import copy
from contextvars import ContextVar
from typing import Any

import httpx


_PROVIDER: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_http_provider",
    default=None,
)


def _normalise_host(value: str, default: str = "") -> str:
    host = str(value or default).strip().rstrip("/")
    if host.endswith("/api"):
        host = host[:-4].rstrip("/")
    return host


def direct_model_name(cloud_tag: str, override: str = "") -> str:
    explicit = str(override or "").strip()
    if explicit:
        return explicit
    value = str(cloud_tag or "").strip()
    return value[:-6] if value.lower().endswith("-cloud") else value


class HybridOllamaHTTPClient:
    """Route local and direct Ollama Cloud requests through one safe client.

    Existing HomeBrain agents continue calling the normal Ollama URLs. Requests
    whose JSON model matches the configured cloud tag are transparently sent to
    ollama.com with bearer authentication. A failed direct request may retry the
    original local Ollama URL, allowing a signed-in PC proxy to remain a backup.
    """

    def __init__(
        self,
        *,
        local_base_url: str,
        cloud_model: str,
        direct_enabled: bool,
        direct_base_url: str,
        direct_api_key: str,
        direct_model: str = "",
        fallback_local_proxy: bool = True,
    ) -> None:
        self.local_base_url = _normalise_host(local_base_url)
        self.cloud_model = str(cloud_model or "").strip()
        self.direct_enabled = bool(direct_enabled)
        self.direct_base_url = _normalise_host(direct_base_url, "https://ollama.com")
        self._direct_api_key = str(direct_api_key or "").strip()
        self.direct_model = direct_model_name(self.cloud_model, direct_model)
        self.fallback_local_proxy = bool(fallback_local_proxy)
        self._client = httpx.AsyncClient(follow_redirects=True)
        self._last_direct_error: str | None = None

    @property
    def direct_ready(self) -> bool:
        return bool(
            self.direct_enabled
            and self.direct_base_url
            and self._direct_api_key
            and self.cloud_model
            and self.direct_model
        )

    @property
    def direct_api_key_configured(self) -> bool:
        return bool(self._direct_api_key)

    @property
    def last_direct_error(self) -> str | None:
        return self._last_direct_error

    def last_provider(self, default: str | None = None) -> str | None:
        return _PROVIDER.get() or default

    def _is_cloud_request(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        requested = str(payload.get("model") or "").strip().lower()
        configured = self.cloud_model.lower()
        direct = self.direct_model.lower()
        return bool(
            requested
            and configured
            and (
                requested == configured
                or requested == direct
                or requested.endswith("-cloud")
            )
        )

    def _direct_headers(self, supplied: Any = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if isinstance(supplied, dict):
            headers.update({str(key): str(value) for key, value in supplied.items()})
        headers["Authorization"] = f"Bearer {self._direct_api_key}"
        return headers

    def _direct_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(payload)
        value["model"] = self.direct_model
        # keep_alive is meaningful to a local runtime, not the hosted API.
        value.pop("keep_alive", None)
        return value

    @staticmethod
    def _response_ok(response: httpx.Response) -> bool:
        return 200 <= int(response.status_code) < 300

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        payload = kwargs.get("json")
        if self.direct_ready and self._is_cloud_request(payload):
            direct_kwargs = dict(kwargs)
            direct_kwargs["json"] = self._direct_payload(dict(payload))
            direct_kwargs["headers"] = self._direct_headers(kwargs.get("headers"))
            direct_url = f"{self.direct_base_url}/api/chat"
            try:
                response = await self._client.post(direct_url, **direct_kwargs)
                if not self._response_ok(response):
                    response.raise_for_status()
                self._last_direct_error = None
                _PROVIDER.set("Ollama Cloud Direct")
                return response
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_direct_error = str(exc).strip() or type(exc).__name__
                if not self.fallback_local_proxy:
                    raise

        response = await self._client.post(url, **kwargs)
        provider = (
            "Ollama Cloud via local Ollama"
            if self._is_cloud_request(payload)
            else "Local Ollama"
        )
        _PROVIDER.set(provider)
        return response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        if str(url).rstrip("/").endswith("/api/tags") and self.direct_ready:
            local_response: httpx.Response | None = None
            local_error: Exception | None = None
            try:
                local_response = await self._client.get(url, **kwargs)
                if not self._response_ok(local_response):
                    local_response.raise_for_status()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                local_error = exc
                local_response = None

            direct_response: httpx.Response | None = None
            direct_error: Exception | None = None
            direct_kwargs = dict(kwargs)
            direct_kwargs["headers"] = self._direct_headers(kwargs.get("headers"))
            try:
                direct_response = await self._client.get(
                    f"{self.direct_base_url}/api/tags",
                    **direct_kwargs,
                )
                if not self._response_ok(direct_response):
                    direct_response.raise_for_status()
                self._last_direct_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                direct_error = exc
                self._last_direct_error = str(exc).strip() or type(exc).__name__
                direct_response = None

            if local_response is None and direct_response is None:
                raise direct_error or local_error or RuntimeError("No Ollama endpoint is reachable")

            local_models = self._models(local_response)
            direct_models = self._models(direct_response)
            merged = list(local_models)
            seen = {
                str(item.get("name") or item.get("model") or "").strip().lower()
                for item in merged
            }
            for item in direct_models:
                name = str(item.get("name") or item.get("model") or "").strip().lower()
                if name and name not in seen:
                    merged.append(item)
                    seen.add(name)

            if direct_response is not None and self._direct_model_present(direct_models):
                alias = self.cloud_model.lower()
                if alias and alias not in seen:
                    merged.append(
                        {
                            "name": self.cloud_model,
                            "model": self.cloud_model,
                            "details": {"family": "ollama-cloud-direct"},
                        }
                    )

            request = httpx.Request("GET", url)
            _PROVIDER.set(
                "Hybrid local + direct Ollama"
                if local_response is not None and direct_response is not None
                else "Ollama Cloud Direct"
                if direct_response is not None
                else "Local Ollama"
            )
            return httpx.Response(200, json={"models": merged}, request=request)

        response = await self._client.get(url, **kwargs)
        _PROVIDER.set("Local Ollama")
        return response

    def _direct_model_present(self, models: list[dict[str, Any]]) -> bool:
        target = self.direct_model.lower()
        family = target.split(":", 1)[0]
        for item in models:
            name = str(item.get("name") or item.get("model") or "").strip().lower()
            if name == target or (name and name.split(":", 1)[0] == family):
                return True
        return False

    @staticmethod
    def _models(response: httpx.Response | None) -> list[dict[str, Any]]:
        if response is None:
            return []
        try:
            payload = response.json()
        except Exception:
            return []
        if not isinstance(payload, dict):
            return []
        return [dict(item) for item in payload.get("models", []) if isinstance(item, dict)]

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["HybridOllamaHTTPClient", "direct_model_name"]
