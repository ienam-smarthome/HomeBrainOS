from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from control_agent_graph import GraphContext


@dataclass(slots=True)
class ControlSessionContext:
    session_id: str
    last_device_ids: tuple[str, ...] = ()
    last_candidate_ids: tuple[str, ...] = ()
    last_room: str = ""
    last_device_type: str = ""
    last_action: str = ""
    updated_at: float = 0.0
    expires_at: float = 0.0

    def graph_context(self) -> GraphContext:
        return GraphContext(
            last_device_ids=self.last_device_ids,
            last_candidate_ids=self.last_candidate_ids,
            last_room=self.last_room,
            last_device_type=self.last_device_type,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "last_device_ids": list(self.last_device_ids),
            "last_candidate_ids": list(self.last_candidate_ids),
            "last_room": self.last_room,
            "last_device_type": self.last_device_type,
            "last_action": self.last_action,
        }


class ControlContextStore:
    def __init__(self, *, ttl_seconds: float = 600.0, max_sessions: int = 128) -> None:
        self.ttl_seconds = max(60.0, min(3600.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self._items: dict[str, ControlSessionContext] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def session_id(request: Any) -> str:
        value = str(getattr(request, "session_id", "") or "default").strip()
        return value[:160] or "default"

    async def get(self, session_id: str) -> ControlSessionContext:
        key = str(session_id or "default")[:160]
        async with self._lock:
            self._purge_locked()
            current = self._items.get(key)
            if current is not None:
                return current
            return ControlSessionContext(session_id=key)

    async def record_candidates(self, session_id: str, candidate_ids: list[str]) -> None:
        key = str(session_id or "default")[:160]
        now = time.time()
        async with self._lock:
            self._purge_locked()
            current = self._items.get(key) or ControlSessionContext(session_id=key)
            current.last_candidate_ids = tuple(dict.fromkeys(str(item) for item in candidate_ids if item))
            current.updated_at = now
            current.expires_at = now + self.ttl_seconds
            self._put_locked(current)

    async def record_success(
        self,
        session_id: str,
        *,
        device_ids: list[str],
        candidate_ids: list[str],
        room: str,
        device_type: str,
        action: str,
    ) -> None:
        key = str(session_id or "default")[:160]
        now = time.time()
        async with self._lock:
            self._purge_locked()
            current = self._items.get(key) or ControlSessionContext(session_id=key)
            current.last_device_ids = tuple(dict.fromkeys(str(item) for item in device_ids if item))
            current.last_candidate_ids = tuple(
                dict.fromkeys(str(item) for item in (candidate_ids or device_ids) if item)
            )
            current.last_room = str(room or "")[:100]
            current.last_device_type = str(device_type or "")[:50]
            current.last_action = str(action or "")[:30]
            current.updated_at = now
            current.expires_at = now + self.ttl_seconds
            self._put_locked(current)

    async def clear(self, session_id: str) -> bool:
        key = str(session_id or "default")[:160]
        async with self._lock:
            return self._items.pop(key, None) is not None

    def _put_locked(self, value: ControlSessionContext) -> None:
        if len(self._items) >= self.max_sessions and value.session_id not in self._items:
            oldest = min(self._items.values(), key=lambda item: item.updated_at)
            self._items.pop(oldest.session_id, None)
        self._items[value.session_id] = value

    def _purge_locked(self) -> None:
        now = time.time()
        for key in [key for key, value in self._items.items() if value.expires_at and value.expires_at <= now]:
            self._items.pop(key, None)


@dataclass(slots=True)
class PendingControl:
    session_id: str
    kind: str
    plan: Any = None
    action_index: int | None = None
    candidate_ids: tuple[str, ...] = ()
    created_at: float = 0.0
    expires_at: float = 0.0


class PendingControlStore:
    def __init__(self, *, ttl_seconds: float = 120.0, max_sessions: int = 128) -> None:
        self.ttl_seconds = max(30.0, min(600.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(1000, int(max_sessions)))
        self._items: dict[str, PendingControl] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> PendingControl | None:
        key = str(session_id or "default")[:160]
        async with self._lock:
            self._purge_locked()
            return self._items.get(key)

    async def put(
        self,
        session_id: str,
        *,
        kind: str,
        plan: Any = None,
        action_index: int | None = None,
        candidate_ids: list[str] | tuple[str, ...] = (),
    ) -> PendingControl:
        key = str(session_id or "default")[:160]
        now = time.time()
        value = PendingControl(
            session_id=key,
            kind=kind,
            plan=plan,
            action_index=action_index,
            candidate_ids=tuple(dict.fromkeys(str(item) for item in candidate_ids if item)),
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        async with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_sessions and key not in self._items:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.session_id, None)
            self._items[key] = value
        return value

    async def clear(self, session_id: str) -> bool:
        key = str(session_id or "default")[:160]
        async with self._lock:
            return self._items.pop(key, None) is not None

    def _purge_locked(self) -> None:
        now = time.time()
        for key in [key for key, value in self._items.items() if value.expires_at <= now]:
            self._items.pop(key, None)


class LearnedAliasStore:
    """Small explicit alias store persisted in the add-on data directory."""

    def __init__(self, path: str = "/data/control_agent_aliases.json") -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self._aliases: dict[str, str] | None = None

    async def all(self) -> dict[str, str]:
        async with self._lock:
            self._load_locked()
            return dict(self._aliases or {})

    async def add(self, alias: str, device_label: str) -> None:
        clean_alias = " ".join(str(alias or "").strip().split())[:100]
        clean_label = " ".join(str(device_label or "").strip().split())[:140]
        if len(clean_alias) < 2 or not clean_label:
            raise ValueError("Alias and device label are required")
        async with self._lock:
            self._load_locked()
            assert self._aliases is not None
            self._aliases[clean_alias] = clean_label
            self._save_locked()

    async def remove(self, alias: str) -> bool:
        target = " ".join(str(alias or "").strip().split())
        async with self._lock:
            self._load_locked()
            assert self._aliases is not None
            key = next((item for item in self._aliases if item.lower() == target.lower()), None)
            if key is None:
                return False
            self._aliases.pop(key, None)
            self._save_locked()
            return True

    def _load_locked(self) -> None:
        if self._aliases is not None:
            return
        try:
            decoded = json.loads(self.path.read_text(encoding="utf-8"))
            self._aliases = {
                str(key): str(value)
                for key, value in decoded.items()
                if str(key).strip() and str(value).strip()
            } if isinstance(decoded, dict) else {}
        except FileNotFoundError:
            self._aliases = {}
        except Exception:
            self._aliases = {}

    def _save_locked(self) -> None:
        assert self._aliases is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._aliases, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


__all__ = [
    "ControlContextStore",
    "ControlSessionContext",
    "LearnedAliasStore",
    "PendingControl",
    "PendingControlStore",
]
