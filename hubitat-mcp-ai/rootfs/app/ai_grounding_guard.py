from __future__ import annotations

import json
import re
from collections import deque
from typing import Any


_PROSE_KEYS = {
    "message",
    "original_message",
    "technical",
    "summary",
    "reasoning",
    "analysis",
}
_GENERIC_ENTITY_NAMES = {
    "home",
    "hubitat",
    "homebrain",
    "ollama",
}


def _normalise(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()),
    ).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {text} "


def _is_ai_answer(answer: dict[str, Any]) -> bool:
    if answer.get("ai_used") is True:
        return True
    route = _normalise(answer.get("route"))
    intent = _normalise(answer.get("intent"))
    answered_by = _normalise(answer.get("answered_by"))
    return (
        "ollama" in route
        or route.startswith("ai ")
        or intent.startswith("ai ")
        or "ollama" in answered_by
    )


def _evidence_value(value: Any, *, key: str = "") -> Any:
    if key.casefold() in _PROSE_KEYS:
        return None
    if isinstance(value, dict):
        return {
            str(child_key): cleaned
            for child_key, child_value in value.items()
            if (cleaned := _evidence_value(child_value, key=str(child_key)))
            not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            cleaned
            for item in value
            if (cleaned := _evidence_value(item)) not in (None, "", [], {})
        ]
    return value


def _evidence_text(answer: dict[str, Any]) -> str:
    cleaned = _evidence_value(answer)
    return _normalise(json.dumps(cleaned, ensure_ascii=False, default=str))


def _device_labels(devices: list[dict[str, Any]]) -> list[str]:
    labels: set[str] = set()
    for item in devices:
        for key in ("label", "displayName", "name"):
            value = str(item.get(key) or "").strip()
            normal = _normalise(value)
            if (
                len(normal) >= 3
                and normal not in _GENERIC_ENTITY_NAMES
                and not normal.isdigit()
            ):
                labels.add(value)
    return sorted(labels, key=lambda value: (-len(_normalise(value)), value.casefold()))


def _fallback_message(answer: dict[str, Any], unverified: list[str]) -> str:
    for key in ("grounded_fallback", "deterministic_message", "fallback_message"):
        value = str(answer.get(key) or "").strip()
        if value:
            return value

    verified_rows: list[str] = []
    queue: deque[Any] = deque(
        value for key, value in answer.items() if key.casefold() not in _PROSE_KEYS
    )
    seen: set[str] = set()
    while queue and len(verified_rows) < 8:
        value = queue.popleft()
        if isinstance(value, list):
            queue.extend(value)
            continue
        if not isinstance(value, dict):
            continue
        label = str(
            value.get("device")
            or value.get("label")
            or value.get("displayName")
            or ""
        ).strip()
        if label:
            detail = str(
                value.get("detail")
                or value.get("status")
                or value.get("value")
                or ""
            ).strip()
            row = f"{label}: {detail}" if detail else label
            marker = _normalise(row)
            if marker and marker not in seen:
                seen.add(marker)
                verified_rows.append(row)
        queue.extend(value.values())

    withheld = ", ".join(unverified)
    prefix = (
        "I withheld the AI wording because these device names were not present "
        f"in its Hubitat evidence: {withheld}."
    )
    if verified_rows:
        return prefix + "\n\nVerified evidence:\n- " + "\n- ".join(verified_rows)
    return prefix + " Please retry so HomeBrain can return a deterministic evidence view."


class AIGroundingGuard:
    """Reject AI device claims that are absent from the supplied tool evidence."""

    def __init__(self, device_index: Any, *, limit: int = 50) -> None:
        self.device_index = device_index
        self.limit = max(10, min(500, int(limit)))
        self.total_ai_answers = 0
        self.evaluated_answers = 0
        self.triggered_answers = 0
        self.index_errors = 0
        self._recent: deque[dict[str, Any]] = deque(maxlen=self.limit)

    async def guard(
        self,
        request: Any,
        answer: dict[str, Any],
    ) -> dict[str, Any]:
        if not _is_ai_answer(answer):
            return answer

        self.total_ai_answers += 1
        try:
            devices = await self.device_index.summary_devices()
        except Exception as exc:
            self.index_errors += 1
            answer["grounding_guard"] = {
                "evaluated": False,
                "reason": f"device-index-unavailable:{type(exc).__name__}",
            }
            return answer

        message = _normalise(answer.get("message"))
        evidence = _evidence_text(answer)
        mentioned = [
            label
            for label in _device_labels(devices)
            if _contains_phrase(message, _normalise(label))
        ]
        unverified = [
            label
            for label in mentioned
            if not _contains_phrase(evidence, _normalise(label))
        ]
        self.evaluated_answers += 1
        record = {
            "query": str(getattr(request, "query", "") or "")[:200],
            "route": answer.get("route"),
            "mentioned_entities": mentioned,
            "unverified_entities": unverified,
            "triggered": bool(unverified),
        }
        self._recent.appendleft(record)

        answer["grounding_guard"] = {
            "evaluated": True,
            "triggered": bool(unverified),
            "mentioned_entities": mentioned,
            "unverified_entities": unverified,
        }
        if not unverified:
            return answer

        self.triggered_answers += 1
        answer["message"] = _fallback_message(answer, unverified)
        answer["ai_used"] = False
        answer["ai_grounding_rejected"] = True
        answer["answered_by"] = "HomeBrain grounding guard"
        answer["route"] = "grounded-evidence-fallback"
        return answer

    def response(self) -> dict[str, Any]:
        rate = (
            self.triggered_answers / self.evaluated_answers * 100.0
            if self.evaluated_answers
            else 0.0
        )
        return {
            "success": True,
            "total_ai_answers": self.total_ai_answers,
            "evaluated_answers": self.evaluated_answers,
            "triggered_answers": self.triggered_answers,
            "trigger_rate_percent": round(rate, 2),
            "device_index_errors": self.index_errors,
            "recent": list(self._recent),
        }


def install_ai_grounding_guard(application: Any, device_index: Any) -> AIGroundingGuard:
    guard = AIGroundingGuard(device_index)

    @application.app.get("/api/ai-grounding", response_model=None)
    async def ai_grounding():
        return guard.response()

    application.ai_grounding_guard = guard
    return guard


__all__ = ["AIGroundingGuard", "install_ai_grounding_guard"]
