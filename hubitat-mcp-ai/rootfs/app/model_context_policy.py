"""Bound copied conversation and tool-result context sent to the model.

This policy owns payload budgeting only.  It never mutates the authoritative
conversation, evidence receipts, confirmation state, or tool results used by
the orchestrator.  Character budgets remain explicit until the runtime has a
reliable tokenizer for every configured model family.
"""

from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger("HomeBrainOS.ModelContextPolicy")


class ModelContextPolicy:
    """Apply immutable history and cumulative tool-content bounds."""

    def __init__(
        self,
        *,
        max_history_messages: int = 8,
        max_history_chars: int = 12000,
        max_tool_context_chars: int = 48000,
        compacted_tool_result_chars: int = 1200,
    ) -> None:
        self.max_history_messages = max(0, int(max_history_messages))
        self.max_history_chars = max(0, int(max_history_chars))
        self.max_tool_context_chars = max(4000, int(max_tool_context_chars))
        self.compacted_tool_result_chars = max(
            256,
            min(
                int(compacted_tool_result_chars),
                self.max_tool_context_chars // 2,
            ),
        )

    def history(self, history: Any) -> list[dict[str, Any]]:
        """Return recent user/assistant messages inside both configured bounds."""

        messages: list[dict[str, Any]] = []
        for item in list(history or []):
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            role = (
                "assistant"
                if item.get("role") in {"assistant", "model"}
                else "user"
            )
            content = item.get("content") or item.get("text")
            if content:
                messages.append({"role": role, "content": str(content)})
        if not self.max_history_messages or not self.max_history_chars:
            return []

        bounded: list[dict[str, Any]] = []
        remaining = self.max_history_chars
        for message in reversed(messages[-self.max_history_messages:]):
            content = str(message["content"])
            if remaining <= 0:
                break
            if len(content) > remaining:
                marker = "\n[earlier history truncated]"
                if remaining <= len(marker):
                    break
                keep = max(0, remaining - len(marker))
                content = content[:keep] + (marker if keep else "")
            bounded.append({**message, "content": content})
            remaining -= len(content)
        return list(reversed(bounded))

    @staticmethod
    def compact_tool_content(content: str, max_chars: int) -> str:
        """Replace older tool content with a labelled bounded excerpt."""

        if max_chars <= 0:
            return ""
        if max_chars < 160:
            return "[older tool result compacted]"[:max_chars]
        payload = {
            "context_compacted": True,
            "original_chars": len(content),
            "result_excerpt": "",
            "instruction": "Use the newer tool results for current detail.",
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        excerpt_chars = max(0, max_chars - len(serialized))
        payload["result_excerpt"] = content[:excerpt_chars]
        serialized = json.dumps(payload, ensure_ascii=False)
        while len(serialized) > max_chars and payload["result_excerpt"]:
            overflow = len(serialized) - max_chars
            payload["result_excerpt"] = payload["result_excerpt"][:-overflow]
            serialized = json.dumps(payload, ensure_ascii=False)
        return serialized[:max_chars]

    def bounded_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Copy messages and compact oldest tool results to the shared budget."""

        bounded = [dict(message) for message in messages]
        tool_indices = [
            index
            for index, message in enumerate(bounded)
            if message.get("role") == "tool"
            and message.get("content") is not None
        ]
        total = sum(
            len(str(bounded[index]["content"])) for index in tool_indices
        )
        original_total = total
        for index in tool_indices:
            if total <= self.max_tool_context_chars:
                break
            content = str(bounded[index]["content"])
            excess = total - self.max_tool_context_chars
            target = max(
                self.compacted_tool_result_chars,
                len(content) - excess,
            )
            if target >= len(content):
                continue
            replacement = self.compact_tool_content(content, target)
            bounded[index]["content"] = replacement
            total += len(replacement) - len(content)
        for index in tool_indices:
            if total <= self.max_tool_context_chars:
                break
            content = str(bounded[index]["content"])
            excess = total - self.max_tool_context_chars
            target = max(0, len(content) - excess)
            replacement = self.compact_tool_content(content, target)
            bounded[index]["content"] = replacement
            total += len(replacement) - len(content)
        if total < original_total:
            logger.info(
                "Compacted retained tool context from %d to %d chars",
                original_total,
                total,
            )
        return bounded
