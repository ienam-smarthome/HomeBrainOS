from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from fallback_router import _label, _normalise
from fast_fallback_device_health import FastFallbackRouter as DeviceHealthFastFallbackRouter


_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def normalise_spoken_device_name(value: str) -> str:
    """Normalise common speech-to-text variants without changing device meaning."""
    words = re.findall(r"[a-z0-9]+", _normalise(value))
    normalised: list[str] = []
    for word in words:
        if word == "number":
            continue
        normalised.append(_NUMBER_WORDS.get(word, word))
    return " ".join(normalised)


class FastFallbackRouter(DeviceHealthFastFallbackRouter):
    """Fast fallback with safe speech-number matching and richer ambiguity data."""

    @staticmethod
    def _match_device(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[str]]:
        target = normalise_spoken_device_name(requested_name)
        exact = [
            item
            for item in candidates
            if normalise_spoken_device_name(_label(item)) == target
        ]
        if len(exact) == 1:
            return exact[0], []

        scored = sorted(
            (
                (
                    SequenceMatcher(
                        None,
                        target,
                        normalise_spoken_device_name(_label(item)),
                    ).ratio(),
                    item,
                )
                for item in candidates
                if _label(item)
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        alternatives = [_label(item) for score, item in scored if score >= 0.35]
        return None, alternatives

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        answer = await super()._control_device(requested_name, action)
        if answer.get("intent") not in {
            "fallback-ambiguous-device",
            "fallback-device-not-found",
        }:
            return answer

        # The MCP label filter may not equate spoken numbers with digits. Retry
        # against the live switch inventory, then repeat the command using the
        # authoritative label when one exact normalised match exists.
        live_result = await self._live_devices("Switch")
        candidates = self._device_rows(live_result.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if match:
            return await super()._control_device(_label(match), action)

        enriched = dict(answer)
        enriched.update(
            {
                "requested_name": requested_name,
                "requested_action": action,
                "alternatives": alternatives[:5],
                "normalised_requested_name": normalise_spoken_device_name(
                    requested_name
                ),
            }
        )
        if alternatives:
            enriched["message"] = (
                "I could not find an exact device match. Closest matches: "
                + ", ".join(alternatives[:5])
                + "."
            )
            enriched["intent"] = "fallback-ambiguous-device"
        return enriched


__all__ = ["FastFallbackRouter", "normalise_spoken_device_name"]
