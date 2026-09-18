"""Cross-check final temporal narratives against deterministic history proof."""

from __future__ import annotations

import re
from typing import Any

_COUNT_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_COUNT_TOKEN = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_EXHAUSTIVE_INTERVAL_CLAIM = re.compile(
    rf"\b(?:during|across|over|in|through)\s+(?P<count>{_COUNT_TOKEN})\s+"
    r"(?:(?:separate|observed|recorded|bounded)\s+)*(?:periods?|intervals?|stretches?|runs?|times?)\b"
    r"|\b(?P<count2>" + _COUNT_TOKEN + r")\s+"
    r"(?:(?:separate|observed|recorded|bounded)\s+)+(?:periods?|intervals?|stretches?|runs?)\b",
    re.I,
)

_KNOWN_HISTORY_ATTRIBUTES = (
    "motion", "illuminance", "contact", "presence", "switch",
    "temperature", "humidity", "power", "battery", "level",
)
_ATTRIBUTE_ABSENCE = re.compile(
    r"\b(?:no|without)\b[^.!?]{0,90}\b(?:"
    + "|".join(_KNOWN_HISTORY_ATTRIBUTES)
    + r")\b[^.!?]{0,90}\b(?:data|events?|activity|history|readings?)\b",
    re.I,
)


def _sentence_pieces(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(?P<space>\s+)", str(text or ""))


def _count_value(token: str) -> int | None:
    token = str(token or "").strip().casefold()
    if token.isdigit():
        try:
            return int(token)
        except ValueError:
            return None
    return _COUNT_WORDS.get(token)


def _history_receipts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and isinstance(receipt.get("details"), dict)
    ]


def _temporal(receipt: dict[str, Any]) -> dict[str, Any] | None:
    details = receipt.get("details")
    if not isinstance(details, dict):
        return None
    temporal = details.get("temporalAnalysis")
    return temporal if isinstance(temporal, dict) else None


def _label(receipt: dict[str, Any]) -> str:
    details = receipt.get("details")
    return str((details or {}).get("label") or "").strip()


def _matching_temporal_receipt(
    sentence: str,
    receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    comparable = re.sub(r"[*_]", "", sentence).casefold()
    named = [
        receipt
        for receipt in receipts
        if _temporal(receipt) is not None
        and _label(receipt)
        and _label(receipt).casefold() in comparable
    ]
    if named:
        return max(named, key=lambda receipt: len(_label(receipt)))
    nonzero = []
    for receipt in receipts:
        temporal = _temporal(receipt)
        if temporal is None:
            continue
        try:
            count = int(temporal.get("intervalCount") or 0)
        except (TypeError, ValueError):
            continue
        if count > 0:
            nonzero.append(receipt)
    return nonzero[0] if len(nonzero) == 1 else None


def guard_history_interval_count_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Keep exhaustive interval-cardinality claims aligned with temporal proof."""

    text = str(message or "")
    if not _EXHAUSTIVE_INTERVAL_CLAIM.search(text):
        return text, []

    receipts = _history_receipts(evidence)
    if not receipts:
        return text, []

    pieces = _sentence_pieces(text)
    changed_receipts: list[dict[str, Any]] = []
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        match = _EXHAUSTIVE_INTERVAL_CLAIM.search(sentence)
        if match is None:
            continue
        claimed = _count_value(match.group("count") or match.group("count2"))
        receipt = _matching_temporal_receipt(sentence, receipts)
        if claimed is None or receipt is None:
            continue
        temporal = _temporal(receipt) or {}
        try:
            expected = int(temporal.get("intervalCount"))
        except (TypeError, ValueError):
            continue
        if expected < 0 or claimed == expected:
            continue

        details = receipt.get("details") or {}
        label = str(details.get("label") or "the device").strip() or "the device"
        active_state = str(temporal.get("activeState") or "active").strip() or "active"
        window_label = str(temporal.get("windowLabel") or "").strip()
        window_suffix = f" {window_label}" if window_label else ""
        if claimed < expected:
            replacement = (
                f"during {claimed} highlighted periods out of {expected} observed "
                f"bounded {active_state} intervals"
            )
        else:
            replacement = f"during {expected} observed bounded {active_state} intervals"
        pieces[index] = (
            sentence[: match.start()]
            + replacement
            + sentence[match.end() :]
        )
        if receipt not in changed_receipts:
            changed_receipts.append(receipt)

    return "".join(pieces), changed_receipts


def _attributes_in_sentence(sentence: str) -> list[str]:
    lower = sentence.casefold()
    return [
        attribute
        for attribute in _KNOWN_HISTORY_ATTRIBUTES
        if re.search(rf"\b{re.escape(attribute)}\b", lower)
    ]


def _receipts_for_attribute(
    receipts: list[dict[str, Any]],
    attribute: str,
) -> list[dict[str, Any]]:
    return [
        receipt
        for receipt in receipts
        if str((receipt.get("details") or {}).get("attribute") or "").casefold()
        == attribute.casefold()
    ]


def _generic_receipts_observing(
    receipts: list[dict[str, Any]],
    attribute: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    wanted = attribute.casefold()
    for receipt in receipts:
        details = receipt.get("details") or {}
        if details.get("attribute"):
            continue
        names = details.get("observedEventNames")
        if not isinstance(names, list):
            continue
        if any(str(name).casefold() == wanted for name in names):
            matches.append(receipt)
    return matches


def guard_history_attribute_absence_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Prevent unverified or generic history from proving attribute absence."""

    text = str(message or "")
    if not _ATTRIBUTE_ABSENCE.search(text):
        return text, []

    receipts = _history_receipts(evidence)
    if not receipts:
        return text, []

    pieces = _sentence_pieces(text)
    changed_receipts: list[dict[str, Any]] = []
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _ATTRIBUTE_ABSENCE.search(sentence):
            continue
        attributes = _attributes_in_sentence(sentence)
        if not attributes:
            continue

        corrections: list[str] = []
        unsafe = False
        for attribute in attributes:
            explicit = _receipts_for_attribute(receipts, attribute)
            explicit_unsafe = False
            if explicit:
                for receipt in explicit:
                    temporal = _temporal(receipt)
                    if temporal is None:
                        continue
                    verified = temporal.get("sourceIntegrityVerified") is True
                    if verified:
                        continue
                    explicit_unsafe = True
                    unsafe = True
                    label = _label(receipt) or "the related device"
                    active_state = str(
                        temporal.get("activeState") or attribute
                    ).strip() or attribute
                    try:
                        interval_count = int(temporal.get("intervalCount") or 0)
                    except (TypeError, ValueError):
                        interval_count = 0
                    if interval_count == 0:
                        corrections.append(
                            f"For {label}, no bounded {active_state} interval was "
                            f"established from the retrieved {attribute} rows; the "
                            "event stream is unverified, so this does not prove "
                            f"{attribute} activity was absent."
                        )
                    else:
                        corrections.append(
                            f"{label}'s {attribute} history was checked and contains "
                            f"{interval_count} observed bounded interval"
                            f"{'s' if interval_count != 1 else ''}; it cannot be "
                            "described as missing."
                        )
                    if receipt not in changed_receipts:
                        changed_receipts.append(receipt)
            if explicit_unsafe:
                continue

            generic = _generic_receipts_observing(receipts, attribute)
            if generic:
                unsafe = True
                labels = ", ".join(
                    dict.fromkeys(
                        _label(receipt) or "related device" for receipt in generic
                    )
                )
                corrections.append(
                    f"Generic history for {labels} contains recorded {attribute} rows, "
                    f"but {attribute} was not explicitly analyzed for this correlation; "
                    "absence is therefore not established."
                )
                for receipt in generic:
                    if receipt not in changed_receipts:
                        changed_receipts.append(receipt)
                continue

            unsafe = True
            corrections.append(
                f"No explicit {attribute} history read established absence for the "
                "requested period."
            )

        if unsafe and corrections:
            pieces[index] = " ".join(dict.fromkeys(corrections))

    return "".join(pieces), changed_receipts


__all__ = [
    "guard_history_attribute_absence_claim",
    "guard_history_interval_count_claim",
]
