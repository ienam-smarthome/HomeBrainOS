"""Primary request objective used by routing, synthesis and completion.

This module DOES NOT authorize Hubitat writes or certify observations.
It resolves the *kind of question* once with explicit priority: implementation
source > installed Rule Machine logic > other investigation.

Downstream stages may not turn a source-code request into a rule verification,
broad-performance report or historical-device-command investigation merely
because incidental keywords occur in the same prompt or model answer.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from groovy_source_investigation import requested_groovy_app_id
from targeted_rule_scope_policy import is_existing_rule_verification_request

PrimaryDomain = Literal["source_code", "existing_rule_verification", "general"]

_METHOD = re.compile(
    r"(?i)\b(?:method|function|procedure)\s+[`*]*"
    r"([A-Za-z_][A-Za-z_0-9]{2,80})\b"
)
# Ordinary language such as "method body" must never become a Groovy
# identifier. Explicit named methods and code-form identifiers win.
_NOT_METHOD_SYMBOLS = frozenset({
    "body", "bodies", "source", "code", "logic", "implementation",
    "implementations", "signature", "signatures", "name", "names",
    "definition", "definitions", "behavior", "behaviour", "callers",
    "calls", "execution", "history", "details", "level", "scope",
    "analysis", "and", "that", "which", "where", "used", "with",
})
_INLINE_METHOD = re.compile(
    r"(?i)\b(?:method|function|procedure)\s+[\x60*]*"
    r"([A-Za-z_][A-Za-z_0-9]{2,80})\b"
)
_QUOTED_SYMBOL = re.compile(r"[\x60]([A-Za-z_][A-Za-z_0-9]{2,80})[\x60]")
_CAMEL_METHOD = re.compile(
    r"\b(?:[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*|"
    r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]{2,})\b"
)


def requested_groovy_method_symbol(request: str) -> str | None:
    """Choose an actual code-shaped method identifier, not 'method body'."""
    question = str(request or "")
    for pattern in (_INLINE_METHOD, _QUOTED_SYMBOL, _CAMEL_METHOD):
        for match in pattern.finditer(question):
            symbol = match.group(1) if match.lastindex else match.group(0)
            if symbol.casefold() in _NOT_METHOD_SYMBOLS:
                continue
            if symbol in ("LimitExceededException", "DeviceStatusReport", "Groovy"):
                continue
            return symbol
    return None


_ERROR = re.compile(r"(?i)\b(?:LimitExceededException|excessive[- ]load|overload)\b")


@dataclass(frozen=True, slots=True)
class InvestigationObjective:
    domain: PrimaryDomain
    request: str
    installed_app_id: str | None = None
    method_symbol: str | None = None
    excessive_load_requested: bool = False

    @property
    def is_source(self) -> bool:
        return self.domain == "source_code"

    @property
    def is_rule(self) -> bool:
        return self.domain == "existing_rule_verification"


def resolve_primary_objective(request: str) -> InvestigationObjective:
    question = str(request or "")
    installed_app_id = requested_groovy_app_id(question)
    if installed_app_id is not None:
        return InvestigationObjective(
            domain="source_code",
            request=question,
            installed_app_id=installed_app_id,
            method_symbol=requested_groovy_method_symbol(question),
            excessive_load_requested=bool(_ERROR.search(question)),
        )
    if is_existing_rule_verification_request(question):
        return InvestigationObjective(
            domain="existing_rule_verification", request=question
        )
    return InvestigationObjective(domain="general", request=question)


__all__ = ["InvestigationObjective", "resolve_primary_objective", "requested_groovy_method_symbol"]
