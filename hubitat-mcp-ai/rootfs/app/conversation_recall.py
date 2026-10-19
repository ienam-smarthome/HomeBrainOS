"""One-turn conversation references: answer from supplied chat, never Hubitat.

Keep simple history-metadata questions out of MCP discovery and the model's
general action loop. This is a *capability/intent boundary*, not a device-name
rule: all topics, device labels and app names are treated identically.
"""
from __future__ import annotations

import re
from typing import Any


_LAST_QUESTION = re.compile(
    r"^\s*(?:(?:please\s+)?(?:tell|remind)\s+me\s+)?"
    r"(?:what\s+(?:was|is)\s+(?:my|the)\s+(?:last|previous)\s+(?:question|request)"
    r"|what\s+did\s+i\s+(?:just|last|previously)\s+ask(?:\s+you)?"
    r"|repeat\s+my\s+(?:last|previous)\s+(?:question|request))\s*[.?!]?\s*$",
    re.I,
)
_LAST_RESPONSE = re.compile(
    r"^\s*(?:what\s+(?:was|did)\s+(?:your|you)\s+(?:last|previous)\s+(?:answer|reply|response|say)"
    r"|repeat\s+your\s+(?:last|previous)\s+(?:answer|reply|response))\s*[.?!]?\s*$",
    re.I,
)
_HISTORY_REFERENCE = re.compile(
    r"^\s*(?:(?:what|which|who)\s+.+?\s+(?:did\s+i|we)\s+(?:just|last|previously)\s+"
    r"(?:ask|discuss|mention|talk\s+about)|"
    r"(?:which|what)\s+(?:device|room|app|rule|subject|topic|automation|sensor)\s+"
    r"did\s+i\s+(?:just|last|previously)\s+(?:ask|mention|discuss|talk\s+about)|"
    r"(?:summari[sz]e|recap)\s+(?:our|the|this)\s+(?:last|previous|recent)\s+"
    r"(?:chat|conversation|exchange|discussion)|"
    r"(?:what|who|which)\s+were\s+we\s+(?:just|previously)\s+(?:discussing|talking\s+about))"
    r".*?[.?!]?\s*$",
    re.I,
)
# A memory request and a separate live/control instruction require normal
# request classification, so the history-only route cannot swallow a write.
_MIXED_LIVE = re.compile(
    r"\b(?:and|then|also)\s+(?:check|read|query|fetch|refresh|update|change|"
    r"turn|switch|disable|enable|delete|create|set|run)\b",
    re.I,
)


def conversation_reference_intent(question: str) -> str | None:
    """Return a conservative conversation-only intent, with no target guessing."""
    text = str(question or "").strip()
    if not text or len(text) > 260 or _MIXED_LIVE.search(text):
        return None
    if _LAST_QUESTION.fullmatch(text):
        return "last_user_question"
    if _LAST_RESPONSE.fullmatch(text):
        return "last_assistant_answer"
    if _HISTORY_REFERENCE.fullmatch(text):
        return "contextual_recall"
    return None


def _history_items(history: Any) -> list[dict[str, str]]:
    """Only accept caller-provided same-session user/assistant chat entries."""
    items = []
    for row in list(history or [])[-8:]:
        if hasattr(row, "model_dump"):
            row = row.model_dump()
        if not isinstance(row, dict) or row.get("role") not in ("user", "assistant"):
            continue
        content = row.get("content")
        if isinstance(content, str) and content.strip():
            items.append({"role": row["role"], "content": content[:4000]})
    return items


def conversation_reference_answer(
    question: str, history: Any,
) -> tuple[str | None, list[dict[str, str]] | None]:
    """Return deterministic text or a bounded, tool-free model transcript.

    The host answers exact last-question/answer requests verbatim. Interpretive
    references use *one* model call, without tool declarations. Previous model
    replies are discussion context, not evidence of current Hubitat state.
    """
    intent = conversation_reference_intent(question)
    if intent is None:
        return None, None
    rows = _history_items(history)
    if not rows:
        return "I have no earlier messages available in this chat to answer that.", None
    if intent == "last_user_question":
        latest = next((r["content"] for r in reversed(rows) if r["role"] == "user"), None)
        return (f"Your previous question was: {latest}" if latest else
                "I have no earlier question available in this chat."), None
    if intent == "last_assistant_answer":
        latest = next((r["content"] for r in reversed(rows) if r["role"] == "assistant"), None)
        return (f"My previous answer was:\n{latest}" if latest else
                "I have no earlier answer available in this chat."), None
    if not any(row["role"] == "user" for row in rows):
        return "I have no earlier question available in this chat.", None

    return None, [
        {"role": "system", "content": (
            "Answer a question ONLY about this supplied conversation. "
            "Do not query Hubitat, invent previous turns, call tools, or treat "
            "earlier assistant claims as fresh/live device evidence. "
            "Identify the subject only when named in the prior user questions; "
            "if the answer is ambiguous or missing, say so succinctly. "
            "Never reinterpret this as permission to change devices or rules."
        )},
        *rows,
        {"role": "user", "content": str(question).strip()},
    ]


__all__ = ["conversation_reference_intent", "conversation_reference_answer"]
