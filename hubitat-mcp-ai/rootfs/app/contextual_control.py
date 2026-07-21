from __future__ import annotations

import re


def parse_contextual_device_control(query: str) -> tuple[str, str] | None:
    """Parse on/off commands whose target refers to prior conversation state."""

    text = str(query or "").strip()
    patterns = (
        r"^(?:please\s+)?(?:turn|switch)\s+(on|off)\s+(.+?)[?.!]*$",
        r"^(?:please\s+)?(?:turn|switch)\s+(.+?)\s+(on|off)[?.!]*$",
    )
    for index, pattern in enumerate(patterns):
        match = re.match(pattern, text, flags=re.I)
        if not match:
            continue
        action = match.group(1 if index == 0 else 2).lower()
        target = match.group(2 if index == 0 else 1).strip()
        normal = " ".join(target.lower().strip(" .!?").split())
        contextual = (
            normal
            in {
                "it",
                "that",
                "this",
                "the one",
                "this one",
                "that one",
                "them",
                "those",
                "these",
                "all of them",
            }
            or bool(re.search(r"\b(?:first|second|third|fourth|fifth|[1-5](?:st|nd|rd|th))\s+one\b", normal))
            or (
                normal not in {"other one", "the other one"}
                and bool(re.search(r"\b(?:the|that|this)\s+.+\s+one$", normal))
            )
        )
        if contextual:
            return action, target
    return None


def is_contextual_device_control(query: str) -> bool:
    return parse_contextual_device_control(query) is not None


def is_other_device_control(query: str) -> bool:
    """Recognise the control graph's relative reference to the other device."""

    text = " ".join(str(query or "").lower().strip(" .!?").split())
    return bool(
        re.match(
            r"^(?:please )?(?:turn|switch) (?:on|off )?(?:the )?other one(?: on| off)?$",
            text,
        )
    )


__all__ = [
    "is_contextual_device_control",
    "is_other_device_control",
    "parse_contextual_device_control",
]
