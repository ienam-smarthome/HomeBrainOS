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
        entry = devices.setdefault(ident, {"id": ident, "label": aliases[0], "aliases": []})
        for alias in aliases:
            if alias not in entry["aliases"]:
                entry["aliases"].append(alias)
    if not devices:
        raise ValueError("Live Hubitat device names unavailable")
    return devices


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
        if len(matching) != 1:
            raise ValueError(
                "Device name does not uniquely match the live Hubitat inventory. "
                "Choose a full unique device name or use an ID under Advanced options."
            )
        item = matching[0]
        return (item["id"],), [{"id": item["id"], "label": item["label"]}], "device_name"

    if not isinstance(question, str) or not question.strip():
        raise ValueError("An investigation question is required")
    normalized = unicodedata.normalize("NFKC", question).casefold()
    mentions: list[tuple[int, int, str, str, int]] = []
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
                mentions.append((match.start(), match.end(), item["id"], item["label"],
                                 len("".join(words))))
    if not mentions:
        raise ValueError(
            "No device name in the question matched live Hubitat inventory. "
            "Enter a full device name under Advanced options; no device was queried."
        )

    # Prefer most-specific complete names: shorter aliases inside longer names
    # must never silently add another device. Tied different devices are unsafe.
    mentions.sort(key=lambda item: (-(item[1]-item[0]), -item[4], item[0], item[2]))
    selected: list[tuple[int, int, str, str, int]] = []
    for mention in mentions:
        overlapping = [row for row in selected
                       if mention[0] < row[1] and row[0] < mention[1]]
        if overlapping:
            best = overlapping[0]
            if mention[:2] == best[:2] and mention[2] != best[2]:
                raise ValueError(
                    "Ambiguous device name: multiple Hubitat devices match the same phrase. "
                    "Enter a full unique device name under Advanced options."
                )
            continue
        if mention[2] not in {row[2] for row in selected}:
            selected.append(mention)
    if len(selected) > 4:
        raise ValueError("More than four Hubitat device names matched; narrow the question")
    selected.sort(key=lambda item: item[0])
    return tuple(row[2] for row in selected), [
        {"id": row[2], "label": row[3]} for row in selected
    ], "question"


__all__ = [
    "require_test_access", "match_verified_device_ids",
    "resolve_verified_device_subjects",
]
