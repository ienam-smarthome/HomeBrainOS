from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from device_intelligence_index import _attributes, _label, _normalise, _room_name
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_AUTOMATION_RECOMMENDATION_QUERY = re.compile(
    r"^(?:"
    r"(?:please\s+)?(?:suggest|recommend|propose|give\s+me)\s+"
    r"(?:(?:one|a|an)\s+)?(?:(?:useful|practical|smart)\s+)?"
    r"(?:home\s+)?automation(?:\s+idea)?"
    r"(?:\s+(?:for|using|based\s+on)\s+(?:the\s+)?devices?"
    r"(?:\s+(?:i|we)\s+have)?)?"
    r"|what\s+(?:useful\s+)?automation\s+(?:should|could|can)\s+i\s+"
    r"(?:create|make|add)"
    r")[?.!]*$",
    re.IGNORECASE,
)


def _state(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", value.get("currentValue", value.get("currentState")))
    return _normalise(value)


class AutomationRecommendationService:
    """Recommend one grounded automation from the selected Hubitat devices.

    Device discovery and candidate selection are deterministic. AI receives one
    compact recommendation candidate and may only improve its wording. This avoids
    the general MCP planner failing before it has called a device tool.
    """

    def __init__(
        self,
        application: Any,
        device_index: Any,
        *,
        ai_timeout_seconds: float = 20.0,
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.ai_timeout_seconds = max(8.0, min(60.0, float(ai_timeout_seconds)))

    @staticmethod
    def matches(query: str) -> bool:
        return bool(_AUTOMATION_RECOMMENDATION_QUERY.match(str(query or "").strip()))

    async def answer(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        devices = list(await self.device_index.enriched_devices(force=True))
        records = self._records(devices)
        candidates = self._candidates(records)
        selected = candidates[0] if candidates else self._generic_candidate(records)
        deterministic = self._deterministic(selected)

        ai_message: str | None = None
        ai_error: str | None = None
        model: str | None = None
        ai_provider: str | None = None
        if selected:
            try:
                ai_message, model, ai_provider = await asyncio.wait_for(
                    self._natural_answer(query, selected, deterministic),
                    timeout=self.ai_timeout_seconds + 1.0,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                ai_error = str(exc) or exc.__class__.__name__

        message = ai_message or deterministic
        display = self._display(selected, records, message, ai_error)
        elapsed = round((time.perf_counter() - started) * 1000)
        ai_attempted = selected is not None
        ai_used = bool(ai_message)

        return {
            "success": selected is not None,
            "route": (
                "ollama+automation-recommendation"
                if ai_used
                else "mcp-automation-recommendation-ai-fallback"
                if ai_attempted
                else "mcp-automation-recommendation"
            ),
            "intent": "automation-recommendation",
            "message": message,
            "model": model,
            "answered_by": "Ollama" if ai_used else "HomeBrain recommendation",
            "ai_provider": ai_provider,
            "ai_attempted": ai_attempted,
            "ai_used": ai_used,
            "ai_status": (
                "used" if ai_used else "fallback" if ai_attempted else "not-attempted"
            ),
            "evidence_source": "Hubitat MCP selected devices",
            "display": display,
            "recommendation": selected,
            "candidate_count": len(candidates),
            "selected_device_count": len(records),
            "synthesis_error": ai_error,
            "elapsed_ms": elapsed,
            "technical": safe_debug(
                {
                    "selected_recommendation": selected,
                    "candidate_count": len(candidates),
                    "candidate_types": [item["type"] for item in candidates[:8]],
                    "selected_device_count": len(records),
                    "model": model,
                    "ai_provider": ai_provider,
                    "ollama_synthesis_error": ai_error,
                }
            ),
        }

    def _records(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        group_resolver = getattr(self.device_index, "_groups", None)
        for item in devices:
            if item.get("disabled") is True:
                continue
            try:
                groups = set(group_resolver(item)) if callable(group_resolver) else set()
            except Exception:
                groups = set()
            attrs = _attributes(item)
            label = _label(item) or "Unnamed device"
            values.append(
                {
                    "label": label,
                    "normal": _normalise(label),
                    "room": _room_name(item),
                    "groups": groups,
                    "attributes": attrs,
                    "switch": _state(attrs.get("switch")),
                }
            )
        return values

    def _candidates(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        for item in records:
            text = item["normal"]
            groups = item["groups"]
            attrs = item["attributes"]
            if (
                any(term in text for term in ("washing", "washer", "laundry"))
                and ("power" in groups or "power" in attrs)
            ):
                candidates.append(
                    self._candidate(
                        score=100,
                        kind="washing-complete",
                        title="Washing machine finished notification",
                        room=item["room"],
                        devices=[item["label"]],
                        trigger=(
                            f"Arm when {item['label']} rises above 10 W, then trigger when "
                            "power stays below 5 W for 3 minutes."
                        ),
                        action="Send a phone notification that the washing cycle has finished.",
                        safeguard=(
                            "Only allow the low-power trigger after a cycle has first crossed "
                            "the running threshold, so standby power does not create false alerts."
                        ),
                        reason="It uses a power-reading device to replace repeated manual checking.",
                    )
                )

            if "contact" in groups and any(term in text for term in ("fridge", "freezer")):
                candidates.append(
                    self._candidate(
                        score=95,
                        kind="cold-storage-door",
                        title=f"{item['label']} left-open alert",
                        room=item["room"],
                        devices=[item["label"]],
                        trigger=f"Trigger when {item['label']} remains open for 2 minutes.",
                        action="Send a high-priority phone notification and repeat once after 5 minutes if it is still open.",
                        safeguard="Cancel all pending alerts immediately when the contact closes.",
                        reason="It can prevent wasted energy and food warming after a door is left open.",
                    )
                )

        by_room: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            if item["room"]:
                by_room.setdefault(_normalise(item["room"]), []).append(item)

        for room_key, items in by_room.items():
            room = items[0]["room"]
            motions = [item for item in items if "motion" in item["groups"]]
            lights = [item for item in items if "light" in item["groups"]]
            if motions and lights:
                motion_names = [item["label"] for item in motions[:2]]
                light_names = [item["label"] for item in lights[:3]]
                candidates.append(
                    self._candidate(
                        score=80,
                        kind="motion-lighting",
                        title=f"Motion lighting for {room}",
                        room=room,
                        devices=motion_names + light_names,
                        trigger=f"Trigger when {' or '.join(motion_names)} becomes active.",
                        action=f"Turn on {', '.join(light_names)}, then turn them off after 3 minutes with no motion.",
                        safeguard="Run only when the light level is low or during the evening, and restart the off-delay when motion returns.",
                        reason="It links sensors and lights already assigned to the same Hubitat room.",
                    )
                )

            humidity = [item for item in items if "humidity" in item["groups"]]
            fans = [
                item
                for item in items
                if "fan" in item["groups"]
                or ("switch" in item["groups"] and "fan" in item["normal"])
            ]
            if humidity and fans:
                candidates.append(
                    self._candidate(
                        score=70,
                        kind="humidity-ventilation",
                        title=f"Humidity-controlled ventilation for {room}",
                        room=room,
                        devices=[humidity[0]["label"], fans[0]["label"]],
                        trigger=f"Turn on {fans[0]['label']} when {humidity[0]['label']} rises above 65% humidity.",
                        action="Keep ventilation running until humidity falls below 60% for 5 minutes.",
                        safeguard="Use separate on/off thresholds and a minimum run time to prevent rapid cycling.",
                        reason="It combines a humidity reading with a controllable fan in the same room.",
                    )
                )

        candidates.sort(key=lambda item: (-int(item["score"]), item["title"].lower()))
        return candidates

    @staticmethod
    def _candidate(
        *,
        score: int,
        kind: str,
        title: str,
        room: str,
        devices: list[str],
        trigger: str,
        action: str,
        safeguard: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "score": score,
            "type": kind,
            "title": title,
            "room": room or None,
            "devices": list(dict.fromkeys(devices)),
            "trigger": trigger,
            "action": action,
            "safeguard": safeguard,
            "reason": reason,
        }

    def _generic_candidate(self, records: list[dict[str, Any]]) -> dict[str, Any] | None:
        battery_devices = [item for item in records if "battery" in item["groups"]]
        if battery_devices:
            names = [item["label"] for item in battery_devices[:5]]
            return self._candidate(
                score=10,
                kind="battery-maintenance",
                title="Weekly low-battery maintenance alert",
                room="",
                devices=names,
                trigger="Run once each week and check selected battery devices for values at or below 20%.",
                action="Send one grouped notification naming only the devices that need attention.",
                safeguard="Do not repeat the same device every day; notify again only after its value changes or one week passes.",
                reason="The selected device inventory contains battery-powered devices but no stronger paired-device opportunity was found.",
            )
        return None

    @staticmethod
    def _deterministic(candidate: dict[str, Any] | None) -> str:
        if not candidate:
            return (
                "I could not find a safe automation pairing in the currently selected Hubitat "
                "devices. Assign accurate rooms and expose motion, contact, power or humidity "
                "capabilities, then ask again."
            )
        devices = ", ".join(candidate["devices"])
        return (
            f"A useful automation is **{candidate['title']}** using {devices}. "
            f"Trigger: {candidate['trigger']} Action: {candidate['action']} "
            f"Safeguard: {candidate['safeguard']}"
        )

    @staticmethod
    def _display(
        candidate: dict[str, Any] | None,
        records: list[dict[str, Any]],
        message: str,
        ai_error: str | None,
    ) -> dict[str, Any]:
        if not candidate:
            display = display_payload(
                "automation-recommendation",
                "Automation recommendation",
                subtitle="No safe device pairing found",
                metrics=[
                    {"label": "Selected devices checked", "value": str(len(records)), "icon": "📱"}
                ],
                note="No automation was invented without a compatible verified device pairing.",
            )
            display["summary"] = message
            return display

        items = [
            {
                "icon": "⚡",
                "title": "Trigger",
                "value": "",
                "subtitle": candidate["trigger"],
            },
            {
                "icon": "▶️",
                "title": "Action",
                "value": "",
                "subtitle": candidate["action"],
            },
            {
                "icon": "🛡️",
                "title": "Safeguard",
                "value": "",
                "subtitle": candidate["safeguard"],
            },
        ]
        display = display_payload(
            "automation-recommendation",
            candidate["title"],
            subtitle=(
                f"Grounded in {len(candidate['devices'])} selected Hubitat device"
                f"{'s' if len(candidate['devices']) != 1 else ''}"
            ),
            metrics=[
                {"label": "Devices used", "value": str(len(candidate["devices"])), "icon": "📱"},
                {"label": "Room", "value": candidate.get("room") or "Multiple/none", "icon": "🚪"},
                {"label": "Candidate type", "value": candidate["type"].replace("-", " "), "icon": "⚙️"},
            ],
            items=items,
            note=(
                "This is a recommendation only; HomeBrain has not created or changed a rule. "
                "Check for an existing similar automation before implementing it."
                + (
                    " AI wording failed, so the grounded HomeBrain recommendation is shown."
                    if ai_error
                    else ""
                )
            ),
        )
        display["summary"] = message
        return display

    async def _natural_answer(
        self,
        query: str,
        candidate: dict[str, Any],
        deterministic: str,
    ) -> tuple[str, str, str]:
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
        body = await ollama._chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are HomeBrain. Recommend exactly one practical smart-home automation "
                        "using only the verified candidate supplied. Keep the exact device names, "
                        "trigger, action and safeguard. Explain briefly why it is useful. Do not "
                        "claim the rule already exists, do not create it, and do not introduce "
                        "devices or capabilities that are not in the evidence. Use one short heading "
                        "and three concise paragraphs or bullets."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {query}\n"
                        f"Verified automation candidate: {json.dumps(candidate, ensure_ascii=False, separators=(',', ':'))}\n"
                        f"Reliable fallback: {deterministic}"
                    ),
                },
            ],
            tools=None,
            timeout_seconds=self.ai_timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=180,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty automation recommendation")
        actual_model = str(body.get("_homebrain_model_used") or model).strip()
        provider = str(body.get("_homebrain_provider") or "Local Ollama").strip()
        return content, actual_model, provider


def install_automation_recommendation(
    application: Any,
    device_index: Any,
    *,
    ai_timeout_seconds: float = 20.0,
) -> AutomationRecommendationService:
    original_ask: AskHandler = application.ask
    service = AutomationRecommendationService(
        application,
        device_index,
        ai_timeout_seconds=ai_timeout_seconds,
    )

    async def ask_with_automation_recommendation(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if service.matches(query):
            answer = await service.answer(query)
            answer.setdefault("version", application.VERSION)
            return answer
        return await original_ask(request)

    application.ask = ask_with_automation_recommendation
    application.automation_recommendation = service
    return service


__all__ = [
    "AutomationRecommendationService",
    "_AUTOMATION_RECOMMENDATION_QUERY",
    "install_automation_recommendation",
]
