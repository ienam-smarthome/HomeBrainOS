"""Bind model-selected READ results to the subject the user actually referenced.

No keyword-based intent routing or model-provided device identity as proof.
A successful target-specific READ must return the matching device identity.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def _normal(value: Any) -> str:
    return " ".join(re.findall(r"[^\\W_]+", str(value or "").casefold(),
                               flags=re.UNICODE))


def verified_device_focus(
    question: str, operation: str, args: Mapping[str, Any],
    source: Mapping[str, Any], verified_device_ids: set[str],
) -> dict[str, str] | None:
    """Return an ID only with a successful identity-matched device READ.

    A particular device's state alone must never change the focus of a
    question about general hub health. IDs must be verified by existing
    read-only host guards, and the source must echo that *same* device ID.
    """
    if operation != "hub_get_device" or not isinstance(question, str):
        return None
    if not isinstance(args, Mapping) or not isinstance(source, Mapping):
        return None
    requested = args.get("deviceId")
    if type(requested) not in (int, str) or not str(requested).isdecimal():
        return None
    target = str(requested)
    if target not in verified_device_ids or str(source.get("id")) != target:
        return None
    if re.search(r"(?<![0-9])" + re.escape(target) + r"(?![0-9])", question):
        return {"device_id": target, "identity_basis": "explicit_verified_device_id"}

    normalized_question = " " + _normal(question) + " "
    for value in (source.get("label"), source.get("name")):
        if not isinstance(value, str):
            continue
        aliases = [value]
        if " - [" in value:
            aliases.append(value.split(" - [", 1)[0])
        for alias in aliases:
            normalized_alias = _normal(alias)
            if (len(normalized_alias) >= 9
                    and len(normalized_alias.split()) >= 2
                    and " " + normalized_alias + " " in normalized_question):
                return {"device_id": target,
                        "identity_basis": "explicit_verified_device_name"}
    return None


__all__ = ["verified_device_focus"]
