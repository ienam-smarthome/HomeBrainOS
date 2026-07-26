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
_NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}
_DOMAIN_TERMS = {
    "motion": ("motion sensor", "motion sensors", "motion"),
    "contacts": ("contact sensor", "contact sensors", "contact", "door", "window", "open"),
    "lights": ("light", "lights", "lamp", "lamps", "on"),
    "low_batteries": ("low battery", "low batteries", "battery", "batteries"),
    "heating": ("heating", "thermostat", "trv", "radiator"),
}


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


def _item_names(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [
        str(item.get("device") or item.get("title") or "").strip()
        for item in items
        if isinstance(item, dict) and (item.get("device") or item.get("title"))
    ]


def _fact_manifest(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        return []

    manifest: list[dict[str, Any]] = []
    mode = str(data.get("mode") or "").strip()
    if mode:
        manifest.append({"domain": "mode", "value": mode, "required": True})

    for domain, count_key, items_key in (
        ("motion", "active_count", "active"),
        ("contacts", "open_count", "open"),
        ("lights", "on_count", "on"),
        ("low_batteries", "count", "items"),
    ):
        block = data.get(domain) if isinstance(data.get(domain), dict) else {}
        count = int(block.get(count_key) or 0)
        names = _item_names(block.get(items_key))
        manifest.append(
            {
                "domain": domain,
                "count": count,
                "names": names,
                "required": domain == "motion" or count > 0,
            }
        )

    heating = _item_names(data.get("heating"))
    if heating:
        manifest.append({"domain": "heating", "names": heating, "required": True})
    return manifest


def _fallback(evidence: dict[str, Any]) -> str:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        return "I could not obtain enough live evidence to give you a reliable home summary."

    sentences: list[str] = []
    mode = str(data.get("mode") or "").strip()
    if mode:
        sentences.append(f"It's {mode} mode.")

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
            for item in items[:4]
            if item.get("device")
        )
        sentences.append(
            f"{_count_phrase(low_count, 'device')} {'has' if low_count == 1 else 'have'} a low battery"
            + (f": {detail}." if detail else ".")
        )

    heating = list(data.get("heating") or [])
    if heating:
        sentences.append(f"Heating is active on {_names(heating)}.")

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
        "low_batteries": data.get("low_batteries"),
        "fact_manifest": _fact_manifest(evidence),
    }


def _capitalise_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    fixed: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.search(r"[A-Za-z]", part)
        if match:
            index = match.start()
            part = part[:index] + part[index].upper() + part[index + 1 :]
        fixed.append(part)
    return " ".join(fixed)


def _normalise_answer(text: str) -> str:
    text = _STATES_READ_RE.sub("", str(text or ""))
    text = re.sub(r"^\s*(?:home summary|summary)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bactive[- ]motion (?:devices|sensors)\b", "motion sensors", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmotion devices\b", "motion sensors", text, flags=re.IGNORECASE)
    text = re.sub(r"\bplease note that\b\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return _capitalise_sentences(text)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _count_is_present(text: str, count: int) -> bool:
    lowered = text.lower()
    if count == 0 and re.search(r"\b(?:no|none|zero)\b", lowered):
        return True
    if re.search(rf"(?<!\d){count}(?!\d)", lowered):
        return True
    word = _NUMBER_WORDS.get(count)
    return bool(word and re.search(rf"\b{re.escape(word)}\b", lowered))


def _domain_sentences(text: str, domain: str, names: list[str]) -> list[str]:
    terms = _DOMAIN_TERMS.get(domain, ())
    sentences = _sentences(text)
    matched = [sentence for sentence in sentences if any(term in sentence.lower() for term in terms)]
    if names:
        named = [sentence for sentence in sentences if any(name.lower() in sentence.lower() for name in names)]
        matched.extend(sentence for sentence in named if sentence not in matched)
    return matched


def _contains_required_facts(text: str, evidence: dict[str, Any]) -> bool:
    lowered = text.lower()
    for fact in _fact_manifest(evidence):
        if not fact.get("required"):
            continue
        domain = str(fact.get("domain") or "")
        if domain == "mode":
            if str(fact.get("value") or "").lower() not in lowered:
                return False
            continue

        names = [str(name) for name in list(fact.get("names") or []) if str(name).strip()]
        relevant = _domain_sentences(text, domain, names)
        if not relevant:
            return False
        domain_text = " ".join(relevant)

        count = fact.get("count")
        if count is not None and not _count_is_present(domain_text, int(count)):
            return False
        for name in names:
            if name.lower() not in domain_text.lower():
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

    system = (
        "/no_think\n"
        "You are HomeBrain. Write a natural, concise household update in 2 to 4 sentences using only the verified JSON. "
        "Sound conversational, not like a report. Always say 'motion sensors', never 'active-motion devices'. "
        "Include every fact marked required in fact_manifest, preserving exact counts and exact device names. "
        "Keep each domain's count in the same sentence as that domain. "
        "For a zero motion count, say no motion sensors are active. "
        "Mention non-empty open contacts, lights on, heating and low batteries. Prioritise anything needing attention. "
        "Do not mention coverage, states read, tool names, JSON, technical details or evidence gathering. "
        "Do not invent, calculate, diagnose, repeat a heading or add unverified context."
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
                            f"Verified household facts: {json.dumps(_public_evidence(evidence), ensure_ascii=False, separators=(',', ':'))}"
                        ),
                    },
                ],
                "stream": False,
                "think": False,
                "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                "options": {"num_ctx": 4096, "num_predict": 280, "temperature": 0.1},
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
            "fact_manifest": _fact_manifest(evidence),
            "tools_used": list(evidence.get("tools_used") or []),
            "model": str(getattr(application.ollama, "cloud_model", "") or getattr(application.ollama, "model", "") or "") or None,
            "provider": provider,
            "synthesis_error": synthesis_error,
            "answered_by": "AI using semantic HomeBrain evidence tools",
            "technical": safe_debug(
                {
                    "evidence": evidence,
                    "fact_manifest": _fact_manifest(evidence),
                    "synthesis_error": synthesis_error,
                }
            ),
        }

    application.ask = semantic_home_ask
    application.semantic_home_evidence_broker = broker
    return original_ask


__all__ = ["_fact_manifest", "install_semantic_home_summary_agent"]
