from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from home_assistant_tts import (  # noqa: E402
    HomeAssistantTTS,
    HomeAssistantTTSConfigurationError,
)


@pytest.mark.asyncio
async def test_explicit_mobile_service_sends_android_tts_payload() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["json"] = request.content.decode()
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tts = HomeAssistantTTS(
            enabled=True,
            supervisor_token="supervisor-token",
            notify_service="notify.mobile_app_s25_ultra",
            media_stream="alarm_stream",
            client=client,
        )
        result = await tts.speak("Bedroom 2 Light is on.")

    assert captured["url"].endswith("/services/notify/mobile_app_s25_ultra")
    assert captured["auth"] == "Bearer supervisor-token"
    assert '"message":"TTS"' in captured["json"]
    assert '"tts_text":"Bedroom 2 Light is on."' in captured["json"]
    assert '"media_stream":"alarm_stream"' in captured["json"]
    assert result["service"] == "notify.mobile_app_s25_ultra"


@pytest.mark.asyncio
async def test_single_mobile_service_is_auto_discovered() -> None:
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "domain": "notify",
                        "services": {
                            "mobile_app_s25_ultra": {},
                            "persistent_notification": {},
                        },
                    }
                ],
            )
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tts = HomeAssistantTTS(
            enabled=True,
            supervisor_token="token",
            client=client,
        )
        result = await tts.speak("Hello")

    assert calls[0][1].endswith("/services")
    assert calls[1][1].endswith("/services/notify/mobile_app_s25_ultra")
    assert result["service"] == "notify.mobile_app_s25_ultra"


@pytest.mark.asyncio
async def test_multiple_mobile_services_require_explicit_target() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "domain": "notify",
                    "services": {
                        "mobile_app_phone_one": {},
                        "mobile_app_phone_two": {},
                    },
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tts = HomeAssistantTTS(
            enabled=True,
            supervisor_token="token",
            client=client,
        )
        with pytest.raises(
            HomeAssistantTTSConfigurationError,
            match="Multiple mobile-app notify services",
        ):
            await tts.speak("Hello")


@pytest.mark.asyncio
async def test_stop_uses_companion_app_tts_stop_command() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tts = HomeAssistantTTS(
            enabled=True,
            supervisor_token="token",
            notify_service="mobile_app_s25_ultra",
            client=client,
        )
        await tts.stop()

    assert '"message":"command_stop_tts"' in captured["body"]


@pytest.mark.asyncio
async def test_missing_supervisor_token_fails_closed() -> None:
    tts = HomeAssistantTTS(
        enabled=True,
        supervisor_token="",
        notify_service="notify.mobile_app_s25_ultra",
    )
    try:
        with pytest.raises(
            HomeAssistantTTSConfigurationError,
            match="SUPERVISOR_TOKEN is missing",
        ):
            await tts.speak("Hello")
    finally:
        await tts.close()
