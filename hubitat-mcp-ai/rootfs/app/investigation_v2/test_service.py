"""Explicitly gated read-only Investigation V2 browser test service.

The admission gate uses an operator-set secret and live Hubitat device IDs.
It does not call production V1, disclose the key, change a device, or install
any model-proposed permission. No implicit background/shadow execution.
"""
from __future__ import annotations

import hmac
import re
import unicodedata
from typing import Any, Iterable


def require_test_access(*, enabled: bool, configured_token: str,
                        supplied_token: str, explicit_opt_in: bool) -> None:
    if enabled is not True or len(configured_token) < 16:
        raise PermissionError("v2_test_disabled")
    if explicit_opt_in is not True:
        raise PermissionError("explicit_opt_in_required")
    if not supplied_token or not hmac.compare_digest(configured_token, supplied_token):
        raise PermissionError("invalid_test_token")


def match_verified_device_ids(requested: Iterable[str],
                              live_devices: Any) -> tuple[str, ...]:
    """Allow only exact, independently observed IDs from refreshed inventory."""
    requested = list(requested)
    if not 1 <= len(requested) <= 4:
        raise ValueError("Select one to four device IDs")
    ids = []
    for item in requested:
        if not isinstance(item, str) or not item.isdecimal() or len(item) > 20:
            raise ValueError("Device IDs must be decimal strings")
        ids.append(item)
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate device ID")
    if not isinstance(live_devices, list):
        raise ValueError("Live Hubitat device inventory unavailable")
    verified = {
        str(d["id"]) for d in live_devices if isinstance(d, dict)
        and type(d.get("id")) in (int, str)
        and str(d["id"]).isdecimal()
    }
    if not verified or any(i not in verified for i in ids):
        raise ValueError("Device ID not verified in refreshed Hubitat inventory")
    return tuple(ids)



def _words(value: str) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    return tuple(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold(),
                            flags=re.UNICODE))


def _inventory(live_devices: Any) -> dict[str, dict[str, Any]]:
    """Index trusted live identity IDs with labels and names; never model output."""
    if not isinstance(live_devices, list) or not live_devices:
        raise ValueError("Live Hubitat device inventory unavailable")
    devices: dict[str, dict[str, Any]] = {}
    for row in live_devices:
        if not isinstance(row, dict) or type(row.get("id")) not in (str, int):
            continue
        ident = str(row["id"])
        if not ident.isdecimal() or len(ident) > 20:
            continue
        aliases = []
        for key in ("label", "name"):
            value = row.get(key)
            if isinstance(value, str) and 1 <= len(value) <= 160 and _words(value):
                aliases.append(value.strip())
        if not aliases:
            continue
        friendly = row.get("label")
        friendly_words = (_words(friendly) if isinstance(friendly, str) else ())
        entry = devices.setdefault(
            ident, {"id": ident, "label": aliases[0],
                    "aliases": [], "friendly_words": friendly_words})
        if friendly_words and not entry["friendly_words"]:
            entry["friendly_words"] = friendly_words
            entry["label"] = friendly.strip()
        for alias in aliases:
            if alias not in entry["aliases"]:
                entry["aliases"].append(alias)
    if not devices:
        raise ValueError("Live Hubitat device names unavailable")
    return devices


def _ambiguous_inventory_targets(
    items: Iterable[dict[str, Any]], *, matched_phrase: str | None = None,
) -> str:
    """Safe, bounded candidate disclosure for an authenticated V2 operator.

    The choices are verified Hubitat inventory identities, never model guesses.
    Duplicate friendly labels remain ambiguous and require explicit ID input.
    """
    distinct = {item["id"]: item for item in items}
    choices = sorted(distinct.values(), key=lambda item: int(item["id"]))
    labels = []
    for item in choices[:6]:
        label = re.sub(r"[^\w .,&()/-]", "", item["label"])[:72].strip()
        labels.append(f"{label or 'Device'} (#{item['id']})")
    suffix = "; more matches exist" if len(choices) > 6 else ""
    phrase = (re.sub(r"[^\w .,&()/-]", "", matched_phrase)[:80].strip()
              if isinstance(matched_phrase, str) else "")
    phrase_text = f" Matching phrase: '{phrase}'." if phrase else ""
    return (
        "Ambiguous device name: multiple Hubitat devices have the same "
        "highest-priority verified name and cannot be matched uniquely."
        + phrase_text + " Matching IDs: " + "; ".join(labels) + suffix
        + ". Select the intended ID under Advanced options."
    )


# These are schema-level *read attributes*, never device aliases or
# instructions to choose a target. The grammar below only disambiguates
# attribute mentions adjacent to independently verified full device labels.
_STATE_ATTRIBUTE_TERMS = frozenset({
    "switch", "level", "power", "energy", "battery", "temperature",
    "humidity", "motion", "contact", "presence", "illuminance",
    "voltage", "current", "health", "network", "connectivity",
})


def _attribute_qualifier_before_subject(
    text: str, *, start: int, end: int, subject_start: int,
) -> bool:
    """Identify 'switch state of Hallway Light 1' as a property, not a plug.

    Only a narrow attribute + relation spanning directly to an already
    verified multiword subject qualifies. No ambiguous name is suppressed
    if the user actually refers to that device (e.g. 'check the switch
    and Hallway Light 1'), or if no independent full-name anchor exists.
    """
    if not 0 <= start < end <= subject_start <= len(text):
        return False
    if text[start:end] not in _STATE_ATTRIBUTE_TERMS:
        return False
    between = text[end:subject_start]
    return re.fullmatch(
        # Pair-valued status questions must retain a SINGLE verified
        # device subject: "switch state and brightness level of <label>".
        # Bare "switch and <label>" is still an ambiguous extra device.
        r"\s+(?:state|status|value|reading|readings|measurement|level)"
        r"(?:\s+and\s+(?:brightness(?:\s+level)?|dimmer\s+level|"
        r"switch(?:\s+(?:state|status))?|power|temperature|humidity|battery))?"
        r"\s+(?:of|for)\s+(?:the\s+)?", between,
    ) is not None


def resolve_verified_device_subjects(
    question: str, live_devices: Any, *,
    device_name: str | None = None,
    device_ids: Iterable[str] = (),
) -> tuple[tuple[str, ...], list[dict[str, str]], str]:
    """Read-only target resolution: exact host inventory names, no LLM ID guesses.

    Explicit IDs (advanced override) retain the existing strict verification.
    An optional entered friendly name must uniquely equal a live label/name.
    Otherwise identify longest whole-name mentions in the question. Ambiguous
    identity is never silently converted into a device read.
    """
    requested_ids = list(device_ids)
    if requested_ids:
        ids = match_verified_device_ids(requested_ids, live_devices)
        labels = {str(row["id"]): str(row.get("label") or row.get("name") or "Device")
                  for row in live_devices if isinstance(row, dict)
                  and type(row.get("id")) in (str, int)}
        return ids, [
            {"id": ident, "label": labels.get(ident, "Device " + ident)}
            for ident in ids
        ], "manual_id"

    inventory = _inventory(live_devices)
    hint = (device_name or "").strip()
    if hint:
        key = _words(hint)
        matching = [item for item in inventory.values()
                    if any(_words(alias) == key for alias in item["aliases"])]
        # Friendly Hubitat labels are user-defined device identities; a
        # second device's generic driver name must not override an exact
        # label. Duplicate friendly labels remain ambiguous.
        preferred = [item for item in matching if item["friendly_words"] == key]
        candidates = preferred or matching
        if len(candidates) != 1:
            if len(candidates) > 1:
                raise ValueError(_ambiguous_inventory_targets(
                    candidates, matched_phrase=hint))
            raise ValueError(
                "Device name does not uniquely match the live Hubitat inventory. "
                "Choose a full unique device name or use an ID under Advanced options."
            )
        item = candidates[0]
        return (item["id"],), [{"id": item["id"], "label": item["label"]}], "device_name"

    if not isinstance(question, str) or not question.strip():
        raise ValueError("An investigation question is required")
    normalized = unicodedata.normalize("NFKC", question).casefold()
    mentions: list[tuple[int, int, str, str, int, int]] = []
    for item in inventory.values():
        for alias in item["aliases"]:
            words = _words(alias)
            if not words:
                continue
            short_alias = len(words) == 1 and len(words[0]) < 6
            expression = r"(?<!\w)" + r"[\W_]+".join(map(re.escape, words)) + r"(?!\w)"
            for match in re.finditer(expression, normalized):
                if short_alias:
                    # A short label is admissible only when used as a device
                    # noun phrase ("the TV", "my fan"), not merely as an
                    # incidental word such as "on" or a suffix of Google TV.
                    # Overlapping longer aliases still win below.
                    before = normalized[max(0, match.start()-18):match.start()]
                    if not re.search(r"\b(?:the|my|our|this|that)\s+$",before):
                        continue
                # Rank actual friendly-label matches above generic device
                # names only for an identical whole-phrase match. Longer
                # different phrases still win regardless of their source.
                priority = 2 if item["friendly_words"] == words else 1
                mentions.append((match.start(), match.end(), item["id"], item["label"],
                                 len("".join(words)), priority))
    if not mentions:
        raise ValueError(
            "No device name in the question matched live Hubitat inventory. "
            "Enter a full device name under Advanced options; no device was queried."
        )

    # Prefer most-specific complete names: shorter aliases inside longer names
    # must never silently add another device. Tied different devices are unsafe.
    mentions.sort(key=lambda item: (-(item[1]-item[0]), -item[4], -item[5],
                                    item[0], item[2]))
    selected: list[tuple[int, int, str, str, int, int]] = []
    ambiguous: dict[tuple[int, int, int], dict[str, dict[str, Any]]] = {}
    for mention in mentions:
        overlapping = [row for row in selected
                       if mention[0] < row[1] and row[0] < mention[1]]
        if overlapping:
            best = overlapping[0]
            if (mention[:2] == best[:2] and mention[2] != best[2]
                    and mention[5] == best[5]):
                key = (mention[0], mention[1], mention[5])
                tied = ambiguous.setdefault(key, {})
                tied[best[2]] = inventory[best[2]]
                tied[mention[2]] = inventory[mention[2]]
                # Do not abort before considering whether this is an
                # incidental alias outside the actual named subject.
            continue
        if mention[2] not in {row[2] for row in selected}:
            selected.append(mention)

    # Device names are not arbitrary search terms. An exact, multiword
    # friendly label is a higher-confidence SUBJECT reference than incidental
    # device names in instructions such as "check current device status" or
    # "inspect switch events". The latter must not veto a verified subject,
    # even if two unrelated devices expose that same generic alias.
    anchored = [
        row for row in selected
        if (row[0], row[1], row[5]) not in ambiguous
        and row[5] == 2 and len(inventory[row[2]]["friendly_words"]) >= 2
    ]
    if anchored:
        earliest = min(row[0] for row in anchored)
        # Earlier ambiguous generic aliases may be a *property* of the
        # independently verified subject, not a third device. Suppress only
        # the narrow "switch state of <full friendly label>" relationship.
        # Every remaining earlier ambiguous device mention still fails closed.
        # Do not use the model's guessed name or an inventory shortcut here.
        blocking_keys = [
            key for key in ambiguous
            if key[0] <= earliest and not _attribute_qualifier_before_subject(
                normalized, start=key[0], end=key[1],
                subject_start=earliest,
            )
        ]
        if blocking_keys:
            first = min(blocking_keys, key=lambda key: key[0])
            raise ValueError(_ambiguous_inventory_targets(
                (item for key in blocking_keys for item in ambiguous[key].values()),
                matched_phrase=normalized[first[0]:first[1]]))
        selected = anchored
    elif ambiguous:
        first = min(ambiguous, key=lambda key: key[0])
        raise ValueError(_ambiguous_inventory_targets(
            (item for group in ambiguous.values() for item in group.values()),
            matched_phrase=normalized[first[0]:first[1]]))
    if len(selected) > 4:
        raise ValueError("More than four Hubitat device names matched; narrow the question")
    selected.sort(key=lambda item: item[0])
    return tuple(row[2] for row in selected), [
        {"id": row[2], "label": row[3]} for row in selected
    ], "question"


def resolve_planned_device_subjects(
    question: str, live_devices: Any, *,
    model_device_name: str | None = None,
) -> tuple[tuple[str, ...], list[dict[str, str]], str]:
    """Ground automatic device identity in the question before model proposals.

    A model-selected name is a proposed description, not identity authority.
    The host prefers unambiguous phrases in the original question and only
    accepts a model name if the question contains no matching device name
    and the proposed name uniquely matches a real live-inventory label.
    An ambiguous phrase is never resolved using the model's guess.
    """
    try:
        return resolve_verified_device_subjects(question, live_devices)
    except ValueError as exc:
        if not str(exc).startswith(
            "No device name in the question matched live Hubitat inventory."
        ) or not model_device_name:
            raise
    ids, resolved, _ = resolve_verified_device_subjects(
        question, live_devices, device_name=model_device_name,
    )
    return ids, resolved, "model_name_verified"


__all__ = [
    "require_test_access", "match_verified_device_ids",
    "resolve_verified_device_subjects", "resolve_planned_device_subjects",
]
