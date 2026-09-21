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
    format_health_audit_messages,
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
        "new_issues": [
            {"title": "Telemetry stale: Washer Monitor Status"}
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
    assert "New since previous check:\n• Telemetry stale: Washer Monitor Status" in message
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

    _, messages = format_health_audit_messages(audit)
    message = "\n".join(messages)

    assert '<font color="#ff5c5c">Offline device 0</font>' in message
    assert '<font color="#ff5c5c">Offline device 7</font>' in message
    assert "• +2 more" in message
    assert "Offline device 8" not in message
    assert all(len(part) <= 1024 for part in messages)


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

    _, messages = format_health_audit_messages(audit)

    assert all(len(message) <= 1024 for message in messages)
    assert all(not message.endswith("<") for message in messages)
    assert all(message.count("<font") == message.count("</font>") for message in messages)


def test_large_system_check_is_split_without_losing_later_sections() -> None:
    audit = _audit()
    audit["issues"] = [
        *[
            {
                "severity": "warning",
                "domain": "devices",
                "title": f"Device unavailable: Offline device {index}",
                "detail": "offline",
                "count": 1,
            }
            for index in range(5)
        ],
        *[
            {
                "severity": "warning",
                "domain": "devices",
                "title": f"Low battery: Battery device {index}",
                "detail": f"{index + 1}% (threshold 20%).",
                "count": 1,
            }
            for index in range(3)
        ],
        *[
            {
                "severity": "warning",
                "domain": "automations",
                "title": f"Automation broken: Broken automation {index}",
                "detail": "Hubitat marked the automation name *BROKEN*.",
                "count": 1,
            }
            for index in range(6)
        ],
        {
            "severity": "warning",
            "domain": "devices",
            "title": "Telemetry stale: Washer Monitor Status",
            "detail": "Periodic telemetry last reported 43.9h ago.",
            "count": 1,
        },
        {
            "severity": "warning",
            "domain": "logs",
            "title": "MCP Rule Server",
            "detail": "VRB feed missing 1/356 devices.",
            "count": 6,
        },
        {
            "severity": "warning",
            "domain": "logs",
            "title": "Fridge door automation",
            "detail": "Not triggered after the contact stayed open.",
            "count": 1,
        },
    ]
    audit["new_issues"] = [
        {"title": "Telemetry stale: Washer Monitor Status"}
    ]
    audit["resolved_issues"] = [
        {"title": "Motion active too long: Bedroom 3 Soft Sensor"},
        {"title": "Telemetry stale: Fridge Meter"},
    ]

    title, messages = format_health_audit_messages(audit)
    combined = "\n".join(messages)

    assert title == "HomeBrain System Check: Attention"
    assert len(messages) >= 2
    assert all(len(message) <= 1024 for message in messages)
    assert "Offline:" in combined
    assert "Low battery:" in combined
    assert "Device warnings:" in combined
    assert "Telemetry stale: Washer Monitor Status" in combined
    assert "Broken automations:" in combined
    assert "Broken automation 5" in combined
    assert "Logs:" in combined
    assert "Fridge door automation" in combined
    assert "New since previous check:" in combined
    assert "Resolved:" in combined
    assert "Telemetry stale: Fridge Meter" in combined


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
async def test_pushover_sends_all_parts_of_large_report() -> None:
    audit = _audit()
    audit["issues"] = [
        *[
            {
                "severity": "warning",
                "domain": "devices",
                "title": f"Device unavailable: Long offline device {index}",
                "detail": "offline",
                "count": 1,
            }
            for index in range(8)
        ],
        *[
            {
                "severity": "warning",
                "domain": "devices",
                "title": f"Low battery: Long battery device {index}",
                "detail": f"{index + 1}% (threshold 20%).",
                "count": 1,
            }
            for index in range(6)
        ],
        *[
            {
                "severity": "warning",
                "domain": "automations",
                "title": f"Automation broken: Long automation {index}",
                "detail": "Hubitat marked the automation name *BROKEN*.",
                "count": 1,
            }
            for index in range(6)
        ],
        {
            "severity": "warning",
            "domain": "logs",
            "title": "Final log finding",
            "detail": "This must still be delivered after device sections.",
            "count": 1,
        },
    ]
    sent_forms = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent_forms.append(parse_qs(request.content.decode()))
        return httpx.Response(
            200,
            json={"status": 1, "request": f"request-{len(sent_forms)}"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = PushoverNotifier(
            enabled=True,
            app_token="app-token",
            user_key="user-key",
            client=client,
        )
        result = await notifier.send(audit)

    assert result["sent"] is True
    assert result["messages_sent"] == len(sent_forms)
    assert len(sent_forms) >= 2
    assert all(len(form["message"][0]) <= 1024 for form in sent_forms)
    assert sent_forms[0]["title"][0].endswith(f"(1/{len(sent_forms)})")
    assert sent_forms[-1]["title"][0].endswith(
        f"({len(sent_forms)}/{len(sent_forms)})"
    )
    combined = "\n".join(form["message"][0] for form in sent_forms)
    assert "Final log finding" in combined


@pytest.mark.asyncio
async def test_enabled_pushover_requires_credentials() -> None:
    notifier = PushoverNotifier(enabled=True, app_token="", user_key="")

    with pytest.raises(RuntimeError, match="token or user/group key is missing"):
        await notifier.send(_audit())
