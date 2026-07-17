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

# Safe speech/name variants that preserve the intended device meaning. The
# normalised form is accepted only when exactly one selected MCP device matches.
_DEVICE_WORD_ALIASES = {
    "prayer": "pray",
    "prayers": "pray",
}

_HUMIDITY_APPLIANCE_WORDS = {"humidifier", "dehumidifier"}


def normalise_spoken_device_name(value: str) -> str:
    """Normalise common speech-to-text variants without changing device meaning."""
    words = re.findall(r"[a-z0-9]+", _normalise(value))
    normalised: list[str] = []
    for word in words:
        if word == "number":
            continue
        word = _NUMBER_WORDS.get(word, word)
        word = _DEVICE_WORD_ALIASES.get(word, word)
        normalised.append(word)
    return " ".join(normalised)


def _humidity_speech_key(value: str) -> str | None:
    """Return a shared key for humidifier/dehumidifier speech variants.

    Speech recognition commonly drops the short leading "de" sound. This key is
    used only after exact matching has failed, and only a unique full-label match
    is accepted. Other words and number suffixes must still match exactly.
    """
    words = normalise_spoken_device_name(value).split()
    if not any(word in _HUMIDITY_APPLIANCE_WORDS for word in words):
        return None
    return " ".join(
        "humidity-appliance" if word in _HUMIDITY_APPLIANCE_WORDS else word
        for word in words
    )


class FastFallbackRouter(DeviceHealthFastFallbackRouter):
    """Fast fallback with speech-aware matching and verified device controls."""

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

    @staticmethod
    def _humidity_speech_alias_match(
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        requested_key = _humidity_speech_key(requested_name)
        if not requested_key:
            return None
        matches = [
            item
            for item in candidates
            if _label(item) and _humidity_speech_key(_label(item)) == requested_key
        ]
        return matches[0] if len(matches) == 1 else None

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        answer = await super()._control_device(requested_name, action)
        if answer.get("intent") not in {
            "fallback-ambiguous-device",
            "fallback-device-not-found",
        }:
            return answer

        # The MCP label filter may not equate spoken numbers with digits. Retry
        # against the complete live switch inventory before involving Ollama.
        live_result = await self._live_devices("Switch")
        candidates = self._device_rows(live_result.data)
        match, alternatives = self._match_device(requested_name, candidates)
        if match:
            return await super()._control_device(_label(match), action)

        # Speech-to-text often hears "dehumidifier" as "humidifier". Treat those
        # words as equivalent only when every other label token (including its
        # number) matches and exactly one live switch candidate exists.
        speech_alias = self._humidity_speech_alias_match(requested_name, candidates)
        if speech_alias:
            resolved_label = _label(speech_alias)
            resolved = await super()._control_device(resolved_label, action)
            resolved = dict(resolved)
            resolved.update(
                {
                    "speech_alias_applied": True,
                    "heard_device_name": requested_name,
                    "resolved_device_name": resolved_label,
                }
            )
            resolved["message"] = (
                f'Interpreted “{requested_name}” as “{resolved_label}” from speech.\n'
                + str(resolved.get("message") or "")
            ).strip()
            return resolved

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


__all__ = [
    "FastFallbackRouter",
    "normalise_spoken_device_name",
]
