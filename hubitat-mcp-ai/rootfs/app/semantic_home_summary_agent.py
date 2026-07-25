from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from presenter import safe_debug
from semantic_home_evidence import SemanticHomeEvidenceBroker

AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_HOME_SUMMARY_RE = re.compile(r"\b(?:what(?:'s| is) happening(?: at home)?|home insight|home status|what is going on at home)\b", re.IGNORECASE)


def _names(items: list[dict[str, Any]]) -> str:
    values = [str(item.get("device") or "").strip() for item in items if item.get("device")]
    if len(values) < 2:
        return "".join(values)
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _fallback(evidence: dict[str, Any]) -> str:
    data = evidence.get("data") if isinstance(evidence, dict) else {}
    if not isinstance(data, dict):
        return "HomeBrain could not obtain enough live evidence for a home summary."
    parts: list[str] = []
    if data.get("mode"):
        parts.append(f"The home is in {data['mode']} mode")
    motion = data.get("motion") if isinstance(data.get("motion"), dict) else {}
    count = int(motion.get("active_count") or 0)
    active = list(motion.get("active") or [])
    parts.append(f"{count} motion sensor{' is' if count == 1 else 's are'} active" + (f": {_names(active)}" if count else ""))
    contacts = data.get("contacts") if isinstance(data.get("contacts"), dict) else {}
    lights = data.get("lights") if isinstance(data.get("lights"), dict) else {}
    low = data.get("low_batteries") if isinstance(data.get("low_batteries"), dict) else {}
    if int(contacts.get("open_count") or 0):
        parts.append(f"{int(contacts['open_count'])} contact sensor(s) are open")
    if int(lights.get("on_count") or 0):
        parts.append(f"{int(lights['on_count'])} light(s) are on")
    if int(low.get("count") or 0):
        parts.append(f"{int(low['count'])} device(s) have a battery at or below 20%")
    return ". ".join(part[:1].upper() + part[1:] for part in parts) + "."


async def _synthesise(application: Any, query: str, evidence: dict[str, Any]) -> tuple[str, str | None, str | None]:
    agent = application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    model = str(getattr(agent, "cloud_model", "") or getattr(agent, "model", "") or "").strip()
    if not callable(post) or not model:
        return _fallback(evidence), None, "Synthesis model unavailable"
    try:
        response = await post(
            f"{str(agent.base_url).rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "/no_think\nWrite a concise HomeBrain summary using only the verified JSON. Mention the exact active-motion count and every active-motion device. Do not infer states or calculate facts."},
                    {"role": "user", "content": f"Question: {query.strip()}\nVerified semantic evidence: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}"},
                ],
                "stream": False,
                "think": False,
                "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                "options": {"num_ctx": 4096, "num_predict": 260, "temperature": 0},
            },
            timeout=25.0,
        )
        response.raise_for_status()
        body = response.json()
        text = str(((body.get("message") if isinstance(body, dict) else {}) or {}).get("content") or "").strip()
        if not text:
            raise RuntimeError("Empty synthesis response")
        return text, "Ollama semantic home synthesis", None
    except Exception as exc:
        return _fallback(evidence), None, str(exc).strip() or type(exc).__name__


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
            "display": {"kind": "home-summary", "title": "Home summary", "subtitle": "AI synthesis from typed live evidence", "summary": message, "note": "Python calculated counts and aggregations before AI synthesis."},
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
