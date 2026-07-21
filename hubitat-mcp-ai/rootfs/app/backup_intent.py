from __future__ import annotations

import re


_CREATE_WORDS = {"create", "do", "make", "perform", "run", "start", "take", "trigger"}
_REJECT_WORDS = {
    "are",
    "check",
    "delete",
    "download",
    "failed",
    "failure",
    "how",
    "is",
    "last",
    "list",
    "restore",
    "show",
    "status",
    "when",
    "what",
    "why",
}


def is_explicit_backup_request(query: str) -> bool:
    """Recognise an explicit request to create a hub backup, not a backup question."""

    text = re.sub(r"\bback\s+up\b", "backup", str(query or "").lower())
    text = re.sub(r"\s+", " ", text).strip(" .!?")
    words = set(re.findall(r"[a-z]+", text))
    if "backup" not in words or words.intersection(_REJECT_WORDS):
        return False
    if words.intersection(_CREATE_WORDS):
        return True
    return bool(
        re.match(r"^(?:please\s+)?backup\b", text)
        or re.match(r"^(?:please\s+)?(?:can|could|would|will)\s+you\s+backup\b", text)
    )


__all__ = ["is_explicit_backup_request"]
