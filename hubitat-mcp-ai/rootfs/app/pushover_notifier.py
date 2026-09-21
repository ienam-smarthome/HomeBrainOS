from __future__ import annotations

from html import escape
import re
from typing import Any

import httpx


PUSHOVER_MESSAGES_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_MESSAGE_LIMIT = 1024
PUSHOVER_CRITICAL_COLOR = "#ff5c5c"
PUSHOVER_WARNING_COLOR = "#ffb300"


def _clean_named_finding(title: str, prefix: str) -> str:
    value = title[len(prefix):].strip() if title.lower().startswith(prefix.lower()) else title.strip()
    return value or "Unknown"


def _html_text(value: Any) -> str:
    return escape(str(value or ""), quote=False)


def _color(value: Any, color: str) -> str:
    return f'<font color="{color}">{_html_text(value)}</font>'


def _split_state_detail(detail: str) -> tuple[str, str]:
    match = re.match(r"^(\S+)(.*)$", str(detail or "").strip())
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def _fit_message_line(line: str) -> str:
    """Keep one logical line safely below the Pushover body limit."""

    if len(line) <= 850:
        return line
    plain = re.sub(r"<[^>]+>", "", line)
    return plain[:847].rstrip() + "…"


def _chunk_message_lines(lines: list[str]) -> list[str]:
    """Split a report into complete Pushover messages without cutting HTML tags."""

    chunks: list[str] = []
    current: list[str] = []
    for raw_line in lines:
        line = _fit_message_line(raw_line)
        candidate = "\n".join([*current, line])
        if len(candidate) <= PUSHOVER_MESSAGE_LIMIT:
            current.append(line)
            continue

        # Do not leave a section heading stranded at the bottom of a message.
        heading = ""
        if current and current[-1].endswith(":") and len(current) > 1:
            heading = current.pop()

        if current:
            chunks.append("\n".join(current))
        current = [heading] if heading else []

        candidate = "\n".join([*current, line])
        if len(candidate) > PUSHOVER_MESSAGE_LIMIT:
            if current:
                chunks.append("\n".join(current))
                current = []
            line = _fit_message_line(line)
        current.append(line)

    if current:
        chunks.append("\n".join(current))
    return chunks or [""]


def _append_section(lines: list[str], heading: str, values: list[str], *, limit: int) -> None:
    if not values:
        return
    lines.append(f"{heading}:")
    for value in values[:limit]:
        lines.append(f"• {value}")
    remaining = len(values) - limit
    if remaining > 0:
        lines.append(f"• +{remaining} more")


def _format_health_audit_lines(audit: dict[str, Any]) -> tuple[str, list[str]]:
    status = str(audit.get("status") or "unknown").strip().title()
    title = f"HomeBrain System Check: {status}"[:250]
    hierarchy = audit.get("health_hierarchy") or {}

    lines: list[str] = []
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
        lines.append(f"{icon} {_html_text(label)}: {_html_text(summary)}")

    attention = int(audit.get("attention_count") or 0)
    new_count = int(audit.get("new_count") or 0)
    resolved_count = int(audit.get("resolved_count") or 0)
    lines.append(
        f"Total: {attention} attention · {new_count} new · {resolved_count} resolved"
    )

    issues = [
        row
        for row in (audit.get("issues") or [])
        if isinstance(row, dict) and row.get("severity") in {"critical", "warning"}
    ]
    offline: list[str] = []
    low_battery: list[str] = []
    broken_automations: list[str] = []
    logs: list[str] = []
    other: list[str] = []

    for item in issues:
        finding_title = str(item.get("title") or "Issue").strip()
        detail = str(item.get("detail") or "").strip()
        domain = str(item.get("domain") or "").strip().lower()
        occurrence = int(item.get("count") or 1)
        suffix = f" ×{occurrence}" if occurrence > 1 else ""

        if finding_title.lower().startswith("device unavailable:"):
            name = _clean_named_finding(finding_title, "Device unavailable:")
            state = detail or "offline"
            offline.append(
                f"{_color(name, PUSHOVER_CRITICAL_COLOR)} — "
                f"{_color(state, PUSHOVER_CRITICAL_COLOR)}{_html_text(suffix)}"
            )
        elif finding_title.lower().startswith("low battery:"):
            name = _clean_named_finding(finding_title, "Low battery:")
            state, remainder = _split_state_detail(detail)
            if state:
                low_battery.append(
                    f"{_color(name, PUSHOVER_WARNING_COLOR)} — "
                    f"{_color(state, PUSHOVER_WARNING_COLOR)}{_html_text(remainder)}"
                )
            else:
                low_battery.append(_color(name, PUSHOVER_WARNING_COLOR))
        elif finding_title.lower().startswith("automation broken:"):
            broken_automations.append(
                _html_text(_clean_named_finding(finding_title, "Automation broken:"))
                + _html_text(suffix)
            )
        elif domain == "logs":
            logs.append(_html_text(f"{finding_title} — {detail}{suffix}" if detail else finding_title + suffix))
        else:
            other.append(_html_text(f"{finding_title} — {detail}{suffix}" if detail else finding_title + suffix))

    _append_section(lines, "Offline", offline, limit=8)
    _append_section(lines, "Low battery", low_battery, limit=6)
    _append_section(lines, "Broken automations", broken_automations, limit=6)
    _append_section(lines, "Logs", logs, limit=3)
    _append_section(lines, "Other findings", other, limit=3)

    resolved = [
        _html_text(str(item.get("title") or "Issue").strip())
        for item in (audit.get("resolved_issues") or [])
        if isinstance(item, dict)
    ]
    _append_section(lines, "Resolved", resolved, limit=3)

    if not issues:
        lines.append("No current findings need attention.")

    return title, lines


def format_health_audit_messages(audit: dict[str, Any]) -> tuple[str, list[str]]:
    title, lines = _format_health_audit_lines(audit)
    return title, _chunk_message_lines(lines)


def format_health_audit(audit: dict[str, Any]) -> tuple[str, str]:
    """Backward-compatible single-message formatter.

    Delivery uses format_health_audit_messages() so a large report is never
    silently truncated. This helper returns the first part for existing callers
    and focused unit tests.
    """

    title, messages = format_health_audit_messages(audit)
    return title, messages[0]


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
            "html": "1",
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
        title, messages = format_health_audit_messages(audit)
        deliveries: list[dict[str, Any]] = []
        total = len(messages)
        for index, message in enumerate(messages, start=1):
            part_title = title if total == 1 else f"{title} ({index}/{total})"
            deliveries.append(
                await self._send_message(title=part_title, message=message)
            )
        return {
            "sent": True,
            "request": str(deliveries[0].get("request") or "") if deliveries else "",
            "requests": [str(item.get("request") or "") for item in deliveries],
            "title": title,
            "messages_sent": total,
        }


__all__ = [
    "PushoverNotifier",
    "format_health_audit",
    "format_health_audit_messages",
]
