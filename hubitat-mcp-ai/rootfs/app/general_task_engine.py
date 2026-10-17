"""Semantic task and skill selection for the general MCP agent.

The language model proposes *what evidence/capabilities are needed*, never how
to bypass tool permissions or how to author Hubitat wire arguments. Actual tool
availability, effect classification and execution remain owned by MCP/runtime.
This is an opt-in planning layer; failed classification degrades to the existing
native function-calling loop without asserting any facts or changing devices.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import logging
from typing import Any

from general_evidence_completion import EVIDENCE_KINDS

logger = logging.getLogger("HomeBrainOS.GeneralTaskEngine")

DOMAINS = frozenset({
    "device", "automations", "rooms", "diagnostics", "hub",
    "integrations", "system_state", "code", "other",
})
OPERATIONS = frozenset({"read", "investigate", "propose", "write"})
SKILLS = frozenset({
    "device_control", "automation", "diagnostics",
    "hub_admin", "integrations", "code_management",
})
DOMAIN_SKILL = {
    "device": "device_control",
    "automations": "automation",
    "rooms": "hub_admin",
    "diagnostics": "diagnostics",
    "hub": "hub_admin",
    "integrations": "integrations",
    "code": "code_management",
}
ChatCallable = Callable[
    [list[dict[str, Any]], list[dict[str, Any]]],
    Awaitable[dict[str, Any]],
]


def _bounded_strings(value: Any, *, count: int, width: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    values: list[str] = []
    for raw in value:
        if not isinstance(raw, str):
            continue
        candidate = " ".join(raw.split())[:width].strip()
        if candidate and candidate.casefold() not in {x.casefold() for x in values}:
            values.append(candidate)
        if len(values) == count:
            break
    return tuple(values)


@dataclass(frozen=True, slots=True)
class InvestigativeHypothesis:
    """One model-proposed explanation and a read-source discriminator.

    This is an investigation QUESTION, never a finding or authorization.
    """

    explanation: str
    distinguishing_question: str
    evidence_kind: str


def _bounded_hypotheses(value: Any) -> tuple[InvestigativeHypothesis, ...]:
    """Accept only short, schema-known source checks, not model MCP commands."""
    if not isinstance(value, list):
        return ()
    found: list[InvestigativeHypothesis] = []
    seen: set[str] = set()
    for candidate in value[:8]:
        if not isinstance(candidate, dict):
            continue
        explanation = candidate.get("explanation")
        question = candidate.get("distinguishingQuestion")
        kind = candidate.get("evidenceKind")
        if not (isinstance(explanation, str) and isinstance(question, str)
                and isinstance(kind, str) and kind in EVIDENCE_KINDS):
            continue
        explanation = " ".join(explanation.split())[:140].strip()
        question = " ".join(question.split())[:180].strip()
        if not explanation or not question or explanation.casefold() in seen:
            continue
        seen.add(explanation.casefold())
        found.append(InvestigativeHypothesis(explanation, question, kind))
        if len(found) == 3:
            break
    # A single model guess is not a competing-hypothesis investigation.
    return tuple(found) if len(found) >= 2 else ()


@dataclass(frozen=True, slots=True)
class GeneralTaskPlan:
    domain: str
    operation: str
    objective: str
    skill_domains: tuple[str, ...]
    capability_queries: tuple[str, ...]
    evidence_goals: tuple[str, ...]
    required_evidence_kinds: tuple[str, ...] = ()
    candidate_hypotheses: tuple[InvestigativeHypothesis, ...] = ()

    @classmethod
    def from_model(cls, response: str) -> "GeneralTaskPlan | None":
        """Reject invalid/untrusted planner output; never infer authority."""
        text = str(response or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1]).strip()
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            return None
        if not isinstance(value, dict) or value.get("version") != "1":
            return None
        domain, operation = value.get("domain"), value.get("operation")
        objective = value.get("objective")
        if domain not in DOMAINS or operation not in OPERATIONS:
            return None
        if not isinstance(objective, str) or not objective.strip():
            return None
        supplied = _bounded_strings(value.get("skills"), count=4, width=40)
        skills = [item for item in supplied if item in SKILLS]
        fallback_skill = DOMAIN_SKILL.get(domain)
        if fallback_skill and fallback_skill not in skills:
            skills.insert(0, fallback_skill)
        capabilities = _bounded_strings(
            value.get("capabilityQueries"), count=4, width=120
        )
        goals = _bounded_strings(value.get("evidenceGoals"), count=5, width=180)
        kinds = tuple(x for x in _bounded_strings(
            value.get("requiredEvidenceKinds"), count=5, width=48,
        ) if x in EVIDENCE_KINDS)
        hypotheses = (
            _bounded_hypotheses(value.get("candidateHypotheses"))
            if operation == "investigate" else ()
        )
        return cls(
            domain=domain,
            operation=operation,
            objective=" ".join(objective.split())[:300],
            skill_domains=tuple(skills),
            capability_queries=capabilities,
            evidence_goals=goals,
            required_evidence_kinds=kinds,
            candidate_hypotheses=hypotheses,
        )

    def instruction(self) -> str:
        """Planning context, not a tool result or permission/confirmation."""
        payload = {
            "domain": self.domain,
            "operation": self.operation,
            "objective": self.objective,
            "evidence_goals": list(self.evidence_goals),
            "required_source_kinds": list(self.required_evidence_kinds),
            "candidate_hypotheses": [
                {"explanation": item.explanation,
                 "distinguishing_question": item.distinguishing_question,
                 "evidence_kind": item.evidence_kind,
                 "status": "unverified-model-proposal"}
                for item in self.candidate_hypotheses
            ] if self.operation == "investigate" else [],
        }
        intent_guard = (
            "\\nPROPOSAL-ONLY EXECUTION BOUNDARY: The user requested a design "
            "or proposed change, NOT an execution. Do not call a state-changing "
            "MCP operation or queue confirmation. Read-only schema inspection, "
            "target resolution, safety checks and a proposed implementation "
            "are allowed. Identify unresolved choices before implementation."
            if self.operation == "propose" else ""
        )
        return (
            "GENERAL TASK OBJECTIVES (model-proposed, not verified evidence):\\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\nEvaluate every requested objective. Discover the specific live MCP "
              "operation when needed. Use tool receipts to decide what was "
              "established; do not claim execution or a causal explanation "
              "from a proposed plan. The original user message and MCP safety "
              "gates remain authoritative. Report unresolved objectives. "
              "For investigation, compare the candidate hypotheses against "
              "current-turn scoped evidence. A source checked is NOT evidence "
              "that its proposed explanation is true. Do not dismiss alternatives "
              "from empty or incomplete history; revise candidates when receipts "
              "contradict them."
            + intent_guard
        )


class GeneralTaskPlanner:
    """Choose a multi-domain plan semantically without keyword dispatch."""

    PROMPT = (
        "You are the planning stage for a Hubitat MCP assistant. Return exactly "
        "one JSON object, no prose, no markdown:\\n"
        '{"version":"1","domain":"diagnostics","operation":"investigate",'
        '"objective":"Explain an unexpected light activation",'
        '"skills":["diagnostics","automation"],'
        '"capabilityQueries":["light state event history",'
        '"automation app logs and configuration"],'
        '"evidenceGoals":["Observed state transition",'
        '"Verified command provenance"],'
        '"requiredEvidenceKinds":["device_history","app_logs"],'
        '"candidateHypotheses":['
        '{"explanation":"A hub command preceded the switch transition",'
        '"distinguishingQuestion":"Was a producer command recorded at the focal time?",'
        '"evidenceKind":"device_history"},'
        '{"explanation":"An external bridge or physical input initiated it",'
        '"distinguishingQuestion":"Is independently timestamped controller evidence available?",'
        '"evidenceKind":"device_logs"}]}\\n'
        "Allowed domains: device, automations, rooms, diagnostics, hub, "
        "integrations, system_state, code, other. "
        "Allowed operations: read, investigate, propose, write. "
        "Allowed skills: device_control, automation, diagnostics, hub_admin, "
        "integrations, code_management. "
        "Allowed requiredEvidenceKinds values: device_state, device_history, "
        "device_logs, app_config, app_logs, room_inventory, native_rules, "
        "scheduled_jobs, performance_stats, tool_guide, source_code. "
        "For investigate operations choose 1-3 indispensable read-source "
        "classes for requiredEvidenceKinds; for simple state reads use []. "
        "For investigate operations propose TWO or THREE genuinely competing "
        "candidateHypotheses when materially plausible, each with an explanation, "
        "distinguishingQuestion and evidenceKind from the allowed source kinds. "
        "They are provisional tests, NOT supported facts or confidence scores. "
        "Do not add them for read, propose or write tasks. "
        "Checked sources are not proof of a historical cause or event. "
        "Infer the purpose of the request from meaning, not keyword matches. "
        "A request may need several skills and MCP gateway searches. "
        "Include specific capability search phrases (at most four) rather than "
        "imaginary hub_* names; live MCP discovery is authoritative. "
        "Evidence goals are questions/checks, never facts. "
        "Do NOT claim anything has been executed, invent device IDs or command "
        "schemas, or approve writes. Requests to explain prior changes are "
        "read/investigate, even when describing words such as 'turn off'. "
        "For a design, draft, simulation, or plan without execution, choose "
        "operation=propose, never write. The user must explicitly request "
        "execution before any state-changing tool call. "
        "A write plan does not itself authorise a write. "
        "Prefer compact plans: one or two capability queries for a simple task."
    )

    def __init__(self, chat: ChatCallable) -> None:
        self._chat = chat

    async def plan(
        self,
        request: str,
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> GeneralTaskPlan | None:
        if not str(request or "").strip():
            return None
        prior = []
        for item in (history or [])[-4:]:
            if item.get("role") not in {"user", "assistant"}:
                continue
            prior.append({
                "role": item["role"],
                "content": str(item.get("content") or "")[:600],
            })
        try:
            response = await self._chat([
                {"role": "system", "content": self.PROMPT},
                *prior,
                {"role": "user", "content": str(request).strip()},
            ], [])
            return GeneralTaskPlan.from_model(
                str(response.get("content") or "")
            )
        except Exception as exc:
            logger.warning(
                "General task planning unavailable; using existing MCP loop (%s)",
                type(exc).__name__,
            )
            return None


__all__ = [
    "GeneralTaskPlan", "GeneralTaskPlanner", "InvestigativeHypothesis",
    "DOMAINS", "OPERATIONS", "SKILLS",
]
