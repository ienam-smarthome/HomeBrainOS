from __future__ import annotations

import json
from typing import Any

from temperature_insight import TemperatureInsightService


class HybridTemperatureInsightService(TemperatureInsightService):
    """Temperature comparison that reports the model that actually answered."""

    async def answer(self, query: str) -> dict[str, Any]:
        result = dict(await super().answer(query))
        model = str(result.get("model") or "").strip()
        if result.get("ai_used"):
            cloud_model = str(
                self.application.OPTIONS.get("ollama_cloud_model") or ""
            ).strip()
            if model and cloud_model and model.lower() == cloud_model.lower():
                result["ai_provider"] = "Ollama Cloud"
            else:
                result["ai_provider"] = "Local Ollama fallback"
                display = result.get("display")
                if isinstance(display, dict):
                    display = dict(display)
                    note = str(display.get("note") or "").strip()
                    note += (
                        " Gemma Cloud was unavailable or limited, so local Qwen wrote "
                        "the explanation from the same verified Hubitat evidence."
                    )
                    display["note"] = note.strip()
                    result["display"] = display
        return result

    async def _natural_answer(
        self,
        query: str,
        readings: list[dict[str, Any]],
        deterministic: str,
    ) -> tuple[str, str]:
        ollama = self.application.ollama
        health = await ollama.health()
        if not health.get("online"):
            raise RuntimeError(health.get("error") or "Ollama is offline")
        installed = list(health.get("models") or [])
        resolver = getattr(ollama, "_resolve_routine_model", None)
        model = (
            resolver(installed)
            if callable(resolver)
            else str(getattr(ollama, "model", ""))
        )
        evidence = [
            {
                "room": item["room"],
                "representative_temperature_c": item["temperature"],
                "representative_device": item["device"],
                "alternate_sensors": [
                    {
                        "device": alternate["device"],
                        "temperature_c": alternate["temperature"],
                    }
                    for alternate in item.get("alternate_sources") or []
                ],
            }
            for item in readings
        ]
        body = await ollama._chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are HomeBrain, a concise smart-home analyst. Compare only the "
                        "verified temperatures supplied. Count each room once using its "
                        "representative temperature. Alternate sensors belong to the same room "
                        "and must never be described as separate rooms. State each bedroom's "
                        "representative reading, then the coldest, warmest and exact room-to-room "
                        "difference. Mention any meaningful same-room sensor discrepancy, "
                        "especially a warmer TRV versus an ambient meter. Explain plausible "
                        "causes cautiously as possibilities, not facts. Do not claim knowledge "
                        "of windows, heating, occupancy or sensor placement unless supplied. "
                        "Use two or three short paragraphs."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {query}\n"
                        f"Verified readings: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}\n"
                        f"Reliable fallback wording: {deterministic}"
                    ),
                },
            ],
            tools=None,
            timeout_seconds=self.timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=170,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty temperature comparison")
        actual_model = str(body.get("_homebrain_model_used") or model).strip()
        return content, actual_model


__all__ = ["HybridTemperatureInsightService"]
