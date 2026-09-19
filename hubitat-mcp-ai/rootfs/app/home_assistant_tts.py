from __future__ import annotations

from typing import Any

import httpx


HOME_ASSISTANT_CORE_API = "http://supervisor/core/api"
MAX_TTS_CHARS = 1500


class HomeAssistantTTSConfigurationError(RuntimeError):
    """Raised when Home Assistant mobile-app TTS cannot be targeted safely."""


class HomeAssistantTTS:
    """Send text to the Home Assistant Android companion app as native TTS."""

    def __init__(
        self,
        *,
        enabled: bool,
        supervisor_token: str,
        notify_service: str = "",
        media_stream: str = "",
        base_url: str = HOME_ASSISTANT_CORE_API,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.supervisor_token = str(supervisor_token or "").strip()
        self.notify_service = str(notify_service or "").strip()
        self.media_stream = str(media_stream or "").strip()
        self.base_url = str(base_url or HOME_ASSISTANT_CORE_API).rstrip("/")
        self._client = client
        self._owns_client = client is None
        self._resolved_service: str | None = None

    @property
    def token_available(self) -> bool:
        return bool(self.supervisor_token)

    @property
    def explicitly_configured(self) -> bool:
        return bool(self.notify_service)

    @property
    def can_attempt(self) -> bool:
        return self.enabled and self.token_available

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "token_available": self.token_available,
            "notify_service": self.notify_service or None,
            "auto_discovery": not self.explicitly_configured,
            "can_attempt": self.can_attempt,
        }

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    def _headers(self) -> dict[str, str]:
        if not self.supervisor_token:
            raise HomeAssistantTTSConfigurationError(
                "Home Assistant API access is unavailable; SUPERVISOR_TOKEN is missing"
            )
        return {
            "Authorization": f"Bearer {self.supervisor_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _normalize_service(value: str) -> str:
        service = str(value or "").strip()
        if service.startswith("notify."):
            service = service[len("notify.") :]
        if not service.startswith("mobile_app_"):
            raise HomeAssistantTTSConfigurationError(
                "ha_tts_notify_service must be a notify.mobile_app_* service"
            )
        return service

    async def _discover_mobile_services(self) -> list[str]:
        response = await self._http().get(
            f"{self.base_url}/services",
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        for domain in payload:
            if not isinstance(domain, dict) or domain.get("domain") != "notify":
                continue
            services = domain.get("services")
            if not isinstance(services, dict):
                return []
            return sorted(
                str(name)
                for name in services
                if str(name).startswith("mobile_app_")
            )
        return []

    async def resolve_notify_service(self) -> str:
        if not self.enabled:
            raise HomeAssistantTTSConfigurationError(
                "Home Assistant native TTS is disabled"
            )
        self._headers()
        if self.notify_service:
            return self._normalize_service(self.notify_service)
        if self._resolved_service:
            return self._resolved_service

        services = await self._discover_mobile_services()
        if len(services) == 1:
            self._resolved_service = services[0]
            return services[0]
        if not services:
            raise HomeAssistantTTSConfigurationError(
                "No notify.mobile_app_* service was found in Home Assistant"
            )
        choices = ", ".join(f"notify.{name}" for name in services[:8])
        suffix = "" if len(services) <= 8 else f", +{len(services) - 8} more"
        raise HomeAssistantTTSConfigurationError(
            "Multiple mobile-app notify services were found; set "
            f"ha_tts_notify_service to one of: {choices}{suffix}"
        )

    async def speak(self, text: str) -> dict[str, Any]:
        spoken = str(text or "").strip()
        if not spoken:
            raise ValueError("TTS text is empty")
        if len(spoken) > MAX_TTS_CHARS:
            raise ValueError(f"TTS text exceeds {MAX_TTS_CHARS} characters")

        service = await self.resolve_notify_service()
        data: dict[str, Any] = {"tts_text": spoken}
        if self.media_stream:
            data["media_stream"] = self.media_stream
        response = await self._http().post(
            f"{self.base_url}/services/notify/{service}",
            headers=self._headers(),
            json={"message": "TTS", "data": data},
        )
        response.raise_for_status()
        return {
            "sent": True,
            "service": f"notify.{service}",
            "method": "home-assistant-mobile-app",
        }

    async def stop(self) -> dict[str, Any]:
        service = await self.resolve_notify_service()
        response = await self._http().post(
            f"{self.base_url}/services/notify/{service}",
            headers=self._headers(),
            json={"message": "command_stop_tts"},
        )
        response.raise_for_status()
        return {
            "sent": True,
            "service": f"notify.{service}",
            "method": "home-assistant-mobile-app",
        }

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = [
    "HOME_ASSISTANT_CORE_API",
    "MAX_TTS_CHARS",
    "HomeAssistantTTS",
    "HomeAssistantTTSConfigurationError",
]
