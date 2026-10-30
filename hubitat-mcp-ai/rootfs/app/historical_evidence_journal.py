"""Opt-in persistent Hubitat live-event journal.

Hubitat /eventsocket and /logsocket are unofficial read-only streams. This
collector never assumes an uninterrupted event history: reception time is
explicitly distinguished from hub event time and every connection gap is
recorded. No device/app commands, polling or backfilling are performed.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from skill_secret_guard import redact_secrets

logger = logging.getLogger(__name__)

EVENT_NAMES = frozenset({
    "switch", "motion", "presence", "occupancy", "level", "mode",
    "pushed", "held", "released", "doubletapped", "double_tapped",
})
MAX_FRAME_BYTES = 65536
MAX_ROWS_PER_QUERY = 200
SENSITIVE = re.compile(
    r"(?i)\b(password|token|secret|api[_-]?key|authorization|bearer)\b"
    r"(\s*[:=]\s*|\s+)([^\s,;]+)"
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _aware_iso(raw: Any) -> str | None:
    try:
        value = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds") if value.tzinfo else None
    except (ValueError, TypeError):
        return None


def _hub_base_url(raw: str) -> str:
    """Reject credentials, arbitrary URL paths and Internet-facing endpoints."""
    parsed = urlsplit(raw.strip())
    if (parsed.scheme not in {"http", "https", "ws", "wss"}
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Set a local Hubitat URL without a path, query or credentials")
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        host = parsed.hostname.casefold()
        if not (host.endswith(".local") or "." not in host):
            raise ValueError("Journal requires a LAN Hubitat IP or local hostname")
    else:
        if not (ip.is_private or ip.is_loopback):
            raise ValueError("Journal refuses non-private Hubitat addresses")
    protocol = "wss" if parsed.scheme in {"https", "wss"} else "ws"
    port = f":{parsed.port}" if parsed.port else ""
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"{protocol}://{host}{port}"


def _limited(value: Any, length: int) -> str:
    return str(value if value is not None else "")[:length]


class HistoricalEvidenceJournal:
    def __init__(
        self, *, enabled: bool = False, hub_url: str = "",
        path: Path | str = "/data/homebrain-evidence-journal.sqlite3",
        retention_days: int = 30, max_rows: int = 100000,
        capture_logs: bool = False, log_app_ids: str = "",
        log_retention_hours: int = 48, log_max_rows: int = 100000,
    ) -> None:
        self.enabled = bool(enabled)
        self.path = Path(path)
        self.retention_days = max(1, min(365, int(retention_days)))
        self.max_rows = max(1000, min(500000, int(max_rows)))
        self.capture_logs = bool(capture_logs)
        self.log_retention_hours = max(1, min(720, int(log_retention_hours)))
        self.log_max_rows = max(1000, min(500000, int(log_max_rows)))
        self.log_app_ids = frozenset(
            part.strip() for part in str(log_app_ids).split(",")
            if part.strip().isdigit() or part.strip() == "*"
        )
        self.base_url = ""
        self.error: str | None = None
        if self.enabled:
            try:
                self.base_url = _hub_base_url(hub_url)
            except (ValueError, OverflowError) as exc:
                self.error = str(exc)
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
        self._tasks: list[asyncio.Task] = []
        self._connected = {"events": False, "logs": False}
        self._last_received: dict[str, str | None] = {"events": None, "logs": None}
        self._dropped = 0
        self._recorded = 0
        self._started = False

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS journal_events (
                id INTEGER PRIMARY KEY,
                stream TEXT NOT NULL,
                device_id TEXT NOT NULL DEFAULT '',
                app_id TEXT NOT NULL DEFAULT '',
                attribute TEXT NOT NULL,
                value TEXT NOT NULL,
                display_name TEXT NOT NULL,
                source TEXT NOT NULL,
                source_time TEXT NOT NULL DEFAULT '',
                observed_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                timestamp_basis TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                signature TEXT NOT NULL UNIQUE
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS journal_event_lookup
                ON journal_events(device_id, attribute, observed_at)""")
            db.execute("""CREATE INDEX IF NOT EXISTS journal_event_window
                ON journal_events(observed_at)""")
            db.execute("""CREATE TABLE IF NOT EXISTS journal_gaps (
                id INTEGER PRIMARY KEY,
                stream TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                reason TEXT NOT NULL
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS journal_gap_lookup
                ON journal_gaps(stream, started_at, ended_at)""")
            self._prune(db)

    def _prune(self, db: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(days=self.retention_days)).isoformat(timespec="microseconds")
        db.execute("DELETE FROM journal_events WHERE received_at < ?", (cutoff,))
        log_cutoff = (datetime.now(timezone.utc) -
                      timedelta(hours=self.log_retention_hours)).isoformat(timespec="microseconds")
        # Independent time and row caps: noisy app logs cannot evict device
        # switch history. Prune old log rows even if log capture is disabled
        # after an upgrade or setting change.
        db.execute("DELETE FROM journal_events WHERE stream='logs' AND received_at < ?",
                   (log_cutoff,))
        for stream, limit in (("events", self.max_rows), ("logs", self.log_max_rows)):
            db.execute("""DELETE FROM journal_events WHERE id IN (
                SELECT id FROM journal_events WHERE stream=? ORDER BY received_at DESC
                LIMIT -1 OFFSET ?)""", (stream, limit))
        db.execute("DELETE FROM journal_gaps WHERE ended_at IS NOT NULL AND ended_at < ?", (cutoff,))

    def _mark_disconnected(self, stream: str, reason: str) -> None:
        with self._connect() as db:
            exists = db.execute(
                "SELECT 1 FROM journal_gaps WHERE stream=? AND ended_at IS NULL LIMIT 1",
                (stream,),
            ).fetchone()
            if not exists:
                db.execute(
                    "INSERT INTO journal_gaps (stream,started_at,reason) VALUES (?,?,?)",
                    (stream, utcnow(), reason[:120]),
                )

    def _mark_connected(self, stream: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE journal_gaps SET ended_at=? WHERE stream=? AND ended_at IS NULL",
                (utcnow(), stream),
            )

    @staticmethod
    def _row(stream: str, packet: Any, received_at: str, app_ids: frozenset[str]) -> dict[str, Any] | None:
        if not isinstance(packet, dict):
            return None
        if stream == "events":
            attribute = _limited(packet.get("name"), 64).lower()
            if attribute not in EVENT_NAMES:
                return None
            device_id = _limited(packet.get("deviceId"), 40)
            source = _limited(packet.get("source"), 40)
            if not device_id and not (attribute == "mode" and source.upper() == "LOCATION"):
                return None
            observed = _aware_iso(packet.get("date") or packet.get("timestamp"))
            return {
                "stream": stream, "device_id": device_id, "app_id": "",
                "attribute": attribute, "value": _limited(packet.get("value"), 128),
                "display_name": _limited(packet.get("displayName"), 128),
                "source": source,
                "source_time": _limited(packet.get("date") or packet.get("timestamp"), 64),
                "observed_at": observed or received_at, "received_at": received_at,
                "timestamp_basis": "source" if observed else "collector-received",
                "message": "",
            }
        if stream == "logs":
            if _limited(packet.get("type"), 12).lower() != "app":
                return None
            app_id = _limited(packet.get("id"), 40)
            if not app_id.isdecimal() or ("*" not in app_ids and app_id not in app_ids):
                return None
            # Redact *before storage*, including JSON keys, query parameters,
            # bearer tokens and ordinary key=value sequences.
            message = redact_secrets(_limited(packet.get("msg"), 512))
            message = SENSITIVE.sub(lambda match: match.group(1) + "=REDACTED", message)
            return {
                "stream": stream, "device_id": "", "app_id": app_id,
                "attribute": _limited(packet.get("level"), 24).lower(),
                "value": "", "display_name": _limited(packet.get("name"), 128),
                "source": "hubitat-logsocket",
                "source_time": _limited(packet.get("time"), 64),
                "observed_at": received_at, "received_at": received_at,
                "timestamp_basis": "collector-received", "message": message,
            }
        return None

    def _write_batch(self, rows: list[dict[str, Any]], prune: bool = False) -> int:
        with self._connect() as db:
            inserted = 0
            for row in rows:
                packed = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                # A genuine source timestamp supports stable reconnect de-duplication.
                # Frames without one can represent repeated real events, so
                # keep collector-receive time in their signatures.
                identity = dict(row)
                if row["source_time"]:
                    identity.pop("received_at", None)
                    identity.pop("observed_at", None) if row["timestamp_basis"] == "collector-received" else None
                stable = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                signature = hashlib.sha256(stable.encode("utf-8")).hexdigest()
                cursor = db.execute("""INSERT OR IGNORE INTO journal_events
                    (stream,device_id,app_id,attribute,value,display_name,source,
                     source_time,observed_at,received_at,timestamp_basis,message,signature)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["stream"], row["device_id"], row["app_id"],
                     row["attribute"], row["value"], row["display_name"], row["source"],
                     row["source_time"], row["observed_at"], row["received_at"],
                     row["timestamp_basis"], row["message"], signature),
                )
                inserted += max(0, cursor.rowcount)
            if prune:
                self._prune(db)
            return inserted

    async def _writer(self) -> None:
        tick = 0
        while True:
            batch = [await self._queue.get()]
            while len(batch) < 100:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            try:
                tick += 1
                self._recorded += await asyncio.to_thread(
                    self._write_batch, batch, tick % 10 == 0
                )
            except Exception as exc:
                self.error = f"Journal storage unavailable: {type(exc).__name__}"
                logger.warning("Historical journal write failed: %s", exc)
                self._dropped += len(batch)
            finally:
                for _ in batch:
                    self._queue.task_done()

    async def ingest(self, stream: str, packet: Any) -> bool:
        """Accept a single parsed socket message; never infer missing events."""
        row = self._row(stream, packet, utcnow(), self.log_app_ids)
        if row is None:
            return False
        try:
            self._queue.put_nowait(row)
        except asyncio.QueueFull:
            self._dropped += 1
            self.error = "Journal queue overflow; coverage has gaps"
            await asyncio.to_thread(self._mark_disconnected, stream, "queue-overflow")
            return False
        self._last_received[stream] = row["received_at"]
        return True

    async def ingest_native_history(self, device_id: str, payload: Any) -> int:
        """Preserve safe, source-timestamped historical rows seen in MCP reads.

        The websocket stream may not expose command invocation metadata.
        Opportunistic read-through retains only approved switch states and
        command-on/off/setLevel observations from a *successful* native device
        history request. A reported command is never recorded as a physical
        state transition. No backfill is claimed beyond the returned page.
        """
        if not self.enabled or not self._started or not str(device_id).isdigit():
            return 0
        value = payload
        for _ in range(3):
            if isinstance(value, dict) and any(
                isinstance(value.get(key), list)
                for key in (
                    "events", "commandEvents", "boundaryEvents",
                    "correlationEvents", "observedEvents", "windowEvents",
                )
            ):
                break
            if isinstance(value, dict):
                value = value.get("result") or value.get("data") or {}
        if not isinstance(value, dict):
            return 0
        # DeviceHistoryService returns a source-typed combination of direct
        # events, commandEvents, boundaryEvents and correlationEvents. Each
        # projection may overlap; persist unique source observations only.
        events: list[dict[str, Any]] = []
        for key in (
            "events", "commandEvents", "boundaryEvents", "correlationEvents",
            "observedEvents", "windowEvents",
        ):
            values = value.get(key)
            if isinstance(values, list):
                events.extend(item for item in values if isinstance(item, dict))
        if not events:
            return 0
        accepted = 0
        seen: set[tuple[str, str, str, str]] = set()
        for event in events[:400]:
            if not isinstance(event, dict):
                continue
            name = str(event.get("name") or "").strip()
            if name not in {"switch", "command-on", "command-off", "command-setLevel"}:
                continue
            timestamp = _aware_iso(event.get("date"))
            if not timestamp:
                continue
            source = event.get("producedBy") or {}
            if not isinstance(source, dict):
                source = {}
            if name.startswith("command-"):
                if source.get("type") != "app" or not str(source.get("id") or "").isdigit():
                    continue
                origin = "hubitat-mcp-command:app:" + _limited(source.get("id"), 18)
                label = _limited(source.get("label"), 128)
                state = ""
            else:
                origin = "hubitat-mcp-state"
                label = ""
                state = str(event.get("value") or "").lower()
                if state not in {"on", "off"}:
                    continue
            identity = (
                name, timestamp, state, origin,
            )
            if identity in seen:
                continue
            seen.add(identity)
            row = {
                "stream": "events", "device_id": str(device_id),
                "app_id": "", "attribute": name, "value": state,
                "display_name": label, "source": origin,
                "source_time": timestamp, "observed_at": timestamp,
                "received_at": utcnow(), "timestamp_basis": "source",
                "message": "",
            }
            try:
                self._queue.put_nowait(row)
                accepted += 1
            except asyncio.QueueFull:
                self._dropped += 1
                self.error = "Journal queue overflow; coverage has gaps"
                await asyncio.to_thread(self._mark_disconnected, "events", "queue-overflow")
                break
        return accepted

    async def _stream(self, stream: str) -> None:
        path = "/eventsocket" if stream == "events" else "/logsocket"
        delay = 2
        await asyncio.to_thread(self._mark_disconnected, stream, "collector-start")
        while True:
            try:
                async with connect(
                    self.base_url + path, open_timeout=8, close_timeout=5,
                    ping_interval=20, ping_timeout=20, max_size=MAX_FRAME_BYTES,
                ) as socket:
                    await asyncio.to_thread(self._mark_connected, stream)
                    self._connected[stream] = True
                    # A recovered transport error must not keep the mobile
                    # status panel in "Attention" forever. Never clear
                    # storage or queue-overflow errors on socket recovery.
                    streams_ready = self._connected["events"] and (
                        not self.capture_logs or not self.log_app_ids
                        or self._connected["logs"]
                    )
                    if (
                        streams_ready and isinstance(self.error, str)
                        and self.error.startswith((
                            "events stream disconnected:",
                            "logs stream disconnected:",
                        ))
                    ):
                        self.error = None
                    delay = 2
                    async for frame in socket:
                        try:
                            packet = json.loads(frame)
                        except (ValueError, TypeError):
                            continue
                        await self.ingest(stream, packet)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = f"{stream} stream disconnected: {type(exc).__name__}"
                logger.warning("Historical journal %s socket: %s", stream, type(exc).__name__)
            finally:
                self._connected[stream] = False
                await asyncio.to_thread(self._mark_disconnected, stream, "socket-disconnected")
            await asyncio.sleep(delay)
            delay = min(60, delay * 2)

    async def start(self) -> None:
        if self._started or not self.enabled or self.error:
            return
        try:
            await asyncio.to_thread(self._initialize)
        except Exception as exc:
            self.error = f"Could not initialize journal storage: {type(exc).__name__}"
            return
        self._started = True
        self._tasks = [asyncio.create_task(self._writer(), name="journal-writer")]
        self._tasks.append(asyncio.create_task(self._stream("events"), name="journal-events"))
        if self.capture_logs and self.log_app_ids:
            self._tasks.append(asyncio.create_task(self._stream("logs"), name="journal-logs"))

    async def close(self) -> None:
        for task in self._tasks[1:]:
            task.cancel()
        for task in self._tasks[1:]:
            with suppress(asyncio.CancelledError):
                await task
        if self._tasks:
            await self._queue.join()
            self._tasks[0].cancel()
            with suppress(asyncio.CancelledError):
                await self._tasks[0]
        self._tasks.clear()
        self._started = False

    def status(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "enabled": self.enabled, "started": self._started,
            "connected": dict(self._connected),
            "last_received": dict(self._last_received),
            "queued": self._queue.qsize(), "recorded_this_run": self._recorded,
            "dropped_this_run": self._dropped,
            "retention_days": self.retention_days, "max_rows": self.max_rows,
            "log_retention_hours": self.log_retention_hours,
            "log_max_rows": self.log_max_rows,
            "capture_all_app_logs": self.capture_logs and "*" in self.log_app_ids,
            "capture_logs": self.capture_logs and bool(self.log_app_ids),
            "tracked_app_ids": sorted(self.log_app_ids) if self.capture_logs else [],
            "coverage_complete": False, "error": self.error,
        }
        if self._started:
            try:
                with self._connect() as db:
                    count, first, last = db.execute(
                        "SELECT COUNT(*), MIN(received_at), MAX(received_at) FROM journal_events"
                    ).fetchone()
                    counts = dict(db.execute(
                        "SELECT stream, COUNT(*) FROM journal_events GROUP BY stream"
                    ).fetchall())
                    last_event_received = db.execute(
                        "SELECT MAX(received_at) FROM journal_events "
                        "WHERE stream='events'"
                    ).fetchone()[0]
                    app_counts = dict(db.execute(
                        "SELECT app_id, COUNT(*) FROM journal_events "
                        "WHERE stream='logs' GROUP BY app_id"
                    ).fetchall())
                    gaps = db.execute("SELECT COUNT(*) FROM journal_gaps").fetchone()[0]
                    open_gaps = db.execute(
                        "SELECT COUNT(*) FROM journal_gaps WHERE ended_at IS NULL"
                    ).fetchone()[0]
                    last_gaps = db.execute(
                        "SELECT stream, started_at, ended_at, reason "
                        "FROM journal_gaps ORDER BY id DESC LIMIT 5"
                    ).fetchall()
                bytes_used = sum(
                    candidate.stat().st_size
                    for candidate in (
                        self.path, Path(str(self.path) + "-wal"),
                        Path(str(self.path) + "-shm")
                    ) if candidate.exists()
                )
                snapshot.update(
                    rows=count, first_received=first, last_retained=last,
                    event_rows=int(counts.get("events", 0)),
                    app_log_rows=int(counts.get("logs", 0)),
                    last_persisted_device_event=last_event_received,
                    captured_app_log_counts=(
                        {"*": sum(app_counts.values())}
                        if "*" in self.log_app_ids
                        else {app_id: int(app_counts.get(app_id, 0))
                              for app_id in sorted(self.log_app_ids)}
                    ) if self.capture_logs else {},
                    db_bytes=bytes_used, gaps=gaps, open_gaps=open_gaps,
                    recent_gaps=[
                        dict(zip(("stream", "started_at", "ended_at", "reason"), row))
                        for row in last_gaps
                    ],
                )
            except (sqlite3.Error, OSError):
                snapshot["storage_unavailable"] = True
        return snapshot

    def recent_events(self, limit: int = 12) -> dict[str, Any]:
        """Read-only dashboard sample: device events only, no app-log text.

        Never imply that these recent rows cover a continuous time window.
        """
        if not self.enabled or not self._started:
            return {"events": [], "coverage_complete": False, "unavailable": True}
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT device_id,attribute,value,display_name,source,"
                "observed_at,received_at,timestamp_basis "
                "FROM journal_events WHERE stream='events' "
                "ORDER BY id DESC LIMIT ?",
                (max(1, min(20, int(limit))),),
            )
            events = [dict(row) for row in rows]
        return {
            "events": events,
            "count": len(events),
            "coverage_complete": False,
            "empty_means_inactivity": False,
        }

    def query(
        self, *, since: str, until: str,
        device_id: str = "", attribute: str = "", app_id: str = "",
        limit: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        start, end = _aware_iso(since), _aware_iso(until)
        if not start or not end or start >= end:
            raise ValueError("since and until must be ordered offset-aware ISO timestamps")
        if (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days > 31:
            raise ValueError("Journal query window cannot exceed 31 days")
        if not (device_id or app_id):
            raise ValueError("An exact device_id or app_id is required")
        if not isinstance(offset, int) or not 0 <= offset <= self.max_rows:
            raise ValueError("Journal offset is out of bounds")
        clauses = ["observed_at>=?", "observed_at<=?"]
        params: list[Any] = [start, end]
        for col, val in (("device_id", device_id), ("app_id", app_id), ("attribute", attribute)):
            if val:
                clauses.append(col + "=?")
                params.append(val)
        sql = ("SELECT stream,device_id,app_id,attribute,value,display_name,source,"
               "source_time,observed_at,received_at,timestamp_basis,message "
               "FROM journal_events WHERE " + " AND ".join(clauses)
               + " ORDER BY observed_at ASC, id ASC LIMIT ? OFFSET ?")
        requested_limit = max(1, min(MAX_ROWS_PER_QUERY, int(limit)))
        # Fetch one extra row to expose result-window truncation.
        params.extend((requested_limit + 1, offset))
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            fetched = [dict(row) for row in db.execute(sql, params)]
            truncated = len(fetched) > requested_limit
            events = fetched[:requested_limit]
            gaps = [dict(zip(("stream", "started_at", "ended_at", "reason"), row))
                    for row in db.execute(
                        "SELECT stream,started_at,ended_at,reason FROM journal_gaps "
                        "WHERE started_at<=? AND (ended_at IS NULL OR ended_at>=?) "
                        "ORDER BY started_at DESC LIMIT 100", (end, start))]
        return {
            "events": events, "count": len(events), "gaps": gaps,
            "truncated": truncated, "has_more": truncated,
            "limit": requested_limit, "offset": offset,
            "next_offset": offset + len(events) if truncated else None,
            "coverage_complete": False,
            "empty_means_inactivity": False,
            "timestamps": "source time if timezone-aware, otherwise collector reception time",
        }
