from __future__ import annotations

from typing import Any, Awaitable, Callable

from presenter import safe_debug
from semantic_home_evidence import SemanticHomeEvidenceBroker
from semantic_home_summary_agent import (
    _HOME_SUMMARY_RE,
    _fact_manifest,
    _synthesise,
)


TerminalRoute = Callable[[Any], Awaitable[dict[str, Any] | None]]


def build_semantic_home_summary_terminal_route(
    application: Any,
    snapshot_service: Any,
) -> TerminalRoute:
    """Build the exact-phrase semantic home-summary terminal route."""

    broker = SemanticHomeEvidenceBroker(application, snapshot_service)
    application.semantic_home_evidence_broker = broker

    async def semantic_home_summary_route(
        request: Any,
    ) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "")
        if not _HOME_SUMMARY_RE.search(query):
            return None

        evidence = await broker.collect(limit=20)
        if not evidence.get("success"):
            return None

        message, provider, synthesis_error = await _synthesise(
            application,
            query,
            evidence,
        )
        fact_manifest = _fact_manifest(evidence)
        model = str(
            getattr(application.ollama, "cloud_model", "")
            or getattr(application.ollama, "model", "")
            or ""
        ) or None
        return {
            "success": True,
            "route": "ai-semantic-home-evidence",
            "intent": "home-summary",
            "message": message,
            "semantic_evidence": evidence.get("data"),
            "required_facts": evidence.get("required_facts"),
            "fact_manifest": fact_manifest,
            "tools_used": list(evidence.get("tools_used") or []),
            "model": model,
            "provider": provider,
            "synthesis_error": synthesis_error,
            "answered_by": "AI using semantic HomeBrain evidence tools",
            "technical": safe_debug(
                {
                    "evidence": evidence,
                    "fact_manifest": fact_manifest,
                    "synthesis_error": synthesis_error,
                }
            ),
        }

    return semantic_home_summary_route


__all__ = ["build_semantic_home_summary_terminal_route"]
