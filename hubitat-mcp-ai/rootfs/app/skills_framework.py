"""Progressively disclosed, versioned and bounded HomeBrain skill packs.

Skills are repository-owned guidance; they do not grant tools or permissions.
The MCP live catalog is always authoritative, and skill files never execute.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from investigation_policy import is_causal_investigation, is_history_investigation
from investigation_intelligence import plan_investigation
from request_metrics import increment_active_metric

_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
_ALLOWED = {
    "hubitat-operations": "hubitat-operations/SKILL.md",
    "hubitat-investigator": "hubitat-investigator/SKILL.md",
}
_MAX_CHARS = 6800


def _read_skill(name: str) -> str:
    """Load only declared local skill documents, never arbitrary paths."""
    relative = _ALLOWED.get(name)
    if not relative:
        return ""
    try:
        body = (_SKILL_ROOT / relative).read_text(encoding="utf-8")
    except OSError:
        return ""
    if body.startswith("---\n"):
        _, _, remainder = body.partition("\n---\n")
        if remainder:
            body = remainder
    return body.strip()


@lru_cache(maxsize=4)
def _cached_skill(name: str) -> str:
    return _read_skill(name)


def select_skills(request: str) -> tuple[str, ...]:
    """Intent-based selection without a model round or live hub request."""
    text = str(request or "").casefold()
    if not text.strip():
        return ()
    investigative = bool(
        is_causal_investigation(request)
        or is_history_investigation(request)
        or plan_investigation(request) is not None
        or (
            any(word in text for word in ("investigat", "diagnos", "troubleshoot", "why "))
            and any(word in text for word in (
                "device", "hubitat", "light", "motion", "mqtt", "rule", "sensor",
                "switch", "automation", "hub", "button",
            ))
        )
    )
    if investigative:
        return ("hubitat-operations", "hubitat-investigator")
    if any(word in text for word in (
        "hubitat", "device", "switch", "light", "thermostat", "automation",
        "rule machine", "mqtt", "sensor", "motion", "button",
    )):
        return ("hubitat-operations",)
    return ()


def render_skills_for_request(request: str, *, max_chars: int = _MAX_CHARS) -> str:
    selected = select_skills(request)
    if not selected:
        return ""
    rendered = []
    budget = min(_MAX_CHARS, max(1000, max_chars))
    for name in selected:
        body = _cached_skill(name)
        if not body:
            continue
        part = f"ACTIVE HOMEBRAIN SKILL: {name}\n{body}\n"
        if sum(map(len, rendered)) + len(part) > budget:
            break  # no broken instructions from truncation
        rendered.append(part)
    if rendered:
        increment_active_metric("skills_framework_activated")
    return "\n".join(rendered)


def skill_index() -> tuple[dict[str, str], ...]:
    """Small explicit catalog for diagnostics; does not expose file contents."""
    return (
        {"name": "hubitat-operations", "intent": "Hubitat MCP operation/safety"},
        {"name": "hubitat-investigator", "intent": "Historical and causal investigation"},
    )


__all__ = ["render_skills_for_request", "select_skills", "skill_index"]
