from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from presenter import safe_debug
from semantic_home_summary_agent import _normalise_answer, _synthesise

AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_WRITE_RE = re.compile(
    r"\b(?:turn|switch|set|enable|disable|open|close|lock|unlock|start|stop|pause|resume|create|delete|remove|run|reboot|restart)\b",
    re.IGNORECASE,
)


def _json_object(text: str) -> dict[str, Any] | None:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(value[start : end + 1])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


async def _classify(application: Any, query: str) -> tuple[str, str | None]:
    if _WRITE_RE.search(query):
        return "passthrough", "write-like request"

    agent = application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    model = str(
        getattr(agent, "planner_model", "")
        or getattr(agent, "cloud_model", "")
        or getattr(agent, "model", "")
        or ""
    ).strip()
    if not callable(post) or not model:
        return "passthrough", "semantic classifier unavailable"

    system = (
        "/no_think\n"
        "Classify the user's smart-home request. Return JSON only with one key named intent. "
        "Allowed intents: home_summary, home_attention, passthrough. "
        "Use home_summary for broad requests asking what is happening, the overall home state, or a general household update. "
        "Use home_attention for broad requests asking what is unusual, wrong, important, concerning, needs attention, or should be checked. "
        "Use passthrough for direct device questions, controls, automations, weather, energy, people, rooms, or any request that is not a broad whole-home summary. "
        "Classify by meaning, not exact wording. When uncertain, use passthrough."
    )
    try:
        response = await post(
            f"{str(agent.base_url).rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query.strip()},
                ],
                "stream": False,
                "think": False,
                "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                "format": "json",
                "options": {"num_ctx": 2048, "num_predict": 40, "temperature": 0},
            },
            timeout=8.0,
        )
        response.raise_for_status()
        body = response.json()
        content = str(((body.get("message") if isinstance(body, dict) else {}) or {}).get("content") or "")
        parsed = _json_object(content) or {}
        intent = str(parsed.get("intent") or "passthrough").strip().lower()
        if intent not in {"home_summary", "home_attention", "passthrough"}:
            intent = "passthrough"
        return intent, None
    except Exception as exc:
        return "passthrough", str(exc).strip() or type(exc).__name__


def _attention_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        data = {}

    low_block = data.get("low_batteries") if isinstance(data.get("low_batteries"), dict) else {}
    low_items = [item for item in list(low_block.get("items") or []) if isinstance(item, dict)]
    low_names = {str(item.get("device") or "").strip().casefold() for item in low_items}

    stale: list[dict[str, Any]] = []
    offline: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []

    for item in list(data.get("attention") or []):
        if not isinstance(item, dict):
            continue
        room = str(item.get("room") or "").strip()
        title = str(item.get("title") or item.get("device") or "").strip()
        if room.casefold() == "life360" or title.casefold() in low_names:
            continue
        text = " ".join(
            str(item.get(key) or "") for key in ("title", "value", "subtitle", "tone")
        ).casefold()
        row = {
            "device": title,
            "room": room or None,
            "value": item.get("value"),
            "detail": item.get("subtitle"),
        }
        if "offline" in text:
            offline.append(row)
        elif "stale" in text or "last activity" in text:
            stale.append(row)
        elif "update" in text:
            updates.append(row)
        else:
            warnings.append(row)

    result = {
        "low_batteries": {
            "count": len(low_items),
            "items": low_items,
        },
        "offline": {"count": len(offline), "items": offline},
        "stale": {"count": len(stale), "items": stale},
        "warnings": {"count": len(warnings), "items": warnings},
        "updates": {"count": len(updates), "items": updates},
        "open_contacts": data.get("contacts"),
        "lights_on": data.get("lights"),
    }
    result["issue_count"] = sum(
        int(result[name].get("count") or 0)
        for name in ("low_batteries", "offline", "stale", "warnings", "updates")
    )
    return result


def _names(items: list[dict[str, Any]]) -> str:
    values = [str(item.get("device") or item.get("title") or "").strip() for item in items]
    values = [value for value in values if value]
    if len(values) < 2:
        return "".join(values)
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _attention_fallback(attention: dict[str, Any]) -> str:
    parts: list[str] = []
    low = attention["low_batteries"]
    if low["count"]:
        details = ", ".join(
            f"{item.get('device')} at {float(item.get('value') or 0):g}%"
            for item in low["items"]
            if item.get("device")
        )
        parts.append(f"Low batteries need attention: {details}.")
    for domain, label in (("offline", "offline"), ("stale", "stale"), ("warnings", "showing warnings"), ("updates", "have updates available")):
        block = attention[domain]
        if block["count"]:
            parts.append(f"{_names(block['items'])} {'is' if block['count'] == 1 else 'are'} {label}.")
    contacts = attention.get("open_contacts") if isinstance(attention.get("open_contacts"), dict) else {}
    if int(contacts.get("open_count") or 0):
        parts.append(f"Open contacts: {_names(list(contacts.get('open') or []))}.")
    if not parts:
        return "Nothing currently stands out as needing attention."
    return " ".join(parts[:5])


def _attention_complete(text: str, attention: dict[str, Any]) -> bool:
    lowered = text.casefold()
    for domain in ("low_batteries", "offline", "stale", "warnings", "updates"):
        block = attention[domain]
        if not int(block.get("count") or 0):
            continue
        for item in block.get("items") or []:
            name = str(item.get("device") or "").strip()
            if name and name.casefold() not in lowered:
                return False
    return True


async def _synthesise_attention(application: Any, query: str, attention: dict[str, Any]) -> tuple[str, str | None, str | None]:
    fallback = _attention_fallback(attention)
    agent = application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    model = str(getattr(agent, "cloud_model", "") or getattr(agent, "model", "") or "").strip()
    if not callable(post) or not model:
        return fallback, None, "Synthesis model unavailable"
    try:
        response = await post(
            f"{str(agent.base_url).rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "/no_think\nWrite a concise, natural smart-home attention summary using only the verified JSON. "
                            "Mention every named item in each non-empty issue category. Prioritise safety and outages, then stale devices, low batteries, warnings and updates. "
                            "Do not mention Life360 phone batteries, raw state counts, selected-device counts, tools, JSON or evidence gathering."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question: {query.strip()}\nVerified attention facts: {json.dumps(attention, ensure_ascii=False, separators=(',', ':'))}",
                    },
                ],
                "stream": False,
                "think": False,
                "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                "options": {"num_ctx": 3072, "num_predict": 220, "temperature": 0.1},
            },
            timeout=20.0,
        )
        response.raise_for_status()
        body = response.json()
        text = _normalise_answer(str(((body.get("message") if isinstance(body, dict) else {}) or {}).get("content") or ""))
        if not text or not _attention_complete(text, attention):
            return fallback, None, "Synthesis omitted required attention facts"
        return text, "Ollama semantic attention synthesis", None
    except Exception as exc:
        return fallback, None, str(exc).strip() or type(exc).__name__


def install_semantic_home_query_router(application: Any) -> AskHandler:
    original_ask: AskHandler = application.ask
    broker = application.semantic_home_evidence_broker

    async def semantic_router_ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        intent, classification_error = await _classify(application, query)
        if intent == "passthrough":
            return await original_ask(request)

        evidence = await broker.collect(limit=20)
        if not evidence.get("success"):
            return await original_ask(request)

        if intent == "home_summary":
            message, provider, synthesis_error = await _synthesise(application, query, evidence)
            return {
                "success": True,
                "route": "ai-semantic-home-evidence",
                "intent": "home-summary",
                "message": message,
                "semantic_evidence": evidence.get("data"),
                "tools_used": list(evidence.get("tools_used") or []),
                "provider": provider,
                "synthesis_error": synthesis_error,
                "classification_error": classification_error,
                "answered_by": "AI semantic intent router using verified HomeBrain evidence",
                "technical": safe_debug({"intent": intent, "evidence": evidence, "synthesis_error": synthesis_error, "classification_error": classification_error}),
            }

        attention = _attention_evidence(evidence)
        message, provider, synthesis_error = await _synthesise_attention(application, query, attention)
        return {
            "success": True,
            "route": "ai-semantic-home-attention",
            "intent": "home-attention-summary",
            "message": message,
            "semantic_attention": attention,
            "tools_used": list(evidence.get("tools_used") or []),
            "provider": provider,
            "synthesis_error": synthesis_error,
            "classification_error": classification_error,
            "answered_by": "AI semantic intent router using verified HomeBrain attention evidence",
            "technical": safe_debug({"intent": intent, "attention": attention, "synthesis_error": synthesis_error, "classification_error": classification_error}),
        }

    application.ask = semantic_router_ask
    application.semantic_home_query_router = semantic_router_ask
    return original_ask


__all__ = [
    "_attention_complete",
    "_attention_evidence",
    "_attention_fallback",
    "_json_object",
    "install_semantic_home_query_router",
]
