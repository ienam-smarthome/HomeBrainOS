"""Opt-in, external, read-only Hubitat resource and outage recorder.

Runs in HomeBrainOS (Home Assistant add-on), never on the Hubitat JVM.
The live OS-memory endpoint is sampled at a bounded cadence; the native
Java/CPU CSV is only requested every five minutes. Samples and connection
losses survive Hubitat reboots in the add-on's /data SQLite store.

This is evidence collection, NOT heap/Metaspace diagnosis or reboot control.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from urllib.parse import urlsplit

import httpx


_MEMORY_CSV = "/hub/advanced/freeOSMemoryLast"
_LIVE_MEMORY = "/hub/advanced/freeOSMemory"
_RFC1918 = tuple(ipaddress.ip_network(net) for net in
                 ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
_NUMBER = re.compile(r"^\s*[0-9]+(?:\.[0-9]+)?\s*$")


def validate_hub_url(value: str) -> str:
    """Only literal RFC1918 IPv4, no credentials, paths, redirects or DNS."""
    parts = urlsplit(str(value).strip())
    if (parts.scheme != "http" or not parts.hostname or
            parts.username or parts.password or parts.path not in ("", "/")
            or parts.query or parts.fragment):
        raise ValueError("Use an HTTP LAN Hubitat IPv4 URL without credentials or path")
    try:
        host = ipaddress.IPv4Address(parts.hostname)
        port = parts.port
    except (ValueError, TypeError) as exc:
        raise ValueError("Use a private IPv4 address for the hub") from exc
    if not any(host in block for block in _RFC1918) or port not in (None, 80, 8080):
        raise ValueError("Only local RFC1918 Hubitat addresses on port 80/8080 are allowed")
    return "http://" + str(host) + ((":" + str(port)) if port else "")


def parse_live_memory(value: str) -> float:
    """The live Free OS endpoint reports KiB."""
    raw = str(value).strip()
    if not _NUMBER.fullmatch(raw):
        raise ValueError("Live memory response is not a KiB number")
    kib = float(raw)
    if not 0 <= kib <= 64 * 1024 * 1024:
        raise ValueError("Live memory response is outside plausible bounds")
    return round(kib / 1024.0, 2)


def parse_native_sample(value: str) -> dict[str, Any]:
    """Parse one actual Hubitat five-minute sample; never synthesize its timestamp."""
    rows = [line.strip() for line in str(value).splitlines() if line.strip()]
    if not rows:
        raise ValueError("Native five-minute data is empty")
    cells = [part.strip() for part in rows[-1].split(",")]
    if len(cells) < 5:
        raise ValueError("Missing columns in five-minute memory row")
    try:
        free_os, load, total, free = (float(cells[i]) for i in (1, 2, 3, 4))
        direct = float(cells[5]) if len(cells) > 5 else None
    except (ValueError, IndexError) as exc:
        raise ValueError("Non-numeric five-minute memory row") from exc
    if any(not (0 <= n <= 64 * 1024 * 1024) for n in (free_os, total, free)):
        raise ValueError("Invalid native memory sample")
    if total <= 0 or free > total or not 0 <= load <= 1000:
        raise ValueError("Invalid native heap/load sample")
    if direct is not None and not 0 <= direct <= 64 * 1024 * 1024:
        direct = None
    return {
        "native_sample_label": cells[0][:48],
        "native_load5": round(load, 3),
        "native_free_os_mb": round(free_os / 1024, 2),
        "java_total_mb": round(total / 1024, 2),
        "java_free_mb": round(free / 1024, 2),
        "java_direct_mb": round(direct / 1024, 2) if direct is not None else None,
        "java_allocated_heap_used_pct": round(100 * (total - free) / total, 1),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ExternalHubDiagnostics:
    def __init__(self, *, enabled: bool = False, hub_url: str = "",
                 path: str | Path = "/data/homebrain-hub-diagnostics.sqlite3",
                 probe_seconds: int = 30, retention_days: int = 30) -> None:
        self.enabled = bool(enabled)
        self.path = Path(path)
        self.probe_seconds = max(30, min(300, int(probe_seconds)))
        self.retention_days = max(1, min(90, int(retention_days)))
        self.hub_url = ""
        self.error: str | None = None
        if self.enabled:
            try:
                self.hub_url = validate_hub_url(hub_url)
            except ValueError as exc:
                self.error = str(exc)
        self._task: asyncio.Task | None = None
        self._last: dict[str, Any] | None = None
        self._failures = 0
        self._last_good: str | None = None
        self._pending_failure_start: str | None = None
        self._native: dict[str, Any] = {}
        self._native_last_attempt: float = -1e12

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS samples (
                recorded_at TEXT PRIMARY KEY, reachable INTEGER NOT NULL,
                latency_ms REAL, free_os_mb REAL, http_status INTEGER,
                error_kind TEXT, native_sample_label TEXT, native_load5 REAL,
                native_free_os_mb REAL, java_total_mb REAL, java_free_mb REAL,
                java_direct_mb REAL, java_allocated_heap_used_pct REAL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
                recovered_at TEXT, kind TEXT NOT NULL,
                detail TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS incident_by_start ON incidents(started_at)")
            last = db.execute("SELECT * FROM samples ORDER BY recorded_at DESC LIMIT 1").fetchone()
            if last is not None:
                self._last = dict(last)
                self._last_good = db.execute(
                    "SELECT MAX(recorded_at) FROM samples WHERE reachable=1"
                ).fetchone()[0]
            self._prune(db)

    def _prune(self, db: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(days=self.retention_days)).isoformat(timespec="milliseconds")
        db.execute("DELETE FROM samples WHERE recorded_at < ?", (cutoff,))
        db.execute(
            "DELETE FROM incidents WHERE recovered_at IS NOT NULL AND recovered_at < ?",
            (cutoff,),
        )

    def _save(self, row: dict[str, Any], opened: str | None, recovered: bool) -> None:
        fields = ("recorded_at", "reachable", "latency_ms", "free_os_mb", "http_status",
                  "error_kind", "native_sample_label", "native_load5", "native_free_os_mb",
                  "java_total_mb", "java_free_mb", "java_direct_mb",
                  "java_allocated_heap_used_pct")
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO samples (" + ",".join(fields) + ") VALUES (" +
                ",".join("?" for _ in fields) + ")",
                tuple(row.get(k) for k in fields),
            )
            if opened:
                existing = db.execute(
                    "SELECT id FROM incidents WHERE recovered_at IS NULL "
                    "AND kind='hub-unreachable' LIMIT 1"
                ).fetchone()
                if existing is None:
                    db.execute(
                        "INSERT INTO incidents (started_at, kind, detail) VALUES (?, ?, ?)",
                        (opened, "hub-unreachable", "Two consecutive external probe failures"),
                    )
            if recovered:
                db.execute(
                    "UPDATE incidents SET recovered_at=? WHERE recovered_at IS NULL "
                    "AND kind='hub-unreachable'",
                    (row["recorded_at"],),
                )
            if row["recorded_at"].endswith("00:00:00.000+00:00"):
                self._prune(db)

    async def _poll(self, client: httpx.AsyncClient) -> None:
        row: dict[str, Any] = {
            "recorded_at": utc_now(), "reachable": 0, "latency_ms": None,
            "free_os_mb": None, "http_status": None, "error_kind": None,
        }
        started = time.monotonic()
        try:
            response = await client.get(self.hub_url + _LIVE_MEMORY)
            row["latency_ms"] = round((time.monotonic() - started) * 1000, 1)
            row["http_status"] = response.status_code
            response.raise_for_status()
            row["free_os_mb"] = parse_live_memory(response.text)
            row["reachable"] = 1
        except httpx.TimeoutException:
            row["error_kind"] = "timeout"
        except httpx.ConnectError:
            row["error_kind"] = "connect_error"
        except httpx.HTTPStatusError:
            row["error_kind"] = "http_error"
        except (ValueError, httpx.RequestError):
            row["error_kind"] = "invalid_response_or_request"

        if row["reachable"]:
            self._failures = 0
            self._last_good = row["recorded_at"]
            recovered = self._pending_failure_start is not None
            self._pending_failure_start = None
            now = time.monotonic()
            if now - self._native_last_attempt >= 300:
                self._native_last_attempt = now
                try:
                    native_response = await client.get(self.hub_url + _MEMORY_CSV)
                    native_response.raise_for_status()
                    self._native = parse_native_sample(native_response.text)
                except (httpx.HTTPError, ValueError):
                    # Keep older Java figures with original native timestamp; never
                    # imply the previous Java sample has been refreshed.
                    pass
            row.update(self._native)
        else:
            self._failures += 1
            recovered = False
            if self._failures == 1:
                self._pending_failure_start = row["recorded_at"]
            # No cached memory values in an unreachable sample.
            row["native_sample_label"] = None
        opened = self._pending_failure_start if self._failures == 2 else None
        self._last = row
        await asyncio.to_thread(self._save, row, opened, recovered)

    async def _run(self) -> None:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(3.0), follow_redirects=False, trust_env=False,
        ) as client:
            while True:
                before = time.monotonic()
                try:
                    await self._poll(client)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.error = "Recorder storage or collection failed: " + type(exc).__name__
                await asyncio.sleep(max(1.0, self.probe_seconds - (time.monotonic() - before)))

    async def start(self) -> None:
        if not self.enabled or self.error or self._task:
            return
        try:
            await asyncio.to_thread(self._initialize)
        except (OSError, sqlite3.Error) as exc:
            self.error = "Cannot initialize recorder database: " + type(exc).__name__
            return
        self._task = asyncio.create_task(self._run(), name="external-hub-diagnostics")

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def status(self) -> dict[str, Any]:
        row = self._last or {}
        return {
            "enabled": self.enabled, "running": bool(self._task and not self._task.done()),
            "error": self.error, "probe_seconds": self.probe_seconds,
            "retention_days": self.retention_days, "last": dict(row),
            "last_good_at": self._last_good,
            "consecutive_failures": self._failures,
            "status": (
                "disabled" if not self.enabled else "error" if self.error else
                "waiting" if not row else
                "online" if row.get("reachable") else
                "offline" if self._failures >= 2 else "degraded"
            ),
            "limitations": (
                "Free OS memory is observed at probe time; Java/CPU are from "
                "Hubitat's separate native five-minute sample. No direct Metaspace metric."
            ),
        }

    def history(self, hours: int = 6) -> dict[str, Any]:
        if not self.enabled or not self.path.exists():
            return {"samples": [], "incidents": [], "coverage": "not_recorded"}
        window = max(1, min(24, int(hours)))
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(hours=window)).isoformat(timespec="milliseconds")
        with self._connect() as db:
            rows = [dict(v) for v in db.execute(
                "SELECT * FROM samples WHERE recorded_at>=? ORDER BY recorded_at ASC "
                "LIMIT 3000", (cutoff,),
            )]
            incidents = [dict(v) for v in db.execute(
                "SELECT * FROM incidents WHERE started_at>=? OR recovered_at>=? "
                "ORDER BY started_at DESC LIMIT 40", (cutoff, cutoff),
            )]
        return {
            "samples": rows, "incidents": incidents, "hours": window,
            "coverage": "partial_observations_not_proof_of_cause",
            "native_java_resolution_seconds": 300,
        }


__all__ = [
    "ExternalHubDiagnostics", "validate_hub_url",
    "parse_live_memory", "parse_native_sample",
]
