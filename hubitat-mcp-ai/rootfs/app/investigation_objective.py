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
        symbol = _METHOD.search(question)
        return InvestigationObjective(
            domain="source_code",
            request=question,
            installed_app_id=installed_app_id,
            method_symbol=symbol.group(1) if symbol else None,
            excessive_load_requested=bool(_ERROR.search(question)),
        )
    if is_existing_rule_verification_request(question):
        return InvestigationObjective(
            domain="existing_rule_verification", request=question
        )
    return InvestigationObjective(domain="general", request=question)


__all__ = ["InvestigationObjective", "resolve_primary_objective"]
