from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from presenter import safe_debug
from semantic_home_evidence import SemanticHomeEvidenceBroker

AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_HOME_SUMMARY_RE = re.compile(
    r"\b(?:what(?:'s| is) happening(?: at home)?|home insight|home status|what is going on at home)\b",
    re.IGNORECASE,
)
_STATES_READ_RE = re.compile(r"\s*\([^)]*states? read[^)]*\)", re.IGNORECASE)


def _names(items: list[dict[str, Any]]) -> str:
    values = [str(item.get("device") or item.get("title") or "").strip() for item in items]
    values = [value for value in values if value]
    if len(values) < 2:
        return "".join(values)
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _fallback(evidence: dict[str, Any]) -> str:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        return "I could not obtain enough live evidence to give you a reliable home summary."

    sentences: list[str] = []
    mode = str(data.get("mode") or "").strip()
    if mode:
        sentences.append(f"The home is currently in {mode} mode.")

    motion = data.get("motion") if isinstance(data.get("motion"), dict) else {}
    motion_count = int(motion.get("active_count") or 0)
    active_motion = list(motion.get("active") or [])
    if motion_count:
        sentences.append(
            f"{_count_phrase(motion_count, 'motion sensor')} "
            f"{'is' if motion_count == 1 else 'are'} active: {_names(active_motion)}."
        )
    else:
        sentences.append("No motion sensors are currently active.")

    contacts = data.get("contacts") if isinstance(data.get("contacts"), dict) else {}
    contact_count = int(contacts.get("open_count") or 0)
    if contact_count:
        sentences.append(
            f"{_count_phrase(contact_count, 'contact sensor')} "
            f"{'is' if contact_count == 1 else 'are'} open: {_names(list(contacts.get('open') or []))}."
        )

    lights = data.get("lights") if isinstance(data.get("lights"), dict) else {}
    light_count = int(lights.get("on_count") or 0)
    if light_count:
        sentences.append(
            f"{_count_phrase(light_count, 'light')} "
            f"{'is' if light_count == 1 else 'are'} on: {_names(list(lights.get('on') or []))}."
        )

    low = data.get("low_batteries") if isinstance(data.get("low_batteries"), dict) else {}
    low_count = int(low.get("count") or 0)
    if low_count:
        items = list(low.get("items") or [])
        detail = ", ".join(
            f"{item.get('device')} at {float(item.get('value') or 0):g}%"
            for item in items[:3]
            if item.get("device")
        )
        sentences.append(
            f"{_count_phrase(low_count, 'device')} {'has' if low_count == 1 else 'have'} a low battery"
            + (f": {detail}." if detail else ".")
        )

    heating = list(data.get("heating") or [])
    if heating:
        sentences.append(f"Heating activity is currently reported by {_names(heating)}.")

    return " ".join(sentences[:5])


def _public_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        return {}
    return {
        "mode": data.get("mode"),
        "motion": data.get("motion"),
        "contacts": data.get("contacts"),
        "lights": data.get("lights"),
        "heating": data.get("heating"),
        "attention": data.get("attention"),
        "presence": data.get("presence"),
        "low_batteries": data.get("low_batteries"),
        "climate": data.get("climate"),
        "required_facts": evidence.get("required_facts"),
    }


def _normalise_answer(text: str) -> str:
    text = _STATES_READ_RE.sub("", str(text or ""))
    text = re.sub(r"^\s*(?:home summary|summary)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_required_facts(text: str, evidence: dict[str, Any]) -> bool:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        return False
    lowered = text.lower()

    mode = str(data.get("mode") or "").strip()
    if mode and mode.lower() not in lowered:
        return False

    motion = data.get("motion") if isinstance(data.get("motion"), dict) else {}
    motion_count = int(motion.get("active_count") or 0)
    if str(motion_count) not in lowered:
        return False
    for item in list(motion.get("active") or []):
        name = str(item.get("device") or "").strip()
        if name and name.lower() not in lowered:
            return False

    low = data.get("low_batteries") if isinstance(data.get("low_batteries"), dict) else {}
    low_count = int(low.get("count") or 0)
    if low_count and not any(term in lowered for term in ("low battery", "low batteries", "battery")):
        return False

    return True


async def _synthesise(application: Any, query: str, evidence: dict[str, Any]) -> tuple[str, str | None, str | None]:
    agent = application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    model = str(getattr(agent, "cloud_model", "") or getattr(agent, "model", "") or "").strip()
    fallback = _fallback(evidence)
    if not callable(post) or not model:
        return fallback, None, "Synthesis model unavailable"

    public_evidence = _public_evidence(evidence)
    system = (
        "/no_think\n"
        "You are HomeBrain. Write a natural, concise household update in 2 to 4 sentences using only the verified JSON. "
        "Sound conversational, like a helpful smart-home assistant, not like a report or log. "
        "Mention the current mode, the exact active-motion count and every active-motion device. "
        "Mention open contacts, lights on, heating activity and low batteries when those verified lists or counts are non-empty. "
        "Prioritise anything needing attention. Do not mention raw coverage, selected-device counts, states read, tool names, JSON, or technical details. "
        "Do not invent, calculate, diagnose, repeat a heading, or say that evidence was gathered."
    )
    try:
        response = await post(
            f"{str(agent.base_url).rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": (
                            f"Question: {query.strip()}\n"
                            f"Verified household facts: {json.dumps(public_evidence, ensure_ascii=False, separators=(',', ':'))}"
                        ),
                    },
                ],
                "stream": False,
                "think": False,
                "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                "options": {"num_ctx": 4096, "num_predict": 280, "temperature": 0.15},
            },
            timeout=25.0,
        )
        response.raise_for_status()
        body = response.json()
        text = _normalise_answer(
            str(((body.get("message") if isinstance(body, dict) else {}) or {}).get("content") or "")
        )
        if not text:
            raise RuntimeError("Empty synthesis response")
        if not _contains_required_facts(text, evidence):
            return fallback, None, "Synthesis omitted required verified facts"
        return text, "Ollama semantic home synthesis", None
    except Exception as exc:
        return fallback, None, str(exc).strip() or type(exc).__name__


def install_semantic_home_summary_agent(application: Any, snapshot_service: Any) -> AskHandler:
    original_ask: AskHandler = application.ask
    broker = SemanticHomeEvidenceBroker(application, snapshot_service)

    async def semantic_home_ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        if not _HOME_SUMMARY_RE.search(query):
            return await original_ask(request)
        evidence = await broker.collect(limit=20)
        if not evidence.get("success"):
            return await original_ask(request)
        message, provider, synthesis_error = await _synthesise(application, query, evidence)
        return {
            "success": True,
            "route": "ai-semantic-home-evidence",
            "intent": "home-summary",
            "message": message,
            "semantic_evidence": evidence.get("data"),
            "required_facts": evidence.get("required_facts"),
            "tools_used": list(evidence.get("tools_used") or []),
            "model": str(getattr(application.ollama, "cloud_model", "") or getattr(application.ollama, "model", "") or "") or None,
            "provider": provider,
            "synthesis_error": synthesis_error,
            "answered_by": "AI using semantic HomeBrain evidence tools",
            "technical": safe_debug({"evidence": evidence, "synthesis_error": synthesis_error}),
        }

    application.ask = semantic_home_ask
    application.semantic_home_evidence_broker = broker
    return original_ask


__all__ = ["install_semantic_home_summary_agent"]
