from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from pushover_notifier import (  # noqa: E402
    PUSHOVER_MESSAGES_URL,
    PushoverNotifier,
    format_health_audit,
)


def _audit() -> dict:
    return {
        "status": "attention",
        "attention_count": 3,
        "new_count": 1,
        "resolved_count": 2,
        "health_hierarchy": {
            "hub": {"label": "Hub", "status": "healthy", "attention_count": 0},
            "devices": {"label": "Devices", "status": "attention", "attention_count": 2},
            "automations": {"label": "Automations", "status": "healthy", "attention_count": 0},
            "logs": {"label": "Logs", "status": "attention", "attention_count": 1},
        },
        "issues": [
            {
                "severity": "warning",
                "domain": "devices",
                "title": "Device unavailable: Roborock Q7 Max",
                "detail": "offline",
                "count": 1,
            },
            {
                "severity": "warning",
                "domain": "devices",
                "title": "Low battery: Livingroom TRV",
                "detail": "2% (threshold 20%).",
                "count": 1,
            },
            {
                "severity": "warning",
                "domain": "automations",
                "title": "Automation broken: Lighting: bedroom 3 low light",
                "detail": "Hubitat marked the automation name *BROKEN*.",
                "count": 1,
            },
            {
                "severity": "warning",
                "domain": "logs",
                "title": "MCP Rule Server",
                "detail": "VRB feed missing 1/358 devices.",
                "count": 4,
            },
        ],
        "resolved_issues": [
            {"title": "Motion active too long: Bedroom 3 Soft Sensor"}
        ],
    }


def test_pushover_summary_is_bounded_and_problem_first() -> None:
    title, message = format_health_audit(_audit())

    assert title == "HomeBrain System Check: Attention"
    assert "✅ Hub: healthy" in message
    assert "⚠️ Devices: 2 need attention" in message
    assert (
        'Offline:\n• <font color="#ff5c5c">Roborock Q7 Max</font> — '
        '<font color="#ff5c5c">offline</font>'
    ) in message
    assert (
        'Low battery:\n• <font color="#ffb300">Livingroom TRV</font> — '
        '<font color="#ffb300">2%</font> (threshold 20%).'
    ) in message
    assert "Broken automations:\n• Lighting: bedroom 3 low light" in message
    assert "Logs:\n• MCP Rule Server — VRB feed missing 1/358 devices. ×4" in message
    assert "Resolved:\n• Motion active too long: Bedroom 3 Soft Sensor" in message
    assert len(message) <= 1024


def test_pushover_named_sections_are_bounded_with_more_marker() -> None:
    audit = _audit()
    audit["issues"] = [
        {
            "severity": "warning",
            "domain": "devices",
            "title": f"Device unavailable: Offline device {index}",
            "detail": "offline",
            "count": 1,
        }
        for index in range(10)
    ]

    _, message = format_health_audit(audit)

    assert '<font color="#ff5c5c">Offline device 0</font>' in message
    assert '<font color="#ff5c5c">Offline device 7</font>' in message
    assert "• +2 more" in message
    assert "Offline device 8" not in message
    assert len(message) <= 1024


def test_pushover_html_escapes_device_names_and_keeps_only_targeted_colour() -> None:
    audit = _audit()
    audit["issues"][0]["title"] = "Device unavailable: Kitchen <TRV> & sensor"
    audit["issues"][1]["title"] = "Low battery: Hallway <Meter>"

    _, message = format_health_audit(audit)

    assert '<font color="#ff5c5c">Kitchen &lt;TRV&gt; &amp; sensor</font>' in message
    assert '<font color="#ff5c5c">offline</font>' in message
    assert '<font color="#ffb300">Hallway &lt;Meter&gt;</font>' in message
    assert '<font color="#ffb300">2%</font> (threshold 20%).' in message
    assert '<font color="#ff5c5c">Device unavailable:' not in message
    assert '<font color="#ffb300">Low battery:' not in message


def test_pushover_html_truncation_keeps_complete_lines() -> None:
    audit = _audit()
    audit["issues"] = [
        {
            "severity": "warning",
            "domain": "logs",
            "title": f"Long log {index}",
            "detail": "x" * 300,
            "count": 1,
        }
        for index in range(10)
    ]

    _, message = format_health_audit(audit)

    assert len(message) <= 1024
    assert not message.endswith("<")
    assert message.count("<font") == message.count("</font>")


@pytest.mark.asyncio
async def test_pushover_posts_official_message_fields() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"status": 1, "request": "request-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = PushoverNotifier(
            enabled=True,
            app_token="app-token",
            user_key="user-key",
            device="phone",
            client=client,
        )
        result = await notifier.send(_audit())

    assert captured["url"] == PUSHOVER_MESSAGES_URL
    assert "token=app-token" in captured["body"]
    assert "user=user-key" in captured["body"]
    assert "device=phone" in captured["body"]
    form = parse_qs(captured["body"])
    assert form["html"] == ["1"]
    assert '<font color="#ff5c5c">Roborock Q7 Max</font>' in form["message"][0]
    assert result["sent"] is True


@pytest.mark.asyncio
async def test_enabled_pushover_requires_credentials() -> None:
    notifier = PushoverNotifier(enabled=True, app_token="", user_key="")

    with pytest.raises(RuntimeError, match="token or user/group key is missing"):
        await notifier.send(_audit())
