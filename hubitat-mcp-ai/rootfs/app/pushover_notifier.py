from __future__ import annotations

from typing import Any

import httpx


PUSHOVER_MESSAGES_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_MESSAGE_LIMIT = 1024


def format_health_audit(audit: dict[str, Any]) -> tuple[str, str]:
    status = str(audit.get("status") or "unknown").strip().title()
    title = f"HomeBrain System Check: {status}"[:250]
    hierarchy = audit.get("health_hierarchy") or {}

    lines = []
    for key in ("hub", "devices", "automations", "logs"):
        item = hierarchy.get(key) if isinstance(hierarchy, dict) else None
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or key.title())
        item_status = str(item.get("status") or "healthy")
        icon = (
            "✅"
            if item_status == "healthy"
            else "❌"
            if item_status == "critical"
            else "⚠️"
        )
        count = int(item.get("attention_count") or 0)
        summary = "healthy" if not count else f"{count} need attention"
        lines.append(f"{icon} {label}: {summary}")

    attention = int(audit.get("attention_count") or 0)
    new_count = int(audit.get("new_count") or 0)
    resolved_count = int(audit.get("resolved_count") or 0)
    lines.append(
        f"Total: {attention} attention · {new_count} new · {resolved_count} resolved"
    )

    issues = audit.get("issues") or []
    actionable = [
        row
        for row in issues
        if isinstance(row, dict) and row.get("severity") in {"critical", "warning"}
    ]
    if actionable:
        lines.append("Top findings:")
        for item in actionable[:6]:
            occurrence = int(item.get("count") or 1)
            suffix = f" ×{occurrence}" if occurrence > 1 else ""
            lines.append(f"• {item.get('title') or 'Issue'}{suffix}")
    else:
        lines.append("No current findings need attention.")

    message = "\n".join(lines)
    if len(message) > PUSHOVER_MESSAGE_LIMIT:
        message = message[: PUSHOVER_MESSAGE_LIMIT - 1].rstrip() + "…"
    return title, message


class PushoverNotifier:
    """Optional, bounded delivery of scheduled System Check summaries."""

    def __init__(
        self,
        *,
        enabled: bool,
        app_token: str,
        user_key: str,
        device: str = "",
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.app_token = str(app_token or "").strip()
        self.user_key = str(user_key or "").strip()
        self.device = str(device or "").strip()
        self.timeout_seconds = max(1.0, min(30.0, float(timeout_seconds)))
        self._client = client

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.app_token and self.user_key)

    async def _send_message(self, *, title: str, message: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Pushover notifications are disabled")
        if not self.app_token or not self.user_key:
            raise RuntimeError(
                "Pushover is enabled but the application token or user/group key is missing"
            )

        form = {
            "token": self.app_token,
            "user": self.user_key,
            "title": str(title)[:250],
            "message": str(message)[:PUSHOVER_MESSAGE_LIMIT],
            "priority": "0",
        }
        if self.device:
            form["device"] = self.device

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds)
        )
        try:
            response = await client.post(PUSHOVER_MESSAGES_URL, data=form)
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                await client.aclose()

        if not isinstance(payload, dict) or int(payload.get("status") or 0) != 1:
            errors = payload.get("errors") if isinstance(payload, dict) else None
            detail = (
                "; ".join(str(item) for item in errors)
                if isinstance(errors, list)
                else "request rejected"
            )
            raise RuntimeError(f"Pushover delivery failed: {detail[:300]}")
        return {
            "sent": True,
            "request": str(payload.get("request") or ""),
            "title": str(title)[:250],
        }

    async def send(self, audit: dict[str, Any]) -> dict[str, Any]:
        title, message = format_health_audit(audit)
        return await self._send_message(title=title, message=message)


__all__ = ["PushoverNotifier", "format_health_audit"]
