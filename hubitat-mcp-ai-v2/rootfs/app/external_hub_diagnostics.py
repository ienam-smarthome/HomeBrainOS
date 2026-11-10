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
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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



_NATIVE_LOCAL_LABEL = re.compile(
    r"^(?P<month>\d{1,2})[-/](?P<day>\d{1,2})[ T]"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})$"
)


def native_sample_time(label: str, collected_at: str, hub_timezone: str,
                       retention_days: int) -> str | None:
    """Resolve a native source timestamp, never pretend collection time is sample time.

    Hubitat's MM-DD HH:MM:SS CSV labels have no year or offset. The configured
    hub time zone supplies the offset; nearest non-future year supplies the
    year. Unresolvable, out-of-retention and nonexistent DST wall times are
    omitted, not plotted at the collector's receipt timestamp.
    """
    try:
        observed = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return None
        observed = observed.astimezone(timezone.utc)
        zone = ZoneInfo(hub_timezone)
        local = _NATIVE_LOCAL_LABEL.fullmatch(str(label).strip())
        if local:
            parts = {key: int(value) for key, value in local.groupdict().items()}
            candidates: list[datetime] = []
            for year in (observed.astimezone(zone).year - 1,
                         observed.astimezone(zone).year,
                         observed.astimezone(zone).year + 1):
                for fold in (0, 1):
                    try:
                        value = datetime(year, parts["month"], parts["day"],
                                         parts["hour"], parts["minute"],
                                         parts["second"], tzinfo=zone, fold=fold)
                        utc = value.astimezone(timezone.utc)
                        # Reject local times skipped by daylight-saving changes.
                        if utc.astimezone(zone).replace(tzinfo=None) != value.replace(tzinfo=None):
                            continue
                        candidates.append(utc)
                    except ValueError:
                        continue
            candidates = [t for t in candidates
                          if timedelta(seconds=-120) <= observed - t <=
                          timedelta(days=retention_days + 2)]
            if not candidates:
                return None
            source = max(candidates)
        else:
            source = datetime.fromisoformat(str(label).strip().replace("Z", "+00:00"))
            # An ISO timestamp without an explicit offset uses the configured hub zone.
            if source.tzinfo is None:
                source = source.replace(tzinfo=zone)
            source = source.astimezone(timezone.utc)
            if not timedelta(seconds=-120) <= observed - source <= timedelta(days=retention_days + 2):
                return None
        return source.isoformat(timespec="milliseconds")
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        return None


def parse_native_history(payload: str, *, collected_at: str,
                         hub_timezone: str, retention_days: int) -> tuple[dict[str, Any], ...]:
    """Parse all timestamped native CSV rows; dedupe by original Hubitat label."""
    samples: dict[str, dict[str, Any]] = {}
    # Bounded response processing; preserve all available rows within 90-day retention.
    for raw in str(payload).splitlines()[-30000:]:
        if not raw.strip():
            continue
        try:
            row = parse_native_sample(raw)
        except ValueError:
            continue  # Header and malformed records are not measurements.
        label = row["native_sample_label"]
        stamp = native_sample_time(label, collected_at, hub_timezone, retention_days)
        if stamp is None:
            continue
        samples[label] = {
            **row, "recorded_at": stamp, "collected_at": collected_at,
            "reachable": 1, "timestamp_basis": "native_label_hub_timezone",
        }
    return tuple(sorted(samples.values(), key=lambda row: row["recorded_at"]))


_HUB_EVENTS = "/hub/eventsJson"
_HISTORY_METRICS = frozenset((
    "free_os_mb", "java_free_mb", "java_allocated_heap_used_pct",
    "native_load_pct", "native_load5", "native_free_os_mb", "latency_ms",
))
_NATIVE_METRICS = frozenset((
    "java_free_mb", "java_allocated_heap_used_pct", "native_load_pct",
    "native_load5", "native_free_os_mb",
))


def parse_system_start_events(payload: str) -> list[dict[str, str]]:
    """Accept only Hubitat systemStart events with unambiguous source times.

    Source date must contain an explicit timezone offset; never assume the
    add-on's timezone is the same as the hub timezone.
    """
    if len(payload) > 1_000_000:
        raise ValueError("Hub event response too large")
    obj = json.loads(payload)
    source = obj if isinstance(obj, list) else (
        obj.get("events") if isinstance(obj, dict) else None
    )
    if not isinstance(source, list):
        raise ValueError("Unexpected Hubitat Hub Events response")
    found: dict[str, dict[str, str]] = {}
    for event in source[:1000]:
        if not isinstance(event, dict) or event.get("name") != "systemStart":
            continue
        try:
            stamp = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
        except (ValueError, TypeError, KeyError):
            continue
        if stamp.tzinfo is None:
            continue
        at = stamp.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if at.year < 2020 or at > now + timedelta(minutes=5):
            continue
        occurred_at = at.isoformat(timespec="milliseconds")
        value = str(event.get("value") or "")[:48]
        if any(c not in "0123456789.abcdeABCDE-_ " for c in value):
            value = ""
        found[occurred_at] = {
            "occurred_at": occurred_at, "firmware": value,
            "source": "hub_events_json_systemStart",
        }
    return sorted(found.values(), key=lambda entry: entry["occurred_at"])


def summarize_history_samples(
    rows: Iterable[dict[str, Any]], *, metric: str,
    start: datetime, finish: datetime, probe_seconds: int,
    bucket_count: int = 440, raw_limit: int = 3000,
) -> dict[str, Any]:
    """Stream local SQLite samples with bounded memory for 30-day charts.

    Preserve actual first/last/min/max observations per time bucket rather
    than averages that could erase short OS-memory dips. Retain boundaries
    around failed probes or long gaps so they cannot become solid lines.
    """
    if metric not in _HISTORY_METRICS:
        raise ValueError("Invalid diagnostic metric")
    native = metric in _NATIVE_METRICS
    gap_seconds = 900 if native else max(120, probe_seconds * 3)
    epoch_start = start.timestamp()
    span = max(1, finish.timestamp() - epoch_start)
    raw: list[dict[str, Any]] | None = []
    groups: dict[int, dict[str, Any]] = {}
    seen_native: set[str] = set()
    previous: tuple[float, dict[str, Any]] | None = None
    segment = 0
    unknown = False
    count = 0
    observed = 0
    for row in rows:
        count += 1
        # For native metrics, source measurement changes only when the
        # source's five-minute label changes. The intervening 30-second rows
        # repeat one cached reading and are not independent chart points.
        # Preserve every probe row (including outages) for non-native metrics.
        if raw is not None and not native:
            if len(raw) < raw_limit:
                raw.append(row)
            else:
                raw = None
        try:
            stamp = datetime.fromisoformat(str(row["recorded_at"])).timestamp()
        except (KeyError, TypeError, ValueError):
            unknown = True
            continue
        value = row.get(metric)
        if (not row.get("reachable") or isinstance(value, bool) or
                not isinstance(value, (int, float)) or
                not math.isfinite(float(value))):
            unknown = True
            continue
        if native:
            label = str(row.get("native_sample_label") or "")
            if not label:
                unknown = True
                continue
            if label in seen_native:
                continue
            seen_native.add(label)
            if raw is not None:
                if len(raw) < raw_limit:
                    raw.append(row)
                else:
                    raw = None
        if previous and (unknown or stamp - previous[0] > gap_seconds):
            segment += 1
        row["diag_segment"] = segment
        unknown = False
        previous_row = previous[1] if previous else None
        previous = (stamp, row)
        observed += 1
        bucket_id = min(bucket_count - 1,
                        max(0, int((stamp - epoch_start) / span * bucket_count)))
        bucket = groups.setdefault(bucket_id, {
            "first": row, "last": row, "min": row, "max": row,
            "edges": [],
        })
        if (previous_row is not None and
                previous_row["diag_segment"] != segment):
            # Keep the two real readings bordering a gap even when both are
            # in a bucket whose extrema occur elsewhere.
            bucket["edges"].append(previous_row)
            bucket["edges"].append(row)
        bucket["last"] = row
        if row[metric] < bucket["min"][metric]:
            bucket["min"] = row
        if row[metric] > bucket["max"][metric]:
            bucket["max"] = row
    if raw is not None:
        return {
            "samples": raw, "source_sample_count": count,
            "observed_metric_points": observed, "downsampled": False,
        }
    selected: dict[str, dict[str, Any]] = {}
    for bucket in groups.values():
        for sample in (bucket["first"], bucket["last"], bucket["min"],
                       bucket["max"], *bucket["edges"]):
            selected[sample["recorded_at"]] = sample
    return {
        "samples": [selected[key] for key in sorted(selected)],
        "source_sample_count": count,
        "observed_metric_points": observed,
        "downsampled": True,
    }

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ExternalHubDiagnostics:
    def __init__(self, *, enabled: bool = False, hub_url: str = "",
                 path: str | Path = "/data/homebrain-hub-diagnostics.sqlite3",
                 probe_seconds: int = 30, retention_days: int = 30,
                 cpu_cores: int = 4, hub_timezone: str = "Europe/London") -> None:
        self.enabled = bool(enabled)
        self.path = Path(path)
        self.probe_seconds = max(30, min(300, int(probe_seconds)))
        self.retention_days = max(1, min(90, int(retention_days)))
        # Number of logical processors for converting load average to a
        # processor-capacity equivalent, not measured CPU utilisation.
        self.cpu_cores = max(1, min(64, int(cpu_cores)))
        self.hub_url = ""
        self.hub_timezone = str(hub_timezone).strip()
        self.error: str | None = None
        if self.enabled:
            try:
                ZoneInfo(self.hub_timezone)
                self.hub_url = validate_hub_url(hub_url)
            except (ValueError, ZoneInfoNotFoundError) as exc:
                self.error = "Invalid hub time zone or LAN URL: " + str(exc)
        self._task: asyncio.Task | None = None
        self._last: dict[str, Any] | None = None
        self._failures = 0
        self._last_good: str | None = None
        self._pending_failure_start: str | None = None
        self._native: dict[str, Any] = {}
        self._native_last_attempt: float = -1e12
        self._events_last_attempt: float = -1e12
        self._last_prune_at: float = 0

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
            db.execute("""CREATE TABLE IF NOT EXISTS native_samples (
                native_sample_label TEXT PRIMARY KEY, recorded_at TEXT NOT NULL,
                collected_at TEXT NOT NULL, native_free_os_mb REAL,
                native_load5 REAL, timestamp_basis TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS native_samples_time ON native_samples(recorded_at)")
            db.execute("""CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
                recovered_at TEXT, kind TEXT NOT NULL,
                detail TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS incident_by_start ON incidents(started_at)")
            db.execute("""CREATE TABLE IF NOT EXISTS hub_startups (
                occurred_at TEXT PRIMARY KEY,
                firmware TEXT NOT NULL DEFAULT '',
                observed_at TEXT NOT NULL,
                source TEXT NOT NULL
            )""")
            last = db.execute("SELECT * FROM samples ORDER BY recorded_at DESC LIMIT 1").fetchone()
            if last is not None:
                self._last = dict(last)
                self._last_good = db.execute(
                    "SELECT MAX(recorded_at) FROM samples WHERE reachable=1"
                ).fetchone()[0]
            self._prune(db)
            self._last_prune_at = time.monotonic()
            if db.execute("SELECT 1 FROM incidents WHERE recovered_at IS NULL "
                          "AND kind='hub-unreachable' LIMIT 1").fetchone():
                self._pending_failure_start = "persisted-open-incident"

    def _prune(self, db: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(days=self.retention_days)).isoformat(timespec="milliseconds")
        db.execute("DELETE FROM samples WHERE recorded_at < ?", (cutoff,))
        db.execute("DELETE FROM native_samples WHERE recorded_at < ?", (cutoff,))
        db.execute("DELETE FROM hub_startups WHERE occurred_at < ?", (cutoff,))
        db.execute(
            "DELETE FROM incidents WHERE recovered_at IS NOT NULL AND recovered_at < ?",
            (cutoff,),
        )

    def _save(self, row: dict[str, Any], opened: str | None,
              recovered: bool, prune: bool = False,
              startups: tuple[dict[str, str], ...] = (),
              native_samples: tuple[dict[str, Any], ...] = ()) -> None:
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
            for native in native_samples:
                db.execute(
                    "INSERT OR IGNORE INTO native_samples "
                    "(native_sample_label,recorded_at,collected_at,native_free_os_mb,native_load5,timestamp_basis) "
                    "VALUES (?,?,?,?,?,?)",
                    (native["native_sample_label"], native["recorded_at"],
                     native["collected_at"], native["native_free_os_mb"],
                     native["native_load5"], native["timestamp_basis"]),
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
            for event in startups:
                db.execute(
                    "INSERT OR IGNORE INTO hub_startups "
                    "(occurred_at, firmware, observed_at, source) VALUES (?, ?, ?, ?)",
                    (event["occurred_at"], event["firmware"],
                     row["recorded_at"], event["source"]),
                )
            if prune:
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

        startups: tuple[dict[str, str], ...] = ()
        native_samples: tuple[dict[str, Any], ...] = ()
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
                    native_samples = parse_native_history(
                        native_response.text, collected_at=row["recorded_at"],
                        hub_timezone=self.hub_timezone,
                        retention_days=self.retention_days,
                    )
                except (httpx.HTTPError, ValueError):
                    # Keep older Java figures with original native timestamp; never
                    # imply the previous Java sample has been refreshed.
                    pass
            row.update(self._native)
            if now - self._events_last_attempt >= 300:
                self._events_last_attempt = now
                try:
                    response = await client.get(self.hub_url + _HUB_EVENTS)
                    response.raise_for_status()
                    startups = tuple(parse_system_start_events(response.text))
                except (httpx.HTTPError, ValueError):
                    # Failing to retrieve hub events never blocks resource
                    # recording. Startup coverage is only partial.
                    pass
        else:
            self._failures += 1
            recovered = False
            if self._failures == 1:
                self._pending_failure_start = row["recorded_at"]
            # No cached memory values in an unreachable sample.
            row["native_sample_label"] = None
        opened = self._pending_failure_start if self._failures == 2 else None
        self._last = row
        prune = time.monotonic() - self._last_prune_at >= 86400
        if prune:
            self._last_prune_at = time.monotonic()
        await asyncio.to_thread(self._save, row, opened, recovered, prune, startups, native_samples)

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

    def _with_load_pct(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        load = result.get("native_load5")
        if isinstance(load, (int, float)) and 0 <= load <= 1000:
            result["native_load_pct"] = round(float(load) / self.cpu_cores * 100, 1)
        else:
            result["native_load_pct"] = None
        return result

    def status(self) -> dict[str, Any]:
        row = self._with_load_pct(self._last or {})
        return {
            "enabled": self.enabled, "running": bool(self._task and not self._task.done()),
            "hub_timezone": self.hub_timezone,
            "error": self.error, "probe_seconds": self.probe_seconds,
            "retention_days": self.retention_days, "cpu_cores": self.cpu_cores,
            "last": dict(row),
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
                "Hubitat's separate native five-minute sample. CPU percent is "
                "load average divided by configured core count, not utilisation. "
                "No direct Metaspace metric."
            ),
        }

    def history(self, hours: int = 6,
                metric: str = "free_os_mb") -> dict[str, Any]:
        if metric not in _HISTORY_METRICS:
            raise ValueError("Unsupported diagnostic history metric")
        window = max(1, min(720, self.retention_days * 24, int(hours)))
        finish = datetime.now(timezone.utc)
        start = finish - timedelta(hours=window)
        cutoff = start.isoformat(timespec="milliseconds")
        empty: dict[str, Any] = {
            "samples": [], "incidents": [], "reboots": [],
            "coverage": "not_recorded", "cpu_cores": self.cpu_cores,
            "hours": window, "metric": metric, "retention_days": self.retention_days,
            "source_sample_count": 0, "observed_metric_points": 0,
            "downsampled": False,
            "range_start": cutoff,
            "range_end": finish.isoformat(timespec="milliseconds"),
        }
        if not self.enabled or not self.path.exists():
            return empty
        with self._connect() as db:
            sample_rows = (
                self._with_load_pct(dict(row))
                for row in db.execute(
                    "SELECT * FROM samples WHERE recorded_at>=? ORDER BY recorded_at ASC",
                    (cutoff,),
                )
            )
            chart = summarize_history_samples(
                sample_rows, metric=metric, start=start, finish=finish,
                probe_seconds=self.probe_seconds,
            )
            incidents = [dict(v) for v in db.execute(
                "SELECT * FROM incidents WHERE started_at>=? OR recovered_at>=? "
                "OR recovered_at IS NULL "
                "ORDER BY started_at DESC LIMIT 100", (cutoff, cutoff),
            )]
            reboots = [dict(v) for v in db.execute(
                "SELECT occurred_at,firmware,observed_at,source "
                "FROM hub_startups WHERE occurred_at>=? "
                "ORDER BY occurred_at ASC LIMIT 200", (cutoff,),
            )]
        return {
            **chart,
            "incidents": incidents,
            "reboots": reboots,
            "hours": window, "metric": metric, "cpu_cores": self.cpu_cores,
            "retention_days": self.retention_days,
            "range_start": cutoff,
            "range_end": finish.isoformat(timespec="milliseconds"),
            "display_point_count": len(chart["samples"]),
            "summarization": ("first_last_min_max_actual_per_time_bucket"
                              if chart["downsampled"] else "original_records"),
            "coverage": "partial_observations_not_proof_of_cause",
            "reboot_coverage": (
                "confirmed_systemStart_events_returned_by_hub_eventsJson"
            ),
            "native_java_resolution_seconds": 300,
        }


    def timeline(self, hours: int = 24) -> dict[str, Any]:
        """One aligned time window for external memory, native load and observed incidents.

        Reads the same local SQLite recorder as history(); never contacts Hubitat.
        CPU entries use original native labels but their x-coordinate is the
        collector reception timestamp, not a fabricated native measurement time.
        """
        window = max(1, min(720, self.retention_days * 24, int(hours)))
        finish = datetime.now(timezone.utc)
        start = finish - timedelta(hours=window)
        cutoff = start.isoformat(timespec="milliseconds")
        end = finish.isoformat(timespec="milliseconds")
        empty_metric = {
            "samples": [], "source_sample_count": 0,
            "observed_metric_points": 0, "downsampled": False,
        }
        output: dict[str, Any] = {
            "range_start": cutoff, "range_end": end, "hours": window,
            "retention_days": self.retention_days,
            "cpu_cores": self.cpu_cores,
            "metrics": {
                "free_os_mb": dict(empty_metric),
                "native_load_pct": dict(empty_metric),
            },
            "incidents": [], "reboots": [],
            "coverage": "not_recorded",
            "timestamp_basis": {
                "free_os_mb": "external_probe_recorded_at",
                "native_load_pct": "collector_recorded_at_with_native_sample_label",
                "incidents": "external_probe_failure_and_recovery",
                "reboots": "hub_events_json_systemStart_offset_aware",
            },
            "source_limits": {
                "incidents_max": 100, "reboots_max": 200,
                "historical_event_coverage": "partial",
            },
        }
        if not self.enabled or not self.path.exists():
            return output

        with self._connect() as db:
            for metric in ("free_os_mb", "native_load_pct"):
                # Stream bounded display points. The summarizer preserves
                # actual extrema and segment boundaries, not averaged values.
                samples = (
                    self._with_load_pct(dict(row))
                    for row in db.execute(
                        "SELECT * FROM samples WHERE recorded_at>=? "
                        "AND recorded_at<=? ORDER BY recorded_at ASC",
                        (cutoff, end),
                    )
                )
                output["metrics"][metric] = summarize_history_samples(
                    samples, metric=metric, start=start, finish=finish,
                    probe_seconds=self.probe_seconds,
                )
            output["incidents"] = [dict(row) for row in db.execute(
                "SELECT started_at,recovered_at,kind,detail FROM incidents "
                "WHERE started_at<=? AND (recovered_at IS NULL OR recovered_at>=?) "
                "ORDER BY started_at DESC LIMIT 100", (end, cutoff),
            )]
            output["reboots"] = [dict(row) for row in db.execute(
                "SELECT occurred_at,firmware,observed_at,source FROM hub_startups "
                "WHERE occurred_at>=? AND occurred_at<=? "
                "ORDER BY occurred_at ASC LIMIT 200", (cutoff, end),
            )]
        output["coverage"] = "partial_observations_not_proof_of_cause"
        return output


    def incident_evidence(self, start: datetime, end: datetime, focus: datetime) -> dict[str, Any]:
        """Bounded local recorder evidence around one focus time; never polls Hubitat."""
        output: dict[str, Any] = {
            "status": "not_recorded", "samples": [], "sample_limit": 400,
            "samples_truncated": False, "sample_count": 0,
            "reachable_samples": 0, "failed_samples": 0,
            "memory_min": None, "cpu_load_max": None, "java_free_min": None,
            "last_success_before": None, "first_success_after": None,
            "incidents": [], "incidents_truncated": False,
            "startups": [], "startups_truncated": False,
            "source_timestamp_basis": {
                "memory": "external_probe_recorded_at",
                "native_load": "collector_reception_plus_native_sample_label",
                "startup": "hub_systemStart_offset_aware",
                "connectivity": "external_two_failed_probes",
            },
            "causal_status": "unverified",
        }
        if not self.enabled or not self.path.exists():
            return output
        cutoff = start.astimezone(timezone.utc).isoformat(timespec="milliseconds")
        until = end.astimezone(timezone.utc).isoformat(timespec="milliseconds")
        with self._connect() as db:
            samples = [self._with_load_pct(dict(row)) for row in db.execute(
                "SELECT recorded_at,reachable,latency_ms,free_os_mb,error_kind,"
                "native_sample_label,native_load5,java_free_mb,java_allocated_heap_used_pct "
                "FROM samples WHERE recorded_at>=? AND recorded_at<=? "
                "ORDER BY recorded_at ASC LIMIT 401", (cutoff, until),
            )]
            outages = [dict(row) for row in db.execute(
                "SELECT started_at,recovered_at,kind,detail FROM incidents "
                "WHERE started_at<=? AND (recovered_at IS NULL OR recovered_at>=?) "
                "ORDER BY started_at ASC LIMIT 41", (until, cutoff),
            )]
            startups = [dict(row) for row in db.execute(
                "SELECT occurred_at,firmware,observed_at,source FROM hub_startups "
                "WHERE occurred_at>=? AND occurred_at<=? "
                "ORDER BY occurred_at ASC LIMIT 41", (cutoff, until),
            )]
        output["status"] = "partial_observations_not_proof_of_cause"
        output["samples_truncated"] = len(samples) > 400
        output["samples"] = samples[:400]
        output["sample_count"] = len(output["samples"])
        output["incidents_truncated"] = len(outages) > 40
        output["incidents"] = outages[:40]
        output["startups_truncated"] = len(startups) > 40
        output["startups"] = startups[:40]
        seen_native: set[str] = set()
        focus_time = focus.astimezone(timezone.utc)
        for row in output["samples"]:
            if not row.get("reachable"):
                output["failed_samples"] += 1
                continue
            output["reachable_samples"] += 1
            when = datetime.fromisoformat(row["recorded_at"]).astimezone(timezone.utc)
            if when <= focus_time:
                output["last_success_before"] = {
                    "recorded_at": row["recorded_at"], "free_os_mb": row["free_os_mb"],
                    "latency_ms": row["latency_ms"],
                }
            if when >= focus_time and output["first_success_after"] is None:
                output["first_success_after"] = {
                    "recorded_at": row["recorded_at"], "free_os_mb": row["free_os_mb"],
                    "latency_ms": row["latency_ms"],
                }
            memory = row.get("free_os_mb")
            if isinstance(memory, (int, float)) and math.isfinite(memory):
                current = output["memory_min"]
                if current is None or memory < current["value"]:
                    output["memory_min"] = {
                        "value": memory, "recorded_at": row["recorded_at"],
                        "basis": "external_probe",
                    }
            native_label = str(row.get("native_sample_label") or "")
            if not native_label or native_label in seen_native:
                continue
            seen_native.add(native_label)
            for key, target in (("native_load_pct", "cpu_load_max"),
                                ("java_free_mb", "java_free_min")):
                value = row.get(key)
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    continue
                current = output[target]
                if current is None or (
                    value > current["value"] if target == "cpu_load_max"
                    else value < current["value"]
                ):
                    output[target] = {
                        "value": value, "recorded_at": row["recorded_at"],
                        "native_sample_label": native_label,
                        "basis": "native_five_minute_sample_received",
                    }
        return output


__all__ = [
    "ExternalHubDiagnostics", "validate_hub_url",
    "parse_live_memory", "parse_native_sample",
    "parse_system_start_events", "summarize_history_samples",
]
