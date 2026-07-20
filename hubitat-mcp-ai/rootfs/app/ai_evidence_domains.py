from __future__ import annotations

from typing import Any

import ai_evidence_planner as planner_module


_EXTRA_HOME_DOMAIN_TERMS = (
    "electricity",
    "electrical",
    "bathroom",
    "toilet",
    "kitchen",
    "living room",
    "bedroom",
    "hallway",
    "ventilation",
    "dehumidifier",
    "air purifier",
    "camera",
    "appliance",
)


def install_ai_evidence_domains() -> tuple[str, ...]:
    """Extend broad read-only AI planning without changing control routing.

    The core planner keeps a deliberately compact domain gate. This installer adds
    common household rooms and systems before the planner wrapper is installed, so
    natural questions such as bathroom ventilation or electricity diagnosis are
    eligible for AI-led evidence selection. It does not add control verbs, tools,
    metrics, device IDs or write permissions.
    """

    existing = tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))
    merged = tuple(dict.fromkeys((*existing, *_EXTRA_HOME_DOMAIN_TERMS)))
    planner_module._HOME_DOMAIN_TERMS = merged
    return merged


def installed_domain_terms() -> tuple[str, ...]:
    return tuple(getattr(planner_module, "_HOME_DOMAIN_TERMS", ()))


__all__ = [
    "install_ai_evidence_domains",
    "installed_domain_terms",
]
