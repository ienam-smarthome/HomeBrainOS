"""Bounded current-turn tool evidence for final reasoning synthesis."""

from __future__ import annotations

from typing import Any


_MAX_PACKET_ITEMS = 10
_MAX_ITEM_CHARS = 2200
_MAX_PACKET_CHARS = 18000
_SKIP_TOOLS = {"hub_search_tools"}


def build_tool_evidence_packet(
    messages: list[dict[str, Any]],
    *,
    max_items: int = _MAX_PACKET_ITEMS,
    max_item_chars: int = _MAX_ITEM_CHARS,
    max_packet_chars: int = _MAX_PACKET_CHARS,
) -> str | None:
    """Keep recent concrete tool data visible to the no-tools synthesis pass.

    Tool payloads have already passed through ToolExecutor's precise-location
    redaction. This function does not interpret the data or choose a conclusion;
    it merely preserves bounded current-turn evidence after normal context
    compaction.
    """

    rows: list[tuple[str, str]] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        tool_name = str(message.get("tool_name") or message.get("name") or "").strip()
        if not tool_name or tool_name in _SKIP_TOOLS:
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if len(content) > max_item_chars:
            content = content[: max_item_chars - 3] + "..."
        rows.append((tool_name, content))

    if not rows:
        return None

    rows = rows[-max(1, int(max_items)) :]
    rendered = [
        "HOST CURRENT-TURN TOOL EVIDENCE EXCERPTS",
        "These are bounded excerpts of actual tool results from THIS request. "
        "Use them together with the structured evidence brief. Do not treat an "
        "excerpt boundary as proof that omitted rows did not exist.",
    ]
    for index, (tool_name, content) in enumerate(rows, start=1):
        rendered.append(f"[{index}] {tool_name}: {content}")

    packet = "\n".join(rendered)
    if len(packet) > max_packet_chars:
        packet = packet[: max_packet_chars - 3] + "..."
    return packet


__all__ = ["build_tool_evidence_packet"]
