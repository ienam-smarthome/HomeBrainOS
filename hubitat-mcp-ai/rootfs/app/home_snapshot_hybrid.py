from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from home_snapshot_truthful import TruthfulHomeSnapshotService


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class HybridTruthfulHomeSnapshotService(TruthfulHomeSnapshotService):
    """Truthful Home Snapshot with Cloud-first, local-retry AI wording."""

    async def answer(self, query: str) -> dict[str, Any]:
        result = dict(await super().answer(query))
        model = str(result.get("model") or "").strip()
        if result.get("route") == "ollama+snapshot":
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
                        "the summary from the same verified Hubitat snapshot."
                    )
                    display["note"] = note.strip()
                    result["display"] = display
        return result

    async def _natural_summary(
        self,
        snapshot: dict[str, Any],
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
        evidence = {
            "attention": [
                {
                    "device": item["title"],
                    "value": item["value"],
                    "detail": item.get("subtitle"),
                }
                for item in snapshot["attention"][:6]
            ],
            "motion_active": [
                {"device": item["title"], "room": item.get("room")}
                for item in snapshot["motion_active"][:8]
            ],
            "lights_on": [item["title"] for item in snapshot["lights_on"][:8]],
            "other_devices_on": [
                item["title"] for item in snapshot["devices_on"][:8]
            ],
            "open_contacts": [
                item["title"] for item in snapshot["open_contacts"][:6]
            ],
            "heating": [item["title"] for item in snapshot["heating"][:6]],
            "coverage": {
                "selected_devices": snapshot["selected_devices"],
                "states_read": snapshot["states_read"],
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are HomeBrain, a concise natural smart-home assistant. Use only "
                    "the supplied verified snapshot. Write two or three short sentences. "
                    "Put urgent safety or battery issues first. Use exact device names when "
                    "naming devices. Mention active rooms where useful. Do not invent causes, "
                    "do not call tools, do not offer follow-up options, and do not say "
                    "everything is fine when coverage is incomplete."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Summarise what is happening at home now.\n"
                    f"Verified snapshot: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}\n"
                    f"Deterministic wording to improve, not contradict: {deterministic}"
                ),
            },
        ]
        body = await ollama._chat(
            model=model,
            messages=messages,
            tools=None,
            timeout_seconds=self.ai_timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=100,
            temperature=0.1,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty home summary")
        actual_model = str(body.get("_homebrain_model_used") or model).strip()
        return content, actual_model


def install_hybrid_home_snapshot(
    application: Any,
    device_index: Any,
    *,
    ai_enabled: bool = True,
    ai_timeout_seconds: float = 20.0,
    max_items_per_group: int = 8,
) -> HybridTruthfulHomeSnapshotService:
    original_ask: AskHandler = application.ask
    service = HybridTruthfulHomeSnapshotService(
        application,
        device_index,
        ai_enabled=ai_enabled,
        ai_timeout_seconds=ai_timeout_seconds,
        max_items_per_group=max_items_per_group,
    )

    async def ask_with_home_snapshot(request: Any) -> dict[str, Any]:
        if service.matches(str(request.query or "")):
            answer = await service.answer(str(request.query or ""))
            answer.setdefault("version", application.VERSION)
            return answer
        return await original_ask(request)

    application.ask = ask_with_home_snapshot
    application.home_snapshot = service
    return service


__all__ = [
    "HybridTruthfulHomeSnapshotService",
    "install_hybrid_home_snapshot",
]
