"""Persistent home knowledge: owner notes + an observed device profile, and the daily briefing.

Nothing here reads or interprets the user's question. The profile is built from the same
read-only inventory snapshot the System Health tab uses; the notes are text the owner wrote.
Both are given to the model as context, labelled so it can tell notes (owner statements) from
observed data. The briefing is composed from the snapshot with no model involved.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("home_knowledge")

MAX_NOTES_CHARS = 3000
PROFILE_TTL_SECONDS = 900

STARTER_NOTES = (
    "# Home notes (edit freely; the assistant reads these before every answer)\n"
    "- Lights are the devices named light/lamp/bulb or reported as dimmers or colour bulbs. "
    "Sockets, plugs and appliances switch loads and are not lights.\n"
    "- Heating is controlled by thermostatic radiator valves (TRVs) and thermostats; "
    "temperatures are in °C.\n"
    "- Switches named \"Block ...\" are internet-access blockers for a device, not appliances.\n"
)


def clean_notes(text: object) -> str:
    """Plain text only, bounded. Control characters other than newline/tab are dropped."""
    if not isinstance(text, str):
        raise ValueError("notes must be text")
    cleaned = "".join(ch for ch in text.replace("\r\n", "\n").replace("\r", "\n")
                      if ch in "\n\t" or ch >= " ")
    cleaned = cleaned.strip()
    if len(cleaned) > MAX_NOTES_CHARS:
        raise ValueError(f"notes are limited to {MAX_NOTES_CHARS} characters")
    return cleaned


class HomeNotes:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> str:
        try:
            return clean_notes(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""

    def save(self, text: object) -> str:
        cleaned = clean_notes(text)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(cleaned, encoding="utf-8")
        tmp.replace(self.path)
        return cleaned


def _names(items, limit=40) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def profile_text(snapshot: dict | None) -> str:
    """Compact, factual device-class lists from the last overview snapshot."""
    profile = (snapshot or {}).get("profile")
    if not isinstance(profile, dict):
        return ""
    parts = []
    if profile.get("lights"):
        parts.append(f"Lights (recognised by name/type): {_names(profile['lights'])}.")
    if profile.get("heating_devices"):
        parts.append(f"Heating devices (report an operating state): {_names(profile['heating_devices'])}.")
    if profile.get("contact_sensors"):
        parts.append(f"Contact sensors: {_names(profile['contact_sensors'])}.")
    if profile.get("water_sensors"):
        parts.append(f"Water sensors: {_names(profile['water_sensors'])}.")
    parts.append(f"{profile.get('battery_devices', 0)} devices report a battery level; "
                 f"{profile.get('motion_sensors', 0)} report motion.")
    if (snapshot or {}).get("source_declared_total") is not None:
        parts.append(f"The hub declares {snapshot['source_declared_total']} devices.")
    return " ".join(parts)


class HomeKnowledge:
    """Owner notes plus a cached device profile, exposed as one context string."""

    def __init__(self, notes: HomeNotes, read_snapshot, *, clock=time.monotonic):
        self.notes, self._read, self._clock = notes, read_snapshot, clock
        self.snapshot: dict | None = None
        self._taken: float | None = None

    async def refresh(self, force: bool = False) -> dict | None:
        now = self._clock()
        if not force and self._taken is not None and now - self._taken < PROFILE_TTL_SECONDS:
            return self.snapshot
        try:
            self.snapshot = await self._read()
            self._taken = now
        except Exception as exc:  # the profile is optional context; never block an answer
            log.warning("home profile refresh failed: %s", exc)
        return self.snapshot

    def context(self) -> str:
        notes = self.notes.load()
        profile = profile_text(self.snapshot)
        blocks = []
        if notes:
            blocks.append("Owner's home notes (statements by the owner, not tool data):\n" + notes)
        if profile:
            blocks.append("Observed device profile (from a read-only inventory snapshot earlier; "
                          "states may have changed, so read live state before stating it):\n" + profile)
        return "\n\n".join(blocks)


def briefing_text(snapshot: dict, *, problems: dict | None = None, local_now: datetime | None = None) -> tuple[str, str]:
    """Plain-text morning briefing. Only counts and names present in the snapshot."""
    m = snapshot.get("metrics", {})

    def names(key, limit=6):
        members = [x["name"] for x in m.get(key, {}).get("members", [])]
        return _names(members, limit)

    lines = []
    low = m.get("battery_low", {})
    if low.get("count"):
        lines.append("Low batteries (<20%): " + ", ".join(
            f"{x['name']} {x['battery_pct']:.0f}%" for x in low["members"][:6]))
    for key, label in (("contact_open", "Open contact sensors"), ("water_wet", "Wet water sensors"),
                       ("reported_offline", "Reported offline")):
        if m.get(key, {}).get("count"):
            lines.append(f"{label}: {names(key)}")
    stale = m.get("last_activity_over_24h", {})
    if stale.get("count"):
        lines.append(f"No recorded activity for over 24 h: {stale['count']} devices "
                     f"(longest: {stale['members'][0]['name']}, about {stale['members'][0]['inactive_hours']:.0f} h)")
    if m.get("lights_on", {}).get("count"):
        lines.append("Lights on: " + names("lights_on"))
    if m.get("heating_active", {}).get("count"):
        lines.append("Heating now: " + names("heating_active"))
    for key, text in (problems or {}).items():
        lines.append(f"Problem: {text}")
    when = local_now.strftime("%a %d %b, %H:%M") if local_now else ""
    title = f"Home briefing{(' · ' + when) if when else ''}"
    if not lines:
        lines.append("Nothing needs attention: no low batteries, open contacts, leaks or stale devices.")
    if snapshot.get("inventory_full_coverage_verified") is False:
        lines.append("Note: the inventory read was partial, so counts may be incomplete.")
    return title, "\n".join(lines)


class BriefingSchedule:
    """Sends the briefing once a day at HH:MM in the hub's timezone."""

    def __init__(self, build, send, *, time_of_day: str, timezone: str, now=None):
        hh, mm = time_of_day.split(":")
        self.hour, self.minute = int(hh), int(mm)
        if not (0 <= self.hour < 24 and 0 <= self.minute < 60):
            raise ValueError("briefing_time must be HH:MM")
        self.zone = ZoneInfo(timezone)
        self.build, self.send = build, send
        self._now = now or (lambda: datetime.now(self.zone))
        self.last_sent_date = None
        self.last_error: str | None = None
        self._task = None

    def due(self) -> bool:
        now = self._now()
        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        return now >= target and now - target < timedelta(hours=3) and self.last_sent_date != now.date()

    async def tick(self) -> bool:
        if not self.due():
            return False
        try:
            title, body = await self.build()
            await self.send(title, body)
        except Exception as exc:
            self.last_error = f"briefing not sent: {exc}"
            return False
        self.last_sent_date, self.last_error = self._now().date(), None
        return True

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            await self.tick()
            await asyncio.sleep(60)

    async def close(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
