"""Explicitly requested atomic disabled-at-create safety boundary.

The documented native hub_set_rule creation contract exposes name,
addTriggers/addActions, but does not attest a disabled-at-create option.
Creating an active rule then disabling it is NOT equivalent.
No live MCP write is executed here.
"""
from __future__ import annotations
import re

_CREATE_REQUEST = re.compile(
    r"(?i)\b(?:create|build|install|add)\b[^.!?\n]{0,130}"
    r"\b(?:native\s+)?(?:hubitat\s+)?(?:rule\s+machine|automation|rule)\b"
    r"|\b(?:create|build|install|add)\s+(?:the|this|a)\s+rule\b"
)
_REQUIRE_DISABLED_FROM_START = re.compile(
    r"(?i)\b(?:create|created|creating|start|starts|initially|initial|"
    r"from\s+the\s+outset)\b[^.!?\n]{0,105}"
    r"\b(?:disabled|paused)\b"
    r"|\b(?:disabled|paused)\b[^.!?\n]{0,85}"
    r"\b(?:from\s+(?:the\s+)?(?:outset|start)|at\s+creation|"
    r"immediately\s+on\s+creation)\b"
)
_FORBID_STAGE_AFTER_CREATE = re.compile(
    r"(?i)\b(?:do\s+not|don't|never|without)\b[^.!?\n]{0,90}"
    r"\b(?:create|start|make|run)\b[^.!?\n]{0,55}\bactive\b"
    r"|\bdo\s+not\s+create\s+(?:it|the\s+rule)\s+active\b"
)

def demands_atomic_disabled_rule_creation(prompt: str) -> bool:
    """Identify a positive create request with inert-from-birth requirement."""
    text = str(prompt or "").strip()
    if not _CREATE_REQUEST.search(text):
        return False
    from rule_authoring_service import RuleAuthoringService
    if RuleAuthoringService.is_read_only_rule_design_request(text):
        return False
    return bool(
        _REQUIRE_DISABLED_FROM_START.search(text)
        or _FORBID_STAGE_AFTER_CREATE.search(text)
    )


_ATOMIC_STAGING_NOT_VERIFIED = (
    "**Rule creation safely stopped — nothing was created or queued.**\n\n"
    "You required the TEST Rule Machine automation to be **disabled from "
    "the moment it is created**. HomeBrain's installed native hub_set_rule "
    "creation schema has not been verified to support atomic disabled-at-"
    "creation. A create-then-disable sequence could briefly leave the rule "
    "active and violate your explicit safety condition.\n\n"
    "HomeBrain will not substitute an active rule, an incomplete action "
    "sequence or a pending approval for that missing guarantee. "
    "No Hubitat rule or device write was sent. Before retrying, verify an "
    "atomic disabled-at-create method against the installed gateway and "
    "check for an existing TEST rule by its exact name. A separate, "
    "explicitly approved test method is required if the gateway lacks "
    "that operation."
)

def render_atomic_staging_stop() -> str:
    return _ATOMIC_STAGING_NOT_VERIFIED

__all__ = [
    "demands_atomic_disabled_rule_creation",
    "render_atomic_staging_stop",
]
