"""Prevent credential leaks through MCP-to-model messages and final answers.

Redaction affects presentation only. Raw tool execution and authoritative
evidence receipts are not mutated, preserving read-only diagnostics.
"""
from __future__ import annotations

import re
from typing import Any

_KEY = r"(?:password|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|mqtt[_-]?password|auth(?:orization)?[_-]?token|bearer[_-]?token)"
_JSON = re.compile(r'(?i)("(?:' + _KEY + r')"\s*:\s*")([^"]*)(")')
_PAIR = re.compile(r'(?im)(\b' + _KEY + r'\b\s*(?:=|:)\s*["\x27]?)([^\s,}"\x27]+)')
_QUERY = re.compile(r'(?i)([?&]' + _KEY + r'=)[^&\s]+')
_BEARER = re.compile(r'(?i)(\bBearer\s+)[a-z0-9._~+/\-]+=*')


def redact_secrets(value: str) -> str:
    result = str(value or "")
    result = _BEARER.sub(lambda m: m.group(1) + "[REDACTED]", result)
    result = _JSON.sub(lambda m: m.group(1) + "[REDACTED]" + m.group(3), result)
    result = _PAIR.sub(lambda m: m.group(1) + "[REDACTED]", result)
    result = _QUERY.sub(lambda m: m.group(1) + "[REDACTED]", result)
    return result


def redact_model_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scrub server-derived content before reaching the model.

    Keep native tool-call envelopes and user-authored messages unchanged.
    """
    result = []
    for row in messages:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        role = item.get("role")
        body = item.get("content")
        if isinstance(body, str) and (
            role == "tool"
            or (role == "user" and body.lstrip().startswith(("HOST ", "ACTIVE HOMEBRAIN")))
        ):
            item["content"] = redact_secrets(body)
        result.append(item)
    return result


__all__ = ["redact_secrets", "redact_model_messages"]
