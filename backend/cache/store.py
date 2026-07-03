from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            name TEXT,
            label TEXT NOT NULL,
            room TEXT,
            category TEXT NOT NULL,
            json TEXT NOT NULL,
            switch TEXT,
            temperature REAL,
            humidity REAL,
            power REAL,
            energy REAL,
            battery REAL,
            updated_at INTEGER NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            attr TEXT NOT NULL,
            value TEXT,
            created_at INTEGER NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_devices_room_category ON devices(room, category)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_history_device_created ON history(device_id, created_at)')
    return conn


def upsert_devices(conn: sqlite3.Connection, devices: list[dict[str, Any]]) -> None:
    now = int(time.time())
    for d in devices:
        conn.execute('''
            INSERT INTO devices(id,name,label,room,category,json,switch,temperature,humidity,power,energy,battery,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, label=excluded.label, room=excluded.room, category=excluded.category,
                json=excluded.json, switch=excluded.switch, temperature=excluded.temperature,
                humidity=excluded.humidity, power=excluded.power, energy=excluded.energy,
                battery=excluded.battery, updated_at=excluded.updated_at
        ''', (
            d['id'], d['name'], d['label'], d.get('room'), d['category'], json.dumps(d),
            d.get('switch'), d.get('temperature'), d.get('humidity'), d.get('power'), d.get('energy'), d.get('battery'), now
        ))
    conn.commit()


def all_devices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute('SELECT json FROM devices ORDER BY label').fetchall()
    return [json.loads(r['json']) for r in rows]
