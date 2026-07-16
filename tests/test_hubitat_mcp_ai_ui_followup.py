from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from weather_presenter_v2 import present_weather  # noqa: E402
from webui import render_page  # noqa: E402


def test_weather_reads_attribute_list_from_device_payload():
    message, display = present_weather(
        {
            "devices": [
                {
                    "id": "weather-1",
                    "label": "Home Weather",
                    "type": "Virtual Weather Device",
                    "attributes": [
                        {"name": "weatherSummary", "currentValue": "Today: Mostly sunny."},
                        {"name": "temperature", "currentValue": "26.1"},
                        {"name": "humidity", "currentValue": "51.3"},
                        {"name": "precipitation", "currentValue": "0 mm"},
                    ],
                }
            ]
        }
    )

    assert message.startswith("Today: Mostly sunny.")
    metrics = {item["label"]: item["value"] for item in display["metrics"]}
    assert metrics["Temperature"] == "26.1°C"
    assert metrics["Humidity"] == "51.3%"
    assert metrics["Rainfall"] == "0 mm"


def test_homebrain_ui_uses_two_columns_and_smaller_summary_tile_text():
    page = render_page("Hubitat MCP AI", "0.1.4-alpha")
    assert "@media(max-width:820px)" in page
    assert "#summaryCard{grid-template-columns:repeat(2,minmax(0,1fr))}" in page
    assert 'class="big model-value" id="model"' in page
    assert "#summaryCard .big{font-size:24px" in page
    assert ".model-value{font-size:20px!important" in page
    assert ".connection-tile{display:none}" in page


def test_ollama_health_retries_and_retains_recent_online_state():
    from ollama_agent_resilient import OllamaMCPAgent  # noqa: E402

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "qwen3.5:9b"}]}

    class FakeHTTP:
        def __init__(self):
            self.calls = 0

        async def get(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary timeout")
            return FakeResponse()

    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        health_timeout_seconds=3,
    )
    agent._http = FakeHTTP()

    result = asyncio.run(agent.health(force=True))
    assert result["online"] is True
    assert result["model"] == "qwen3.5:9b"
    assert agent._http.calls == 2
