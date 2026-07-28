from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ai_grounding_guard import AIGroundingGuard  # noqa: E402


class FakeDeviceIndex:
    async def summary_devices(self):
        return [
            {"id": "1", "label": "Kitchen Lamp"},
            {"id": "2", "label": "Roborock Q7 Max"},
        ]


def test_ai_device_claim_must_exist_in_supplied_evidence():
    async def scenario():
        guard = AIGroundingGuard(FakeDeviceIndex())
        answer = {
            "route": "ollama+mcp",
            "message": "Roborock Q7 Max is offline.",
            "tools_used": [
                {
                    "name": "hub_get_logs",
                    "preview": '{"warnings":[{"device":"Kitchen Lamp"}]}',
                }
            ],
        }

        result = await guard.guard(
            SimpleNamespace(query="Check logs for issues"),
            answer,
        )

        assert result["route"] == "grounded-evidence-fallback"
        assert result["ai_grounding_rejected"] is True
        assert result["ai_used"] is False
        assert result["grounding_guard"]["unverified_entities"] == [
            "Roborock Q7 Max"
        ]
        assert guard.response()["trigger_rate_percent"] == 100.0

    asyncio.run(scenario())


def test_ai_device_claim_is_kept_when_tool_evidence_names_it():
    async def scenario():
        guard = AIGroundingGuard(FakeDeviceIndex())
        answer = {
            "route": "ollama+mcp",
            "message": "Kitchen Lamp is on.",
            "tools_used": [
                {
                    "name": "hub_get_device",
                    "preview": '{"label":"Kitchen Lamp","switch":"on"}',
                }
            ],
        }

        result = await guard.guard(SimpleNamespace(query="Is it on?"), answer)

        assert result["message"] == "Kitchen Lamp is on."
        assert result["grounding_guard"]["triggered"] is False
        assert guard.response()["trigger_rate_percent"] == 0.0

    asyncio.run(scenario())


def test_deterministic_answer_is_not_subject_to_ai_grounding():
    async def scenario():
        guard = AIGroundingGuard(FakeDeviceIndex())
        answer = {
            "route": "hubitat-log-diagnostics",
            "message": "Roborock Q7 Max emitted one warning.",
            "answered_by": "Deterministic Hubitat log diagnostics",
        }

        result = await guard.guard(
            SimpleNamespace(query="Check logs for issues"),
            answer,
        )

        assert result == answer
        assert guard.response()["total_ai_answers"] == 0

    asyncio.run(scenario())
