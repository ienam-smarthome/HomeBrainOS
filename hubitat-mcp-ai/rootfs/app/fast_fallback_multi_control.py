from __future__ import annotations

import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_index import _FRESH_CONTROL_READS
from fast_fallback_engagement import FastFallbackRouter as EngagementFastFallbackRouter
from presenter import display_payload, safe_debug


_TARGET_SEPARATOR = re.compile(r"\s*(?:,|\band\b)\s*", re.IGNORECASE)
_TRAILING_DISPLAY_QUALIFIER = re.compile(
    r"\s*(?:\([^()]{1,80}\)|\[[^\[\]]{1,80}\])\s*$"
)
_UNSAFE_TARGET_TERMS = (
    " if ",
    " unless ",
    " when ",
    " except ",
    " but ",
    " then ",
    " after ",
    " before ",
    " whichever ",
    " which ",
    " that are ",
)
_CONTEXT_WORDS = {"it", "them", "that", "those", "these", "same", "other", "there"}


def split_explicit_control_targets(value: str) -> list[str] | None:
    """Return two to six safe explicit target names from one control phrase.

    This intentionally handles only conjunctions such as ``fan switch and fan
    boost``. Contextual pronouns, conditions and long natural-language clauses stay
    on the planner route. Every returned target still has to resolve uniquely to one
    live selected Hubitat device before any write is allowed.
    """

    text = re.sub(r"\s+", " ", str(value or "").strip(" .!?"))
    lowered = f" {text.lower()} "
    if not text or not ("," in text or re.search(r"\band\b", text, re.IGNORECASE)):
        return None
    if any(term in lowered for term in _UNSAFE_TARGET_TERMS):
        return None

    targets = [
        re.sub(r"^(?:the\s+)", "", item.strip(), flags=re.IGNORECASE)
        for item in _TARGET_SEPARATOR.split(text)
    ]
    if not 2 <= len(targets) <= 6 or any(not item for item in targets):
        return None

    for target in targets:
        words = re.findall(r"[a-z0-9]+", target.lower())
        if not words or len(words) > 8 or _CONTEXT_WORDS.intersection(words):
            return None
    return targets


def base_device_label(value: str) -> str:
    """Return a label without trailing display/integration qualifiers.

    Hubitat labels commonly include source suffixes such as ``(Tuya Local)``.
    Spoken commands may safely omit such a suffix only when the resulting base name
    identifies exactly one currently selected device. Multiple matching base labels
    remain ambiguous and are never controlled.
    """

    text = re.sub(r"\s+", " ", str(value or "").strip())
    previous = None
    while text and text != previous:
        previous = text
        text = _TRAILING_DISPLAY_QUALIFIER.sub("", text).strip()
    return _normalise(text)


class FastFallbackRouter(EngagementFastFallbackRouter):
    """Final fallback router with exact, verified named multi-device controls."""

    def _match_named_target(
        self,
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[str], str | None]:
        """Resolve an exact label or one unique suffix-free label alias."""

        match, alternatives = self._match_device(requested_name, candidates)
        if match is not None:
            return match, alternatives, "exact-label"

        target = _normalise(requested_name)
        base_matches = [
            item
            for item in candidates
            if _label(item) and base_device_label(_label(item)) == target
        ]
        if len(base_matches) == 1:
            return base_matches[0], [_label(base_matches[0])], "unique-base-label"
        if len(base_matches) > 1:
            return (
                None,
                sorted({_label(item) for item in base_matches if _label(item)}, key=str.lower),
                "ambiguous-base-label",
            )
        return None, alternatives, None

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        targets = split_explicit_control_targets(requested_name)
        if targets is None:
            return await super()._control_device(requested_name, action)

        token = _FRESH_CONTROL_READS.set(True)
        try:
            live_result = await self._live_devices("Switch")
            candidates = self._device_rows(live_result.data)

            # A real selected device label may itself contain "and". Preserve that
            # exact single-device interpretation before treating the phrase as a list.
            whole_match, _, _ = self._match_named_target(requested_name, candidates)
            if whole_match is not None:
                return await super()._control_device(_label(whole_match), action)

            resolved: list[dict[str, Any]] = []
            resolution_details: list[dict[str, Any]] = []
            failures: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            for target in targets:
                match, alternatives, method = self._match_named_target(target, candidates)
                if match is None:
                    error = (
                        "Base device name matches more than one selected device"
                        if method == "ambiguous-base-label"
                        else "No unique selected-device label or safe base-label match"
                    )
                    failures.append(
                        {
                            "target": target,
                            "alternatives": alternatives[:5],
                            "error": error,
                            "match_method": method,
                        }
                    )
                    continue
                device_id = _device_id(match)
                key = str(device_id)
                if device_id is None:
                    failures.append(
                        {
                            "target": target,
                            "alternatives": [],
                            "error": "Matched device has no ID",
                            "match_method": method,
                        }
                    )
                    continue
                if key in seen_ids:
                    failures.append(
                        {
                            "target": target,
                            "alternatives": [_label(match)],
                            "error": "Two requested names resolved to the same device",
                            "match_method": method,
                        }
                    )
                    continue
                seen_ids.add(key)
                resolved.append(match)
                resolution_details.append(
                    {
                        "target": target,
                        "id": device_id,
                        "label": _label(match),
                        "match_method": method,
                    }
                )

            if failures:
                items = []
                lines = []
                for failure in failures:
                    alternatives = failure.get("alternatives") or []
                    detail = str(failure.get("error") or "Could not resolve")
                    if alternatives:
                        detail += ": " + ", ".join(str(item) for item in alternatives)
                    lines.append(f"- {failure['target']}: {detail}")
                    items.append(
                        {
                            "icon": "⚠️",
                            "title": str(failure["target"]),
                            "value": "Not changed",
                            "subtitle": detail,
                            "tone": "warning",
                        }
                    )
                display = display_payload(
                    "named-multi-device-control-blocked",
                    "Multi-device control blocked",
                    subtitle="No commands sent",
                    metrics=[
                        {"label": "Requested", "value": str(len(targets)), "icon": "🎛️"},
                        {"label": "Unique matches", "value": str(len(resolved)), "icon": "✅"},
                        {"label": "Unresolved", "value": str(len(failures)), "icon": "⚠️"},
                    ],
                    items=items,
                    note=(
                        "HomeBrain requires every named target to resolve uniquely before sending "
                        "any command. A trailing label qualifier such as (Tuya Local) may be "
                        "omitted only when the remaining base name is unique."
                    ),
                )
                response = self._response(
                    "No devices were changed because every requested target could not be matched uniquely.\n"
                    + "\n".join(lines),
                    "fallback-named-multi-control-unresolved",
                    False,
                    live_result,
                )
                response.update(
                    {
                        "display": display,
                        "requested_state": _normalise(action),
                        "requested_targets": targets,
                        "technical": safe_debug(
                            {
                                "requested_targets": targets,
                                "resolved": resolution_details,
                                "failures": failures,
                                "commands_sent": 0,
                            }
                        ),
                    }
                )
                return response

            answer = await self._control_group(
                " and ".join(_label(item) or target for item, target in zip(resolved, targets)),
                action,
                resolved,
                live_result,
            )
            answer = dict(answer)
            answer["intent"] = (
                "fallback-named-multi-control-confirmed"
                if answer.get("success")
                else "fallback-named-multi-control-partial"
            )
            answer["requested_targets"] = targets
            answer["resolved_targets"] = [
                {"id": _device_id(item), "label": _label(item)} for item in resolved
            ]
            answer["resolution_details"] = resolution_details
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "Every named target was uniquely matched before any command was sent. "
                    "Trailing display qualifiers may be omitted only for a unique base label. "
                    "Final switch states were read back from Hubitat using fresh MCP reads."
                )
            return answer
        finally:
            _FRESH_CONTROL_READS.reset(token)


__all__ = [
    "FastFallbackRouter",
    "base_device_label",
    "split_explicit_control_targets",
]
