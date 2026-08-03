from __future__ import annotations

from request_metrics import increment_active_metric


def record_mcp_retry_attempt() -> None:
    """Record one actual retry attempt in the active request metrics context."""

    increment_active_metric("mcp_retries")


__all__ = ["record_mcp_retry_attempt"]
