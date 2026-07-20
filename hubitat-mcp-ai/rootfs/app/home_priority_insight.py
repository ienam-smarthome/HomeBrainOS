from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_ISSUE_TERMS = (
    "issue",
    "issues",
    "problem",
    "problems",
    "concern",
    "concerns",
    "needs attention",
    "need attention",
    "important things",
    "wrong",
    "unusual",
)
_HOME_TERMS = ("home", "house", "at home", "around home")
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).strip(" .!?")


def is_home_priority_query(query: str) -> bool:
    q = _normalise(query)
    if q in {"home insight", "ai home insight", "home priorities", "home problems"}:
        return True
    if q.startswith("what looks unusual") and any(term in q for term in _HOME_TERMS):
        return True
    return bool(
        any(term in q for term in _ISSUE_TERMS)
        and any(term in q for term in _HOME_TERMS)
    )


def requested_issue_limit(query: str) -> int:
    q = _normalise(query)
    match = re.search(r"\b(?:top\s+)?([1-5])\b", q)
    if match:
        return int(match.group(1))
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", q):
            return value
    return 3


class WholeHomePriorityInsight:
    """Rank confirmed whole-home issues from a truthful live snapshot.

    Hubitat evidence is gathered before AI is called. The model receives no MCP tools
    and may only rank or phrase the already-confirmed issue rows. A deterministic
    ranking is always retained as the fallback.
    """

    def __init__(
        self,
        application: Any,
        snapshot_service: Any,
        *,
        ai_enabled: bool = True,
        ai_timeout_seconds: float = 20.0,
    ) -> None:
        self.application = application
        self.snapshot_service = snapshot_service
        self.ai_enabled = bool(ai_enabled)
        self.ai_timeout_seconds = max(3.0, min(30.0, float(ai_timeout_seconds)))

    @staticmethod
    def matches(query: str) -> bool:
        return is_home_priority_query(query)

    async def _snapshot(self) -> tuple[dict[str, Any], list[str], bool]:
        errors: list[str] = []
        devices, diagnostics, hub_status = await self.snapshot_service._load_sources(
            force=False,
            coverage_errors=errors,
        )
        snapshot = self.snapshot_service._build_snapshot(devices, diagnostics, hub_status)
        recovery_attempted = False
        if devices and int(snapshot.get("states_read") or 0) == 0:
            recovery_attempted = True
            recovery_errors: list[str] = []
            devices, diagnostics, hub_status = await self.snapshot_service._load_sources(
                force=True,
                coverage_errors=recovery_errors,
            )
            recovered = self.snapshot_service._build_snapshot(
                devices,
                diagnostics,
                hub_status,
            )
            if int(recovered.get("states_read") or 0) > 0:
                snapshot = recovered
                errors = recovery_errors
            else:
                errors.extend(item for item in recovery_errors if item not in errors)
                errors.append("device states: no readable live attributes were returned")
        return snapshot, errors, recovery_attempted

    @staticmethod
    def _issue_rows(snapshot: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(item: dict[str, Any], *, default_priority: float) -> None:
            title = str(item.get("title") or "Unknown issue").strip()
            value = str(item.get("value") or "Needs attention").strip()
            key = (_normalise(title), _normalise(value))
            if key in seen:
                return
            seen.add(key)
            row = dict(item)
            row["title"] = title
            row["value"] = value
            try:
                row["priority"] = float(item.get("priority", default_priority))
            except Exception:
                row["priority"] = default_priority
            rows.append(row)

        for item in list(snapshot.get("attention") or []):
            if isinstance(item, dict):
                add(item, default_priority=10)
        for item in list(snapshot.get("open_contacts") or []):
            if isinstance(item, dict):
                add(item, default_priority=20)

        rows.sort(key=lambda item: (float(item.get("priority", 50)), _normalise(item.get("title"))))
        return rows[: max(1, min(5, int(limit)))]

    @staticmethod
    def _deterministic_message(rows: list[dict[str, Any]], limit: int) -> str:
        if not rows:
            return (
                "No confirmed urgent home issues were found in the selected live Hubitat "
                "devices. HomeBrain did not invent extra problems to fill the requested list."
            )
        parts = []
        for index, item in enumerate(rows[:limit], start=1):
            detail = str(item.get("subtitle") or "").strip()
            text = f"{index}. {item['title']} — {item['value']}"
            if detail:
                text += f" ({detail})"
            parts.append(text + ".")
        suffix = "" if len(rows) >= limit else f" Only {len(rows)} confirmed issue{' was' if len(rows) == 1 else 's were'} found."
        return " ".join(parts) + suffix

    async def _ai_message(
        self,
        *,
        query: str,
        snapshot: dict[str, Any],
        rows: list[dict[str, Any]],
        deterministic: str,
        limit: int,
    ) -> tuple[str, str, str]:
        ollama = self.application.ollama
        health = await ollama.health()
        if not health.get("online"):
            raise RuntimeError(health.get("error") or "Ollama is offline")
        installed = list(health.get("models") or [])
        resolver = getattr(ollama, "_resolve_routine_model", None)
        model = (
            resolver(installed)
            if callable(resolver)
            else str(getattr(ollama, "model", ""))
        )
        if not model:
            raise RuntimeError("No home-insight response model is available")

        evidence = {
            "confirmed_issues": [
                {
                    "device": item.get("title"),
                    "state": item.get("value"),
                    "detail": item.get("subtitle"),
                    "priority": item.get("priority"),
                }
                for item in rows
            ],
            "coverage": {
                "selected_devices": snapshot.get("selected_devices"),
                "states_read": snapshot.get("states_read"),
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are HomeBrain. Use only the supplied verified Hubitat evidence. "
                    f"Rank up to {limit} confirmed home issues from most important to least important. "
                    "Use exact device names. Do not invent causes, devices, states or extra issues. "
                    "If fewer issues are confirmed, state only those and say that fewer were found. "
                    "Use a short numbered list and no follow-up offer."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Current request: {query.strip()}\n"
                    f"Verified evidence: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}\n"
                    f"Deterministic ranking to improve, never contradict: {deterministic}"
                ),
            },
        ]
        body = await ollama._chat(
            model=model,
            messages=messages,
            tools=None,
            timeout_seconds=self.ai_timeout_seconds,
            num_ctx=min(int(getattr(ollama, "num_ctx", 2048)), 2048),
            num_predict=180,
            temperature=0.1,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty home-priority answer")
        actual_model = str(body.get("_homebrain_model_used") or model).strip()
        provider = str(
            body.get("_homebrain_provider")
            or getattr(getattr(ollama, "_http", None), "last_provider", lambda *_: None)()
            or "Ollama"
        ).strip()
        return content, actual_model, provider

    async def answer(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        limit = requested_issue_limit(query)
        snapshot, coverage_errors, recovery_attempted = await self._snapshot()
        states_available = int(snapshot.get("states_read") or 0) > 0
        rows = self._issue_rows(snapshot, limit) if states_available else []
        deterministic = (
            self._deterministic_message(rows, limit)
            if states_available
            else "Current device states could not be verified, so HomeBrain cannot rank home issues safely."
        )

        message = deterministic
        model: str | None = None
        provider: str | None = None
        ai_error: str | None = None
        synthesis_started = time.perf_counter()
        if self.ai_enabled and states_available and rows:
            try:
                message, model, provider = await asyncio.wait_for(
                    self._ai_message(
                        query=query,
                        snapshot=snapshot,
                        rows=rows,
                        deterministic=deterministic,
                        limit=limit,
                    ),
                    timeout=self.ai_timeout_seconds + 1.0,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                ai_error = str(exc).strip() or type(exc).__name__
        synthesis_ms = round((time.perf_counter() - synthesis_started) * 1000)

        subtitle = self.snapshot_service._truthful_subtitle(
            snapshot,
            coverage_errors,
            states_available=states_available,
        )
        note = self.snapshot_service._truthful_coverage_note(
            snapshot,
            coverage_errors,
            states_available=states_available,
            recovery_attempted=recovery_attempted,
        )
        display_items = [
            {
                key: value
                for key, value in {**item, "group": "Priorities"}.items()
                if key not in {"priority", "room"} and value is not None
            }
            for item in rows
        ]
        display = display_payload(
            "home-priority-insight",
            "Home priorities",
            subtitle=subtitle,
            metrics=[
                {"label": "Confirmed issues", "value": str(len(rows)), "icon": "⚠️"},
                {"label": "Requested", "value": str(limit), "icon": "🔢"},
                {
                    "label": "States read",
                    "value": f"{snapshot.get('states_read', 0)}/{snapshot.get('selected_devices', 0)}",
                    "icon": "📡",
                },
            ],
            items=display_items,
            note=note,
        )
        display["summary"] = message

        elapsed = round((time.perf_counter() - started) * 1000)
        answer = {
            "success": states_available,
            "route": "ollama+home-insight" if model else "mcp-home-insight",
            "intent": "home-priority-insight",
            "message": message,
            "model": model,
            "ai_provider": provider,
            "display": display,
            "snapshot": snapshot,
            "confirmed_issues": rows,
            "requested_issue_count": limit,
            "coverage_complete": states_available and not coverage_errors,
            "coverage_errors": coverage_errors,
            "state_recovery_attempted": recovery_attempted,
            "synthesis_error": ai_error,
            "phase_ms": {
                "snapshot_and_hub": max(0, elapsed - synthesis_ms),
                "synthesis": synthesis_ms,
            },
            "elapsed_ms": elapsed,
            "answered_by": (
                "Direct/Hybrid Ollama wording + deterministic Hubitat home snapshot"
                if model
                else "Deterministic Hubitat home snapshot"
            ),
            "technical": safe_debug(
                {
                    "query": query,
                    "requested_issue_count": limit,
                    "confirmed_issues": rows,
                    "coverage_errors": coverage_errors,
                    "state_recovery_attempted": recovery_attempted,
                    "ollama_synthesis_error": ai_error,
                    "model": model,
                    "ai_provider": provider,
                }
            ),
        }
        if not model:
            answer.pop("model", None)
            answer.pop("ai_provider", None)
        return answer


def install_home_priority_insight(
    application: Any,
    snapshot_service: Any,
    *,
    ai_enabled: bool = True,
    ai_timeout_seconds: float = 20.0,
) -> WholeHomePriorityInsight:
    original_ask: AskHandler = application.ask
    service = WholeHomePriorityInsight(
        application,
        snapshot_service,
        ai_enabled=ai_enabled,
        ai_timeout_seconds=ai_timeout_seconds,
    )

    async def ask_with_home_priority(request: Any) -> dict[str, Any]:
        query = str(request.query or "").strip()
        if service.matches(query):
            answer = await service.answer(query)
            answer.setdefault("version", application.VERSION)
            return answer
        return await original_ask(request)

    application.ask = ask_with_home_priority
    application.home_priority_insight = service
    return service


__all__ = [
    "WholeHomePriorityInsight",
    "install_home_priority_insight",
    "is_home_priority_query",
    "requested_issue_limit",
]
