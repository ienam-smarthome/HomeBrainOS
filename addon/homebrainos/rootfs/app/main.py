from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

APP_VERSION = '0.7.56-alpha'
CONFIG_PATH = Path('/data/options.json')
DB_PATH = Path('/data/homebrainos.sqlite3')
HOUSEHOLD_PEOPLE = ['Enamul', 'Samah', 'Tahmid', 'Muhsena']
POWER_SOURCE_TERMS = ('octopus', 'whole house', 'house power', 'smart meter', 'electricity meter')
ROOM_WORDS = [
    'hallway', 'bathroom', 'bedroom 1', 'bedroom 2', 'bedroom 3', 'living room', 'livingroom',
    'kitchen', 'toilet', 'entrance', 'ventilation', 'dehumidifier', 'energy', 'sockets',
    'multimedia', 'office', 'internet', 'router'
]
DEVICE_ATTRS = ['switch','level','temperature','humidity','illuminance','motion','contact','presence','battery','power','energy','thermostatMode','thermostatOperatingState','heatingSetpoint','coolingSetpoint','lock','water','smoke','carbonMonoxide','tamper','acceleration','valve','windowShade','weatherSummary','weatherSummaryLine','pressure','windSpeed','wind_gust','windDirection','precipitationToday']
ATTR_ALIASES = {
    'switch': {'switch', 'switchstate', 'state'},
    'level': {'level', 'switchlevel', 'dimmerlevel'},
    'temperature': {'temperature', 'temp'},
    'humidity': {'humidity', 'relativehumidity'},
    'illuminance': {'illuminance', 'illuminancelevel', 'lux'},
    'motion': {'motion', 'motionsensor'},
    'contact': {'contact', 'contactsensor'},
    'presence': {'presence', 'presencesensor'},
    'battery': {'battery', 'batterylevel'},
    'power': {'power', 'powermeter', 'watts', 'wattage'},
    'energy': {'energy', 'energymeter'},
    'thermostatMode': {'thermostatmode'},
    'thermostatOperatingState': {'thermostatoperatingstate'},
    'heatingSetpoint': {'heatingsetpoint'},
    'coolingSetpoint': {'coolingsetpoint'},
    'lock': {'lock'},
    'water': {'water'},
    'smoke': {'smoke'},
    'carbonMonoxide': {'carbonmonoxide', 'carbonmonoxidelevel'},
    'tamper': {'tamper'},
    'acceleration': {'acceleration'},
    'valve': {'valve'},
    'windowShade': {'windowshade', 'shade'},
    'weatherSummary': {'weathersummary'},
    'weatherSummaryLine': {'weathersummaryline'},
    'windSpeed': {'windspeed'},
    'wind_gust': {'windgust', 'wind_gust'},
    'windDirection': {'winddirection'},
    'precipitationToday': {'precipitationtoday'},
}
ALIAS_LOOKUP = {alias: canonical for canonical, aliases in ATTR_ALIASES.items() for alias in aliases}


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {
        'hubitat_base_url': os.getenv('HUBITAT_BASE_URL', ''),
        'maker_api_app_id': os.getenv('MAKER_API_APP_ID', ''),
        'maker_api_token': os.getenv('MAKER_API_TOKEN', ''),
        'api_token': os.getenv('HOMEBRAIN_API_TOKEN', ''),
        'refresh_seconds': int(os.getenv('REFRESH_SECONDS', '30')),
        'ollama_enabled': os.getenv('OLLAMA_ENABLED', 'false').lower() == 'true',
        'ollama_base_url': os.getenv('OLLAMA_BASE_URL', 'http://homeassistant.local:11434'),
        'ollama_model': os.getenv('OLLAMA_MODEL', 'qwen2.5:3b'),
        'ollama_context_device_limit': int(os.getenv('OLLAMA_CONTEXT_DEVICE_LIMIT', '35')),
        'ollama_include_hub_logs': os.getenv('OLLAMA_INCLUDE_HUB_LOGS', 'false').lower() == 'true',
        'ollama_timeout_seconds': int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '75')),
        'ollama_num_predict': int(os.getenv('OLLAMA_NUM_PREDICT', '90')),
        'ollama_health_timeout_seconds': int(os.getenv('OLLAMA_HEALTH_TIMEOUT_SECONDS', '2')),
        'ollama_health_cache_seconds': int(os.getenv('OLLAMA_HEALTH_CACHE_SECONDS', '60')),
        'device_detail_refresh_limit': int(os.getenv('DEVICE_DETAIL_REFRESH_LIMIT', '150')),
        'device_detail_refresh_seconds': int(os.getenv('DEVICE_DETAIL_REFRESH_SECONDS', '300')),
        'device_detail_refresh_batch': int(os.getenv('DEVICE_DETAIL_REFRESH_BATCH', '30')),
        'heating_on_delta': float(os.getenv('HEATING_ON_DELTA', '1')),
        'heating_off_setpoint': float(os.getenv('HEATING_OFF_SETPOINT', '12')),
        'hubitat_logs_path': os.getenv('HUBITAT_LOGS_PATH', '/logs/past'),
        'hubitat_logs_url': os.getenv('HUBITAT_LOGS_URL', ''),
    }


CONFIG = load_config()
LAST_ERROR: str | None = None
LAST_REFRESH: float | None = None
LAST_DETAIL_ERRORS: list[str] = []
LAST_HUBITAT_EVENT: dict[str, Any] | None = None
STATE_EVENT_VERSION = 0
PENDING_DEVICE_TIMERS: dict[str, dict[str, Any]] = {}
ACTIVE_TIMER_THREADS: dict[str, threading.Timer] = {}
OLLAMA_HEALTH: dict[str, Any] = {'checked_at': 0.0, 'online': None, 'message': 'Not checked', 'base_url': '', 'model': ''}
app = FastAPI(title='HomeBrain OS', version=APP_VERSION)


class AssistantRequest(BaseModel):
    q: str


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
            detail_refreshed_at INTEGER,
            updated_at INTEGER NOT NULL
        )
    ''')
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(devices)').fetchall()}
    if 'detail_refreshed_at' not in columns:
        conn.execute('ALTER TABLE devices ADD COLUMN detail_refreshed_at INTEGER')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            attr TEXT NOT NULL,
            value TEXT,
            created_at INTEGER NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS device_timers (
            id TEXT PRIMARY KEY,
            device_ids TEXT NOT NULL,
            labels TEXT NOT NULL,
            command TEXT NOT NULL,
            due_at REAL NOT NULL,
            created_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS hubitat_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            label TEXT,
            attr TEXT,
            value TEXT,
            raw TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_devices_room_category ON devices(room, category)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_history_device_created ON history(device_id, created_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_device_timers_status_due ON device_timers(status, due_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_hubitat_events_created ON hubitat_events(created_at)')
    return conn


def maker_url(path: str) -> str:
    base = str(CONFIG.get('hubitat_base_url', '')).rstrip('/')
    app_id = quote(str(CONFIG.get('maker_api_app_id', '')).strip(), safe='')
    token = quote(str(CONFIG.get('maker_api_token', '')).strip(), safe='')
    if not base or not app_id or not token:
        raise RuntimeError('Hubitat Maker API is not configured. Set hubitat_base_url, maker_api_app_id, and maker_api_token.')
    sep = '&' if '?' in path else '?'
    return f'{base}/apps/api/{app_id}/{path}{sep}access_token={token}'


def maker_get(path: str, timeout: int = 20) -> Any:
    response = requests.get(maker_url(path), timeout=timeout)
    response.raise_for_status()
    return response.json()


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace('%',''))
    except Exception:
        return None


def compact_name(value: Any) -> str:
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def canonical_attr(name: Any) -> str:
    text = str(name or '').strip()
    return ALIAS_LOOKUP.get(compact_name(text), text)


def attr_value(item: dict[str, Any]) -> Any:
    for key in ('currentValue', 'value', 'displayValue', 'current_value'):
        if item.get(key) is not None:
            return item.get(key)
    return None


def list_names(values: Any, keys: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    if isinstance(values, dict):
        values = list(values.values()) or list(values.keys())
    for value in values or []:
        if isinstance(value, dict):
            name = next((value.get(key) for key in keys if value.get(key)), None)
        else:
            name = value
        if name is not None:
            names.append(str(name))
    return sorted(set(names), key=str.lower)


def caps_text(device: dict[str, Any]) -> str:
    return ' '.join(list_names(device.get('capabilities'), ('name', 'capability', 'id'))).lower()


def commands_text(device: dict[str, Any]) -> str:
    return ' '.join(list_names(device.get('commands'), ('name', 'command'))).lower()


def state_text(value: Any) -> str:
    return str(value or '').strip().lower()


def is_state(value: Any, *states: str) -> bool:
    return state_text(value) in {state.lower() for state in states}


def redact_sensitive(value: Any) -> str:
    text = str(value)
    text = re.sub(r'access_token=[^&\s]+', 'access_token=REDACTED', text, flags=re.IGNORECASE)
    for key in ('maker_api_token', 'api_token'):
        secret = str(CONFIG.get(key, '') or '').strip()
        if secret:
            text = text.replace(secret, 'REDACTED')
    return text


def public_error(exc: Exception) -> str:
    return redact_sensitive(exc)


def hubitat_url(path_or_url: str) -> str:
    value = str(path_or_url or '').strip()
    if value.startswith(('http://', 'https://')):
        return value
    base = str(CONFIG.get('hubitat_base_url', '')).rstrip('/')
    if not base:
        raise RuntimeError('Hubitat base URL is not configured.')
    return f"{base}/{value.lstrip('/')}"


def api_token_required() -> bool:
    return bool(str(CONFIG.get('api_token', '') or '').strip())


def require_api_token(request: Request) -> None:
    expected = str(CONFIG.get('api_token', '') or '').strip()
    if not expected:
        return
    supplied = request.headers.get('x-homebrain-token', '')
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail='Missing or invalid HomeBrain API token.')


def require_event_token(request: Request) -> None:
    expected = str(CONFIG.get('api_token', '') or '').strip()
    if not expected:
        return
    supplied = (
        request.headers.get('x-homebrain-token', '')
        or request.query_params.get('token', '')
        or request.query_params.get('homebrain_token', '')
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail='Missing or invalid HomeBrain event token.')


def attr_map(device: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    sources = (device.get('attributes'), device.get('currentStates'), device.get('states'))
    for source in sources:
        if isinstance(source, dict):
            for name, value in source.items():
                attrs[str(name)] = value
                attrs[canonical_attr(name)] = value
            continue
        for item in source or []:
            if not isinstance(item, dict):
                continue
            name = item.get('name') or item.get('attribute')
            if name:
                value = attr_value(item)
                attrs[str(name)] = value
                attrs[canonical_attr(name)] = value
    return attrs


def canonical_room_name(room: Any) -> str:
    if isinstance(room, dict):
        for key in ('name', 'label', 'roomName', 'room_name'):
            if room.get(key):
                return canonical_room_name(room[key])
    text = normalise(str(room or 'Unknown'))
    if not text or text == 'unknown':
        return 'Unknown'
    m = re.fullmatch(r'bedroom\s*([123])', text)
    if m:
        return f"Bedroom {m.group(1)}"
    if text in ('livingroom', 'living room'):
        return 'Living Room'
    return text.title()


def hubitat_room_name(device: dict[str, Any]) -> str | None:
    for key in ('roomName', 'room_name', 'roomLabel', 'room_label', 'room'):
        value = device.get(key)
        if not value:
            continue
        room = canonical_room_name(value)
        if room != 'Unknown':
            return room
    return None


def infer_room(label: str) -> str:
    text = normalise(label)
    for room in ROOM_WORDS:
        if room in text:
            return canonical_room_name(room)
    # Common Hubitat labels like "01 Livingroom TRV" or "Bedroom 1 Meter"
    m = re.search(r'(bedroom\s*[123]|hallway|bathroom|living\s*room|livingroom|kitchen|toilet)', text)
    if m:
        return canonical_room_name(m.group(1))
    return 'Unknown'


def classify(device: dict[str, Any], attrs: dict[str, Any]) -> str:
    label = (device.get('label') or device.get('name') or '').lower()
    caps = caps_text(device)
    commands = commands_text(device)
    climate_attrs = ('thermostatMode', 'thermostatOperatingState', 'heatingSetpoint', 'coolingSetpoint')
    if 'weather' in label or attrs.get('weatherSummary') is not None or attrs.get('weatherSummaryLine') is not None:
        return 'weather'
    if 'battery' in label and not any(attrs.get(attr) is not None for attr in climate_attrs):
        return 'battery_sensor'
    if 'light sensor' in label or 'illuminance' in attrs or 'illuminance' in caps:
        return 'light_sensor'
    if (
        'light' in label
        or 'bulb' in label
        or 'dimmer' in label
        or 'switchlevel' in caps
        or 'colorcontrol' in caps
        or 'colortemperature' in caps
    ):
        return 'light'
    if 'thermostat' in caps or 'trv' in label or 'heatingsetpoint' in attrs:
        return 'thermostat'
    if 'presence' in attrs or 'presencesensor' in caps:
        return 'presence_sensor'
    if 'motion' in attrs or 'motionsensor' in caps:
        return 'motion_sensor'
    if 'contact' in attrs or 'contactsensor' in caps:
        return 'contact_sensor'
    if 'temperature' in attrs or 'humidity' in attrs:
        return 'climate_sensor'
    if 'power' in attrs or 'energy' in attrs:
        return 'power_device'
    if 'switch' in attrs or 'switch' in caps or ('on' in commands and 'off' in commands):
        return 'switch'
    return 'device'


def normalise_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = attr_map(device)
    label = str(device.get('label') or device.get('name') or f"Device {device.get('id')}")
    capabilities = list_names(device.get('capabilities'), ('name', 'capability', 'id'))
    commands = list_names(device.get('commands'), ('name', 'command'))
    room = hubitat_room_name(device) or infer_room(label)
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': label,
        'room': room,
        'category': classify(device, attrs),
        'capabilities': capabilities,
        'commands': commands,
        'attributes': attrs,
        'switch': attrs.get('switch'),
        'level': attrs.get('level'),
        'temperature': safe_float(attrs.get('temperature')),
        'humidity': safe_float(attrs.get('humidity')),
        'illuminance': safe_float(attrs.get('illuminance')),
        'power': safe_float(attrs.get('power')),
        'energy': safe_float(attrs.get('energy')),
        'battery': safe_float(attrs.get('battery')),
        'motion': attrs.get('motion'),
        'contact': attrs.get('contact'),
        'presence': attrs.get('presence'),
        'thermostatMode': attrs.get('thermostatMode'),
        'thermostatOperatingState': attrs.get('thermostatOperatingState'),
        'heatingSetpoint': attrs.get('heatingSetpoint'),
        'coolingSetpoint': attrs.get('coolingSetpoint'),
        'lock': attrs.get('lock'),
        'water': attrs.get('water'),
        'smoke': attrs.get('smoke'),
        'carbonMonoxide': attrs.get('carbonMonoxide'),
        'tamper': attrs.get('tamper'),
        'acceleration': attrs.get('acceleration'),
        'valve': attrs.get('valve'),
        'windowShade': attrs.get('windowShade'),
        'weatherSummary': attrs.get('weatherSummary'),
        'weatherSummaryLine': attrs.get('weatherSummaryLine'),
        'pressure': safe_float(attrs.get('pressure')),
        'windSpeed': safe_float(attrs.get('windSpeed')),
        'wind_gust': safe_float(attrs.get('wind_gust')),
        'windDirection': safe_float(attrs.get('windDirection')),
        'precipitationToday': safe_float(attrs.get('precipitationToday')),
        '_detail_refreshed_at': safe_float(device.get('_homebrain_detail_refreshed_at')),
    }


def merge_raw_device(summary: dict[str, Any], detail: Any) -> dict[str, Any]:
    if isinstance(detail, list):
        detail = detail[0] if len(detail) == 1 and isinstance(detail[0], dict) else {}
    if not isinstance(detail, dict):
        return summary
    merged = dict(summary)
    for key, value in detail.items():
        if value not in (None, '', [], {}):
            merged[key] = value
    merged.setdefault('id', summary.get('id'))
    merged.setdefault('name', summary.get('name'))
    merged.setdefault('label', summary.get('label'))
    return merged


def needs_device_detail(raw_device: dict[str, Any], device: dict[str, Any]) -> bool:
    if not device.get('attributes'):
        return True
    if is_switchable_device(device) and device.get('switch') is None:
        return True
    sensor_categories = {'light_sensor', 'climate_sensor', 'motion_sensor', 'contact_sensor', 'presence_sensor', 'thermostat'}
    if device.get('category') in sensor_categories and not any(device.get(attr) is not None for attr in DEVICE_ATTRS):
        return True
    return False


def cached_detail_refresh_times() -> dict[str, int]:
    conn = db()
    try:
        rows = conn.execute('SELECT id, detail_refreshed_at FROM devices').fetchall()
        return {str(row['id']): int(row['detail_refreshed_at']) for row in rows if row['detail_refreshed_at'] is not None}
    finally:
        conn.close()


def should_refresh_device_detail(device: dict[str, Any], last_detail_at: int | None, now: int) -> bool:
    seconds = max(0, int(CONFIG.get('device_detail_refresh_seconds', 300)))
    if seconds <= 0:
        return False
    if last_detail_at and now - int(last_detail_at) < seconds:
        return False
    priority_categories = {
        'light', 'switch', 'power_device', 'thermostat', 'climate_sensor',
        'motion_sensor', 'presence_sensor', 'contact_sensor', 'weather',
    }
    return device.get('category') in priority_categories or is_switchable_device(device)


def enrich_raw_devices(raw_devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    global LAST_DETAIL_ERRORS
    limit = max(0, int(CONFIG.get('device_detail_refresh_limit', 150)))
    batch = max(0, int(CONFIG.get('device_detail_refresh_batch', 30)))
    detail_times = cached_detail_refresh_times()
    now = int(time.time())
    enriched: list[dict[str, Any]] = []
    detail_errors: list[str] = []
    detail_count = 0
    stale_detail_count = 0
    for raw_device in raw_devices:
        device = normalise_device(raw_device)
        incomplete = needs_device_detail(raw_device, device)
        stale = should_refresh_device_detail(device, detail_times.get(str(device['id'])), now)
        should_fetch = detail_count < limit and (incomplete or (stale and stale_detail_count < batch))
        if should_fetch:
            try:
                detail = maker_get(f"devices/{quote(str(device['id']), safe='')}", timeout=8)
                raw_device = merge_raw_device(raw_device, detail)
                raw_device['_homebrain_detail_refreshed_at'] = now
                detail_count += 1
                if not incomplete:
                    stale_detail_count += 1
            except Exception as exc:
                detail_errors.append(f"{device['label']}: {public_error(exc)}")
        enriched.append(raw_device)
    LAST_DETAIL_ERRORS = detail_errors[:10]
    return enriched


def upsert_devices(devices: list[dict[str, Any]]) -> None:
    now = int(time.time())
    conn = db()
    try:
        for d in devices:
            old = conn.execute('SELECT json, detail_refreshed_at FROM devices WHERE id=?', (d['id'],)).fetchone()
            detail_refreshed_at = int(d['_detail_refreshed_at']) if d.get('_detail_refreshed_at') is not None else (old['detail_refreshed_at'] if old else None)
            if old and d.get('switch') is None:
                old_d = json.loads(old['json'])
                if old_d.get('switch') is not None:
                    d['switch'] = old_d.get('switch')
                    d.setdefault('attributes', {})['switch'] = old_d.get('switch')
            conn.execute('''
                INSERT INTO devices(id,name,label,room,category,json,switch,temperature,humidity,power,energy,battery,detail_refreshed_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, label=excluded.label, room=excluded.room, category=excluded.category,
                    json=excluded.json, switch=excluded.switch, temperature=excluded.temperature,
                    humidity=excluded.humidity, power=excluded.power, energy=excluded.energy,
                    battery=excluded.battery, detail_refreshed_at=excluded.detail_refreshed_at, updated_at=excluded.updated_at
            ''', (
                d['id'], d['name'], d['label'], d['room'], d['category'], json.dumps(d),
                d.get('switch'), d.get('temperature'), d.get('humidity'), d.get('power'), d.get('energy'), d.get('battery'), detail_refreshed_at, now
            ))
            if old:
                old_d = json.loads(old['json'])
                for attr in ('switch','temperature','humidity','power','battery','motion','presence'):
                    if old_d.get(attr) != d.get(attr):
                        conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', (d['id'], attr, str(d.get(attr)), now))
        conn.commit()
    finally:
        conn.close()


def prune_missing_devices(device_ids: set[str]) -> int:
    conn = db()
    try:
        existing = [str(row['id']) for row in conn.execute('SELECT id FROM devices').fetchall()]
        stale = [device_id for device_id in existing if device_id not in device_ids]
        for device_id in stale:
            conn.execute('DELETE FROM devices WHERE id=?', (device_id,))
            conn.execute('DELETE FROM history WHERE device_id=?', (device_id,))
        conn.commit()
        return len(stale)
    finally:
        conn.close()


def update_cached_switch(device_ids: list[str], switch: str) -> list[dict[str, Any]]:
    now = int(time.time())
    updated: list[dict[str, Any]] = []
    conn = db()
    try:
        for device_id in device_ids:
            row = conn.execute('SELECT json FROM devices WHERE id=?', (device_id,)).fetchone()
            if not row:
                continue
            device = json.loads(row['json'])
            device['switch'] = switch
            device.setdefault('attributes', {})['switch'] = switch
            updated.append(device)
            conn.execute(
                'UPDATE devices SET json=?, switch=?, updated_at=? WHERE id=?',
                (json.dumps(device), switch, now, device_id),
            )
            conn.execute(
                'INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)',
                (device_id, 'switch', switch, now),
            )
        conn.commit()
    finally:
        conn.close()
    return updated


def update_cached_setpoint(device_id: str, setpoint: float) -> dict[str, Any] | None:
    now = int(time.time())
    conn = db()
    try:
        row = conn.execute('SELECT json FROM devices WHERE id=?', (device_id,)).fetchone()
        if not row:
            return None
        device = json.loads(row['json'])
        device['heatingSetpoint'] = setpoint
        device.setdefault('attributes', {})['heatingSetpoint'] = setpoint
        conn.execute('UPDATE devices SET json=?, updated_at=? WHERE id=?', (json.dumps(device), now, device_id))
        conn.execute(
            'INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)',
            (device_id, 'heatingSetpoint', str(setpoint), now),
        )
        conn.commit()
        return device
    finally:
        conn.close()


def update_cached_level(device_id: str, level: int) -> dict[str, Any] | None:
    now = int(time.time())
    conn = db()
    try:
        row = conn.execute('SELECT json FROM devices WHERE id=?', (device_id,)).fetchone()
        if not row:
            return None
        device = json.loads(row['json'])
        device['level'] = level
        device.setdefault('attributes', {})['level'] = level
        if level > 0:
            device['switch'] = 'on'
            device['attributes']['switch'] = 'on'
        conn.execute(
            'UPDATE devices SET json=?, switch=?, updated_at=? WHERE id=?',
            (json.dumps(device), device.get('switch'), now, device_id),
        )
        conn.execute(
            'INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)',
            (device_id, 'level', str(level), now),
        )
        conn.commit()
        return device
    finally:
        conn.close()


def update_cached_thermostat_mode(device_ids: list[str], mode: str) -> list[dict[str, Any]]:
    now = int(time.time())
    updated: list[dict[str, Any]] = []
    conn = db()
    try:
        for device_id in device_ids:
            row = conn.execute('SELECT json FROM devices WHERE id=?', (device_id,)).fetchone()
            if not row:
                continue
            device = json.loads(row['json'])
            device['thermostatMode'] = mode
            device.setdefault('attributes', {})['thermostatMode'] = mode
            updated.append(device)
            conn.execute('UPDATE devices SET json=?, updated_at=? WHERE id=?', (json.dumps(device), now, device_id))
            conn.execute(
                'INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)',
                (device_id, 'thermostatMode', mode, now),
            )
        conn.commit()
    finally:
        conn.close()
    return updated


def update_cached_attribute(device_id: str, attr: str, value: Any, label: str | None = None) -> dict[str, Any] | None:
    now = int(time.time())
    attr = str(attr or '').strip()
    if not device_id or not attr:
        return None
    conn = db()
    try:
        row = conn.execute('SELECT json, detail_refreshed_at FROM devices WHERE id=?', (str(device_id),)).fetchone()
        if not row:
            return None
        device = json.loads(row['json'])
        if label and not device.get('label'):
            device['label'] = label
        device.setdefault('attributes', {})[attr] = value
        device[attr] = safe_float(value) if attr in ('temperature', 'humidity', 'illuminance', 'power', 'energy', 'battery', 'pressure', 'windSpeed', 'wind_gust', 'windDirection', 'precipitationToday') else value
        normalized = normalise_device(device)
        normalized['capabilities'] = device.get('capabilities', normalized.get('capabilities', []))
        normalized['commands'] = device.get('commands', normalized.get('commands', []))
        normalized['_detail_refreshed_at'] = row['detail_refreshed_at']
        conn.execute('''
            UPDATE devices SET json=?, category=?, switch=?, temperature=?, humidity=?, power=?, energy=?, battery=?, updated_at=?
            WHERE id=?
        ''', (
            json.dumps(normalized), normalized.get('category'), normalized.get('switch'), normalized.get('temperature'),
            normalized.get('humidity'), normalized.get('power'), normalized.get('energy'), normalized.get('battery'),
            now, str(device_id)
        ))
        conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', (str(device_id), attr, str(value), now))
        conn.commit()
        return normalized
    finally:
        conn.close()


def event_records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict):
        for key in ('events', 'content', 'items'):
            if isinstance(payload.get(key), list):
                events = payload[key]
                break
        else:
            events = [payload]
    else:
        return []
    records: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        device_id = event.get('deviceId') or event.get('device_id') or event.get('device') or event.get('id')
        attr = event.get('name') or event.get('attribute') or event.get('attr')
        value = event.get('value')
        label = event.get('displayName') or event.get('label') or event.get('deviceLabel') or event.get('deviceName')
        if device_id and attr:
            records.append({'device_id': str(device_id), 'attr': str(attr), 'value': value, 'label': str(label) if label else None, 'raw': event})
    return records


def record_hubitat_events(payload: Any) -> dict[str, Any]:
    global LAST_HUBITAT_EVENT, STATE_EVENT_VERSION
    now = int(time.time())
    records = event_records_from_payload(payload)
    updated: list[dict[str, Any]] = []
    conn = db()
    try:
        for event in records:
            conn.execute(
                'INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)',
                (event['device_id'], event.get('label'), event['attr'], str(event.get('value')), json.dumps(event['raw']), now),
            )
        conn.commit()
    finally:
        conn.close()
    for event in records:
        device = update_cached_attribute(event['device_id'], event['attr'], event.get('value'), event.get('label'))
        if device:
            updated.append(device)
    LAST_HUBITAT_EVENT = {
        'received_at': now,
        'count': len(records),
        'updated': len(updated),
        'last': records[-1] if records else None,
    }
    if records:
        STATE_EVENT_VERSION += 1
    return {'success': True, 'events': len(records), 'updated': len(updated), 'last_event': LAST_HUBITAT_EVENT, 'devices': updated}


def refresh_devices() -> int:
    global LAST_ERROR, LAST_REFRESH
    try:
        raw = maker_get('devices', timeout=20)
        raw = enrich_raw_devices(raw if isinstance(raw, list) else [])
        devices = [normalise_device(d) for d in raw]
        upsert_devices(devices)
        prune_missing_devices({d['id'] for d in devices})
        LAST_REFRESH = time.time()
        LAST_ERROR = None
        return len(devices)
    except Exception as exc:
        LAST_ERROR = public_error(exc)
        return count_devices()


def rows_to_devices(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [json.loads(r['json']) for r in rows]


def all_devices() -> list[dict[str, Any]]:
    conn = db()
    try:
        return rows_to_devices(conn.execute('SELECT json FROM devices ORDER BY label').fetchall())
    finally:
        conn.close()


def count_devices() -> int:
    conn = db()
    try:
        return int(conn.execute('SELECT COUNT(*) c FROM devices').fetchone()['c'])
    finally:
        conn.close()


def clear_cache() -> None:
    conn = db()
    try:
        conn.execute('DELETE FROM history')
        conn.execute('DELETE FROM devices')
        conn.commit()
    finally:
        conn.close()


def dashboard_summary() -> dict[str, Any]:
    devices = all_devices()
    environment_devices = [d for d in devices if not is_fridge_meter_device(d)]
    lights_on = [d for d in devices if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
    switches_on = [d for d in devices if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on')]
    temps = [d['temperature'] for d in environment_devices if isinstance(d.get('temperature'), (int, float))]
    hums = [d['humidity'] for d in environment_devices if isinstance(d.get('humidity'), (int, float))]
    power_devices = [d for d in devices if isinstance(d.get('power'), (int, float))]
    powers = [d['power'] for d in power_devices]
    power_source = select_power_source(power_devices)
    people = household_people(devices)
    low_batt = [d for d in devices if isinstance(d.get('battery'), (int, float)) and d['battery'] <= 20]
    motion_active = [d for d in devices if is_state(d.get('motion'), 'active')]
    power_total = round(power_source['power'], 1) if power_source else round(sum(powers), 1) if powers else 0
    return {
        'devices': len(devices),
        'lights_on': len(lights_on),
        'switches_on': len(switches_on),
        'avg_temperature': round(sum(temps) / len(temps), 1) if temps else None,
        'avg_humidity': round(sum(hums) / len(hums), 1) if hums else None,
        'power_total': power_total,
        'power_display': format_power_value(power_total),
        'power_source': power_source,
        'power_source_label': power_source['label'] if power_source else 'Octopus meter',
        'power_is_whole_house': bool(power_source),
        'low_batteries': len(low_batt),
        'low_battery_devices': summary_devices(low_batt, 'battery'),
        'motion_active': len(motion_active),
        'active_motion_devices': summary_devices(motion_active, 'motion'),
        'people_home': len([p for p in people if p['status'] == 'present']),
        'people_tracked': len(people),
        'people_home_names': [p['name'] for p in people if p['status'] == 'present'],
        'people': people,
        'last_refresh': LAST_REFRESH,
    }


def device_search_text(device: dict[str, Any]) -> str:
    return ' '.join(
        str(device.get(key, '') or '').lower()
        for key in ('label', 'name', 'room', 'category')
    )


def is_fridge_meter_device(device: dict[str, Any]) -> bool:
    text = device_search_text(device)
    return 'fridge' in text and 'meter' in text


def select_power_source(power_devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    for device in power_devices:
        text = device_search_text(device)
        if any(term in text for term in POWER_SOURCE_TERMS):
            return {
                'id': device.get('id'),
                'label': device.get('label') or device.get('name') or 'Octopus meter',
                'room': device.get('room') or 'Unknown',
                'power': device.get('power'),
            }
    return None


def household_people(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    people = []
    for name in HOUSEHOLD_PEOPLE:
        matches = [d for d in devices if name.lower() in device_search_text(d) and d.get('presence') is not None]
        device = matches[0] if matches else None
        state = state_text(device.get('presence')) if device else ''
        if state == 'present':
            status = 'present'
        elif state in ('not present', 'away', 'absent'):
            status = 'away'
        else:
            status = 'unknown'
        people.append({
            'name': name,
            'status': status,
            'device': device.get('label') if device else None,
        })
    return people


def summary_devices(devices: list[dict[str, Any]], attr: str | None = None) -> list[dict[str, Any]]:
    items = []
    for device in sorted(devices, key=lambda d: d.get('label', ''))[:30]:
        item = {
            'id': device.get('id'),
            'label': device.get('label') or device.get('name') or 'Unknown device',
            'room': device.get('room') or 'Unknown',
        }
        if attr:
            item[attr] = device.get(attr)
        items.append(item)
    return items


def format_power_value(watts: Any) -> str:
    value = safe_float(watts)
    if value is None:
        return '0W'
    if value > 999:
        kw = round(value / 1000, 1)
        kw_text = f'{kw:g}'
        return f'{kw_text}kW'
    watts_text = f'{round(value):g}' if float(value).is_integer() else f'{value:g}'
    return f'{watts_text}W'


def spoken_number(value: Any) -> str:
    if value in (None, ''):
        return 'unknown'
    numeric = safe_float(value)
    if numeric is None:
        return str(value)
    return f'{numeric:g}'


def spoken_degrees(value: Any) -> str:
    return f'{spoken_number(value)} degrees'


def spoken_percent(value: Any) -> str:
    return f'{spoken_number(value)} percent'


def spoken_power_value(watts: Any) -> str:
    value = safe_float(watts)
    if value is None:
        return '0 watts'
    if abs(value) > 999:
        return f'{value / 1000:g} kilowatts'
    amount = round(value)
    unit = 'watt' if amount == 1 else 'watts'
    return f'{amount:g} {unit}'


def format_summary_device(item: dict[str, Any], attr: str | None = None, unit: str = '') -> str:
    detail = ''
    if attr and item.get(attr) is not None:
        detail = f" - {item[attr]}{unit}"
    return f"{item['label']} ({item.get('room') or 'Unknown'}){detail}"


def spoken_list(values: list[str]) -> str:
    clean = [value for value in values if value]
    if not clean:
        return 'None.'
    if len(clean) == 1:
        return f'{clean[0]}.'
    if len(clean) == 2:
        return f'{clean[0]} and {clean[1]}.'
    return f"{', '.join(clean[:-1])}, and {clean[-1]}."


def spoken_device_locations(devices: list[dict[str, Any]]) -> str:
    values: list[str] = []
    for device in devices:
        room = canonical_room_name(device.get('room') or 'Unknown')
        value = room if room != 'Unknown' else str(device.get('label') or device.get('name') or '')
        if value and value not in values:
            values.append(value)
    return spoken_list(values)


def spoken_command_confirmation(labels: list[str], command: str) -> str:
    action = 'turned on' if command == 'on' else 'turned off'
    return spoken_list([f'{label} {action}' for label in labels])


def explain_summary_tile(text: str) -> dict[str, Any] | None:
    summary = dashboard_summary()
    wants_low_battery = 'battery' in text or 'batteries' in text
    wants_motion = 'motion' in text
    wants_people = 'people' in text or 'who is home' in text or any(name.lower() in text for name in HOUSEHOLD_PEOPLE)
    wants_power = 'power' in text or 'octopus' in text or 'meter' in text
    wants_tiles = 'summary tile' in text or 'summary tiles' in text or 'dashboard tile' in text or 'dashboard tiles' in text

    if wants_low_battery:
        devices = summary['low_battery_devices']
        lines = [format_summary_device(d, 'battery', '%') for d in devices]
        message = 'Low battery devices:\n' + ('\n'.join(lines) if lines else 'None')
        return {'success': True, 'intent': 'summary_low_batteries', 'message': message, 'devices': devices}

    if wants_motion:
        devices = summary['active_motion_devices']
        lines = [format_summary_device(d) for d in devices]
        message = 'Active motion sensors:\n' + ('\n'.join(lines) if lines else 'None')
        return {'success': True, 'intent': 'summary_active_motion', 'message': message, 'devices': devices}

    if wants_people:
        names = summary['people_home_names']
        message = 'People home:\n' + ('\n'.join(names) if names else 'None')
        return {'success': True, 'intent': 'summary_people_home', 'message': message, 'people_home': names}

    if wants_power:
        source = summary.get('power_source')
        if source:
            message = f"Power is whole-house live power from {source['label']}: {summary['power_display']}."
            speech = f"Power is whole-house live power from {source['label']}: {spoken_power_value(summary['power_total'])}."
        else:
            message = f"Power is shown as whole-house power, but no Octopus meter device was found. Current value: {summary['power_display']}."
            speech = f"Power is shown as whole-house power, but no Octopus meter device was found. Current value: {spoken_power_value(summary['power_total'])}."
        return {'success': True, 'intent': 'summary_power', 'message': message, 'speech': speech, 'power_source': source}

    if wants_tiles:
        message = (
            f"Summary tiles: {summary['lights_on']} lights on, {summary['switches_on']} switches on, "
            f"{summary['power_display']} whole-house power from {summary['power_source_label']}, "
            f"{summary['people_home']} of {summary['people_tracked']} people home, "
            f"{summary['low_batteries']} low batteries, and {summary['motion_active']} active motion sensors."
        )
        speech = (
            f"Summary tiles: {summary['lights_on']} lights on, {summary['switches_on']} switches on, "
            f"{spoken_power_value(summary['power_total'])} whole-house power from {summary['power_source_label']}, "
            f"{summary['people_home']} of {summary['people_tracked']} people home, "
            f"{summary['low_batteries']} low batteries, and {summary['motion_active']} active motion sensors."
        )
        return {'success': True, 'intent': 'summary_tiles', 'message': message, 'speech': speech, 'summary': summary}

    return None


def device_diagnostics() -> dict[str, Any]:
    devices = all_devices()
    switchable = switchable_devices(devices)
    unknown_switches = [d for d in switchable if d.get('switch') is None]
    no_room = [d for d in devices if (d.get('room') or 'Unknown') == 'Unknown']
    temp_devices = [d for d in devices if isinstance(d.get('temperature'), (int, float))]
    humidity_devices = [d for d in devices if isinstance(d.get('humidity'), (int, float))]
    power_devices = [d for d in devices if isinstance(d.get('power'), (int, float))]
    return {
        'devices': len(devices),
        'switchable': len(switchable),
        'unknown_switch_state': len(unknown_switches),
        'unknown_switch_examples': [d['label'] for d in unknown_switches[:8]],
        'unknown_room': len(no_room),
        'unknown_room_examples': [d['label'] for d in no_room[:8]],
        'temperature_devices': len(temp_devices),
        'humidity_devices': len(humidity_devices),
        'power_devices': len(power_devices),
        'last_error': LAST_ERROR,
        'detail_errors': LAST_DETAIL_ERRORS,
        'last_refresh': LAST_REFRESH,
    }


def active_rooms_answer() -> dict[str, Any]:
    devices = all_devices()
    by_room: dict[str, list[str]] = {}
    active_devices: list[dict[str, Any]] = []
    for device in devices:
        label = str(device.get('label') or device.get('name') or '').strip()
        if not label:
            continue
        active_label = ''
        if is_state(device.get('switch'), 'on'):
            active_label = f'{label} on'
        elif is_state(device.get('motion'), 'active'):
            active_label = f'{label} active'
        elif 'heat' in normalise(device.get('thermostatOperatingState', '')):
            active_label = f'{label} heating'
        if not active_label:
            continue
        room = canonical_room_name(device.get('room') or 'Unknown')
        if room in ('Unknown', 'Life360'):
            continue
        by_room.setdefault(room, []).append(active_label)
        active_devices.append(device)
    lines = [f"{room}: {', '.join(labels)}" for room, labels in sorted(by_room.items())]
    rooms = [{'room': room, 'active_devices': labels, 'active_count': len(labels)} for room, labels in sorted(by_room.items())]
    return {
        'success': True,
        'intent': 'active_rooms',
        'message': 'Active rooms:\n' + ('\n'.join(lines) if lines else 'None'),
        'rooms': rooms,
        'devices': active_devices,
        'speech': spoken_list(lines) if lines else 'No active rooms.',
    }


def cold_rooms_answer() -> dict[str, Any]:
    rooms = [
        room for room in api_rooms()['rooms']
        if isinstance(room.get('avg_temperature'), (int, float)) and room['avg_temperature'] < 18
    ]
    lines = [f"{room['room']}: {room['avg_temperature']}C" for room in rooms]
    return {
        'success': True,
        'intent': 'cold_rooms',
        'message': 'Rooms below 18C:\n' + ('\n'.join(lines) if lines else 'None'),
        'rooms': rooms,
    }


def heating_status_answer() -> dict[str, Any]:
    devices = climate_control_devices(all_devices())
    lines = []
    for device in devices[:20]:
        mode = device.get('thermostatMode') or device.get('attributes', {}).get('thermostatMode') or 'unknown'
        temp = device.get('temperature') or device.get('attributes', {}).get('temperature')
        setpoint = device.get('heatingSetpoint') or device.get('attributes', {}).get('heatingSetpoint')
        detail = f"{device['label']}: mode {mode}"
        if temp is not None:
            detail += f", temp {temp}C"
        if setpoint is not None:
            detail += f", heat set {setpoint}C"
        lines.append(detail)
    return {
        'success': True,
        'intent': 'heating_status',
        'message': 'Heating status:\n' + ('\n'.join(lines) if lines else 'No heating devices found'),
        'devices': devices[:20],
    }


def room_on_status_answer(room: str) -> dict[str, Any]:
    devices = room_devices(room)
    if not devices:
        return {'success': False, 'intent': 'room_on_status', 'message': f'I found no devices in {room}.'}
    lights = [d for d in devices if d.get('category') == 'light' and is_state(d.get('switch'), 'on')]
    switches = [
        d for d in devices
        if d.get('category') != 'light'
        and d.get('switch') is not None
        and is_state(d.get('switch'), 'on')
    ]
    heating = [d for d in climate_control_devices(devices) if 'heat' in normalise(d.get('thermostatOperatingState', ''))]
    lines = []
    if lights:
        lines.append('Lights on:\n' + '\n'.join(d['label'] for d in lights))
    if switches:
        lines.append('Switches on:\n' + '\n'.join(d['label'] for d in switches))
    if heating:
        lines.append('Heating active:\n' + '\n'.join(d['label'] for d in heating))
    active = lights + switches + heating
    room_name = canonical_room_name(room)
    message = f'{room_name} active devices:\n' + ('\n\n'.join(lines) if lines else 'None')
    speech = f"{room_name}: {spoken_list([d['label'] for d in active])}" if active else f'{room_name}: nothing is on.'
    return {'success': True, 'intent': 'room_on_status', 'message': message, 'speech': speech, 'devices': active, 'room': room_name}


def device_health_answer() -> dict[str, Any]:
    summary = dashboard_summary()
    diagnostics = device_diagnostics()
    low_battery = [format_summary_device(d, 'battery', '%') for d in summary['low_battery_devices']]
    lines = [
        f"Devices: {diagnostics['devices']}",
        f"Unknown switch states: {diagnostics['unknown_switch_state']}",
        f"Unknown rooms: {diagnostics['unknown_room']}",
        f"Low batteries: {summary['low_batteries']}",
    ]
    if low_battery:
        lines.append('Low battery devices:\n' + '\n'.join(low_battery))
    if diagnostics['last_error']:
        lines.append(f"Last Hubitat error: {diagnostics['last_error']}")
    return {'success': True, 'intent': 'device_health', 'message': '\n'.join(lines), 'summary': summary, 'diagnostics': diagnostics}


def weather_device() -> dict[str, Any] | None:
    devices = all_devices()
    weather_devices = [
        device for device in devices
        if device.get('category') == 'weather'
        or 'weather' in device_search_text(device)
        or device.get('weatherSummary')
        or device.get('weatherSummaryLine')
        or (device.get('attributes') or {}).get('weatherSummary')
        or (device.get('attributes') or {}).get('weatherSummaryLine')
    ]
    return weather_devices[0] if weather_devices else None


def weather_speech(text: str) -> str:
    speech = str(text or '').strip()
    speech = re.sub(r'(\d+(?:\.\d+)?)C\b', r'\1 degrees', speech)
    speech = re.sub(r'(\d+(?:\.\d+)?)mm\b', r'\1 millimetres', speech)
    speech = re.sub(r'\b0\.00 millimetres\b', '0 millimetres', speech)
    speech = speech.replace('SE13', 'S E 13')
    return speech


def weather_answer() -> dict[str, Any]:
    device = weather_device()
    if not device:
        return {
            'success': False,
            'intent': 'weather',
            'message': 'No weather device found. Add your Hubitat weather device to Maker API, then refresh from Hubitat.',
        }
    attrs = device.get('attributes') or {}
    summary = device.get('weatherSummary') or attrs.get('weatherSummary')
    line = device.get('weatherSummaryLine') or attrs.get('weatherSummaryLine')
    if summary:
        message = str(summary).strip()
    elif line:
        message = str(line).strip()
    else:
        parts = []
        if device.get('temperature') is not None:
            parts.append(f"Current temperature {device['temperature']}C")
        if device.get('humidity') is not None:
            parts.append(f"Humidity {device['humidity']}%")
        if device.get('precipitationToday') is not None:
            parts.append(f"Precipitation today {device['precipitationToday']}mm")
        if device.get('windSpeed') is not None:
            parts.append(f"Wind speed {device['windSpeed']}")
        message = ', '.join(parts) if parts else f"{device['label']} has no weather summary yet."
    return {
        'success': True,
        'intent': 'weather',
        'message': message,
        'speech': weather_speech(message),
        'device': device,
    }


def log_source_url() -> str:
    configured_url = str(CONFIG.get('hubitat_logs_url') or '').strip()
    if configured_url:
        return hubitat_url(configured_url)
    return hubitat_url(str(CONFIG.get('hubitat_logs_path') or '/logs/past'))


def normalize_log_entry(entry: Any) -> dict[str, str]:
    if isinstance(entry, dict):
        level = str(entry.get('level') or entry.get('type') or entry.get('severity') or '').strip()
        name = str(entry.get('name') or entry.get('device') or entry.get('app') or '').strip()
        message = str(entry.get('msg') or entry.get('message') or entry.get('description') or entry.get('text') or entry).strip()
        timestamp = str(entry.get('time') or entry.get('date') or entry.get('timestamp') or '').strip()
    else:
        text = str(entry).strip()
        match = re.match(r'^(?:(\S+\s+\S+)\s+)?(?:\[(\w+)\]|\b(debug|info|warn|warning|error)\b)?\s*(.*)$', text, re.I)
        timestamp = (match.group(1) or '').strip() if match else ''
        level = next((group for group in (match.group(2), match.group(3)) if group), '') if match else ''
        name = ''
        message = (match.group(4) or text).strip() if match else text
    level = {'warning': 'warn'}.get(level.lower(), level.lower())
    return {'time': timestamp, 'level': level or 'info', 'name': name, 'message': redact_sensitive(message)}


def parse_logs_payload(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        for key in ('logs', 'events', 'items', 'data'):
            if isinstance(payload.get(key), list):
                return [normalize_log_entry(item) for item in payload[key]]
        return [normalize_log_entry(payload)]
    if isinstance(payload, list):
        return [normalize_log_entry(item) for item in payload]
    text = str(payload or '')
    return [normalize_log_entry(line) for line in text.splitlines() if line.strip()]


def fetch_hub_logs(limit: int = 120) -> list[dict[str, str]]:
    response = requests.get(log_source_url(), timeout=12)
    response.raise_for_status()
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return parse_logs_payload(payload)[:limit]


def hub_logs_diagnostics(limit: int = 120) -> dict[str, Any]:
    logs = fetch_hub_logs(limit)
    problem_terms = ('error', 'warn', 'warning', 'exception', 'failed', 'timeout', 'not found')
    problem_logs = [
        log for log in logs
        if log.get('level') in ('error', 'warn')
        or any(term in log.get('message', '').lower() for term in problem_terms)
    ]
    labels = [device.get('label') or device.get('name') for device in all_devices()]
    affected: dict[str, int] = {}
    for log in problem_logs:
        text = normalise(log.get('name', '') + ' ' + log.get('message', ''))
        for label in labels:
            if label and normalise(label) in text:
                affected[label] = affected.get(label, 0) + 1
    return {
        'logs': logs,
        'total': len(logs),
        'problems': problem_logs,
        'affected_devices': sorted(affected.items(), key=lambda item: item[1], reverse=True)[:8],
        'errors': len([log for log in problem_logs if log.get('level') == 'error' or 'error' in log.get('message', '').lower()]),
        'warnings': len([log for log in problem_logs if log.get('level') == 'warn' or 'warn' in log.get('message', '').lower()]),
    }


def hub_logs_answer() -> dict[str, Any]:
    try:
        diagnostics = hub_logs_diagnostics()
    except Exception as exc:
        hint = (
            'Set hubitat_logs_path or hubitat_logs_url in the add-on options if your hub exposes logs at a different endpoint.'
        )
        return {'success': False, 'intent': 'hub_logs', 'message': f'Hub logs unavailable: {public_error(exc)}\n{hint}'}
    lines = [
        f"Hub logs checked: {diagnostics['total']} entries",
        f"Warnings: {diagnostics['warnings']}",
        f"Errors: {diagnostics['errors']}",
    ]
    if diagnostics['affected_devices']:
        lines.append('Likely affected devices:\n' + '\n'.join(f"{label}: {count}" for label, count in diagnostics['affected_devices']))
    if diagnostics['problems']:
        lines.append('Recent issues:\n' + '\n'.join(log['message'] for log in diagnostics['problems'][:8]))
    else:
        lines.append('No warnings or errors found in the recent logs.')
    speech = f"Hub logs checked. {diagnostics['warnings']} warnings and {diagnostics['errors']} errors found."
    return {'success': True, 'intent': 'hub_logs', 'message': '\n'.join(lines), 'speech': speech, 'diagnostics': diagnostics}


def metric_value(device: dict[str, Any], exact_names: tuple[str, ...], contains: tuple[str, ...] = ()) -> Any:
    attrs: dict[str, Any] = {}
    attrs.update(device.get('attributes') or {})
    for key, value in device.items():
        if key not in ('attributes', 'capabilities', 'commands'):
            attrs[key] = value
    normalized = {compact_name(key): value for key, value in attrs.items()}
    for name in exact_names:
        key = compact_name(name)
        if key in normalized and normalized[key] is not None:
            return normalized[key]
    if contains:
        for key, value in normalized.items():
            if value is not None and all(part in key for part in contains):
                return value
    return None


def hub_info_rows(device: dict[str, Any]) -> dict[str, str]:
    attrs: dict[str, Any] = {}
    attrs.update(device.get('attributes') or {})
    for key, value in device.items():
        if key not in ('attributes', 'capabilities', 'commands'):
            attrs[key] = value
    rows: dict[str, str] = {}
    for value in attrs.values():
        if not isinstance(value, str):
            continue
        text = value
        if '<' in text and '>' in text:
            text = re.sub(r'(?i)<br\s*/?>', '\n', text)
            text = re.sub(r'(?i)</(?:tr|p|div|li)>', '\n', text)
            text = re.sub(r'(?i)</t[dh]>\s*<t[dh][^>]*>', ' : ', text)
            text = re.sub(r'<[^>]+>', ' ', text)
        text = text.replace('&nbsp;', ' ')
        for line in text.splitlines():
            line = re.sub(r'\s+', ' ', line).strip()
            match = re.match(r'^(.+?)\s*(?:[:=]| {2,})\s*(.+)$', line)
            if match:
                rows[compact_name(match.group(1))] = match.group(2).strip()
    return rows


def hub_metric(device: dict[str, Any], labels: tuple[str, ...], contains: tuple[str, ...] = ()) -> Any:
    rows = hub_info_rows(device)
    for label in labels:
        key = compact_name(label)
        if key in rows:
            return rows[key]
    if contains:
        for key, row_value in rows.items():
            if all(part in key for part in contains):
                return row_value
    value = metric_value(device, labels, contains)
    if value is not None:
        return value
    return None


def hub_info_device() -> dict[str, Any] | None:
    return next((d for d in all_devices() if 'hub info' in device_search_text(d)), None)


def hub_health_metrics(hub: dict[str, Any]) -> dict[str, Any]:
    return {
        'CPU load': hub_metric(hub, ('cpu', 'cpuLoad', 'cpuLoadLoad%', 'cpuPct', 'cpuPercent', 'cpu5Min', 'cpuLoad5Min'), ('cpu',)),
        'Free memory': hub_metric(hub, ('freeMemory', 'freeMemoryMb', 'freeMem', 'freeMemMb', 'memoryFree', 'availableMemory'), ('free', 'mem')),
        'DB size': hub_metric(hub, ('dbSize', 'databaseSize', 'database'), ('db', 'size')),
        'Last restart': hub_metric(hub, ('lastRestart', 'lastHubRestart'), ('last', 'restart')),
        'Uptime': hub_metric(hub, ('uptime', 'hubUptime'), ('uptime',)),
        'Temperature': hub_metric(hub, ('temperature', 'hubTemperature'), ('temperature',)),
    }


def number_values(value: Any) -> list[float]:
    return [float(match) for match in re.findall(r'\d+(?:\.\d+)?', str(value or ''))]


def cpu_percent(value: Any) -> float | None:
    values = number_values(value)
    if not values:
        return None
    return values[-1] if '/' in str(value) else values[0]


def memory_mb(value: Any) -> float | None:
    values = number_values(value)
    if not values:
        return None
    amount = values[0]
    text = str(value).lower()
    if 'gb' in text:
        return amount * 1000
    if 'kb' in text:
        return amount / 1024
    if amount < 16:
        return amount * 1000
    return amount


def format_memory(value_mb: float) -> str:
    if value_mb >= 1000:
        gb = f"{value_mb / 1000:.2f}".rstrip('0').rstrip('.')
        return f"{gb}GB"
    return f"{value_mb:g}MB"


def format_uptime(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return text
    if re.fullmatch(r'\d+(?:\.\d+)?', text):
        total_seconds = int(float(text))
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        if minutes or hours or days:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return ' '.join(parts)
    match = re.fullmatch(r'(?:(\d+)d:)?(?:(\d+)h:)?(?:(\d+)m:)?(\d+)s', text)
    if match:
        days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
        return format_uptime(days * 86400 + hours * 3600 + minutes * 60 + seconds)
    return text


def format_restart(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return text
    if re.fullmatch(r'\d+(?:\.\d+)?', text):
        timestamp = float(text)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp).strftime('%d %b %Y %H:%M')
    match = re.fullmatch(r'(\d{1,2})([A-Za-z]{3})(\d{4})\s+(\d{1,2}:\d{2})', text)
    if match:
        day, month, year, clock = match.groups()
        return f"{int(day):02d} {month.title()} {year} {clock}"
    return text


def hub_health_display_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    display = dict(metrics)
    free_mb = memory_mb(metrics.get('Free memory'))
    if free_mb is not None:
        display['Free memory'] = format_memory(free_mb)
    if metrics.get('Last restart') is not None:
        display['Last restart'] = format_restart(metrics.get('Last restart'))
    if metrics.get('Uptime') is not None:
        display['Uptime'] = format_uptime(metrics.get('Uptime'))
    return display


def hub_health_summary() -> dict[str, Any]:
    hub = hub_info_device()
    if not hub:
        return {'available': False, 'level': 'unknown', 'label': 'Hub health unavailable'}
    metrics = hub_health_metrics(hub)
    cpu = cpu_percent(metrics.get('CPU load'))
    free_mb = memory_mb(metrics.get('Free memory'))
    level = 'ok'
    if (cpu is not None and cpu >= 80) or (free_mb is not None and free_mb < 256):
        level = 'error'
    elif (cpu is not None and cpu >= 60) or (free_mb is not None and free_mb < 512):
        level = 'warning'
    parts = []
    if cpu is not None:
        parts.append(f"Hub CPU {cpu:g}%")
    if free_mb is not None:
        parts.append(f"Free {format_memory(free_mb)}")
    label = ' · '.join(parts) if parts else 'Hub health available'
    return {
        'available': True,
        'level': level,
        'label': label,
        'cpu_load_percent': cpu,
        'free_memory_mb': free_mb,
        'metrics': metrics,
        'display_metrics': hub_health_display_metrics(metrics),
    }


def hub_health_answer() -> dict[str, Any]:
    hub = hub_info_device()
    if not hub:
        return {
            'success': False,
            'intent': 'hub_health',
            'message': 'No Hub Info device found. Add or expose the Hub Info device from Hubitat, then refresh from Hubitat.',
        }
    metrics = hub_health_metrics(hub)
    display_metrics = hub_health_display_metrics(metrics)
    lines = [f"{label}: {value}" for label, value in display_metrics.items() if value is not None]
    if not lines:
        available = ', '.join(sorted(str(k) for k in (hub.get('attributes') or {}).keys()))
        detail = f" Available attributes: {available}" if available else ''
        message = f"Hub Info was found, but CPU/free-memory attributes were not available.{detail}"
    else:
        message = f"Hub health from {hub.get('label') or hub.get('name') or 'Hub Info'}:\n" + '\n'.join(lines)
    return {'success': True, 'intent': 'hub_health', 'message': message, 'device': hub, 'metrics': metrics, 'display_metrics': display_metrics}


def normalise(text: Any) -> str:
    text = str(text or '').lower().strip()
    replacements = {
        'turn of': 'turn off', 'switch of': 'switch off', 'the humidifier': 'dehumidifier',
        'de humidifier': 'dehumidifier', 'humidifier': 'dehumidifier', 'ligth': 'light',
        'lite': 'light', 'livingroom': 'living room', 'one': '1', 'two': '2', 'three': '3',
        'de humidifer': 'dehumidifier', 'dehumidifer': 'dehumidifier', 'purifer': 'purifier',
        'purifyer': 'purifier', 'air purify': 'air purifier', 'bath room': 'bathroom',
    }
    for a, b in replacements.items():
        text = re.sub(rf'\b{re.escape(a)}\b', b, text)
    text = re.sub(r'[^\w\s%-]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def command_target_text(text: str) -> str:
    target = normalise(text)
    target = re.sub(r'\b(?:please|can you|could you|would you)\b', ' ', target)
    target = re.sub(r'\b(?:the|a|an|my)\b', ' ', target)
    target = re.sub(r'\b(?:to|too|for|in|on|off)\s*$', ' ', target)
    return re.sub(r'\s+', ' ', target).strip()


def device_match_text(device: dict[str, Any]) -> str:
    parts = [
        device.get('label', ''),
        device.get('name', ''),
        device.get('room', ''),
        device.get('category', ''),
        ' '.join(device.get('capabilities', []) or []),
        ' '.join(device.get('commands', []) or []),
    ]
    attrs = device.get('attributes') or {}
    parts.extend(str(key) for key in attrs.keys())
    if is_room_socket_device(device):
        parts.append('socket plug appliance')
    if is_level_device(device):
        parts.append('dimmer brightness level')
    if is_switchable_device(device):
        parts.append('switch on off')
    return command_target_text(' '.join(str(part or '') for part in parts))


def targeted_devices(query: str, category: str | None = None, room: str | None = None) -> list[dict[str, Any]]:
    q = command_target_text(query)
    room_q = command_target_text(room or '')
    if not q and not room_q:
        return []
    devices = all_devices()
    if category:
        devices = [d for d in devices if d['category'] == category]
    if room_q:
        room_matches = [
            d for d in devices
            if room_q in command_target_text(d.get('room', '')) or room_q in command_target_text(d.get('label', ''))
        ]
        if room_matches:
            devices = room_matches
    scored: list[tuple[int, dict[str, Any]]] = []
    query_words = set(q.split())
    for device in devices:
        label = command_target_text(device.get('label', ''))
        name = command_target_text(device.get('name', ''))
        haystack = device_match_text(device)
        score = 0
        if q and (q == label or q == name):
            score += 100
        if q and (q in label or q in name):
            score += 80
        if q and q in haystack:
            score += 45
        if query_words:
            score += 10 * len(query_words & set(haystack.split()))
        if room_q:
            score += 25
        if score:
            scored.append((score, device))
    if not scored:
        labels = {command_target_text(d.get('label', '')): d for d in devices}
        match = get_close_matches(q, list(labels.keys()), n=1, cutoff=0.55)
        return [labels[match[0]]] if match else []
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][0]
    return [device for score, device in scored if score == best]


def find_devices(query: str, category: str | None = None) -> list[dict[str, Any]]:
    q = normalise(query)
    if not q:
        return []
    devices = all_devices()
    if category:
        devices = [d for d in devices if d['category'] == category]
    direct = [d for d in devices if q in normalise(d['label']) or q in normalise(d['name']) or q == normalise(d.get('room',''))]
    if direct:
        return direct
    query_words = set(q.split())
    scored: list[tuple[int, dict[str, Any]]] = []
    for d in devices:
        haystack = ' '.join([normalise(d.get('label', '')), normalise(d.get('name', '')), normalise(d.get('room', ''))])
        hay_words = set(haystack.split())
        score = len(query_words & hay_words)
        if score:
            scored.append((score, d))
    if scored:
        best = max(score for score, _ in scored)
        return [d for score, d in scored if score == best]
    labels = {normalise(d['label']): d for d in devices}
    match = get_close_matches(q, list(labels.keys()), n=1, cutoff=0.55)
    return [labels[match[0]]] if match else []


def room_devices(room: str, category: str | None = None) -> list[dict[str, Any]]:
    room_n = normalise(room)
    generic_targets = {'', 'all', 'any', 'home', 'house', 'everything', 'device', 'devices', 'light', 'lights', 'switch', 'switches'}
    if room_n in generic_targets:
        return []
    devices = [d for d in all_devices() if room_n in normalise(d.get('room','')) or room_n in normalise(d.get('label',''))]
    if category:
        devices = [d for d in devices if d['category'] == category]
    return devices


def maker_command(device_id: str, command: str) -> Any:
    response = requests.get(maker_url(f'devices/{device_id}/{command}'), timeout=10)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return {'success': True}


def maker_command_value(device_id: str, command: str, value: Any) -> Any:
    response = requests.get(maker_url(f'devices/{device_id}/{command}/{quote(str(value), safe="")}'), timeout=10)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return {'success': True}


def device_line(device: dict[str, Any]) -> str:
    parts = [device['label'], f"room {device.get('room') or 'Unknown'}", device['category']]
    for attr, unit in (('switch', ''), ('level', '%'), ('temperature', 'C'), ('humidity', '%'), ('illuminance', ' lux'), ('power', 'W'), ('energy', 'kWh'), ('battery', '%'), ('motion', ''), ('contact', ''), ('presence', ''), ('lock', ''), ('water', ''), ('valve', '')):
        value = device.get(attr)
        if value is not None:
            parts.append(f"{attr} {value}{unit}")
    return ' - ' + ', '.join(parts)


def exact_room_devices(room: str) -> list[dict[str, Any]]:
    room_name = canonical_room_name(room)
    return [d for d in all_devices() if canonical_room_name(d.get('room') or 'Unknown') == room_name]


def room_visible_signals(room: dict[str, Any]) -> list[str]:
    signals = []
    if room.get('lights_total'):
        signals.append('lights')
    if room.get('switches_total'):
        signals.append('sockets' if room.get('sockets_total') else 'switches')
    if room.get('motion_total'):
        signals.append('motion')
    if room.get('avg_temperature') is not None:
        signals.append('temperature')
    if room.get('avg_humidity') is not None:
        signals.append('humidity')
    if room.get('power_devices'):
        signals.append('power')
    return signals


def room_detail_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = {}
    for attr in ('switch', 'level', 'temperature', 'humidity', 'illuminance', 'power', 'energy', 'battery', 'motion', 'presence', 'contact', 'thermostatMode', 'thermostatOperatingState', 'heatingSetpoint'):
        value = device.get(attr)
        if value is not None:
            attrs[attr] = value
    return {
        'id': device.get('id'),
        'label': device.get('label') or device.get('name') or 'Unknown device',
        'room': device.get('room') or 'Unknown',
        'category': device.get('category') or 'device',
        'attributes': attrs,
        'capabilities': device.get('capabilities') or [],
    }


def room_explanation(summary: dict[str, Any], devices: list[dict[str, Any]]) -> str:
    signals = room_visible_signals(summary)
    lines = [f"{summary['room']}: {summary['devices']} devices"]
    if signals:
        lines.append('Signals: ' + ', '.join(signals))
    else:
        lines.append('No summarized signals yet')
    if summary.get('lights_total'):
        lines.append(f"Lights: {summary['lights_on']} of {summary['lights_total']} on")
    if summary.get('motion_total'):
        lines.append(f"Motion: {summary['motion_active']} of {summary['motion_total']} active")
    if summary.get('sockets_total'):
        lines.append(f"Sockets: {summary['sockets_on']} of {summary['sockets_total']} on")
    elif summary.get('switches_total'):
        lines.append(f"Switches: {summary['switches_on']} of {summary['switches_total']} on")
    if summary.get('avg_temperature') is not None:
        lines.append(f"Temperature: {summary['avg_temperature']}C")
    if summary.get('avg_humidity') is not None:
        lines.append(f"Humidity: {summary['avg_humidity']}%")
    if summary.get('power_devices'):
        lines.append(f"Power: {format_power_value(summary.get('power_total'))}")
    device_labels = ', '.join((d.get('label') or d.get('name') or 'Unknown device') for d in devices[:6])
    if device_labels:
        suffix = '' if len(devices) <= 6 else f", +{len(devices) - 6} more"
        lines.append('Includes: ' + device_labels + suffix)
    return '\n'.join(lines)


def room_details_payload(room: str) -> dict[str, Any]:
    room_name = canonical_room_name(room)
    summaries = api_rooms()['rooms']
    summary = next((item for item in summaries if normalise(item.get('room')) == normalise(room_name)), None)
    if not summary:
        raise HTTPException(status_code=404, detail='Room not found.')
    devices = exact_room_devices(summary['room'])
    detail_devices = [room_detail_device(device) for device in sorted(devices, key=lambda d: normalise(d.get('label') or d.get('name') or ''))]
    return {
        'success': True,
        'room': summary,
        'visible_signals': room_visible_signals(summary),
        'explanation': room_explanation(summary, devices),
        'devices': detail_devices,
    }


def room_details_answer(text: str) -> dict[str, Any] | None:
    if not any(word in text for word in ('explain', 'detail', 'details', 'why', 'show')):
        return None
    for room in api_rooms()['rooms']:
        if normalise(room['room']) in text:
            payload = room_details_payload(room['room'])
            return {
                'success': True,
                'intent': 'room_details',
                'message': payload['explanation'],
                'room': payload['room'],
                'devices': payload['devices'],
                'visible_signals': payload['visible_signals'],
            }
    return None


def is_switchable_device(device: dict[str, Any]) -> bool:
    label = normalise(device.get('label', '') + ' ' + device.get('name', ''))
    caps = ' '.join(device.get('capabilities', []) or []).lower()
    commands = {str(command).lower() for command in device.get('commands', []) or []}
    category = device.get('category')
    sensor_categories = {'light_sensor', 'climate_sensor', 'motion_sensor', 'contact_sensor', 'presence_sensor', 'thermostat'}
    sensor_words = ('sensor', 'meter', 'lux', 'camera', 'cam', 'contact', 'motion', 'temperature', 'humidity')
    switch_capable = 'switch' in caps or category in ('light', 'switch', 'power_device')
    explicit_switch = switch_capable or {'on', 'off'}.issubset(commands)
    if category in sensor_categories and not explicit_switch:
        return False
    if category == 'thermostat' and not switch_capable:
        return False
    if any(word in label for word in sensor_words) and not explicit_switch:
        return False
    controllable_words = ('light', 'dimmer', 'plug', 'socket', 'outlet', 'switch', 'fan', 'dehumidifier', 'humidifier', 'purifier')
    return (
        explicit_switch
        or category in ('light', 'switch', 'power_device')
        or any(word in label for word in controllable_words)
    )


def is_room_socket_device(device: dict[str, Any]) -> bool:
    if device.get('category') == 'light':
        return False
    text = normalise(device_search_text(device))
    socket_words = ('socket', 'plug', 'outlet', 'meter', 'power', 'energy', 'sockets')
    appliance_words = ('app', 'apps', 'appliance', 'appliances', 'multimedia', 'dehumidifier', 'humidifier', 'purifier', 'fan', 'pc', 'mesh', 'fridge')
    return (
        device.get('category') == 'power_device'
        or isinstance(device.get('power'), (int, float))
        or any(word in text for word in socket_words + appliance_words)
    )


def is_room_switch_device(device: dict[str, Any]) -> bool:
    if device.get('category') == 'light':
        return False
    caps = caps_text(device)
    commands = commands_text(device)
    return (
        device.get('switch') is not None
        or device.get('category') == 'switch'
        or 'switch' in caps
        or {'on', 'off'}.issubset(commands)
    )


def is_room_motion_device(device: dict[str, Any]) -> bool:
    return (
        device.get('category') == 'motion_sensor'
        or device.get('motion') is not None
        or 'motionsensor' in caps_text(device)
        or 'motion' in device.get('attributes', {})
    )


def switchable_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in devices if is_switchable_device(d)]


def is_level_device(device: dict[str, Any]) -> bool:
    label = normalise(device.get('label', '') + ' ' + device.get('name', ''))
    caps = caps_text(device)
    commands = commands_text(device)
    return (
        device.get('level') is not None
        or device.get('category') == 'light'
        or 'setlevel' in commands
        or 'switchlevel' in caps
        or 'dimmer' in label
    )


def level_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in devices if is_level_device(d)]


def is_climate_control_device(device: dict[str, Any]) -> bool:
    label = normalise(device.get('label', ''))
    sensor_words = ('battery', 'sensor', 'meter', 'lux', 'power')
    if any(word in label for word in sensor_words):
        return False
    has_climate_state = (
        device.get('category') == 'thermostat'
        or device.get('thermostatMode') is not None
        or device.get('heatingSetpoint') is not None
        or device.get('thermostatOperatingState') is not None
    )
    if not has_climate_state:
        return False
    return True


def climate_control_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in devices if is_climate_control_device(d)]


def is_controllable_active(device: dict[str, Any]) -> bool:
    if is_climate_control_device(device):
        return 'heat' in normalise(device.get('thermostatOperatingState', ''))
    return normalise(device.get('switch', '')) == 'on'


def controllable_sort_key(device: dict[str, Any]) -> tuple[int, str]:
    label = normalise(device.get('label') or device.get('name') or '')
    return (0 if is_controllable_active(device) else 1, label)


def controllable_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    for device in switchable_devices(devices) + climate_control_devices(devices):
        controls[device['id']] = device
    return sorted(controls.values(), key=controllable_sort_key)


def command_devices(devices: list[dict[str, Any]], command: str, explicit_bulk: bool = False) -> dict[str, Any]:
    candidates = [d for d in switchable_devices(devices) if d.get('category') != 'thermostat']
    if not candidates:
        labels = [d['label'] for d in devices[:5]]
        suffix = '\nMatched: ' + '\n'.join(labels) if labels else ''
        return {'success': False, 'message': 'No switchable devices found.' + suffix, 'matched': labels}
    max_devices = 50 if explicit_bulk else 10
    if len(candidates) > max_devices:
        return {
            'success': False,
            'message': (
                f'Matched {len(candidates)} devices. Narrow the target or use an explicit all-room/all-device command.'
            ),
            'matched': [d['label'] for d in candidates[:20]],
        }
    if len(candidates) > 1 and not explicit_bulk:
        return disambiguation_response(candidates, 'control')
    changed = []
    errors = []
    for d in candidates:
        try:
            maker_command(d['id'], command)
            changed.append(d['label'])
        except Exception as exc:
            errors.append(f"{d['label']}: {public_error(exc)}")
    refresh_devices()
    if changed:
        updated = update_cached_switch([d['id'] for d in candidates if d['label'] in changed], command)
        message = f"Turned {command}:\n" + '\n'.join(changed)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
        return {'success': True, 'message': message, 'speech': spoken_command_confirmation(changed, command), 'changed': changed, 'errors': errors, 'devices': updated}
    return {'success': False, 'message': 'Hubitat command failed:\n' + '\n'.join(errors), 'errors': errors}


def resolve_switch_target(target: str) -> tuple[list[dict[str, Any]], bool, str | None]:
    target = command_target_text(target)
    explicit_bulk = target in ('all lights', 'all light', 'all switches', 'all switch', 'all devices')
    if target in ('lights', 'light', 'switches', 'switch', 'devices', 'device'):
        return [], explicit_bulk, f"Please specify a room/device, or say 'all {target}' if you mean the whole home."
    if target in ('all lights', 'all light'):
        return [d for d in all_devices() if d.get('category') == 'light'], explicit_bulk, None
    if target in ('all switches', 'all switch'):
        return [d for d in all_devices() if d.get('category') != 'light' and d.get('switch') is not None], explicit_bulk, None
    if target == 'all devices':
        return switchable_devices(all_devices()), explicit_bulk, None
    m_room_target = re.search(r'^(.+?)\s+(?:in|inside|for)\s+(.+)$', target)
    if m_room_target:
        device_target, room = m_room_target.group(1).strip(), m_room_target.group(2).strip()
        plural_or_group = bool(re.search(r'\b(all|lights|switches|devices)\b', device_target))
        category = 'light' if re.search(r'\blights?\b', device_target) else None
        cleaned_target = device_target.replace('lights', '').replace('light', '').replace('switches', '').replace('switch', '').strip()
        devices = targeted_devices(cleaned_target or device_target, category, room)
        if not devices and category == 'light':
            devices = room_devices(room, 'light')
        return devices, plural_or_group or explicit_bulk, None
    if re.search(r'\b(all\s+)?(.+\s+)?lights$', target):
        room = target.replace('lights', '').replace('light', '').replace('all ', '').strip()
        return room_devices(room, 'light'), True, None
    if target.endswith(' light'):
        devices = find_devices(target, 'light')
        if not devices:
            room = target.removesuffix(' light').strip()
            devices = room_devices(room, 'light')
        return devices, explicit_bulk, None
    devices = targeted_devices(target) or find_devices(target)
    if not devices and not re.search(r'\b(light|switch|plug|socket|dimmer|lamp)\s+\d+$', target):
        devices = room_devices(target)
    return devices, explicit_bulk, None


def duration_seconds(amount: str, unit: str) -> int:
    value = float(amount)
    unit_n = normalise(unit)
    if unit_n.startswith('sec'):
        return max(1, int(value))
    if unit_n.startswith('hour') or unit_n in ('hr', 'hrs'):
        return max(1, int(value * 3600))
    return max(1, int(value * 60))


def duration_label(seconds: int) -> str:
    if seconds % 3600 == 0 and seconds >= 3600:
        hours = seconds // 3600
        return f"{hours} hour" + ('' if hours == 1 else 's')
    if seconds % 60 == 0 and seconds >= 60:
        minutes = seconds // 60
        return f"{minutes} minute" + ('' if minutes == 1 else 's')
    return f"{seconds} second" + ('' if seconds == 1 else 's')


def timer_payload(record: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    due_at = float(record.get('due_at') or 0)
    return {
        'id': record.get('id'),
        'device_ids': list(record.get('device_ids') or []),
        'labels': list(record.get('labels') or []),
        'command': record.get('command'),
        'due_at': due_at,
        'created_at': record.get('created_at'),
        'seconds_remaining': max(0, int(due_at - now)),
        'duration_remaining': duration_label(max(0, int(due_at - now))),
    }


def save_timer_record(record: dict[str, Any]) -> None:
    conn = db()
    try:
        conn.execute(
            '''
            INSERT OR REPLACE INTO device_timers(id, device_ids, labels, command, due_at, created_at, status)
            VALUES(?,?,?,?,?,?,?)
            ''',
            (
                record['id'],
                json.dumps(record['device_ids']),
                json.dumps(record['labels']),
                record['command'],
                float(record['due_at']),
                float(record.get('created_at') or time.time()),
                record.get('status', 'pending'),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def pending_timer_records() -> list[dict[str, Any]]:
    conn = db()
    try:
        rows = conn.execute(
            "SELECT id, device_ids, labels, command, due_at, created_at FROM device_timers WHERE status='pending' ORDER BY due_at"
        ).fetchall()
    finally:
        conn.close()
    records = []
    for row in rows:
        records.append({
            'id': row['id'],
            'device_ids': json.loads(row['device_ids']),
            'labels': json.loads(row['labels']),
            'command': row['command'],
            'due_at': row['due_at'],
            'created_at': row['created_at'],
        })
    return records


def mark_timer_status(timer_id: str, status: str) -> bool:
    conn = db()
    try:
        cursor = conn.execute('UPDATE device_timers SET status=? WHERE id=? AND status=?', (status, timer_id, 'pending'))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def register_timer(record: dict[str, Any]) -> dict[str, Any]:
    timer_id = str(record['id'])
    existing = ACTIVE_TIMER_THREADS.pop(timer_id, None)
    if existing:
        existing.cancel()
    seconds = max(1, int(float(record['due_at']) - time.time()))
    timer = threading.Timer(seconds, delayed_device_command, args=(timer_id, record['device_ids'], record['command']))
    timer.daemon = True
    ACTIVE_TIMER_THREADS[timer_id] = timer
    PENDING_DEVICE_TIMERS[timer_id] = timer_payload(record)
    timer.start()
    return PENDING_DEVICE_TIMERS[timer_id]


def delayed_device_command(timer_id: str, device_ids: list[str], command: str) -> None:
    try:
        for device_id in device_ids:
            try:
                maker_command(device_id, command)
            except Exception:
                continue
        refresh_devices()
        update_cached_switch(device_ids, command)
    finally:
        mark_timer_status(timer_id, 'done')
        ACTIVE_TIMER_THREADS.pop(timer_id, None)
        PENDING_DEVICE_TIMERS.pop(timer_id, None)


def schedule_delayed_command(device_ids: list[str], command: str, seconds: int, labels: list[str]) -> dict[str, Any]:
    now = time.time()
    timer_id = f"{int(now)}-{'-'.join(device_ids)}-{command}"
    record = {
        'id': timer_id,
        'device_ids': device_ids,
        'labels': labels,
        'command': command,
        'due_at': now + seconds,
        'created_at': now,
        'status': 'pending',
    }
    save_timer_record(record)
    return register_timer(record)


def restore_pending_timers() -> None:
    now = time.time()
    for record in pending_timer_records():
        if float(record['due_at']) <= now:
            threading.Thread(
                target=delayed_device_command,
                args=(record['id'], record['device_ids'], record['command']),
                daemon=True,
            ).start()
        elif record['id'] not in ACTIVE_TIMER_THREADS:
            register_timer(record)


def cancel_timer(timer_id: str) -> dict[str, Any]:
    timer = ACTIVE_TIMER_THREADS.pop(timer_id, None)
    if timer:
        timer.cancel()
    PENDING_DEVICE_TIMERS.pop(timer_id, None)
    if not mark_timer_status(timer_id, 'cancelled') and timer is None:
        return {'success': False, 'message': 'Timer not found or already completed.'}
    return {'success': True, 'message': 'Timer cancelled.'}


def timed_command_devices(devices: list[dict[str, Any]], command: str, seconds: int, explicit_bulk: bool = False) -> dict[str, Any]:
    result = command_devices(devices, command, explicit_bulk=explicit_bulk)
    if not result.get('success'):
        return result
    changed = result.get('changed', [])
    device_ids = [d['id'] for d in switchable_devices(devices) if d['label'] in changed]
    if command == 'on' and device_ids:
        timer = schedule_delayed_command(device_ids, 'off', seconds, changed)
        label = duration_label(seconds)
        result['message'] += f"\n\nScheduled off in {label}."
        result['speech'] = f"{spoken_command_confirmation(changed, command)} I will turn it off in {label}."
        result['timer'] = timer
    return result


def scheduled_command_devices(devices: list[dict[str, Any]], command: str, seconds: int, explicit_bulk: bool = False) -> dict[str, Any]:
    candidates = [d for d in switchable_devices(devices) if d.get('category') != 'thermostat']
    if not candidates:
        labels = [d['label'] for d in devices[:5]]
        suffix = '\nMatched: ' + '\n'.join(labels) if labels else ''
        return {'success': False, 'message': 'No switchable devices found.' + suffix, 'matched': labels}
    if len(candidates) > 1 and not explicit_bulk:
        return disambiguation_response(candidates, 'schedule')
    labels = [d['label'] for d in candidates]
    timer = schedule_delayed_command([d['id'] for d in candidates], command, seconds, labels)
    label = duration_label(seconds)
    message = f"Scheduled {command} in {label}:\n" + '\n'.join(labels)
    return {
        'success': True,
        'intent': 'scheduled_command',
        'message': message,
        'speech': f"{spoken_command_confirmation(labels, command)} scheduled in {label}.",
        'changed': labels,
        'timer': timer,
    }


def disambiguation_response(devices: list[dict[str, Any]], action: str) -> dict[str, Any]:
    labels = [d['label'] for d in devices[:8]]
    return {
        'success': False,
        'intent': 'disambiguation',
        'message': (
            f'I found multiple devices to {action}:\n'
            + '\n'.join(labels)
            + '\nPlease say the exact device name, or use plural/all wording for a group.'
        ),
        'speech': f'I found multiple matches. Please say the exact device name.',
        'matched': labels,
    }


def level_command_devices(devices: list[dict[str, Any]], level: int, explicit_bulk: bool = False) -> dict[str, Any]:
    target_level = max(0, min(100, int(level)))
    candidates = level_devices(devices)
    if not candidates:
        labels = [d['label'] for d in devices[:5]]
        suffix = '\nMatched: ' + '\n'.join(labels) if labels else ''
        return {'success': False, 'message': 'No dimmable devices found.' + suffix, 'matched': labels}
    if len(candidates) > 1 and not explicit_bulk:
        return disambiguation_response(candidates, 'set level for')
    changed = []
    errors = []
    updated = []
    for device in candidates[:50]:
        try:
            maker_command_value(device['id'], 'setLevel', target_level)
            if target_level > 0 and is_switchable_device(device):
                try:
                    maker_command(device['id'], 'on')
                except Exception:
                    pass
            changed.append(device['label'])
        except Exception as exc:
            errors.append(f"{device['label']}: {public_error(exc)}")
    refresh_devices()
    for device in candidates:
        if device['label'] in changed:
            cached = update_cached_level(device['id'], target_level)
            if cached:
                updated.append(cached)
    if changed:
        message = f"Set level to {target_level}%:\n" + '\n'.join(changed)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
        speech = spoken_list([f'{label} set to {target_level} percent' for label in changed])
        return {'success': True, 'message': message, 'speech': speech, 'changed': changed, 'errors': errors, 'devices': updated}
    return {'success': False, 'message': 'Level command failed:\n' + '\n'.join(errors), 'errors': errors}


def adjust_setpoint(device_id: str, delta: float) -> dict[str, Any]:
    matches = [d for d in all_devices() if d['id'] == device_id]
    if not matches:
        raise HTTPException(status_code=404, detail='Device not found.')
    device = matches[0]
    current = safe_float(device.get('heatingSetpoint') or device.get('attributes', {}).get('heatingSetpoint'))
    if current is None:
        raise HTTPException(status_code=400, detail='Device has no heating setpoint.')
    new_value = round(current + delta, 1)
    try:
        maker_command_value(device_id, 'setHeatingSetpoint', new_value)
    except Exception as exc:
        return {'success': False, 'message': f"Setpoint command failed for {device['label']}: {public_error(exc)}", 'device': device}
    refresh_devices()
    updated = update_cached_setpoint(device_id, new_value)
    return {'success': True, 'message': f"{device['label']} heating setpoint set to {new_value}°", 'device': updated or device, 'setpoint': new_value}


def set_setpoint_devices(devices: list[dict[str, Any]], setpoint: float, explicit_bulk: bool = False) -> dict[str, Any]:
    target_setpoint = round(float(setpoint), 1)
    if target_setpoint < 5 or target_setpoint > 35:
        return {'success': False, 'message': 'Heating setpoint must be between 5C and 35C.'}
    candidates = climate_control_devices(devices)
    if not candidates:
        labels = [d['label'] for d in devices[:5]]
        suffix = '\nMatched: ' + '\n'.join(labels) if labels else ''
        return {'success': False, 'message': 'No heating devices found.' + suffix, 'matched': labels}
    if len(candidates) > 1 and not explicit_bulk:
        return disambiguation_response(candidates, 'set heating for')
    changed = []
    errors = []
    updated = []
    for device in candidates[:20]:
        try:
            maker_command_value(device['id'], 'setHeatingSetpoint', target_setpoint)
            changed.append(device['label'])
        except Exception as exc:
            errors.append(f"{device['label']}: {public_error(exc)}")
    refresh_devices()
    for device in candidates:
        if device['label'] in changed:
            cached = update_cached_setpoint(device['id'], target_setpoint)
            if cached:
                updated.append(cached)
    if changed:
        setpoint_text = f'{target_setpoint:g}'
        message = f"Heating setpoint set to {setpoint_text}C:\n" + '\n'.join(changed)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
        speech = spoken_list([f'{label} set to {setpoint_text} degrees' for label in changed])
        return {'success': True, 'message': message, 'speech': speech, 'changed': changed, 'errors': errors, 'devices': updated, 'setpoint': target_setpoint}
    return {'success': False, 'message': 'Heating setpoint command failed:\n' + '\n'.join(errors), 'errors': errors}


def set_heating_mode(mode: str, target: str = 'home') -> dict[str, Any]:
    devices = climate_control_devices(all_devices())
    if target not in ('home', 'house', 'heating', 'heat'):
        matched_ids = {d['id'] for d in room_devices(target)}
        devices = [d for d in devices if d['id'] in matched_ids]
    if not devices:
        return {'success': False, 'message': f'No heating devices found for {target}.'}
    on_delta = safe_float(CONFIG.get('heating_on_delta')) or 1
    off_setpoint = safe_float(CONFIG.get('heating_off_setpoint')) or 12
    changed = []
    errors = []
    setpoints: list[str] = []
    changed_setpoints: dict[str, float] = {}
    for device in devices[:20]:
        try:
            temperature = safe_float(device.get('temperature') or device.get('attributes', {}).get('temperature'))
            current_setpoint = safe_float(device.get('heatingSetpoint') or device.get('attributes', {}).get('heatingSetpoint'))
            if mode == 'heat':
                target_setpoint = round((temperature if temperature is not None else current_setpoint or off_setpoint) + on_delta, 1)
                if current_setpoint is not None and current_setpoint > target_setpoint:
                    target_setpoint = current_setpoint
                if current_setpoint is None or current_setpoint < target_setpoint:
                    maker_command_value(device['id'], 'setHeatingSetpoint', target_setpoint)
                    changed_setpoints[device['id']] = target_setpoint
                    setpoints.append(f"{device['label']}: {target_setpoint}°")
                changed.append(device['label'])
            elif current_setpoint is None or current_setpoint > off_setpoint:
                maker_command_value(device['id'], 'setHeatingSetpoint', off_setpoint)
                changed_setpoints[device['id']] = off_setpoint
                setpoints.append(f"{device['label']}: {off_setpoint:g}°")
                changed.append(device['label'])
            else:
                changed.append(device['label'])
        except Exception as exc:
            errors.append(f"{device['label']}: {public_error(exc)}")
    refresh_devices()
    for device_id, setpoint in changed_setpoints.items():
        update_cached_setpoint(device_id, setpoint)
    updated = [d for d in all_devices() if d['id'] in {device['id'] for device in devices if device['label'] in changed}]
    if changed:
        action = 'raised' if mode == 'heat' else 'lowered'
        message = f"Heating setpoints {action} for:\n" + '\n'.join(changed)
        if setpoints:
            heading = 'Setpoints above room temp:' if mode == 'heat' else 'Heating off setpoints:'
            message += f'\n\n{heading}\n' + '\n'.join(setpoints)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
        speech_action = 'Heating setpoints raised' if mode == 'heat' else 'Heating setpoints lowered'
        return {'success': True, 'message': message, 'speech': f"{speech_action} for {spoken_list(changed)}", 'changed': changed, 'errors': errors, 'devices': updated}
    return {'success': False, 'message': 'Heating command failed:\n' + '\n'.join(errors), 'errors': errors}


def answer_attribute(target: str, attr: str) -> dict[str, Any]:
    if target in ('home', 'house'):
        summary = dashboard_summary()
        key = {'temperature': 'avg_temperature', 'humidity': 'avg_humidity', 'power': 'power_total'}.get(attr)
        if key and summary.get(key) is not None:
            unit = {'temperature': 'C', 'humidity': '%', 'power': 'W'}.get(attr, '')
            speech_value = {
                'temperature': spoken_degrees,
                'humidity': spoken_percent,
                'power': spoken_power_value,
            }.get(attr, spoken_number)(summary[key])
            if attr == 'power' and summary.get('power_source'):
                speech = f"Power is whole-house live power from {summary['power_source_label']}: {speech_value}."
            else:
                speech = f"Home {attr} is {speech_value}."
            return {'success': True, 'message': f"Home {attr} is {summary[key]}{unit}", 'speech': speech, 'attribute': attr, 'value': summary[key]}
    candidates = room_devices(target) or find_devices(target)
    candidates = [d for d in candidates if d.get(attr) is not None]
    if not candidates:
        return {'success': False, 'message': f'I could not find {attr} for {target}.'}
    d = candidates[0]
    unit = {'temperature': '°C', 'humidity': '%', 'power': 'W', 'battery': '%', 'energy': 'kWh', 'level': '%', 'illuminance': ' lux'}.get(attr, '')
    speech_value = {
        'temperature': spoken_degrees,
        'humidity': spoken_percent,
        'power': spoken_power_value,
        'battery': spoken_percent,
        'level': spoken_percent,
        'illuminance': lambda value: f"{spoken_number(value)} lux",
        'energy': lambda value: f"{spoken_number(value)} kilowatt hours",
    }.get(attr, spoken_number)(d[attr])
    return {'success': True, 'message': f"{d['label']} {attr} is {d[attr]}{unit}", 'speech': f"{d['label']} {attr} is {speech_value}.", 'device': d, 'attribute': attr, 'value': d[attr]}


def ai_device_fact(device: dict[str, Any]) -> dict[str, Any]:
    keys = (
        'id', 'label', 'room', 'category', 'switch', 'level', 'temperature', 'humidity',
        'power', 'energy', 'battery', 'motion', 'contact', 'presence',
        'thermostatMode', 'thermostatOperatingState', 'heatingSetpoint',
        'weatherSummaryLine',
    )
    fact = {key: device.get(key) for key in keys if device.get(key) not in (None, '', [], {})}
    attrs = device.get('attributes') or {}
    useful_attrs = {}
    for key in ('weatherSummary', 'weatherSummaryLine', 'pressure', 'windSpeed', 'precipitationToday'):
        if attrs.get(key) not in (None, '', [], {}) and key not in fact:
            useful_attrs[key] = attrs[key]
    if useful_attrs:
        fact['attributes'] = useful_attrs
    return fact


def ai_context_pack(include_logs: bool | None = None) -> dict[str, Any]:
    devices = all_devices()
    device_limit = max(10, int(CONFIG.get('ollama_context_device_limit', 80)))
    summary = dashboard_summary()
    context: dict[str, Any] = {
        'app': 'HomeBrain OS',
        'version': APP_VERSION,
        'safety': {
            'control_policy': 'Deterministic HomeBrain commands handle device control before AI. AI should answer and advise only; do not claim to send device commands.',
            'risky_actions': 'Ask the user to confirm broad or risky actions such as all-device changes, heating changes, or security-related actions.',
        },
        'summary': {
            'devices': summary.get('devices'),
            'lights_on': summary.get('lights_on'),
            'switches_on': summary.get('switches_on'),
            'avg_temperature': summary.get('avg_temperature'),
            'avg_humidity': summary.get('avg_humidity'),
            'power_total': summary.get('power_total'),
            'power_source_label': summary.get('power_source_label'),
            'people_home_names': summary.get('people_home_names'),
            'low_batteries': summary.get('low_batteries'),
            'motion_active': summary.get('motion_active'),
        },
        'weather': None,
        'hub_health': hub_health_summary(),
        'diagnostics': device_diagnostics(),
        'active_rooms': active_rooms_answer().get('rooms', [])[:12],
        'devices': [ai_device_fact(device) for device in sorted(devices, key=controllable_sort_key)[:device_limit]],
        'allowed_direct_commands': [
            'summary', 'weather', 'hub health', 'hub logs', 'device health',
            'turn on/off exact device', 'turn on/off explicit room lights',
            'set exact light level', 'increase/decrease room brightness',
            'heating setpoint adjustments', 'set room heating to exact temperature',
            'what is on in room', 'turn on device for timed duration',
        ],
    }
    weather = weather_device()
    if weather:
        context['weather'] = ai_device_fact(weather)
    should_include_logs = CONFIG.get('ollama_include_hub_logs', True) if include_logs is None else include_logs
    if should_include_logs:
        try:
            log_info = hub_logs_diagnostics(limit=40)
            context['hub_logs'] = {
                'total': log_info.get('total'),
                'warnings': log_info.get('warnings'),
                'errors': log_info.get('errors'),
                'affected_devices': log_info.get('affected_devices'),
                'recent_issues': [log.get('message') for log in log_info.get('problems', [])[:5]],
            }
        except Exception as exc:
            context['hub_logs'] = {'available': False, 'error': public_error(exc)}
    return context


def ai_context_text(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=True, separators=(',', ':'))


def clean_ollama_message(message: str, data: dict[str, Any]) -> tuple[str, bool]:
    text = re.sub(r'\s+', ' ', str(message or '')).strip()
    done_reason = str(data.get('done_reason') or '').lower()
    truncated = done_reason in {'length', 'limit'} or bool(data.get('truncated'))
    if truncated and text and text[-1] not in '.!?':
        text = text.rstrip(' ,;:') + '...'
    return text, truncated


def ollama_base_url() -> str:
    return str(CONFIG.get('ollama_base_url', '')).rstrip('/')


def set_ollama_health(online: bool, message: str) -> dict[str, Any]:
    OLLAMA_HEALTH.update({
        'checked_at': time.time(),
        'online': online,
        'message': message,
        'base_url': ollama_base_url(),
        'model': CONFIG.get('ollama_model', 'qwen2.5:3b'),
    })
    return dict(OLLAMA_HEALTH)


def ollama_health(force: bool = False) -> dict[str, Any]:
    if not CONFIG.get('ollama_enabled'):
        return {'checked_at': time.time(), 'online': False, 'message': 'Local AI is disabled', 'base_url': ollama_base_url(), 'model': CONFIG.get('ollama_model', 'qwen2.5:3b')}
    base_url = ollama_base_url()
    if not base_url:
        return set_ollama_health(False, 'Local AI URL is not configured')
    cache_seconds = max(5, int(CONFIG.get('ollama_health_cache_seconds', 60)))
    if (
        not force
        and OLLAMA_HEALTH.get('base_url') == base_url
        and OLLAMA_HEALTH.get('model') == CONFIG.get('ollama_model', 'qwen2.5:3b')
        and OLLAMA_HEALTH.get('online') is not None
        and time.time() - float(OLLAMA_HEALTH.get('checked_at') or 0) < cache_seconds
    ):
        return dict(OLLAMA_HEALTH)
    try:
        timeout = max(1, int(CONFIG.get('ollama_health_timeout_seconds', 2)))
        response = requests.get(base_url + '/api/tags', timeout=timeout)
        response.raise_for_status()
        return set_ollama_health(True, 'Local AI is online')
    except Exception as exc:
        return set_ollama_health(False, f'Local AI is offline: {public_error(exc)}')


def ollama_answer(text: str) -> dict[str, Any] | None:
    if not CONFIG.get('ollama_enabled'):
        return None
    health = ollama_health()
    if not health.get('online'):
        return {'success': False, 'message': 'Local AI is offline. Basic HomeBrain commands are still available.', 'intent': 'ollama_offline', 'source': 'ollama', 'ollama': health}
    context = ai_context_pack()
    prompt = (
        'You are HomeBrain OS, a fast concise smart home assistant. '
        'Use only the JSON context below. Do not invent device states. '
        'Device control is handled before you are called by deterministic HomeBrain commands. '
        'If the user asks for a control action that was not already handled, explain the exact deterministic phrase they should use. '
        'Answer in one short paragraph of 1-2 complete sentences. Finish the final sentence before stopping. '
        'No markdown headings or bullet lists unless the user asks for a list.\n\n'
        f'Context JSON:\n{ai_context_text(context)}\n\nUser: {text}\nAssistant:'
    )
    try:
        timeout = max(10, int(CONFIG.get('ollama_timeout_seconds', 75)))
        num_predict = max(32, int(CONFIG.get('ollama_num_predict', 120)))
        response = requests.post(
            ollama_base_url() + '/api/generate',
            json={
                'model': CONFIG.get('ollama_model', 'qwen2.5:3b'),
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_predict': num_predict,
                    'temperature': 0.2,
                    'top_p': 0.8,
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        set_ollama_health(True, 'Local AI is online')
        data = response.json()
        message, truncated = clean_ollama_message(str(data.get('response') or ''), data)
        if message:
            return {'success': True, 'message': message, 'speech': message, 'intent': 'ollama_answer', 'source': 'ollama', 'context': context, 'truncated': truncated}
    except Exception as exc:
        set_ollama_health(False, f'Local AI is offline: {public_error(exc)}')
        return {'success': False, 'message': f'Ollama is enabled but did not answer: {exc}', 'intent': 'ollama_error'}
    return None


def assistant(text: str) -> dict[str, Any]:
    t = normalise(text)
    if t in ('help', 'what can you do', 'commands'):
        return {
            'success': True,
            'intent': 'help',
            'message': (
                "I can summarize the home, read weather, list lights or switches that are on, answer temperature/humidity/power/battery questions, "
                "control switchable devices, keep a device on for a timed duration, set heating temperatures, adjust brightness, "
                "refresh or clear the cache, list room devices, read hub logs, and run diagnostics."
            ),
        }
    if 'weather' in t or 'forecast' in t:
        return weather_answer()
    if 'hub log' in t or 'hub logs' in t or 'recent logs' in t or 'log diagnostic' in t:
        return hub_logs_answer()
    if 'room' in t and ('motion' in t or 'active' in t):
        return active_rooms_answer()
    if 'cold' in t and 'room' in t:
        return cold_rooms_answer()
    if 'heating status' in t or 'heating state' in t:
        return heating_status_answer()
    m_room_on = re.search(r"^(?:what(?:'s| is)|which|show|list)\s+(?:devices\s+)?(?:are\s+)?on\s+(?:in|inside)\s+(.+)$", t)
    if not m_room_on:
        m_room_on = re.search(r"^(?:what(?:'s| is)|which|show|list)\s+(?:is\s+)?on\s+(?:in|inside)\s+(.+)$", t)
    if m_room_on:
        return room_on_status_answer(m_room_on.group(1).strip())
    if 'hub health' in t or 'hub info' in t or 'hubitat health' in t:
        return hub_health_answer()
    if 'device health' in t or 'home health' in t:
        return device_health_answer()
    room_answer = room_details_answer(t)
    if room_answer:
        return room_answer
    summary_answer = explain_summary_tile(t)
    if summary_answer:
        return summary_answer
    if any(word in t for word in ('diagnostic', 'diagnostics', 'problem', 'problems', 'why', 'unknown', 'missing')):
        d = device_diagnostics()
        lines = [
            f"Devices: {d['devices']}",
            f"Switchable devices: {d['switchable']}",
            f"Unknown switch states: {d['unknown_switch_state']}",
            f"Unknown rooms: {d['unknown_room']}",
            f"Temperature sensors: {d['temperature_devices']}",
            f"Humidity sensors: {d['humidity_devices']}",
            f"Power sensors: {d['power_devices']}",
        ]
        if d['unknown_switch_examples']:
            lines.append('Unknown switch examples:\n' + '\n'.join(d['unknown_switch_examples']))
        if d['last_error']:
            lines.append(f"Last Hubitat error: {d['last_error']}")
        if d['detail_errors']:
            lines.append('Detail refresh issues:\n' + '\n'.join(d['detail_errors'][:5]))
        return {'success': True, 'intent': 'diagnostics', 'message': '\n'.join(lines), 'diagnostics': d}
    m = re.search(r'(devices|what|list|show).*(in|inside) (.+)', t)
    if m:
        room = m.group(3).strip()
        devices = room_devices(room)
        if not devices:
            return {'success': False, 'intent': 'room_devices', 'message': f'I found no devices in {room}.'}
        return {'success': True, 'intent': 'room_devices', 'message': f"{room.title()} devices:\n" + '\n'.join(device_line(d) for d in devices[:20]), 'devices': devices[:20]}
    result = run_command(text)
    if result.get('success') or result.get('message') != f'I did not understand yet: {text}':
        result.setdefault('intent', 'deterministic_command')
        return result
    ollama = ollama_answer(text)
    if ollama:
        return ollama
    return {
        'success': False,
        'intent': 'unknown',
        'message': "I do not understand that yet. Try 'summary', 'diagnostics', 'which lights are on', 'turn off hallway light', or 'devices in hallway'.",
    }


def run_command(text: str) -> dict[str, Any]:
    t = normalise(text)
    if t in ('refresh', 'refresh cache', 'reload cache', 'update cache'):
        count = refresh_devices()
        if LAST_ERROR:
            return {'success': False, 'message': f'Refresh failed: {LAST_ERROR}', 'devices': count, 'error': LAST_ERROR}
        return {'success': True, 'message': f'Cache refreshed: {count} devices', 'devices': count, 'last_refresh': LAST_REFRESH}
    if t in ('summary', 'status', 'home summary'):
        s = dashboard_summary()
        people = ', '.join(s['people_home_names']) if s['people_home_names'] else 'None'
        speech = (
            f"Home summary. {s['lights_on']} lights are on. {s['switches_on']} switches are on. "
            f"Average temperature is {spoken_degrees(s['avg_temperature'])}. "
            f"Average humidity is {spoken_percent(s['avg_humidity'])}. "
            f"Power is whole-house live power from {s['power_source_label']}: {spoken_power_value(s['power_total'])}. "
            f"{s['people_home']} of {s['people_tracked']} people are home. "
            f"{s['low_batteries']} devices have low batteries. {s['motion_active']} motion sensors are active."
        )
        return {'success': True, 'message': f"Home Summary\nDevices: {s['devices']}\nLights on: {s['lights_on']}\nSwitches on: {s['switches_on']}\nAverage temperature: {s['avg_temperature']}C\nAverage humidity: {s['avg_humidity']}%\nWhole-house power: {s['power_display']} from {s['power_source_label']}\nPeople home: {s['people_home']}/{s['people_tracked']} ({people})\nLow batteries: {s['low_batteries']}\nMotion active: {s['motion_active']}", 'speech': speech}
    m_room_on = re.search(r"^(?:what(?:'s| is)|which|show|list)\s+(?:devices\s+)?(?:are\s+)?on\s+(?:in|inside)\s+(.+)$", t)
    if not m_room_on:
        m_room_on = re.search(r"^(?:what(?:'s| is)|which|show|list)\s+(?:is\s+)?on\s+(?:in|inside)\s+(.+)$", t)
    if m_room_on:
        return room_on_status_answer(m_room_on.group(1).strip())
    if re.search(r'\b(which|what)\s+lights?\s+(are|is)\s+on\b', t):
        lights = [d['label'] for d in all_devices() if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
        light_devices = [d for d in all_devices() if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
        return {'success': True, 'message': 'Lights on:\n' + ('\n'.join(lights) if lights else 'None'), 'speech': spoken_device_locations(light_devices)}
    if re.search(r'\b(which|what)\s+switch(es)?\s+(are|is)\s+on\b', t):
        switch_devices = [d for d in all_devices() if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on')]
        switches = [d['label'] for d in switch_devices]
        return {'success': True, 'message': 'Switches on:\n' + ('\n'.join(switches) if switches else 'None'), 'speech': spoken_device_locations(switch_devices)}
    m_setpoint = re.search(r'^(?:set|change|adjust)\s+(.+?)\s+(?:heating|heat|trv|thermostat|temperature|temp|setpoint)\s+(?:to|at)\s+(\d+(?:\.\d+)?)\s*(?:degrees?|c)?$', t)
    if not m_setpoint:
        m_setpoint = re.search(r'^(?:set|change|adjust)\s+(?:heating|heat|trv|thermostat|temperature|temp|setpoint)\s+(?:in|for)\s+(.+?)\s+(?:to|at)\s+(\d+(?:\.\d+)?)\s*(?:degrees?|c)?$', t)
    if m_setpoint:
        target = m_setpoint.group(1).replace('the ', '').strip()
        value = float(m_setpoint.group(2))
        explicit_bulk = target in ('home', 'house', 'all', 'all heating', 'heating', 'heat')
        if explicit_bulk:
            devices = climate_control_devices(all_devices())
        else:
            devices = climate_control_devices(room_devices(target)) or find_devices(target)
        if not devices:
            return {'success': False, 'message': f'Heating device not found: {target}'}
        return set_setpoint_devices(devices, value, explicit_bulk=explicit_bulk)
    m_heat = re.search(r'^(turn on|switch on|enable|start|turn off|switch off|disable|stop)\s+(?:(.+?)\s+)?heating(?:\s+(?:in|for)\s+(.+))?$', t)
    if m_heat:
        action = m_heat.group(1)
        target = (m_heat.group(3) or m_heat.group(2) or 'home').replace('the ', '').replace('all ', '').strip() or 'home'
        mode = 'off' if any(word in action for word in ('off', 'disable', 'stop')) else 'heat'
        return set_heating_mode(mode, target)
    m_level = re.search(r'^(?:set|change|adjust|dim)\s+(.+?)\s+(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?$', t)
    if not m_level:
        m_level = re.search(r'^(?:set|change|adjust)\s+(.+?)\s+level\s+(?:to|at)?\s*(\d{1,3})\s*(?:%|percent)?$', t)
    if m_level:
        target, level_text = m_level.group(1).strip(), m_level.group(2)
        target = target.replace(' level', '').replace('the ', '').strip()
        explicit_bulk = bool(re.search(r'\b(all|lights|devices)\b', target))
        if re.search(r'\b(all\s+)?(.+\s+)?lights$', target):
            room = target.replace('lights', '').replace('light', '').replace('all ', '').strip()
            devices = room_devices(room, 'light')
            explicit_bulk = True
        else:
            devices = find_devices(target, 'light') or find_devices(target)
        if not devices:
            return {'success': False, 'message': f'Dimmable device not found: {target}'}
        return level_command_devices(devices, int(level_text), explicit_bulk=explicit_bulk)
    m_dim = re.search(r'^(?:dim|lower)\s+(.+)$', t)
    m_bright = re.search(r'^(?:brighten|make)\s+(.+?)\s+(?:brighter|brighter lights?)$', t)
    if m_dim or m_bright:
        target = (m_dim.group(1) if m_dim else m_bright.group(1)).replace('the ', '').strip()
        explicit_bulk = bool(re.search(r'\b(all|lights|devices)\b', target))
        if re.search(r'\b(all\s+)?(.+\s+)?lights$', target):
            room = target.replace('lights', '').replace('light', '').replace('all ', '').strip()
            devices = room_devices(room, 'light')
            explicit_bulk = True
        else:
            devices = find_devices(target, 'light') or find_devices(target)
        if not devices:
            return {'success': False, 'message': f'Dimmable device not found: {target}'}
        dimmable = level_devices(devices)
        if len(dimmable) > 1 and not explicit_bulk:
            return disambiguation_response(dimmable, 'set level for')
        current = safe_float((dimmable[0] if dimmable else devices[0]).get('level'))
        if m_dim:
            target_level = max(1, int((current if current is not None else 50) - 20))
        else:
            target_level = min(100, int((current if current is not None else 50) + 20))
        return level_command_devices(devices, target_level, explicit_bulk=explicit_bulk)
    m_brightness = re.search(r'^(increase|raise|brighten|decrease|lower|dim)\s+(?:the\s+)?(?:brightness|light level)(?:\s+(?:in|for|of)\s+(.+))?$', t)
    m_brightness_alt = None if m_brightness else re.search(r'^(increase|raise|brighten|decrease|lower|dim)\s+(.+?)\s+(?:brightness|light level)$', t)
    if m_brightness or m_brightness_alt:
        action = (m_brightness or m_brightness_alt).group(1)
        target = ((m_brightness.group(2) if m_brightness else m_brightness_alt.group(2)) or 'all lights').replace('the ', '').strip()
        increase = action in ('increase', 'raise', 'brighten')
        explicit_bulk = True
        if target in ('all lights', 'lights', ''):
            devices = [d for d in all_devices() if d.get('category') == 'light']
        else:
            devices = room_devices(target, 'light')
            if not devices:
                devices = find_devices(target, 'light')
                explicit_bulk = False
        if not devices:
            return {'success': False, 'message': f'Dimmable lights not found: {target}'}
        dimmable = level_devices(devices)
        if len(dimmable) > 1 and not explicit_bulk:
            return disambiguation_response(dimmable, 'set level for')
        levels = [safe_float(device.get('level')) for device in dimmable or devices]
        known_levels = [level for level in levels if level is not None]
        current = sum(known_levels) / len(known_levels) if known_levels else 50
        target_level = min(100, int(current + 20)) if increase else max(1, int(current - 20))
        return level_command_devices(devices, target_level, explicit_bulk=explicit_bulk)
    m_timed = re.search(r'^(?:turn on|switch on|keep|leave)\s+(.+?)\s+(?:on\s+)?for\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)$', t)
    if m_timed:
        target = m_timed.group(1).replace(' on', '').replace('the ', '').strip()
        seconds = duration_seconds(m_timed.group(2), m_timed.group(3))
        devices, explicit_bulk, error = resolve_switch_target(target)
        if error:
            return {'success': False, 'message': error}
        if not devices:
            return {'success': False, 'message': f'Device not found: {target}'}
        return timed_command_devices(devices, 'on', seconds, explicit_bulk=explicit_bulk)
    m_delayed = re.search(r'^(turn on|switch on|turn off|switch off)\s+(.+?)\s+in\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)$', t)
    if m_delayed:
        action, target = m_delayed.group(1), m_delayed.group(2).replace('the ', '').strip()
        command = 'on' if 'on' in action else 'off'
        seconds = duration_seconds(m_delayed.group(3), m_delayed.group(4))
        devices, explicit_bulk, error = resolve_switch_target(target)
        if error:
            return {'success': False, 'message': error}
        if not devices:
            return {'success': False, 'message': f'Device not found: {target}'}
        return scheduled_command_devices(devices, command, seconds, explicit_bulk=explicit_bulk)
    attr_terms = {
        'humidity': ('humidity',),
        'temperature': ('temperature', 'temp'),
        'power': ('power', 'watt', 'watts'),
        'battery': ('battery',),
        'energy': ('energy', 'kwh'),
        'illuminance': ('illuminance', 'lux', 'light level'),
        'level': ('level', 'dimmer'),
        'motion': ('motion',),
        'contact': ('contact', 'open', 'closed'),
        'presence': ('presence',),
        'lock': ('lock',),
        'water': ('water', 'leak'),
        'smoke': ('smoke',),
        'carbonMonoxide': ('carbon monoxide', 'co '),
        'tamper': ('tamper',),
        'acceleration': ('acceleration', 'vibration'),
        'valve': ('valve',),
        'windowShade': ('window shade', 'shade'),
        'thermostatMode': ('thermostat mode',),
        'thermostatOperatingState': ('thermostat operating',),
        'heatingSetpoint': ('heating setpoint',),
        'coolingSetpoint': ('cooling setpoint',),
    }
    for attr, terms in attr_terms.items():
        if any(term in t for term in terms):
            target = t.replace('what is','').replace("what's",'').replace('level','').replace('the','').replace(attr,'').replace('temp','').strip()
            for term in terms:
                target = target.replace(term, '').strip()
            if not target:
                target = 'home'
            return answer_attribute(target, attr)
    m = re.search(r'(turn on|switch on|turn off|switch off) (.+)', t)
    if m:
        action, target = m.group(1), m.group(2).strip()
        command = 'on' if 'on' in action else 'off'
        devices, explicit_bulk, error = resolve_switch_target(target)
        if error:
            return {'success': False, 'message': error}
        if not devices:
            return {'success': False, 'message': f'Device not found: {target}'}
        return command_devices(devices, command, explicit_bulk=explicit_bulk)
    return {'success': False, 'message': f'I did not understand yet: {text}'}


async def refresh_loop() -> None:
    seconds = max(10, int(CONFIG.get('refresh_seconds', 30)))
    while True:
        await asyncio.sleep(seconds)
        await asyncio.to_thread(refresh_devices)


@app.on_event('startup')
async def startup() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    refresh_devices()
    restore_pending_timers()
    asyncio.create_task(refresh_loop())


@app.get('/api/status')
def api_status():
    return {'success': True, 'app': 'HomeBrain OS', 'version': APP_VERSION, 'hubitat': CONFIG.get('hubitat_base_url'), 'devices': count_devices(), 'last_refresh': LAST_REFRESH, 'last_hubitat_event': LAST_HUBITAT_EVENT, 'state_event_version': STATE_EVENT_VERSION, 'database': str(DB_PATH), 'error': LAST_ERROR, 'detail_errors': LAST_DETAIL_ERRORS, 'auth_required': api_token_required(), 'hub_health': hub_health_summary(), 'ollama': ollama_health()}


@app.get('/api/events')
async def api_events(request: Request):
    require_event_token(request)

    async def stream():
        last_seen = STATE_EVENT_VERSION
        yield f"event: hello\ndata: {json.dumps({'version': APP_VERSION, 'state_event_version': last_seen})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            if STATE_EVENT_VERSION != last_seen:
                last_seen = STATE_EVENT_VERSION
                yield f"event: state\ndata: {json.dumps({'state_event_version': last_seen, 'last_hubitat_event': LAST_HUBITAT_EVENT})}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type='text/event-stream')


@app.post('/api/hubitat/events')
async def api_hubitat_events(request: Request):
    require_event_token(request)
    content_type = request.headers.get('content-type', '')
    try:
        payload = await request.json()
    except Exception:
        body = (await request.body()).decode('utf-8', errors='replace').strip()
        if 'application/x-www-form-urlencoded' in content_type:
            payload = dict(request.query_params)
            if body:
                payload['body'] = body
        else:
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {'body': body}
    return record_hubitat_events(payload)


@app.get('/api/timers')
def api_timers(request: Request):
    require_api_token(request)
    now = time.time()
    restore_pending_timers()
    timers = [timer_payload(record, now) for record in pending_timer_records()]
    return {'success': True, 'count': len(timers), 'timers': timers}


@app.post('/api/timers/{timer_id}/cancel')
def api_cancel_timer(timer_id: str, request: Request):
    require_api_token(request)
    return cancel_timer(timer_id)


@app.get('/api/hub/logs')
def api_hub_logs():
    return {'success': True, **hub_logs_diagnostics()}


@app.get('/api/ai/context')
def api_ai_context(request: Request):
    require_api_token(request)
    return {'success': True, 'context': ai_context_pack()}


@app.post('/api/refresh')
def api_refresh(request: Request):
    require_api_token(request)
    count = refresh_devices()
    return {'success': LAST_ERROR is None, 'devices': count, 'error': LAST_ERROR, 'last_refresh': LAST_REFRESH}


@app.post('/api/cache/clear-refresh')
def api_cache_clear_refresh(request: Request):
    require_api_token(request)
    clear_cache()
    count = refresh_devices()
    return {'success': LAST_ERROR is None, 'devices': count, 'error': LAST_ERROR, 'last_refresh': LAST_REFRESH}


@app.get('/api/dashboard')
def api_dashboard():
    return {'success': True, **dashboard_summary()}


@app.get('/api/devices')
def api_devices(category: str | None = None, room: str | None = None):
    devices = all_devices()
    if category:
        devices = [d for d in devices if d['category'] == category]
    if room:
        devices = [d for d in devices if normalise(room) in normalise(d.get('room',''))]
    return {'success': True, 'count': len(devices), 'devices': devices}


@app.get('/api/switches')
def api_switches(room: str | None = None):
    devices = all_devices()
    if room:
        devices = [d for d in devices if normalise(room) in normalise(d.get('room',''))]
    devices = controllable_devices(devices)
    return {'success': True, 'count': len(devices), 'devices': devices}


@app.get('/api/rooms')
def api_rooms():
    devices = all_devices()
    rooms: dict[str, dict[str, Any]] = {}
    for d in devices:
        room = canonical_room_name(d.get('room') or 'Unknown')
        rooms.setdefault(room, {
            'room': room,
            'devices': 0,
            'lights_total': 0,
            'lights_on': 0,
            'switches_total': 0,
            'switches_on': 0,
            'sockets_total': 0,
            'sockets_on': 0,
            'motion_total': 0,
            'motion_active': 0,
            'low_batteries': 0,
            'power_total': 0,
            'power_devices': 0,
            'avg_temperature': None,
            'avg_humidity': None,
        })
        rooms[room]['devices'] += 1
        if d['category'] == 'light':
            rooms[room]['lights_total'] += 1
            if is_state(d.get('switch'), 'on'):
                rooms[room]['lights_on'] += 1
        if is_room_switch_device(d):
            rooms[room]['switches_total'] += 1
            if is_room_socket_device(d):
                rooms[room]['sockets_total'] += 1
            if d.get('switch') is not None and is_state(d.get('switch'), 'on'):
                rooms[room]['switches_on'] += 1
                if is_room_socket_device(d):
                    rooms[room]['sockets_on'] += 1
        if is_room_motion_device(d):
            rooms[room]['motion_total'] += 1
            if is_state(d.get('motion'), 'active'):
                rooms[room]['motion_active'] += 1
        if isinstance(d.get('battery'), (int, float)) and d['battery'] <= 20:
            rooms[room]['low_batteries'] += 1
        if isinstance(d.get('power'), (int, float)):
            rooms[room]['power_devices'] += 1
            rooms[room]['power_total'] = round(rooms[room]['power_total'] + d['power'], 1)
    for room in rooms.values():
        ds = [d for d in devices if canonical_room_name(d.get('room') or 'Unknown') == room['room']]
        environment_devices = [d for d in ds if not is_fridge_meter_device(d)]
        temps = [d['temperature'] for d in environment_devices if isinstance(d.get('temperature'), (int,float))]
        hums = [d['humidity'] for d in environment_devices if isinstance(d.get('humidity'), (int,float))]
        room['avg_temperature'] = round(sum(temps)/len(temps),1) if temps else None
        room['avg_humidity'] = round(sum(hums)/len(hums),1) if hums else None
    def room_sort_key(room: dict[str, Any]) -> tuple[int, str]:
        active_score = int(room.get('lights_on') or 0) + int(room.get('motion_active') or 0)
        return (0 if active_score else 1, str(room['room']).lower())

    return {'success': True, 'rooms': sorted(rooms.values(), key=room_sort_key)}


@app.get('/api/rooms/{room_name}')
def api_room_details(room_name: str):
    return room_details_payload(room_name)


@app.get('/api/device/{device_id}')
def api_device(device_id: str):
    matches = [d for d in all_devices() if d['id'] == device_id]
    return {'success': bool(matches), 'device': matches[0] if matches else None}


@app.post('/api/device/{device_id}/command/{command}')
def api_device_command(device_id: str, command: str, request: Request):
    require_api_token(request)
    if command not in ('on', 'off'):
        raise HTTPException(status_code=400, detail='Only on/off commands are supported.')
    matches = [d for d in all_devices() if d['id'] == device_id]
    if not matches:
        raise HTTPException(status_code=404, detail='Device not found.')
    return command_devices(matches, command)


@app.post('/api/device/{device_id}/setpoint/{delta}')
def api_device_setpoint(device_id: str, delta: float, request: Request):
    require_api_token(request)
    if delta not in (-1, 1):
        raise HTTPException(status_code=400, detail='Only -1 and +1 setpoint adjustments are supported.')
    return adjust_setpoint(device_id, delta)


@app.post('/api/device/{device_id}/level/{level}')
def api_device_level(device_id: str, level: int, request: Request):
    require_api_token(request)
    if level < 0 or level > 100:
        raise HTTPException(status_code=400, detail='Level must be between 0 and 100.')
    matches = [d for d in all_devices() if d['id'] == device_id]
    if not matches:
        raise HTTPException(status_code=404, detail='Device not found.')
    return level_command_devices(matches, level)


@app.post('/api/ask')
def api_ask(payload: AssistantRequest, request: Request):
    require_api_token(request)
    return assistant(payload.q)


@app.post('/api/assistant')
def api_assistant(payload: AssistantRequest, request: Request):
    require_api_token(request)
    return assistant(payload.q)


@app.get('/', response_class=HTMLResponse)
def index():
    return Path('/app/static/index.html').read_text()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8787)
