"""Request-scoped evidence receipt construction for the Hubitat MCP agent.

The recorder owns receipt storage, sanitisation, timestamps, and structured
effect metadata. It deliberately does not decide when evidence is required,
which tools are authoritative, or whether the agent should retry or refuse;
those policies remain with ``UnifiedMCPAgent``.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect


_SENSITIVE_ARGUMENT_PARTS = (
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
)


class EvidenceRecorder:
    """Build and retain evidence receipts for one async request context."""

    def __init__(self) -> None:
        self._receipts: ContextVar[list[dict[str, Any]] | None] = ContextVar(
            "hubitat_evidence", default=None
        )

    @property
    def context(self) -> ContextVar[list[dict[str, Any]] | None]:
        """Expose the context for temporary backwards-compatible integrations."""

        return self._receipts

    def begin(self) -> Token:
        """Start an isolated receipt list for the current request context."""

        return self._receipts.set([])

    def reset(self, token: Token) -> None:
        """Restore the previous request context."""

        self._receipts.reset(token)

    def receipts(self) -> list[dict[str, Any]]:
        """Return an isolated snapshot suitable for API output."""

        return deepcopy(self._receipts.get() or [])

    @classmethod
    def redact(cls, value: Any) -> Any:
        """Sanitise nested tool arguments before they enter audit output."""

        if isinstance(value, dict):
            return {
                str(key): (
                    "[redacted]"
                    if any(
                        part in str(key).casefold()
                        for part in _SENSITIVE_ARGUMENT_PARTS
                    )
                    else cls.redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls.redact(item) for item in value[:20]]
        if isinstance(value, str) and len(value) > 240:
            return value[:237] + "..."
        return value

    def record(
        self,
        gateway: str,
        arguments: dict[str, Any],
        *,
        success: bool,
        elapsed_ms: int,
        summary: str,
        supports_live_claim: bool = True,
        evidence_kind: str = "tool_result",
        mutates: bool | None = None,
        effect: ToolEffect | str | None = None,
    ) -> None:
        """Append one sanitised structured receipt when a request is active."""

        receipts = self._receipts.get()
        if receipts is None:
            return
        resolved_effect = (
            effect
            if isinstance(effect, ToolEffect)
            else ToolEffect(effect)
            if isinstance(effect, str) and effect in ToolEffect._value2member_map_
            else classify_tool_effect(MCPTool(gateway, gateway, {}), arguments)
        )
        receipts.append({
            "tool": gateway,
            "sub_tool": arguments.get("tool"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
            "success": success,
            "supports_live_claim": supports_live_claim,
            "evidence_kind": evidence_kind,
            "mutates": resolved_effect.mutates if mutates is None else bool(mutates),
            "effect": resolved_effect.value,
            "arguments": self.redact(arguments),
            "summary": summary,
        })

    def has_live_evidence(self) -> bool:
        """Report whether a successful receipt supports a current-state claim."""

        return any(
            receipt.get("success") and receipt.get("supports_live_claim")
            for receipt in (self._receipts.get() or [])
        )


__all__ = ["EvidenceRecorder"]
