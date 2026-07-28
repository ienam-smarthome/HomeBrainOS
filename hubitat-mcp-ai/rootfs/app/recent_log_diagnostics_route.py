from __future__ import annotations

import re
from typing import Any

from presenter import display_payload, safe_debug


_LOG_QUERY_RE = re.compile(
    r"^(?:please\s+)?(?:check|show|review|inspect|scan|look\s+at)\s+"
    r"(?:the\s+)?(?:homebrain\s+)?(?:logs?|errors?|warnings?|diagnostics?)"
    r"(?:\s+(?:for|and\s+show|and\s+list)\s+(?:any\s+)?(?:issues?|errors?|warnings?))?"
    r"[?.!]*$",
    re.IGNORECASE,
)


def is_recent_log_diagnostics_query(query: str) -> bool:
    text = re.sub(r"\s+", " ", str(query or "").strip())
    return bool(_LOG_QUERY_RE.match(text))


def _problem_kind(item: dict[str, Any]) -> str | None:
    if item.get("error") or item.get("exception_type"):
        return "error"
    route = str(item.get("final_route") or "").strip().lower()
    if route in {
        "server-error",
        "unified-agent-error",
        "mcp-error",
        "ollama-error",
        "cancelled",
    }:
        return "error"
    return None


def build_recent_log_diagnostics_terminal_route(application: Any, trace_store: Any):
    """Summarise bounded HomeBrain request diagnostics without pretending to read HA logs."""

    async def route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_recent_log_diagnostics_query(query):
            return None

        recent = list(trace_store.recent()) if trace_store is not None else []
        problems = [
            dict(item)
            for item in recent
            if isinstance(item, dict) and _problem_kind(item)
        ]

        if problems:
            names = []
            for item in problems[:10]:
                label = str(item.get("query") or item.get("final_route") or "Request").strip()
                reason = str(item.get("error") or item.get("exception_type") or item.get("final_route") or "error").strip()
                names.append(f"{label}: {reason}")
            message = (
                f"I found {len(problems)} error{'s' if len(problems) != 1 else ''} "
                f"in the last {len(recent)} recorded HomeBrain requests. "
                + " ".join(names)
            )
        elif recent:
            message = (
                f"No errors were found in the last {len(recent)} recorded HomeBrain requests. "
                "This checks HomeBrain request diagnostics, not Home Assistant Supervisor or add-on log files."
            )
        else:
            message = (
                "No recent HomeBrain request diagnostics are available yet. "
                "This route does not claim to inspect Home Assistant Supervisor or add-on log files."
            )

        items = [
            {
                "icon": "❌",
                "title": str(item.get("query") or "Request error"),
                "value": str(item.get("exception_type") or item.get("final_route") or "Error"),
                "subtitle": str(item.get("error") or "").strip() or None,
                "tone": "danger",
            }
            for item in problems[:10]
        ]
        display = display_payload(
            "recent-request-diagnostics",
            "HomeBrain request diagnostics",
            subtitle=f"{len(problems)} errors in {len(recent)} recorded requests",
            metrics=[
                {"label": "Recorded", "value": str(len(recent)), "icon": "📋"},
                {"label": "Errors", "value": str(len(problems)), "icon": "❌"},
            ],
            items=items,
            note=(
                "Source: HomeBrain's bounded in-memory request trace history. "
                "Home Assistant Supervisor and container logs are outside this route."
            ),
        )
        display["summary"] = message

        return {
            "success": True,
            "route": "homebrain-recent-request-diagnostics",
            "intent": "recent-log-diagnostics",
            "message": message,
            "display": display,
            "error_count": len(problems),
            "request_count": len(recent),
            "errors": problems[:10],
            "answered_by": "Deterministic HomeBrain request diagnostics",
            "model": None,
            "technical": safe_debug(
                {
                    "query": query,
                    "source": "bounded-request-trace-store",
                    "request_count": len(recent),
                    "error_count": len(problems),
                    "errors": problems[:10],
                    "supervisor_logs_checked": False,
                    "addon_logs_checked": False,
                }
            ),
            "version": getattr(application, "VERSION", None),
        }

    return route


__all__ = [
    "build_recent_log_diagnostics_terminal_route",
    "is_recent_log_diagnostics_query",
]
