"""Strictly opt-in, tool-free answers for static technical explanations.

No Hubitat, device, historical or live-state question can use this route.
Tool-free does not grant write permission or alter paid-model consent.
"""
from __future__ import annotations

import re

_NO_TOOLS = re.compile(
    r"(?i)\b(?:without\s+using\s+(?:any\s+)?(?:hubitat\s+)?(?:mcp\s+)?tools?|"
    r"no\s+(?:hubitat\s+)?(?:mcp\s+)?tools?\s+(?:are\s+)?(?:required|needed)|"
    r"answer\s+(?:only\s+)?from\s+general\s+knowledge)\b"
)
_TECHNICAL = re.compile(
    r"(?i)\b(?:groovy|python|javascript|programming|coding|code|"
    r"defaultvalue|persisted\s+settings|configuration\s+default|"
    r"type\s+annotations?|regular\s+expressions?)\b"
)
_EXPLAIN = re.compile(
    r"(?i)\b(?:explain|define|describe|compare|difference\s+between|"
    r"what\s+(?:is|are|does)|how\s+does)\b"
)
_LIVE = re.compile(
    r"(?i)\b(?:my\s+(?:hub|hubitat|home|lights?|devices?|sensors?|automations?)|"
    r"livingroom|bedroom|bathroom\s+light|app\s*#?\d+|device\s*#?\d+|"
    r"current\s+(?:state|status|setting)|now\s+on|turn\s+(?:on|off)|"
    r"switch\s+(?:on|off)|set\s+(?:level|brightness)|"
    r"change\s+(?:my|the)\s+(?:settings?|config)|"
    r"historical\s+events?|investigate\s+(?:why|what)|"
    r"logs?|last\s+(?:night|week)|today|yesterday)\b"
)
_WRITE_DIRECTIVE = re.compile(
    r"(?i)(?:^|[.!?]\s+)(?:please\s+)?(?:turn|switch|set|change|"
    r"create|remove|delete|disable|enable|restart|block|allow|"
    r"update|configure|write)\b"
)


def eligible_tool_free_knowledge(prompt: str) -> bool:
    text = " ".join(str(prompt or "").split())
    return bool(
        _NO_TOOLS.search(text)
        and _TECHNICAL.search(text)
        and _EXPLAIN.search(text)
        and not _LIVE.search(text)
        and not _WRITE_DIRECTIVE.search(text)
    )


def tool_free_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": (
            "Answer this static technical explanation directly and concisely "
            "from general programming knowledge. Do not claim to have read "
            "Hubitat devices, settings, logs, Groovy application source or "
            "external documentation. No tools are available. Respect the "
            "user's requested length. Do not suggest or perform any writes."
        )},
        {"role": "user", "content": str(prompt or "")},
    ]
