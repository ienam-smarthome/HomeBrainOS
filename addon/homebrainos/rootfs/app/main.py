from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from difflib import get_close_matches
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

APP_VERSION = '1.2.0-alpha'
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
        'refresh_seconds': int(os.getenv('REFRESH_SECONDS', '300')),
        'min_full_refresh_seconds': int(os.getenv('MIN_FULL_REFRESH_SECONDS', '90')),
        'state_sync_seconds': int(os.getenv('STATE_SYNC_SECONDS', '120')),
        'live_switch_sync_seconds': int(os.getenv('LIVE_SWITCH_SYNC_SECONDS', '60')),
        'live_switch_sync_limit': int(os.getenv('LIVE_SWITCH_SYNC_LIMIT', '12')),
        'event_batch_window_ms': int(os.getenv('EVENT_BATCH_WINDOW_MS', '500')),
        'auto_live_sync_enabled': os.getenv('AUTO_LIVE_SYNC_ENABLED', 'false').lower() == 'true',
        'ollama_enabled': os.getenv('OLLAMA_ENABLED', 'false').lower() == 'true',
        'ollama_base_url': os.getenv('OLLAMA_BASE_URL', 'http://homeassistant.local:11434'),
        'ollama_model': os.getenv('OLLAMA_MODEL', 'qwen2.5:3b'),
        'ollama_context_device_limit': int(os.getenv('OLLAMA_CONTEXT_DEVICE_LIMIT', '35')),
        'ollama_include_hub_logs': os.getenv('OLLAMA_INCLUDE_HUB_LOGS', 'false').lower() == 'true',
        'ollama_timeout_seconds': int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '75')),
        'ollama_num_predict': int(os.getenv('OLLAMA_NUM_PREDICT', '90')),
        'ollama_health_timeout_seconds': int(os.getenv('OLLAMA_HEALTH_TIMEOUT_SECONDS', '2')),
        'ollama_health_cache_seconds': int(os.getenv('OLLAMA_HEALTH_CACHE_SECONDS', '60')),
        'device_detail_refresh_limit': int(os.getenv('DEVICE_DETAIL_REFRESH_LIMIT', '25')),
        'device_detail_refresh_seconds': int(os.getenv('DEVICE_DETAIL_REFRESH_SECONDS', '1800')),
        'device_detail_refresh_batch': int(os.getenv('DEVICE_DETAIL_REFRESH_BATCH', '5')),
        'stale_motion_active_minutes': int(os.getenv('STALE_MOTION_ACTIVE_MINUTES', '30')),
        'stale_light_on_hours': int(os.getenv('STALE_LIGHT_ON_HOURS', '4')),
        'stale_device_report_hours': int(os.getenv('STALE_DEVICE_REPORT_HOURS', '24')),
        'presence_occupied_interesting_hours': int(os.getenv('PRESENCE_OCCUPIED_INTERESTING_HOURS', '2')),
        'contact_open_interesting_hours': int(os.getenv('CONTACT_OPEN_INTERESTING_HOURS', '6')),
        'heating_on_delta': float(os.getenv('HEATING_ON_DELTA', '1')),
        'heating_off_setpoint': float(os.getenv('HEATING_OFF_SETPOINT', '12')),
        'time_zone': os.getenv('TZ', os.getenv('TIME_ZONE', 'Europe/London')),
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
PERF_STATS: dict[str, Any] = {
    'started_at': time.time(),
    'full_refresh_count': 0,
    'full_refresh_skipped': 0,
    'full_refresh_last_ms': None,
    'full_refresh_last_device_count': 0,
    'detail_fetch_count': 0,
    'event_count': 0,
    'event_updated_count': 0,
    'cache_write_count': 0,
    'last_refresh_reason': None,
    'maker_get_count': 0,
    'maker_get_error_count': 0,
    'maker_get_last_path': None,
    'maker_get_last_ms': None,
    'state_sync_count': 0,
    'state_sync_skipped': 0,
    'state_sync_last_reason': None,
    'state_sync_last_ms': None,
    'live_switch_sync_count': 0,
    'live_switch_sync_skipped': 0,
    'live_switch_sync_last_ms': None,
    'live_switch_sync_last_reason': None,
    'live_switch_sync_last_devices': 0,
    'summary_rebuild_count': 0,
    'summary_rebuild_last_ms': None,
    'summary_event_push_count': 0,
}
SUMMARY_CACHE: dict[str, Any] | None = None
SUMMARY_CACHE_VERSION = 0
SUMMARY_CACHE_LAST_REBUILD: float | None = None
SSE_CLIENTS = 0
EVENT_HISTORY: list[dict[str, Any]] = []
UI_STATS: dict[str, Any] = {
    'events_received': 0,
    'events_updated': 0,
    'events_ui_relevant': 0,
    'events_ignored_for_ui': 0,
    'sse_payloads_sent': 0,
    'last_event_at': None,
    'last_ui_event_at': None,
    'last_sse_push_at': None,
}
LAST_LIVE_SWITCH_SYNC = 0.0

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
            last_activity_at INTEGER,
            updated_at INTEGER NOT NULL
        )
    ''')
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(devices)').fetchall()}
    if 'detail_refreshed_at' not in columns:
        conn.execute('ALTER TABLE devices ADD COLUMN detail_refreshed_at INTEGER')
    if 'last_activity_at' not in columns:
        conn.execute('ALTER TABLE devices ADD COLUMN last_activity_at INTEGER')
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS performance_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reason TEXT NOT NULL,
            devices INTEGER NOT NULL,
            maker_get_count INTEGER NOT NULL,
            maker_get_error_count INTEGER NOT NULL,
            full_refresh_count INTEGER NOT NULL,
            detail_fetch_count INTEGER NOT NULL,
            event_count INTEGER NOT NULL,
            calls_per_hour REAL NOT NULL,
            json TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_performance_snapshots_created ON performance_snapshots(created_at)')
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
    started = time.time()
    try:
        response = requests.get(maker_url(path), timeout=timeout)
        response.raise_for_status()
        PERF_STATS['maker_get_count'] = int(PERF_STATS.get('maker_get_count') or 0) + 1
        PERF_STATS['maker_get_last_path'] = path
        PERF_STATS['maker_get_last_ms'] = int((time.time() - started) * 1000)
        return response.json()
    except Exception:
        PERF_STATS['maker_get_error_count'] = int(PERF_STATS.get('maker_get_error_count') or 0) + 1
        PERF_STATS['maker_get_last_path'] = path
        PERF_STATS['maker_get_last_ms'] = int((time.time() - started) * 1000)
        raise


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace('%',''))
    except Exception:
        return None


def safe_timestamp(value: Any) -> int | None:
    try:
        if value in (None, ''):
            return None
        if isinstance(value, (int, float)) or re.fullmatch(r'\d+(?:\.\d+)?', str(value).strip()):
            ts = float(value)
            if ts > 10_000_000_000:
                ts = ts / 1000
            if 946684800 <= ts <= time.time() + 86400:
                return int(ts)
            return None
        text = str(value).strip().replace('Z', '+00:00')
        text = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', text)
        dt = datetime.fromisoformat(text)
        return int(dt.timestamp())
    except Exception:
        return None


def extract_last_activity_at(device: dict[str, Any]) -> int | None:
    candidates: list[int] = []
    top_level_keys = (
        'lastActivity', 'last_activity', 'lastActivityAt', 'last_activity_at',
        'lastUpdated', 'last_updated', 'lastUpdate', 'updated', 'updatedAt',
        'date', 'timestamp', 'time'
    )
    for key in top_level_keys:
        ts = safe_timestamp(device.get(key))
        if ts:
            candidates.append(ts)
    for source in (device.get('attributes'), device.get('currentStates'), device.get('states')):
        if isinstance(source, dict):
            for value in source.values():
                if isinstance(value, dict):
                    for key in top_level_keys:
                        ts = safe_timestamp(value.get(key))
                        if ts:
                            candidates.append(ts)
            continue
        for item in source or []:
            if not isinstance(item, dict):
                continue
            for key in top_level_keys:
                ts = safe_timestamp(item.get(key))
                if ts:
                    candidates.append(ts)
    return max(candidates) if candidates else None


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
        '_last_activity_at': extract_last_activity_at(device),
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
    global LAST_DETAIL_ERRORS, PERF_STATS
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
                PERF_STATS['detail_fetch_count'] = int(PERF_STATS.get('detail_fetch_count') or 0) + 1
                if not incomplete:
                    stale_detail_count += 1
            except Exception as exc:
                detail_errors.append(f"{device['label']}: {public_error(exc)}")
        enriched.append(raw_device)
    LAST_DETAIL_ERRORS = detail_errors[:10]
    return enriched


def upsert_devices(devices: list[dict[str, Any]]) -> None:
    global PERF_STATS
    now = int(time.time())
    conn = db()
    try:
        for d in devices:
            old = conn.execute('SELECT json, detail_refreshed_at, last_activity_at FROM devices WHERE id=?', (d['id'],)).fetchone()
            detail_refreshed_at = int(d['_detail_refreshed_at']) if d.get('_detail_refreshed_at') is not None else (old['detail_refreshed_at'] if old else None)
            raw_activity_at = d.get('_last_activity_at') if d.get('_last_activity_at') is not None else extract_last_activity_at(d)
            last_activity_at = int(raw_activity_at) if raw_activity_at is not None else (old['last_activity_at'] if old else None)
            if old:
                old_d = json.loads(old['json'])
                watched_attrs = ('switch','temperature','humidity','power','energy','battery','motion','presence','contact','thermostatMode','thermostatOperatingState','heatingSetpoint')
                if any(old_d.get(attr) != d.get(attr) for attr in watched_attrs):
                    last_activity_at = now
                    d['_last_activity_at'] = now
            if old and d.get('switch') is None:
                old_d = json.loads(old['json'])
                if old_d.get('switch') is not None:
                    d['switch'] = old_d.get('switch')
                    d.setdefault('attributes', {})['switch'] = old_d.get('switch')
            conn.execute('''
                INSERT INTO devices(id,name,label,room,category,json,switch,temperature,humidity,power,energy,battery,detail_refreshed_at,last_activity_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, label=excluded.label, room=excluded.room, category=excluded.category,
                    json=excluded.json, switch=excluded.switch, temperature=excluded.temperature,
                    humidity=excluded.humidity, power=excluded.power, energy=excluded.energy,
                    battery=excluded.battery, detail_refreshed_at=excluded.detail_refreshed_at,
                    last_activity_at=excluded.last_activity_at, updated_at=excluded.updated_at
            ''', (
                d['id'], d['name'], d['label'], d['room'], d['category'], json.dumps(d),
                d.get('switch'), d.get('temperature'), d.get('humidity'), d.get('power'), d.get('energy'), d.get('battery'), detail_refreshed_at, last_activity_at, now
            ))
            if old:
                old_d = json.loads(old['json'])
                for attr in ('switch','temperature','humidity','power','battery','motion','presence'):
                    if old_d.get(attr) != d.get(attr):
                        conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', (d['id'], attr, str(d.get(attr)), now))
        conn.commit()
        PERF_STATS['cache_write_count'] = int(PERF_STATS.get('cache_write_count') or 0) + len(devices)
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
                'UPDATE devices SET json=?, switch=?, last_activity_at=?, updated_at=? WHERE id=?',
                (json.dumps(device), switch, now, now, device_id),
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
        conn.execute('UPDATE devices SET json=?, last_activity_at=?, updated_at=? WHERE id=?', (json.dumps(device), now, now, device_id))
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
            'UPDATE devices SET json=?, switch=?, last_activity_at=?, updated_at=? WHERE id=?',
            (json.dumps(device), device.get('switch'), now, now, device_id),
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
            conn.execute('UPDATE devices SET json=?, last_activity_at=?, updated_at=? WHERE id=?', (json.dumps(device), now, now, device_id))
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
            UPDATE devices SET json=?, category=?, switch=?, temperature=?, humidity=?, power=?, energy=?, battery=?, last_activity_at=?, updated_at=?
            WHERE id=?
        ''', (
            json.dumps(normalized), normalized.get('category'), normalized.get('switch'), normalized.get('temperature'),
            normalized.get('humidity'), normalized.get('power'), normalized.get('energy'), normalized.get('battery'),
            now, now, str(device_id)
        ))
        conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', (str(device_id), attr, str(value), now))
        conn.commit()
        return normalized
    finally:
        conn.close()


def flatten_form_values(values: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, list):
            flattened[key] = value[0] if value else None
        else:
            flattened[key] = value
    return flattened


def parse_event_text(text: str) -> Any:
    text = str(text or '').strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    parsed = parse_qs(text, keep_blank_values=True)
    if parsed:
        flattened = flatten_form_values(parsed)
        # Some clients POST a single nested JSON value, e.g. body={...} or content={...}.
        for key in ('body', 'payload', 'event', 'events', 'content'):
            value = flattened.get(key)
            if isinstance(value, str) and value.strip().startswith(('{', '[')):
                try:
                    return json.loads(value)
                except Exception:
                    continue
        return flattened
    return {'body': text}


def expand_event_payload(payload: Any) -> list[Any]:
    if isinstance(payload, str):
        return expand_event_payload(parse_event_text(payload))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        expanded: list[Any] = []
        for key in ('events', 'content', 'items', 'data'):
            value = payload.get(key)
            if isinstance(value, str):
                value = parse_event_text(value)
            if isinstance(value, list):
                expanded.extend(value)
            elif isinstance(value, dict):
                expanded.append(value)
        # Maker API may be received as a form body wrapped by api_hubitat_events.
        body = payload.get('body') or payload.get('payload') or payload.get('event')
        if isinstance(body, str) and body.strip():
            expanded.extend(expand_event_payload(parse_event_text(body)))
        if expanded:
            return expanded
        return [payload]
    return []


def event_records_from_payload(payload: Any) -> list[dict[str, Any]]:
    events = expand_event_payload(payload)
    records: list[dict[str, Any]] = []
    for event in events:
        if isinstance(event, str):
            for nested in expand_event_payload(event):
                if isinstance(nested, dict):
                    events.append(nested)
            continue
        if not isinstance(event, dict):
            continue
        event = flatten_form_values(event)
        device_id = event.get('deviceId') or event.get('device_id') or event.get('device') or event.get('id')
        attr = event.get('name') or event.get('attribute') or event.get('attr')
        value = event.get('value')
        label = event.get('displayName') or event.get('label') or event.get('deviceLabel') or event.get('deviceName')
        if device_id and attr:
            records.append({'device_id': str(device_id), 'attr': canonical_attr(attr), 'value': value, 'label': str(label) if label else None, 'raw': event})
    return records


DASHBOARD_EVENT_ATTRS = {
    'switch', 'motion', 'presence', 'battery', 'power', 'demand', 'energy', 'energyToday',
    'temperature', 'humidity', 'thermostatOperatingState', 'thermostatMode', 'heatingSetpoint',
}
NOISY_EVENT_ATTRS = {
    'rssi', 'voltage', 'amperage', 'dataAgeSeconds', 'lastSeen', 'lastTelemetry',
    'displaySummary', 'displaySummaryCompact', 'displayToday', 'displayPower', 'displayMini',
    'displayCostToday', 'costTodayEnergy', 'illuminance',
}


def event_affects_dashboard(event: dict[str, Any]) -> bool:
    attr = canonical_attr(event.get('attr'))
    if attr in NOISY_EVENT_ATTRS:
        return False
    if attr in DASHBOARD_EVENT_ATTRS:
        return True
    # Unknown switch/motion-like events should still wake the dashboard, but
    # random display/helper attributes should not. This keeps live UI responsive
    # without flooding the browser for RSSI, voltage, lux, and display text spam.
    text = compact_name(attr)
    return text in {compact_name(item) for item in DASHBOARD_EVENT_ATTRS}



def remember_event_diagnostics(records: list[dict[str, Any]], ui_records: list[dict[str, Any]], updated_count: int, now: int) -> None:
    global EVENT_HISTORY, UI_STATS
    ui_keys = {(event.get('device_id'), event.get('attr'), str(event.get('value'))) for event in ui_records}
    for event in records:
        is_ui = (event.get('device_id'), event.get('attr'), str(event.get('value'))) in ui_keys
        EVENT_HISTORY.append({
            'received_at': now,
            'device_id': event.get('device_id'),
            'attr': event.get('attr'),
            'value': event.get('value'),
            'label': event.get('label'),
            'ui_relevant': is_ui,
        })
    EVENT_HISTORY = EVENT_HISTORY[-50:]
    UI_STATS['events_received'] = int(UI_STATS.get('events_received') or 0) + len(records)
    UI_STATS['events_updated'] = int(UI_STATS.get('events_updated') or 0) + updated_count
    UI_STATS['events_ui_relevant'] = int(UI_STATS.get('events_ui_relevant') or 0) + len(ui_records)
    UI_STATS['events_ignored_for_ui'] = int(UI_STATS.get('events_ignored_for_ui') or 0) + max(0, len(records) - len(ui_records))
    if records:
        UI_STATS['last_event_at'] = now
    if ui_records:
        UI_STATS['last_ui_event_at'] = now


def event_diagnostics_payload() -> dict[str, Any]:
    now = time.time()
    last_event_at = UI_STATS.get('last_event_at')
    age = None if not last_event_at else round(now - float(last_event_at), 1)
    event_warning = bool(last_event_at and age is not None and age > 300)
    return {
        'success': True,
        'version': APP_VERSION,
        'event_stream': {
            'status': 'warning' if event_warning else ('online' if last_event_at else 'waiting'),
            'last_event_age_seconds': age,
            'last_hubitat_event': LAST_HUBITAT_EVENT,
            'state_event_version': STATE_EVENT_VERSION,
            'sse_clients': SSE_CLIENTS,
            'warning': 'No Hubitat events received for more than 5 minutes.' if event_warning else None,
        },
        'summary_cache': {
            'version': SUMMARY_CACHE_VERSION,
            'last_rebuild': SUMMARY_CACHE_LAST_REBUILD,
            'available': SUMMARY_CACHE is not None,
        },
        'ui_stats': dict(UI_STATS),
        'event_filter': {
            'dashboard_attrs': sorted(DASHBOARD_EVENT_ATTRS),
            'ignored_ui_attrs': sorted(NOISY_EVENT_ATTRS),
        },
        'recent_events': list(reversed(EVENT_HISTORY[-20:])),
    }

def record_hubitat_events(payload: Any) -> dict[str, Any]:
    global LAST_HUBITAT_EVENT, STATE_EVENT_VERSION, PERF_STATS
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
    ui_records = [event for event in records if event_affects_dashboard(event)]
    remember_event_diagnostics(records, ui_records, len(updated), now)
    PERF_STATS['event_count'] = int(PERF_STATS.get('event_count') or 0) + len(records)
    PERF_STATS['event_updated_count'] = int(PERF_STATS.get('event_updated_count') or 0) + len(updated)
    PERF_STATS['event_ui_relevant_count'] = int(PERF_STATS.get('event_ui_relevant_count') or 0) + len(ui_records)
    LAST_HUBITAT_EVENT = {
        'received_at': now,
        'count': len(records),
        'updated': len(updated),
        'ui_relevant': len(ui_records),
        'last': records[-1] if records else None,
        'last_ui': ui_records[-1] if ui_records else None,
    }
    summary = None
    if records:
        STATE_EVENT_VERSION += len(records)
    if ui_records:
        summary = rebuild_summary_cache('hubitat-event')
        PERF_STATS['summary_event_push_count'] = int(PERF_STATS.get('summary_event_push_count') or 0) + 1
    return {'success': True, 'events': len(records), 'updated': len(updated), 'ui_relevant': len(ui_records), 'last_event': LAST_HUBITAT_EVENT, 'devices': updated, 'dashboard': summary}


def refresh_devices(force: bool = False, reason: str = 'scheduled') -> int:
    global LAST_ERROR, LAST_REFRESH, PERF_STATS
    now = time.time()
    min_seconds = max(0, int(CONFIG.get('min_full_refresh_seconds', 90)))
    if not force and LAST_REFRESH and min_seconds and now - float(LAST_REFRESH) < min_seconds:
        PERF_STATS['full_refresh_skipped'] = int(PERF_STATS.get('full_refresh_skipped') or 0) + 1
        PERF_STATS['last_refresh_reason'] = f'skipped:{reason}'
        return count_devices()
    started = time.time()
    try:
        raw = maker_get('devices', timeout=20)
        raw = enrich_raw_devices(raw if isinstance(raw, list) else [])
        devices = [normalise_device(d) for d in raw]
        upsert_devices(devices)
        prune_missing_devices({d['id'] for d in devices})
        LAST_REFRESH = time.time()
        LAST_ERROR = None
        PERF_STATS['full_refresh_count'] = int(PERF_STATS.get('full_refresh_count') or 0) + 1
        PERF_STATS['full_refresh_last_ms'] = int((time.time() - started) * 1000)
        PERF_STATS['full_refresh_last_device_count'] = len(devices)
        PERF_STATS['last_refresh_reason'] = reason
        return len(devices)
    except Exception as exc:
        LAST_ERROR = public_error(exc)
        PERF_STATS['full_refresh_last_ms'] = int((time.time() - started) * 1000)
        PERF_STATS['last_refresh_reason'] = f'error:{reason}'
        return count_devices()



def refresh_devices_for_context(reason: str = 'command-context') -> int | None:
    # Tests and older integrations sometimes monkeypatch refresh_devices with a no-arg callable.
    # Keep that compatibility while using throttled refreshes in production.
    try:
        return refresh_devices(False, reason)
    except TypeError:
        return refresh_devices()


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



def maker_configured() -> bool:
    return bool(str(CONFIG.get('hubitat_base_url', '')).strip() and str(CONFIG.get('maker_api_app_id', '')).strip() and str(CONFIG.get('maker_api_token', '')).strip())


def state_sync_needed(max_age_seconds: int | None = None) -> bool:
    """Return True when cached device states are too old for a live-state answer.

    Hubitat event callbacks keep the cache live when configured. If callbacks are
    missing or delayed, state-sensitive UI tiles and questions can otherwise show
    old switch/light states until the next full refresh. This guard performs a
    throttled Maker API refresh only for state-sensitive paths.
    """
    if not maker_configured():
        return False
    age = max(0, int(max_age_seconds if max_age_seconds is not None else CONFIG.get('state_sync_seconds', 20)))
    if age <= 0:
        return False
    now = time.time()
    if LAST_REFRESH is None:
        return True
    return now - float(LAST_REFRESH) >= age


def sync_live_states(reason: str = 'live-state') -> dict[str, Any]:
    """Throttle-protected live state sync for dashboard and state questions."""
    global PERF_STATS
    if not state_sync_needed():
        PERF_STATS['state_sync_skipped'] = int(PERF_STATS.get('state_sync_skipped') or 0) + 1
        PERF_STATS['state_sync_last_reason'] = f'skipped:{reason}'
        return {'synced': False, 'reason': 'fresh', 'last_refresh': LAST_REFRESH}
    started = time.time()
    try:
        count = refresh_devices(True, reason)
    except TypeError:
        # Compatibility for tests/older integrations that monkeypatch refresh_devices with no args.
        count = refresh_devices()
    elapsed_ms = int((time.time() - started) * 1000)
    PERF_STATS['state_sync_count'] = int(PERF_STATS.get('state_sync_count') or 0) + 1
    PERF_STATS['state_sync_last_reason'] = reason
    PERF_STATS['state_sync_last_ms'] = elapsed_ms
    return {'synced': LAST_ERROR is None, 'devices': count, 'error': LAST_ERROR, 'last_refresh': LAST_REFRESH, 'elapsed_ms': elapsed_ms}


def fetch_live_device_detail(device_id: str) -> dict[str, Any] | None:
    """Fetch one device detail from Maker API and return a normalised live snapshot."""
    try:
        raw = maker_get(f"devices/{quote(str(device_id), safe='')}", timeout=6)
        if isinstance(raw, list):
            raw = raw[0] if raw and isinstance(raw[0], dict) else None
        if not isinstance(raw, dict):
            return None
        raw['_homebrain_detail_refreshed_at'] = int(time.time())
        return normalise_device(raw)
    except Exception as exc:
        PERF_STATS['live_switch_sync_last_error'] = public_error(exc)
        return None


def update_cached_device_snapshot(device: dict[str, Any]) -> None:
    """Merge a fresh normalised device snapshot into the SQLite cache."""
    now = int(time.time())
    conn = db()
    try:
        old = conn.execute('SELECT json, detail_refreshed_at FROM devices WHERE id=?', (device['id'],)).fetchone()
        if old:
            old_d = json.loads(old['json'])
            for key in ('room', 'category', 'capabilities', 'commands'):
                if not device.get(key) and old_d.get(key):
                    device[key] = old_d.get(key)
            detail_refreshed_at = int(device.get('_detail_refreshed_at') or old['detail_refreshed_at'] or now)
        else:
            detail_refreshed_at = int(device.get('_detail_refreshed_at') or now)
        conn.execute("""
            INSERT INTO devices(id,name,label,room,category,json,switch,temperature,humidity,power,energy,battery,detail_refreshed_at,last_activity_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, label=excluded.label, room=excluded.room, category=excluded.category,
                json=excluded.json, switch=excluded.switch, temperature=excluded.temperature,
                humidity=excluded.humidity, power=excluded.power, energy=excluded.energy,
                battery=excluded.battery, detail_refreshed_at=excluded.detail_refreshed_at,
                last_activity_at=excluded.last_activity_at, updated_at=excluded.updated_at
        """, (
            device['id'], device['name'], device['label'], device.get('room'), device.get('category') or 'device', json.dumps(device),
            device.get('switch'), device.get('temperature'), device.get('humidity'), device.get('power'), device.get('energy'), device.get('battery'), detail_refreshed_at, now, now
        ))
        conn.commit()
    finally:
        conn.close()


def live_switch_state_sync(reason: str = 'live-switch-state', categories: set[str] | None = None, force: bool = False) -> dict[str, Any]:
    """Refresh current on/off state for lights and switchable devices.

    Maker API /devices can be stale or incomplete on some hubs/drivers. For state-sensitive
    answers such as which lights are on, fetch the current detail endpoint only for relevant
    devices. This is throttled and capped to avoid recreating high hub CPU load.
    """
    global LAST_LIVE_SWITCH_SYNC, STATE_EVENT_VERSION
    if not maker_configured():
        return {'synced': False, 'reason': 'maker-not-configured'}
    if not force and not bool(CONFIG.get('auto_live_sync_enabled', False)):
        PERF_STATS['live_switch_sync_skipped'] = int(PERF_STATS.get('live_switch_sync_skipped') or 0) + 1
        PERF_STATS['live_switch_sync_last_reason'] = f'skipped:auto-disabled:{reason}'
        return {'synced': False, 'reason': 'auto-live-sync-disabled', 'event_callback_seen': bool(LAST_HUBITAT_EVENT)}
    now = time.time()
    min_age = max(0, int(CONFIG.get('live_switch_sync_seconds', 3)))
    if not force and LAST_LIVE_SWITCH_SYNC and min_age and now - LAST_LIVE_SWITCH_SYNC < min_age:
        PERF_STATS['live_switch_sync_skipped'] = int(PERF_STATS.get('live_switch_sync_skipped') or 0) + 1
        PERF_STATS['live_switch_sync_last_reason'] = f'skipped:{reason}'
        return {'synced': False, 'reason': 'fresh', 'last_live_switch_sync': LAST_LIVE_SWITCH_SYNC}
    selected = []
    for d in all_devices():
        if categories and d.get('category') not in categories:
            continue
        if d.get('category') in {'light', 'switch', 'power_device'} or is_switchable_device(d):
            selected.append(d)
    limit = max(1, int(CONFIG.get('live_switch_sync_limit', 40)))
    selected = selected[:limit]
    started = time.time()
    changed = 0
    updated = 0
    for d in selected:
        fresh = fetch_live_device_detail(str(d.get('id')))
        if not fresh:
            continue
        old_switch = d.get('switch')
        if fresh.get('switch') is None and old_switch is not None:
            fresh['switch'] = old_switch
            fresh.setdefault('attributes', {})['switch'] = old_switch
        if fresh.get('switch') != old_switch:
            changed += 1
        update_cached_device_snapshot(fresh)
        updated += 1
    LAST_LIVE_SWITCH_SYNC = time.time()
    if changed:
        STATE_EVENT_VERSION += 1
    elapsed_ms = int((time.time() - started) * 1000)
    PERF_STATS['live_switch_sync_count'] = int(PERF_STATS.get('live_switch_sync_count') or 0) + 1
    PERF_STATS['live_switch_sync_last_ms'] = elapsed_ms
    PERF_STATS['live_switch_sync_last_reason'] = reason
    PERF_STATS['live_switch_sync_last_devices'] = updated
    return {'synced': True, 'updated': updated, 'changed': changed, 'elapsed_ms': elapsed_ms, 'last_live_switch_sync': LAST_LIVE_SWITCH_SYNC}

def clear_cache() -> None:
    conn = db()
    try:
        conn.execute('DELETE FROM history')
        conn.execute('DELETE FROM devices')
        conn.commit()
    finally:
        conn.close()


def rebuild_summary_cache(reason: str = 'manual') -> dict[str, Any]:
    global SUMMARY_CACHE, SUMMARY_CACHE_VERSION, SUMMARY_CACHE_LAST_REBUILD, PERF_STATS
    started = time.time()
    summary = compute_dashboard_summary({'synced': False, 'reason': reason})
    SUMMARY_CACHE_VERSION += 1
    SUMMARY_CACHE_LAST_REBUILD = time.time()
    summary['summary_cache'] = {
        'version': SUMMARY_CACHE_VERSION,
        'last_rebuild': SUMMARY_CACHE_LAST_REBUILD,
        'reason': reason,
        'dirty': False,
    }
    SUMMARY_CACHE = summary
    PERF_STATS['summary_rebuild_count'] = int(PERF_STATS.get('summary_rebuild_count') or 0) + 1
    PERF_STATS['summary_rebuild_last_ms'] = int((time.time() - started) * 1000)
    return summary


def dashboard_summary(live: bool = False) -> dict[str, Any]:
    if live and CONFIG.get('auto_live_sync_enabled'):
        sync_result = live_switch_state_sync('dashboard', categories={'light','switch','power_device'}, force=False)
        return compute_dashboard_summary(sync_result)
    if SUMMARY_CACHE is not None:
        return dict(SUMMARY_CACHE)
    return rebuild_summary_cache('cache-miss')


def compute_dashboard_summary(sync_result: dict[str, Any]) -> dict[str, Any]:
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
        'state_sync': sync_result,
        'event_callback_seen': bool(LAST_HUBITAT_EVENT),
        'last_hubitat_event': LAST_HUBITAT_EVENT,
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
    stale = stale_device_report()
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
        'stale_issues': stale['issue_count'],
        'stale': stale,
        'last_error': LAST_ERROR,
        'detail_errors': LAST_DETAIL_ERRORS,
        'last_refresh': LAST_REFRESH,
    }



def device_text(device: dict[str, Any]) -> str:
    return normalise(f"{device.get('label') or ''} {device.get('name') or ''} {device.get('category') or ''}")


def is_thermostat_like_device(device: dict[str, Any]) -> bool:
    text = device_text(device)
    caps = caps_text(device)
    attrs = device.get('attributes') or {}
    return (
        device.get('category') == 'thermostat'
        or 'thermostat' in caps
        or 'thermostat' in text
        or 'trv' in text
        or any(key in attrs for key in ('thermostatMode', 'thermostatOperatingState', 'heatingSetpoint', 'coolingSetpoint'))
    )


def is_energy_meter_like_device(device: dict[str, Any]) -> bool:
    text = device_text(device)
    caps = caps_text(device)
    attrs = device.get('attributes') or {}
    energy_words = ('octopus', 'live meter', 'smart meter', 'energy meter', 'meter', 'export', 'import', 'electricity')
    has_energy_signal = any(key in attrs for key in ('power', 'energy', 'powerSource', 'voltage', 'amperage')) or any(word in caps for word in ('powermeter', 'energymeter'))
    has_switch_state = attrs.get('switch') is not None or 'switch' in caps
    return has_energy_signal and any(word in text for word in energy_words) and not has_switch_state


def is_read_only_or_helper_device(device: dict[str, Any]) -> bool:
    text = device_text(device)
    return (
        is_thermostat_like_device(device)
        or is_energy_meter_like_device(device)
        or any(word in text for word in ('weather', 'battery', 'sensor only', 'helper', 'bridge'))
    )


def device_intelligence_profile(device: dict[str, Any]) -> dict[str, Any]:
    """Classify devices into practical profiles used by health checks and AI answers.

    Hubitat/Maker API can expose commands that are not useful for HomeBrain's
    switch dashboard. For example TRVs may have on/off commands, and an energy
    meter may be commandable by a driver, but neither should be treated as a
    switch with a missing on/off state. This profile is intentionally pragmatic:
    it favours reducing false-positive housekeeping alerts over exposing every
    raw capability.
    """
    text = device_text(device)
    attrs = device.get('attributes') or {}
    caps = caps_text(device)
    commands = commands_text(device)
    room = device.get('room') or 'Unknown'
    profile = 'device'
    confidence = 0.55
    dashboard = 'general'
    ignore_checks: list[str] = []
    reasons: list[str] = []

    if is_thermostat_like_device(device):
        profile, confidence, dashboard = 'thermostat_trv' if 'trv' in text else 'thermostat', 0.98, 'heating'
        ignore_checks.extend(['unknown_switch_state', 'motion_active_too_long'])
        reasons.append('Thermostat/TRV devices can expose commands without being dashboard switches.')
    elif is_energy_meter_like_device(device):
        profile, confidence, dashboard = 'energy_meter', 0.95, 'energy'
        ignore_checks.append('unknown_switch_state')
        reasons.append('Read-only energy meters should be tracked for power/energy, not switch state.')
    elif device.get('category') == 'light' or 'switchlevel' in caps or 'colorcontrol' in caps:
        profile, confidence, dashboard = 'light', 0.95, 'lighting'
    elif 'switch' in attrs or 'switch' in caps or any(word in text for word in ('plug', 'socket', 'outlet')):
        profile, confidence, dashboard = 'smart_plug_or_switch', 0.86, 'switches'
    elif 'contact' in attrs or 'contactsensor' in caps or 'door' in text or 'window' in text:
        profile, confidence, dashboard = 'contact_sensor', 0.9, 'security'
    elif is_presence_style_motion_device(device):
        profile, confidence, dashboard = 'presence_sensor', 0.96, 'occupancy'
        ignore_checks.append('motion_active_too_long')
    elif 'motion' in attrs or 'motionsensor' in caps:
        profile, confidence, dashboard = 'motion_sensor', 0.87, 'occupancy'
    elif 'temperature' in attrs or 'humidity' in attrs:
        profile, confidence, dashboard = 'climate_sensor', 0.82, 'climate'
    elif 'battery' in attrs or 'battery' in text:
        profile, confidence, dashboard = 'battery_sensor', 0.78, 'maintenance'

    suggested_room = suggested_room_from_label(device)
    room_confidence = 0.0
    if room != 'Unknown':
        suggested_room = room
        room_confidence = 1.0
    elif suggested_room:
        room_confidence = 0.96 if any(word in text for word in ('fridge', 'kitchen', 'bedroom', 'hallway', 'bathroom', 'living')) else 0.75

    return {
        'profile': profile,
        'confidence': round(confidence, 2),
        'dashboard': dashboard,
        'ignore_checks': sorted(set(ignore_checks)),
        'suggested_room': suggested_room,
        'room_confidence': round(room_confidence, 2),
        'reasons': reasons,
        'commands_are_control': profile in ('light', 'smart_plug_or_switch'),
    }

def list_capabilities(device: dict[str, Any]) -> list[str]:
    return [str(c) for c in (device.get('capabilities') or []) if str(c).strip()]


def list_commands(device: dict[str, Any]) -> list[str]:
    return [str(c) for c in (device.get('commands') or []) if str(c).strip()]


def device_issue_base(device: dict[str, Any], reason: str, suggestion: str, severity: str = 'info') -> dict[str, Any]:
    attrs = device.get('attributes') or {}
    return {
        'id': device.get('id'),
        'label': device.get('label') or device.get('name') or str(device.get('id') or 'Unknown device'),
        'name': device.get('name'),
        'room': device.get('room') or 'Unknown',
        'category': device.get('category') or 'unknown',
        'reason': reason,
        'suggestion': suggestion,
        'severity': severity,
        'switch': device.get('switch'),
        'battery': device.get('battery'),
        'power': device.get('power'),
        'capabilities': list_capabilities(device)[:12],
        'commands': list_commands(device)[:12],
        'attribute_names': sorted(str(k) for k in attrs.keys())[:20] if isinstance(attrs, dict) else [],
    }


def unknown_switch_reason(device: dict[str, Any]) -> tuple[str, str, str]:
    caps = caps_text(device)
    commands = commands_text(device)
    attrs = device.get('attributes') or {}
    if 'switch' not in attrs and 'switch' not in caps:
        return (
            'HomeBrain thinks this is controllable, but Hubitat did not expose a current switch attribute.',
            'Check the Hubitat driver/capabilities. If it is not controllable, add it to an ignore/helper list; if it is controllable, refresh/re-save the device in Hubitat.',
            'warning',
        )
    if {'on', 'off'}.issubset(set(commands.split())) and device.get('switch') is None:
        return (
            'Device has on/off commands but no current on/off state in the cached Maker API payload.',
            'Operate the device once or refresh details so HomeBrain can learn its first state. If it stays unknown, the driver may not publish switch state.',
            'warning',
        )
    return (
        'Switch state is missing or null even though the device appears switchable.',
        'Refresh device details and check the Hubitat device page Current States section.',
        'warning',
    )


def suggested_room_from_label(device: dict[str, Any]) -> str | None:
    text = normalise(f"{device.get('label') or ''} {device.get('name') or ''}")
    candidates = [
        ('Bedroom 1', ('bedroom 1', 'bedroom1', 'bed 1')),
        ('Bedroom 2', ('bedroom 2', 'bedroom2', 'bed 2')),
        ('Bedroom 3', ('bedroom 3', 'bedroom3', 'bed 3')),
        ('Living Room', ('living room', 'livingroom', 'lounge')),
        ('Bathroom', ('bathroom', 'bath')),
        ('Hallway', ('hallway', 'hall')),
        ('Kitchen', ('kitchen',)),
        ('Toilet', ('toilet', 'wc')),
        ('Internet', ('router', 'wifi', 'internet', 'mesh')),
        ('Energy', ('octopus', 'energy', 'electricity', 'meter')),
    ]
    for room, words in candidates:
        if any(word in text for word in words):
            return room
    return None


def device_inspector_report() -> dict[str, Any]:
    devices = all_devices()
    switchable = switchable_devices(devices)
    unknown_switches: list[dict[str, Any]] = []
    auto_excluded_switches: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    for device in devices:
        intel = device_intelligence_profile(device)
        if intel.get('confidence', 0) >= 0.8 or intel.get('ignore_checks') or intel.get('suggested_room'):
            base = device_issue_base(device, 'Classified by HomeBrain device intelligence.', 'Use this profile to drive health checks and dashboards.', 'info')
            base['intelligence'] = intel
            classifications.append(base)
        if 'unknown_switch_state' in intel.get('ignore_checks', []) and ({'on', 'off'}.issubset(set(commands_text(device).split())) or device.get('switch') is None):
            base = device_issue_base(device, intel.get('reasons', ['Excluded by device profile.'])[0] if intel.get('reasons') else 'Excluded by device profile.', 'No action needed unless this device is actually a controllable switch.', 'info')
            base['intelligence'] = intel
            auto_excluded_switches.append(base)
    for device in switchable:
        if device.get('switch') is None:
            reason, suggestion, severity = unknown_switch_reason(device)
            item = device_issue_base(device, reason, suggestion, severity)
            item['intelligence'] = device_intelligence_profile(device)
            unknown_switches.append(item)

    unknown_rooms: list[dict[str, Any]] = []
    for device in devices:
        if (device.get('room') or 'Unknown') == 'Unknown':
            suggested = suggested_room_from_label(device)
            suggestion = f'Assign this device to {suggested} in Hubitat/HomeBrain room mapping.' if suggested else 'Assign a room in Hubitat or add a HomeBrain room override.'
            item = device_issue_base(device, 'Device has no recognised room assignment.', suggestion, 'info')
            if suggested:
                item['suggested_room'] = suggested
            item['intelligence'] = device_intelligence_profile(device)
            unknown_rooms.append(item)

    labels: dict[str, list[dict[str, Any]]] = {}
    for device in devices:
        key = normalise(device.get('label') or device.get('name') or '')
        if key:
            labels.setdefault(key, []).append(device)
    duplicates = []
    for group in labels.values():
        if len(group) > 1:
            duplicates.append({
                'label': group[0].get('label') or group[0].get('name'),
                'count': len(group),
                'devices': [device_issue_base(d, 'Duplicate label/name can make voice and AI targeting ambiguous.', 'Rename one device or add a room-specific alias.', 'info') for d in group],
            })
    duplicates.sort(key=lambda item: (-int(item['count']), str(item['label'] or '')))

    generic_devices = []
    generic_words = ('device', 'unknown', 'generic', 'thing')
    for device in devices:
        label_text = normalise(device.get('label') or device.get('name') or '')
        category = str(device.get('category') or '').lower()
        if category in ('unknown', '') or any(word in label_text.split() for word in generic_words):
            generic_devices.append(device_issue_base(device, 'Generic name/category makes AI understanding less reliable.', 'Rename it with room + purpose, e.g. “Bedroom 1 Lamp” or “Kitchen Door Sensor”.', 'info'))

    missing_capability_devices = []
    for device in devices:
        caps = list_capabilities(device)
        attrs = device.get('attributes') or {}
        if not caps and isinstance(attrs, dict) and len(attrs) <= 1:
            missing_capability_devices.append(device_issue_base(device, 'Device exposes very little capability/attribute information.', 'Refresh details. If still limited, check the Hubitat driver or exclude helper/bridge devices from health checks.', 'info'))

    return {
        'success': True,
        'devices': len(devices),
        'summary': {
            'unknown_switch_states': len(unknown_switches),
            'unknown_rooms': len(unknown_rooms),
            'duplicate_names': len(duplicates),
            'generic_or_unknown_devices': len(generic_devices),
            'missing_capability_details': len(missing_capability_devices),
            'auto_excluded_switch_false_positives': len(auto_excluded_switches),
            'classified_devices': len(classifications),
        },
        'unknown_switch_states': unknown_switches,
        'unknown_rooms': unknown_rooms,
        'auto_excluded_switch_false_positives': auto_excluded_switches[:30],
        'classifications': classifications[:50],
        'duplicate_names': duplicates,
        'generic_or_unknown_devices': generic_devices[:30],
        'missing_capability_details': missing_capability_devices[:30],
    }


def device_inspector_answer() -> dict[str, Any]:
    report = device_inspector_report()
    summary = report['summary']
    lines = [
        'Device Inspector:',
        f"Unknown switch states: {summary['unknown_switch_states']}",
        f"Unknown rooms: {summary['unknown_rooms']}",
        f"Duplicate names: {summary['duplicate_names']}",
        f"Generic/unknown devices: {summary['generic_or_unknown_devices']}",
        f"Missing capability details: {summary['missing_capability_details']}",
        f"Auto-excluded false positives: {summary['auto_excluded_switch_false_positives']}",
    ]
    if report.get('auto_excluded_switch_false_positives'):
        lines.append('\nAuto-excluded from unknown switch checks:')
        for item in report['auto_excluded_switch_false_positives'][:8]:
            profile = item.get('intelligence', {}).get('profile', 'device')
            lines.append(f"• {item['label']} — {profile}; {item['reason']}")
    if report['unknown_switch_states']:
        lines.append('\nUnknown switch states:')
        for item in report['unknown_switch_states'][:10]:
            lines.append(f"• {item['label']} ({item['room']}) — {item['reason']}")
    if report['unknown_rooms']:
        lines.append('\nUnknown rooms:')
        for item in report['unknown_rooms'][:10]:
            suggested = f" Suggested: {item['suggested_room']}." if item.get('suggested_room') else ''
            lines.append(f"• {item['label']} — {item['reason']}{suggested}")
    if report['duplicate_names']:
        lines.append('\nDuplicate names:')
        for group in report['duplicate_names'][:5]:
            lines.append(f"• {group['label']} — {group['count']} devices")
    lines.append('\nFix priority: only investigate remaining unknown switch states after auto-exclusions, then assign unknown rooms. TRVs and energy meters are now ignored automatically for switch-state checks.')
    return {'success': True, 'intent': 'device_inspector', 'message': '\n'.join(lines), **report}


def history_current_since(conn: sqlite3.Connection, device_id: str, attr: str, current_value: Any, fallback: int) -> int:
    rows = state_change_rows(conn, str(device_id), attr)
    if not rows:
        return fallback
    latest = rows[0]
    if is_state(latest['value'], str(current_value)):
        return int(latest['created_at'])
    return fallback


def is_presence_style_motion_device(device: dict[str, Any]) -> bool:
    """Return True for mmWave/occupancy devices where long 'motion active' is normal.

    Aqara FP1/FP2/FP300 and similar presence sensors often expose a Hubitat
    motion attribute that remains active while a person is present. Treating
    that as a stale PIR sensor creates false alarms in real rooms.
    """
    label = f"{device.get('label') or ''} {device.get('name') or ''}".lower()
    category = str(device.get('category') or '').lower()
    caps = ' '.join(device.get('capabilities') or []).lower()
    attrs = device.get('attributes') or {}
    if category == 'presence_sensor' or device.get('presence') is not None or 'presence' in attrs or 'presence' in caps:
        return True
    presence_words = ('fp1', 'fp2', 'fp300', 'presence', 'occupancy', 'occupied', 'mmwave', 'mm wave', 'radar')
    return any(word in label or word in caps for word in presence_words)


def stale_motion_exemption_reason(device: dict[str, Any]) -> str:
    if is_presence_style_motion_device(device):
        return 'presence/occupancy sensor; continuous active can be normal'
    return ''


def device_last_activity(conn: sqlite3.Connection, row: sqlite3.Row, device: dict[str, Any]) -> dict[str, Any]:
    candidates: list[tuple[int, str]] = []
    if row['last_activity_at'] is not None:
        candidates.append((int(row['last_activity_at']), 'hubitat attribute timestamp or value change'))
    for event_row in conn.execute(
        'SELECT created_at FROM hubitat_events WHERE device_id=? ORDER BY created_at DESC LIMIT 1',
        (str(row['id']),),
    ).fetchall():
        candidates.append((int(event_row['created_at']), 'event callback'))
    if candidates:
        ts, source = max(candidates, key=lambda item: item[0])
        return {'timestamp': ts, 'source': source, 'confidence': 'high'}
    return {'timestamp': int(row['updated_at'] or 0), 'source': 'HomeBrain cache refresh only', 'confidence': 'low'}


def stale_device_report() -> dict[str, Any]:
    now = int(time.time())
    motion_seconds = max(1, int(CONFIG.get('stale_motion_active_minutes', 30))) * 60
    light_seconds = max(1, int(CONFIG.get('stale_light_on_hours', 4))) * 3600
    report_seconds = max(1, int(CONFIG.get('stale_device_report_hours', 24))) * 3600
    occupied_seconds = max(1, int(CONFIG.get('presence_occupied_interesting_hours', 2))) * 3600
    motion: list[dict[str, Any]] = []
    lights: list[dict[str, Any]] = []
    not_reporting: list[dict[str, Any]] = []
    occupied: list[dict[str, Any]] = []
    empty_report = {
        'motion_active_too_long': motion,
        'lights_on_too_long': lights,
        'not_reporting': not_reporting,
        'occupied_long': occupied,
        'issue_count': 0,
        'thresholds': {
            'motion_active': duration_label(motion_seconds),
            'light_on': duration_label(light_seconds),
            'not_reporting': duration_label(report_seconds),
            'occupied_interesting': duration_label(occupied_seconds),
        },
    }
    try:
        conn = db()
    except sqlite3.Error:
        return empty_report
    try:
        rows = conn.execute('SELECT id, label, room, category, json, updated_at, last_activity_at FROM devices ORDER BY label').fetchall()
        for row in rows:
            device = json.loads(row['json'])
            device_id = str(row['id'])
            updated_at = int(row['updated_at'] or 0)
            label = device.get('label') or row['label'] or device_id
            room = device.get('room') or row['room'] or 'Unknown'
            if is_state(device.get('motion'), 'active'):
                since = history_current_since(conn, device_id, 'motion', device.get('motion'), updated_at)
                age = now - since
                if is_presence_style_motion_device(device):
                    if age >= occupied_seconds:
                        occupied.append({'id': device_id, 'label': label, 'room': room, 'age_seconds': age, 'duration': elapsed_duration_label(age), 'state': 'occupied/active', 'reason': stale_motion_exemption_reason(device)})
                elif age >= motion_seconds:
                    motion.append({'id': device_id, 'label': label, 'room': room, 'age_seconds': age, 'duration': elapsed_duration_label(age), 'state': 'motion active'})
            if device.get('category') == 'light' and is_state(device.get('switch'), 'on'):
                since = history_current_since(conn, device_id, 'switch', device.get('switch'), updated_at)
                age = now - since
                if age >= light_seconds:
                    lights.append({'id': device_id, 'label': label, 'room': room, 'age_seconds': age, 'duration': elapsed_duration_label(age), 'state': 'light on'})
            activity = device_last_activity(conn, row, device)
            activity_ts = int(activity.get('timestamp') or 0)
            if activity_ts and activity.get('confidence') == 'high' and now - activity_ts >= report_seconds:
                not_reporting.append({'id': device_id, 'label': label, 'room': room, 'age_seconds': now - activity_ts, 'duration': elapsed_duration_label(now - activity_ts), 'state': 'not reporting', 'last_activity_source': activity.get('source'), 'confidence': activity.get('confidence')})
            elif updated_at and now - updated_at >= report_seconds:
                not_reporting.append({'id': device_id, 'label': label, 'room': room, 'age_seconds': now - updated_at, 'duration': elapsed_duration_label(now - updated_at), 'state': 'cache not refreshed', 'last_activity_source': 'HomeBrain cache refresh only', 'confidence': 'low'})
    finally:
        conn.close()
    issues = motion + lights + not_reporting
    return {
        'motion_active_too_long': motion,
        'lights_on_too_long': lights,
        'not_reporting': not_reporting,
        'occupied_long': occupied,
        'issue_count': len(issues),
        'thresholds': {
            'motion_active': duration_label(motion_seconds),
            'light_on': duration_label(light_seconds),
            'not_reporting': duration_label(report_seconds),
            'occupied_interesting': duration_label(occupied_seconds),
        },
    }


def stale_devices_answer() -> dict[str, Any]:
    report = stale_device_report()
    lines = []
    spoken = []
    if report['motion_active_too_long']:
        items = report['motion_active_too_long'][:8]
        lines.append('Motion active too long:\n' + '\n'.join(f"{item['label']} ({item['room']}) for {item['duration']}" for item in items))
        spoken.extend(f"{item['label']} motion active for {item['duration']}" for item in items)
    if report['lights_on_too_long']:
        items = report['lights_on_too_long'][:8]
        lines.append('Lights on too long:\n' + '\n'.join(f"{item['label']} ({item['room']}) for {item['duration']}" for item in items))
        spoken.extend(f"{item['label']} on for {item['duration']}" for item in items)
    if report['not_reporting']:
        items = report['not_reporting'][:8]
        lines.append('Not reporting recently:\n' + '\n'.join(f"{item['label']} ({item['room']}) for {item['duration']}" for item in items))
        spoken.extend(f"{item['label']} not reporting for {item['duration']}" for item in items)
    if report.get('occupied_long'):
        items = report['occupied_long'][:8]
        lines.append('Normal occupancy, not stale:\n' + '\n'.join(f"{item['label']} ({item['room']}) occupied for {item['duration']}" for item in items))
    message = 'Device health check:\n' + ('\n\n'.join(lines) if lines else 'No stale device issues found.')
    speech = f"Stale device check found {report['issue_count']} possible issues: {spoken_list(spoken)}" if spoken else 'No stale device issues found.'
    return {'success': True, 'intent': 'stale_devices', 'message': message, 'speech': speech, 'stale': report}


def state_change_rows(conn: sqlite3.Connection, device_id: str, attr: str) -> list[dict[str, Any]]:
    rows = []
    for row in conn.execute(
        'SELECT value, created_at, "history" AS source FROM history WHERE device_id=? AND attr=?',
        (str(device_id), attr),
    ).fetchall():
        rows.append({'value': str(row['value']), 'created_at': int(row['created_at']), 'source': row['source']})
    for row in conn.execute(
        'SELECT value, created_at, "hubitat_event" AS source FROM hubitat_events WHERE device_id=? AND attr=?',
        (str(device_id), attr),
    ).fetchall():
        rows.append({'value': str(row['value']), 'created_at': int(row['created_at']), 'source': row['source']})
    rows.sort(key=lambda item: item['created_at'], reverse=True)
    return rows


def state_since_for_device(device: dict[str, Any], attr: str = 'switch') -> dict[str, Any] | None:
    current = device.get(attr)
    if current is None:
        return None
    try:
        conn = db()
    except sqlite3.Error:
        return None
    try:
        rows = state_change_rows(conn, str(device.get('id')), attr)
    finally:
        conn.close()
    if not rows:
        return None
    latest = rows[0]
    if not is_state(latest['value'], str(current)):
        return None
    return {
        'device': device,
        'attr': attr,
        'state': str(current),
        'since': latest['created_at'],
        'duration_seconds': max(0, int(time.time()) - int(latest['created_at'])),
        'source': latest['source'],
    }


def last_state_session_for_device(device: dict[str, Any], attr: str, expected_state: str) -> dict[str, Any] | None:
    try:
        conn = db()
    except sqlite3.Error:
        return None
    try:
        rows = state_change_rows(conn, str(device.get('id')), attr)
    finally:
        conn.close()
    if not rows:
        return None
    rows_asc = sorted(rows, key=lambda item: item['created_at'])
    sessions = []
    start: dict[str, Any] | None = None
    for row in rows_asc:
        if is_state(row['value'], expected_state):
            start = row
        elif start:
            sessions.append({
                'start': start['created_at'],
                'end': row['created_at'],
                'duration_seconds': max(0, int(row['created_at']) - int(start['created_at'])),
                'start_source': start['source'],
                'end_source': row['source'],
            })
            start = None
    current = device.get(attr)
    if start and is_state(current, expected_state):
        sessions.append({
            'start': start['created_at'],
            'end': None,
            'duration_seconds': max(0, int(time.time()) - int(start['created_at'])),
            'start_source': start['source'],
            'end_source': None,
        })
    return sessions[-1] if sessions else None


def local_timezone() -> ZoneInfo | None:
    name = str(CONFIG.get('time_zone') or os.getenv('TZ') or 'Europe/London').strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None


def local_datetime(timestamp: int | float) -> datetime:
    tz = local_timezone()
    if tz:
        return datetime.fromtimestamp(float(timestamp), tz)
    return datetime.fromtimestamp(float(timestamp))


def format_clock_time(dt: datetime) -> str:
    return dt.strftime('%I:%M %p').lstrip('0').lower()


def display_since(timestamp: int) -> str:
    dt = local_datetime(int(timestamp))
    now = local_datetime(time.time())
    time_text = format_clock_time(dt)
    if dt.date() == now.date():
        return f'{time_text} today'
    return f"{time_text} on {dt.strftime('%d %B %Y')}"


def display_time_range(start: int, end: int | None) -> str:
    start_text = display_since(start)
    if end is None:
        return f'since {start_text}'
    end_text = display_since(end)
    return f'from {start_text} to {end_text}'


def state_name_to_attr(state: str) -> str:
    if state in ('active', 'inactive'):
        return 'motion'
    if state in ('open', 'closed'):
        return 'contact'
    if state in ('locked', 'unlocked'):
        return 'lock'
    return 'switch'


def state_window(period: str) -> tuple[int, int, str]:
    now_ts = int(time.time())
    now_dt = local_datetime(now_ts)
    period = normalise(period or 'today')
    if period in ('yesterday',):
        today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = today_start - timedelta(days=1)
        return int(start_dt.timestamp()), int(today_start.timestamp()), 'yesterday'
    if period in ('last 24 hours', 'past 24 hours', '24 hours'):
        return max(0, now_ts - 86400), now_ts, 'in the last 24 hours'
    start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start_dt.timestamp()), now_ts, 'today'


def state_sessions_in_window(
    device: dict[str, Any],
    attr: str,
    expected_state: str,
    start_ts: int,
    end_ts: int,
) -> tuple[list[dict[str, Any]], bool]:
    try:
        conn = db()
    except sqlite3.Error:
        return [], False
    try:
        rows = state_change_rows(conn, str(device.get('id')), attr)
    finally:
        conn.close()
    if not rows:
        return [], False

    rows_asc = sorted(rows, key=lambda item: item['created_at'])
    active_start: int | None = None
    has_relevant_history = False
    for row in rows_asc:
        ts = int(row['created_at'])
        if ts >= start_ts:
            break
        has_relevant_history = True
        active_start = start_ts if is_state(row['value'], expected_state) else None

    sessions: list[dict[str, Any]] = []
    for row in rows_asc:
        ts = int(row['created_at'])
        if ts < start_ts:
            continue
        if ts > end_ts:
            break
        has_relevant_history = True
        if is_state(row['value'], expected_state):
            if active_start is None:
                active_start = ts
        elif active_start is not None:
            sessions.append({
                'start': active_start,
                'end': ts,
                'duration_seconds': max(0, ts - active_start),
                'ongoing': False,
            })
            active_start = None

    if active_start is not None:
        sessions.append({
            'start': active_start,
            'end': end_ts,
            'duration_seconds': max(0, end_ts - active_start),
            'ongoing': True,
        })
    return sessions, has_relevant_history


def device_total_state_duration_answer(
    target: str,
    attr: str = 'switch',
    expected_state: str = 'on',
    period: str = 'today',
) -> dict[str, Any]:
    devices = intent_devices(target, attr)
    devices = [device for device in devices if device.get(attr) is not None]
    if not devices:
        return {'success': False, 'intent': 'device_total_state_duration', 'message': f'I found no device state history for {target}.'}
    if len(devices) > 1:
        return disambiguation_response(devices, 'check total state duration for')

    device = devices[0]
    start_ts, end_ts, period_label = state_window(period)
    sessions, has_history = state_sessions_in_window(device, attr, expected_state, start_ts, end_ts)
    total_seconds = sum(int(session['duration_seconds']) for session in sessions)
    if total_seconds <= 0:
        if not has_history:
            message = f"I do not have enough {device['label']} {attr} history to calculate {period_label}."
        else:
            message = f"{device['label']} was not {expected_state} {period_label}."
        return {
            'success': True,
            'intent': 'device_total_state_duration',
            'message': message,
            'speech': message,
            'device': device,
            'sessions': sessions,
            'total_seconds': total_seconds,
        }

    duration = elapsed_duration_label(total_seconds)
    message = f"{device['label']} was {expected_state} for {duration} {period_label}."
    return {
        'success': True,
        'intent': 'device_total_state_duration',
        'message': message,
        'speech': message,
        'device': device,
        'sessions': sessions,
        'total_seconds': total_seconds,
    }


def device_state_duration_answer(target: str, attr: str = 'switch', expected_state: str | None = None) -> dict[str, Any]:
    devices = intent_devices(target, attr)
    devices = [device for device in devices if device.get(attr) is not None]
    if not devices:
        return {'success': False, 'intent': 'device_state_duration', 'message': f'I found no device state history for {target}.'}
    if len(devices) > 1:
        return disambiguation_response(devices, 'check state duration for')
    device = devices[0]
    current = str(device.get(attr))
    if expected_state and not is_state(current, expected_state):
        message = f"{device['label']} is currently {current}, not {expected_state}."
        return {'success': True, 'intent': 'device_state_duration', 'message': message, 'speech': message, 'device': device}
    since = state_since_for_device(device, attr)
    if not since:
        return {
            'success': False,
            'intent': 'device_state_duration',
            'message': f"{device['label']} is currently {current}, but HomeBrain does not have a reliable latest {attr} change time yet.",
            'device': device,
        }
    duration = elapsed_duration_label(since['duration_seconds'])
    when = display_since(since['since'])
    message = f"{device['label']} has been {current} for {duration}, since {when}."
    return {'success': True, 'intent': 'device_state_duration', 'message': message, 'speech': message, 'device': device, 'since': since}


def device_last_state_duration_answer(target: str, attr: str = 'switch', expected_state: str = 'on') -> dict[str, Any]:
    devices = intent_devices(target, attr)
    devices = [device for device in devices if device.get(attr) is not None]
    if not devices:
        return {'success': False, 'intent': 'device_state_duration', 'message': f'I found no device state history for {target}.'}
    if len(devices) > 1:
        return disambiguation_response(devices, 'check last state duration for')
    device = devices[0]
    session = last_state_session_for_device(device, attr, expected_state)
    if not session:
        return {
            'success': False,
            'intent': 'device_state_duration',
            'message': f"{device['label']} has no reliable recorded {expected_state} session yet.",
            'device': device,
        }
    duration = elapsed_duration_label(session['duration_seconds'])
    current_word = 'has been' if session['end'] is None else 'was last'
    range_text = display_time_range(session['start'], session['end'])
    message = f"{device['label']} {current_word} {expected_state} for {duration}, {range_text}."
    return {'success': True, 'intent': 'device_state_duration', 'message': message, 'speech': message, 'device': device, 'session': session}


def active_rooms_answer() -> dict[str, Any]:
    devices = all_devices()
    by_room: dict[str, list[str]] = {}
    active_devices: list[dict[str, Any]] = []
    for device in devices:
        active_label = active_device_phrase(device)
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


def active_device_phrase(device: dict[str, Any]) -> str:
    label = str(device.get('label') or device.get('name') or '').strip()
    if not label:
        return ''
    level = safe_float(device.get('level'))
    power = safe_float(device.get('power'))
    if is_state(device.get('switch'), 'on'):
        if device.get('category') == 'light' and level is not None:
            return f'{label} on at {level:g}%'
        if power is not None and power >= 1:
            return f'{label} on, using {format_power_value(power)}'
        return f'{label} on'
    if is_state(device.get('motion'), 'active'):
        return f'{label} active'
    if is_state(device.get('contact'), 'open'):
        return f'{label} open'
    if is_state(device.get('lock'), 'unlocked'):
        return f'{label} unlocked'
    if is_state(device.get('water'), 'wet', 'detected'):
        return f'{label} leak detected'
    if is_state(device.get('presence'), 'present'):
        return f'{label} present'
    if 'heat' in normalise(device.get('thermostatOperatingState', '')):
        return f'{label} heating'
    if power is not None and power >= 3:
        return f'{label} using {format_power_value(power)}'
    return ''


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
    active = [d for d in devices if active_device_phrase(d)]
    lines = [active_device_phrase(d) for d in active]
    room_name = canonical_room_name(room)
    message = f'{room_name} active now:\n' + ('\n'.join(lines) if lines else 'Nothing active.')
    speech = f"{room_name}: {spoken_list(lines)}" if active else f'{room_name}: nothing is active.'
    return {'success': True, 'intent': 'room_on_status', 'message': message, 'speech': speech, 'devices': active, 'room': room_name}


def device_health_answer() -> dict[str, Any]:
    summary = dashboard_summary()
    diagnostics = device_diagnostics()
    stale = diagnostics['stale']
    low_battery_devices = summary['low_battery_devices'][:8]
    healthy_count = max(0, diagnostics['devices'] - stale['issue_count'] - summary['low_batteries'])
    lines = [
        'AI Device Health Monitor:',
        f"🟢 Healthy: {healthy_count} devices",
        f"🟡 Needs attention: {stale['issue_count'] + summary['low_batteries']} items",
        f"Low batteries: {summary['low_batteries']}",
    ]
    if stale['not_reporting']:
        lines.append('🔴 Offline / not reporting:\n' + '\n'.join(f"• {item['label']} ({item['room']}) — {item['duration']}" for item in stale['not_reporting'][:8]))
    if low_battery_devices:
        lines.append('🟠 Battery:\n' + '\n'.join(f"• {format_summary_device(d, 'battery', '%')}" for d in low_battery_devices))
    attention: list[str] = []
    attention.extend(f"• {item['label']} motion active for {item['duration']}" for item in stale['motion_active_too_long'][:5])
    attention.extend(f"• {item['label']} light on for {item['duration']}" for item in stale['lights_on_too_long'][:5])
    if attention:
        lines.append('🟡 Actionable checks:\n' + '\n'.join(attention))
    if stale.get('occupied_long'):
        lines.append('🔵 Normal occupancy, not stale:\n' + '\n'.join(f"• {item['label']} ({item['room']}) occupied for {item['duration']}" for item in stale['occupied_long'][:5]))
    if diagnostics['unknown_switch_state'] or diagnostics['unknown_room']:
        lines.append(f"Housekeeping: unknown switch states {diagnostics['unknown_switch_state']}, unknown rooms {diagnostics['unknown_room']} — ask 'what are the unknowns' for the device list.")
    if diagnostics['last_error']:
        lines.append(f"Last Hubitat error: {diagnostics['last_error']}")
    return {'success': True, 'intent': 'device_health', 'message': '\n'.join(lines), 'summary': summary, 'diagnostics': diagnostics}


# ---------------------------------------------------------------------------
# HomeBrain v0.8 practical intelligence layer
# ---------------------------------------------------------------------------

def device_state_since_seconds(device: dict[str, Any], attr: str, default_seconds: int = 0) -> int:
    state = state_since_for_device(device, attr)
    if state and isinstance(state.get('duration_seconds'), int):
        return int(state['duration_seconds'])
    return default_seconds


def switched_on_devices() -> list[dict[str, Any]]:
    return [d for d in all_devices() if is_state(d.get('switch'), 'on')]


def energy_waste_candidates() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for d in switched_on_devices():
        label = d.get('label') or d.get('name') or str(d.get('id'))
        text = device_search_text(d)
        power = safe_float(d.get('power'))
        on_for = device_state_since_seconds(d, 'switch')
        long_on = on_for >= 4 * 3600
        high_power = power is not None and power >= 25
        standby = power is not None and 2 <= power < 25 and on_for >= 8 * 3600
        ignore = any(term in text for term in ('fridge', 'freezer', 'router', 'mesh', 'hub', 'server', 'octopus', 'meter'))
        if ignore and not high_power:
            continue
        if not (long_on or high_power or standby):
            continue
        monthly_kwh = None
        monthly_cost = None
        if power is not None:
            hours_per_month = 24 * 30 if standby else max(1, min(24, on_for / 3600)) * 30
            monthly_kwh = round((power * hours_per_month) / 1000, 2)
            monthly_cost = round(monthly_kwh * 0.25, 2)
        reason = 'high power now' if high_power else 'low standby left on' if standby else 'on for a long time'
        results.append({
            'id': d.get('id'), 'label': label, 'room': d.get('room') or 'Unknown',
            'power': power, 'power_display': format_power_value(power) if power is not None else 'unknown power',
            'on_for_seconds': on_for, 'on_for': elapsed_duration_label(on_for) if on_for else 'unknown duration',
            'estimated_monthly_kwh': monthly_kwh, 'estimated_monthly_cost_gbp': monthly_cost, 'reason': reason,
        })
    results.sort(key=lambda x: ((x.get('estimated_monthly_cost_gbp') or 0), x.get('on_for_seconds') or 0), reverse=True)
    return results


def energy_advisor_answer() -> dict[str, Any]:
    summary = dashboard_summary()
    candidates = energy_waste_candidates()
    lines = ['AI Energy Advisor:', f"Whole-house power now: {summary['power_display']} from {summary['power_source_label']}"]
    if not candidates:
        lines.append('No obvious energy waste found from current device states.')
    else:
        lines.append('Worth checking:')
        for item in candidates[:8]:
            cost = f", about £{item['estimated_monthly_cost_gbp']}/month" if item.get('estimated_monthly_cost_gbp') is not None else ''
            lines.append(f"• {item['label']} ({item['room']}) — {item['power_display']}, on for {item['on_for']}{cost} [{item['reason']}]")
    return {'success': True, 'intent': 'energy_advisor', 'message': '\n'.join(lines), 'summary': summary, 'candidates': candidates}


def recent_home_timeline(limit: int = 25, hours: int = 12) -> list[dict[str, Any]]:
    cutoff = int(time.time()) - max(1, hours) * 3600
    items: list[dict[str, Any]] = []
    try:
        conn = db()
    except sqlite3.Error:
        return items
    try:
        rows = conn.execute("""
            SELECT device_id, label, attr, value, created_at, 'event' AS source
            FROM hubitat_events
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (cutoff, limit * 2)).fetchall()
        if not rows:
            rows = conn.execute("""
                SELECT h.device_id, d.label, h.attr, h.value, h.created_at, 'history' AS source
                FROM history h LEFT JOIN devices d ON d.id=h.device_id
                WHERE h.created_at >= ?
                ORDER BY h.created_at DESC
                LIMIT ?
            """, (cutoff, limit * 2)).fetchall()
        for row in rows:
            label = row['label'] or row['device_id'] or 'Device'
            attr = row['attr'] or 'event'
            value = row['value'] or ''
            if attr in ('temperature', 'humidity', 'battery', 'energy'):
                continue
            ts = int(row['created_at'])
            items.append({'time': time.strftime('%H:%M', time.localtime(ts)), 'label': label, 'attr': attr, 'value': value, 'source': row['source'], 'created_at': ts, 'text': f"{time.strftime('%H:%M', time.localtime(ts))} — {label} {attr} {value}".strip()})
            if len(items) >= limit:
                break
    finally:
        conn.close()
    return items


def timeline_answer() -> dict[str, Any]:
    items = recent_home_timeline()
    lines = ['Home Timeline:']
    lines.extend(item['text'] for item in items[:20])
    if len(lines) == 1:
        lines.append('No recent device events found. Make sure the Hubitat event callback is configured.')
    return {'success': True, 'intent': 'home_timeline', 'message': '\n'.join(lines), 'events': items}


def practical_home_insights() -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    summary = dashboard_summary()
    stale = stale_device_report()
    if stale['not_reporting']:
        insights.append({'level': 'critical', 'title': 'Devices not reporting', 'detail': f"{len(stale['not_reporting'])} device(s) have not reported recently.", 'items': stale['not_reporting'][:5]})
    if summary['low_batteries']:
        insights.append({'level': 'warning', 'title': 'Low batteries', 'detail': f"{summary['low_batteries']} device(s) need battery attention.", 'items': summary['low_battery_devices'][:5]})
    if stale['motion_active_too_long']:
        insights.append({'level': 'warning', 'title': 'Motion may be stuck', 'detail': f"{len(stale['motion_active_too_long'])} PIR motion sensor(s) active too long.", 'items': stale['motion_active_too_long'][:5]})
    if stale['lights_on_too_long']:
        insights.append({'level': 'info', 'title': 'Lights left on', 'detail': f"{len(stale['lights_on_too_long'])} light(s) have been on a long time.", 'items': stale['lights_on_too_long'][:5]})
    energy = energy_waste_candidates()
    if energy:
        insights.append({'level': 'info', 'title': 'Energy saving opportunity', 'detail': f"{energy[0]['label']} is the top device worth checking.", 'items': energy[:5]})
    return insights


def home_health_answer() -> dict[str, Any]:
    summary = dashboard_summary()
    diagnostics = device_diagnostics()
    insights = practical_home_insights()
    penalty = 0
    for item in insights:
        penalty += {'critical': 12, 'warning': 7, 'info': 3}.get(item['level'], 1)
    if diagnostics.get('last_error'):
        penalty += 10
    score = max(0, min(100, 100 - penalty))
    status = '🟢 Home healthy' if score >= 90 else '🟡 Needs attention' if score >= 70 else '🔴 Needs action'
    lines = [f'Home Health: {score}/100', status, f"Devices: {summary['devices']} · Power: {summary['power_display']} · People home: {summary['people_home']}/{summary['people_tracked']}"]
    if insights:
        lines.append('What needs attention:')
        for insight in insights[:8]:
            lines.append(f"• {insight['title']}: {insight['detail']}")
    else:
        lines.append('No obvious issues found.')
    if stale_device_report().get('occupied_long'):
        lines.append('Presence sensors showing long occupancy are treated as normal, not stale.')
    return {'success': True, 'intent': 'home_health', 'message': '\n'.join(lines), 'score': score, 'summary': summary, 'diagnostics': diagnostics, 'insights': insights}


def daily_briefing_answer() -> dict[str, Any]:
    summary = dashboard_summary()
    weather = weather_device()
    health = home_health_answer()
    energy = energy_waste_candidates()
    lines = ['Daily Home Briefing:', f"Home health: {health['score']}/100"]
    if summary['avg_temperature'] is not None:
        lines.append(f"Inside: {summary['avg_temperature']}°C, humidity {summary['avg_humidity']}%")
    else:
        lines.append('Inside: no temperature summary available')
    lines.extend([f"People home: {summary['people_home']}/{summary['people_tracked']}", f"Power now: {summary['power_display']}"])
    if weather:
        weather_text = weather.get('weatherSummaryLine') or weather.get('weatherSummary') or weather.get('label')
        lines.append(f"Weather: {weather_text}")
    insights = health.get('insights') or []
    if insights:
        lines.append('Today, check:')
        lines.extend(f"• {i['title']} — {i['detail']}" for i in insights[:5])
    if energy:
        lines.append(f"Energy tip: check {energy[0]['label']} ({energy[0]['power_display']}).")
    return {'success': True, 'intent': 'daily_briefing', 'message': '\n'.join(lines), 'summary': summary, 'health': health, 'energy': energy[:5]}



def active_light_explanation_answer(text: str) -> dict[str, Any] | None:
    """Explain why the lights-on summary says what it says.

    This avoids falling through to generic diagnostics for natural questions like
    "why are 3 lights on?" and gives a human answer using live state, room
    activity, and event history.
    """
    t = normalise(text)
    if 'light' not in t or not any(word in t for word in ('why', 'explain')):
        return None

    devices = all_devices()
    lights_on = [d for d in devices if d.get('category') == 'light' and is_state(d.get('switch'), 'on')]
    lights_on.sort(key=lambda d: (canonical_room_name(d.get('room') or 'Unknown').lower(), str(d.get('label') or '').lower()))
    if not lights_on:
        msg = 'No lights are currently on.'
        return {'success': True, 'intent': 'explain_lights_on', 'message': msg, 'speech': msg, 'devices': []}

    number_match = re.search(r'\b(\d+)\s+lights?\b', t)
    expected_count = int(number_match.group(1)) if number_match else None
    count_note = ''
    if expected_count is not None and expected_count != len(lights_on):
        count_note = f" The live event cache now shows {len(lights_on)}, not {expected_count}."

    lines = [f"{len(lights_on)} light" + ('' if len(lights_on) == 1 else 's') + f" are currently on.{count_note}"]
    lines.append('')
    lines.append('Lights on:')

    suggestions: list[str] = []
    for light in lights_on[:12]:
        label = str(light.get('label') or light.get('name') or light.get('id'))
        room = canonical_room_name(light.get('room') or 'Unknown')
        since = state_since_for_device(light, 'switch')
        since_text = ''
        long_on = False
        if since:
            duration = elapsed_duration_label(since['duration_seconds'])
            since_text = f' — on for {duration}'
            long_on = int(since['duration_seconds']) >= 2 * 3600
        activity = room_activity_reason(room, devices)
        reason = activity or 'no recent room activity found in the event cache'
        lines.append(f"• {label}" + (f" ({room})" if room != 'Unknown' else '') + f"{since_text} — {reason}.")
        if long_on and not activity:
            suggestions.append(f"{label} has been on for {elapsed_duration_label(since['duration_seconds'])} with no recent room activity; consider turning it off or adding an auto-off rule.")

    if len(lights_on) > 12:
        lines.append(f"• {len(lights_on) - 12} more lights not shown.")
    if suggestions:
        lines.append('')
        lines.append('Suggestion:')
        lines.extend(f"• {s}" for s in suggestions[:3])
    else:
        lines.append('')
        lines.append('No obvious problem found. These lights look explainable from current state or recent room activity.')

    speech = f"{len(lights_on)} lights are on: " + ', '.join(str(d.get('label') or d.get('name')) for d in lights_on[:5]) + '.'
    return {'success': True, 'intent': 'explain_lights_on', 'message': '\n'.join(lines), 'speech': speech, 'devices': lights_on, 'suggestions': suggestions}


def room_activity_reason(room: str, devices: list[dict[str, Any]], minutes: int = 20) -> str | None:
    if not room or room == 'Unknown':
        return None
    room_norm = canonical_room_name(room)
    now = int(time.time())
    candidates = [d for d in devices if canonical_room_name(d.get('room') or 'Unknown') == room_norm]
    # Current active motion/presence is the strongest explanation.
    for d in candidates:
        if is_state(d.get('motion'), 'active') or is_state(d.get('presence'), 'present'):
            label = str(d.get('label') or d.get('name') or 'room sensor')
            return f'{label} shows activity now'
    # If the room is currently idle, use recent events to explain whether the
    # light likely came from recent occupancy.
    cutoff = now - max(1, minutes) * 60
    ids = [str(d.get('id')) for d in candidates if d.get('id')]
    if not ids:
        return None
    try:
        conn = db()
        placeholders = ','.join('?' for _ in ids)
        rows = conn.execute(
            f"""
            SELECT device_id, label, attr, value, created_at
            FROM hubitat_events
            WHERE device_id IN ({placeholders})
              AND attr IN ('motion','presence','contact')
              AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (*ids, cutoff),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    for row in rows:
        attr = str(row['attr'])
        value = str(row['value'])
        label = str(row['label'] or row['device_id'] or 'room sensor')
        age = elapsed_duration_label(now - int(row['created_at']))
        if (attr == 'motion' and value == 'active') or (attr == 'presence' and value == 'present'):
            return f'{label} reported {value} {age} ago'
        if attr == 'contact' and value in {'open', 'closed'}:
            return f'{label} was {value} {age} ago'
    return None

def explain_home_question_answer(text: str) -> dict[str, Any] | None:
    """Deterministic "why" answers for common real-life home questions.

    This is intentionally rule-based so HomeBrain can explain the home even when
    the local LLM is disabled or slow.
    """
    t = normalise(text)
    devices = all_devices()
    lines: list[str] = []
    intent = 'ai_explain'

    if 'fan' in t or 'humidity' in t or 'bathroom' in t:
        humid = sorted(
            [d for d in devices if isinstance(d.get('humidity'), (int, float))],
            key=lambda d: float(d.get('humidity') or 0),
            reverse=True,
        )[:5]
        fans = [d for d in devices if 'fan' in device_search_text(d) or 'ventilation' in device_search_text(d)]
        if humid or fans:
            lines.append('Bathroom / humidity explanation:')
            for d in humid[:3]:
                lines.append(f"• {d.get('label')}: humidity {d.get('humidity')}%")
            for d in fans[:3]:
                state = d.get('switch') or d.get('motion') or 'unknown'
                lines.append(f"• {d.get('label')}: {state}")
            lines.append('Check whether humidity is above your fan threshold or whether a manual/timer boost is still running.')

    if 'electricity' in t or 'energy' in t or 'power' in t or 'cost' in t:
        energy = energy_waste_candidates()
        summary = dashboard_summary()
        lines.append(f"Energy explanation: whole-house power is {summary['power_display']} from {summary['power_source_label']}.")
        if energy:
            lines.append('Top contributors worth checking:')
            lines.extend(f"• {item['label']} — {item['power_display']}, on for {item['on_for']}" for item in energy[:5])
        else:
            power_devices = sorted([d for d in devices if isinstance(d.get('power'), (int, float))], key=lambda d: d.get('power') or 0, reverse=True)[:5]
            if power_devices:
                lines.append('Highest live power devices:')
                lines.extend(f"• {d.get('label')} — {format_power_value(d.get('power'))}" for d in power_devices)

    if 'heating' in t or 'cold' in t or 'temperature' in t:
        cold = sorted([d for d in devices if isinstance(d.get('temperature'), (int, float))], key=lambda d: d.get('temperature') or 99)[:5]
        thermostats = [d for d in devices if d.get('category') == 'thermostat' or d.get('heatingSetpoint') is not None]
        lines.append('Heating / temperature explanation:')
        for d in cold[:5]:
            lines.append(f"• {d.get('label')}: {d.get('temperature')}°C")
        for d in thermostats[:5]:
            sp = d.get('heatingSetpoint')
            mode = d.get('thermostatMode') or 'unknown mode'
            state = d.get('thermostatOperatingState') or 'unknown state'
            lines.append(f"• {d.get('label')}: set {sp}°C, {mode}, {state}")

    if 'stale' in t or 'offline' in t or 'not reporting' in t:
        stale = stale_device_report()
        lines.append('Device health explanation:')
        if stale['not_reporting']:
            lines.extend(f"• {i['label']}: no real activity for {i['duration']} ({i.get('confidence','unknown')} confidence)" for i in stale['not_reporting'][:5])
        if stale['occupied_long']:
            lines.extend(f"• {i['label']}: occupied for {i['duration']} — normal for presence/mmWave sensors, not stale" for i in stale['occupied_long'][:5])
        if not stale['not_reporting'] and not stale['occupied_long']:
            lines.append('No obvious offline or incorrectly-stale device issue found.')

    if not lines:
        return None
    return {'success': True, 'intent': intent, 'message': '\n'.join(lines), 'speech': ' '.join(line.lstrip('• ') for line in lines[:6])}


def room_intelligence_answer(text: str) -> dict[str, Any] | None:
    t = normalise(text)
    if not any(word in t for word in ('room summary', 'summarise room', 'summarize room', 'room health', 'room status', 'explain room')):
        return None
    matched = None
    for room in api_rooms()['rooms']:
        if normalise(room['room']) in t:
            matched = room['room']
            break
    if not matched:
        return {'success': False, 'intent': 'room_intelligence', 'message': 'Tell me which room, for example: room summary living room.'}
    payload = room_details_payload(matched)
    devices = exact_room_devices(payload['room']['room'])
    occupied = [d for d in devices if is_state(d.get('motion'), 'active') or is_state(d.get('presence'), 'present')]
    lights_on = [d for d in devices if d.get('category') == 'light' and is_state(d.get('switch'), 'on')]
    power = sum(float(d.get('power') or 0) for d in devices if isinstance(d.get('power'), (int, float)))
    temps = [d.get('temperature') for d in devices if isinstance(d.get('temperature'), (int, float))]
    hums = [d.get('humidity') for d in devices if isinstance(d.get('humidity'), (int, float))]
    lines = [f"{payload['room']['room']} summary:"]
    lines.append('Occupied' if occupied else 'No current occupancy detected')
    if temps:
        lines.append(f"Temperature: {round(sum(temps)/len(temps), 1)}°C")
    if hums:
        lines.append(f"Humidity: {round(sum(hums)/len(hums), 1)}%")
    lines.append(f"Lights on: {len(lights_on)}")
    if power:
        lines.append(f"Power now: {format_power_value(power)}")
    attention = []
    for d in devices:
        if isinstance(d.get('battery'), (int, float)) and d.get('battery') <= 20:
            attention.append(f"{d.get('label')} battery {d.get('battery')}%")
    if attention:
        lines.append('Needs attention: ' + '; '.join(attention[:5]))
    else:
        lines.append('No obvious room issues found.')
    return {'success': True, 'intent': 'room_intelligence', 'message': '\n'.join(lines), 'room': payload['room'], 'devices': payload['devices']}


def what_changed_answer() -> dict[str, Any]:
    items = recent_home_timeline(limit=40, hours=24)
    if not items:
        return {'success': True, 'intent': 'what_changed', 'message': 'No changes found in the last 24 hours. Check the Hubitat event callback if this looks wrong.', 'events': []}
    grouped: dict[str, int] = {}
    for item in items:
        key = str(item.get('label') or 'Device')
        grouped[key] = grouped.get(key, 0) + 1
    top = sorted(grouped.items(), key=lambda kv: kv[1], reverse=True)[:5]
    lines = ['What changed in the last 24 hours:', f"{len(items)} recent events recorded."]
    lines.append('Most active devices:')
    lines.extend(f"• {name}: {count} events" for name, count in top)
    lines.append('Latest events:')
    lines.extend('• ' + item['text'] for item in items[:8])
    return {'success': True, 'intent': 'what_changed', 'message': '\n'.join(lines), 'events': items, 'top_devices': top}


def recommendations_answer() -> dict[str, Any]:
    insights = practical_home_insights()
    recs: list[str] = []
    for insight in insights:
        title = insight.get('title', '')
        if title == 'Devices not reporting':
            recs.append('Check power/battery and Zigbee/MQTT connectivity for the devices not reporting.')
        elif title == 'Low batteries':
            recs.append('Replace low batteries before automations become unreliable.')
        elif title == 'Motion may be stuck':
            recs.append('Check PIR sensors that show active too long; they may be stuck, aimed badly, or exposed to heat movement.')
        elif title == 'Lights left on':
            recs.append('Turn off lights left on for a long time or add an auto-off rule for that room.')
        elif title == 'Energy saving opportunity':
            recs.append('Review devices left on with measurable power draw, especially standby loads overnight.')
    if not recs:
        recs.append('No urgent recommendations. Next useful improvement is to add more event callbacks so HomeBrain can build better history.')
    lines = ['Recommended actions:'] + [f'• {r}' for r in recs[:8]]
    return {'success': True, 'intent': 'recommendations', 'message': '\n'.join(lines), 'insights': insights, 'recommendations': recs}


def recent_device_events_for(device_ids: list[str], hours: int = 24, limit: int = 200) -> list[dict[str, Any]]:
    """Return recent Hubitat callback events for a set of device ids."""
    ids = [str(i) for i in device_ids if i is not None]
    if not ids:
        return []
    cutoff = int(time.time()) - max(1, hours) * 3600
    placeholders = ','.join('?' for _ in ids)
    try:
        conn = db()
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(f"""
            SELECT device_id, label, attr, value, created_at
            FROM hubitat_events
            WHERE created_at >= ? AND device_id IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT ?
        """, [cutoff, *ids, limit]).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def numeric_event_values(events: list[dict[str, Any]], attr: str) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for event in events:
        if str(event.get('attr') or '').lower() != attr.lower():
            continue
        try:
            values.append((int(event.get('created_at') or 0), float(event.get('value'))))
        except (TypeError, ValueError):
            continue
    return values


def automation_health_answer() -> dict[str, Any]:
    """Self-check common automations by verifying the expected outcome happened.

    This is deliberately practical and deterministic: it does not need cloud AI.
    It checks for evidence from Hubitat callback events and current device state.
    """
    devices = all_devices()
    now = int(time.time())
    fan_devices = [d for d in devices if 'fan' in device_search_text(d) or 'ventilation' in device_search_text(d) or 'boost' in device_search_text(d)]
    humidity_devices = [d for d in devices if isinstance(d.get('humidity'), (int, float)) and ('bathroom' in normalise(d.get('room') or '') or 'bathroom' in device_search_text(d) or 'humidity' in device_search_text(d))]
    checks: list[dict[str, Any]] = []

    # Bathroom / humidity fan outcome verification.
    if fan_devices or humidity_devices:
        fan_ids = [str(d.get('id')) for d in fan_devices]
        humidity_ids = [str(d.get('id')) for d in humidity_devices]
        fan_events = recent_device_events_for(fan_ids, hours=24, limit=120)
        humidity_events = recent_device_events_for(humidity_ids, hours=24, limit=160)
        humid_values: list[tuple[int, float]] = []
        for d in humidity_devices:
            if isinstance(d.get('humidity'), (int, float)):
                humid_values.append((now, float(d.get('humidity'))))
        humid_values.extend(numeric_event_values(humidity_events, 'humidity'))
        max_humidity = max((v for _, v in humid_values), default=None)
        current_humidity = max((float(d.get('humidity')) for d in humidity_devices if isinstance(d.get('humidity'), (int, float))), default=None)
        fan_on_events = [e for e in fan_events if str(e.get('attr') or '').lower() == 'switch' and is_state(e.get('value'), 'on')]
        fan_off_events = [e for e in fan_events if str(e.get('attr') or '').lower() == 'switch' and is_state(e.get('value'), 'off')]
        fan_current_on = any(is_state(d.get('switch'), 'on') for d in fan_devices)
        status = 'unknown'
        detail = 'Not enough event history yet to fully verify the fan automation. Make sure the Hubitat event callback is enabled.'
        recommendation = 'Ask again after a fan cycle, or trigger the bathroom fan manually and check it is recorded in the timeline.'
        if max_humidity is not None and max_humidity >= 70:
            if fan_on_events or fan_current_on:
                if current_humidity is not None and max_humidity - current_humidity >= 5:
                    status = 'success'
                    detail = f'Humidity reached {round(max_humidity,1)}% and the fan was seen ON; humidity is now {round(current_humidity,1)}%.'
                    recommendation = 'Fan outcome looks good.'
                else:
                    status = 'warning'
                    detail = f'Humidity reached {round(max_humidity,1)}% and the fan was seen ON, but humidity has not clearly dropped yet.'
                    recommendation = 'Check whether the fan needs longer, the threshold is too low, or ventilation needs cleaning.'
            else:
                status = 'critical'
                detail = f'Humidity reached {round(max_humidity,1)}%, but no fan ON confirmation was found in recent events.'
                recommendation = 'Check SwitchBot/Fan switch reliability and Maker API event callback.'
        elif fan_on_events or fan_off_events:
            status = 'success'
            detail = f'Fan activity was recorded today: {len(fan_on_events)} ON event(s), {len(fan_off_events)} OFF event(s).'
            recommendation = 'Command/result feedback is being recorded.'
        checks.append({'name': 'Bathroom fan humidity automation', 'status': status, 'detail': detail, 'recommendation': recommendation, 'devices': [d.get('label') for d in fan_devices[:5] + humidity_devices[:5]]})

    # Device health self-check: tells whether the monitoring automation itself has evidence.
    stale = stale_device_report()
    if stale.get('not_reporting'):
        checks.append({'name': 'Device reporting monitor', 'status': 'warning', 'detail': f"{len(stale['not_reporting'])} device(s) have no recent real activity.", 'recommendation': 'Check batteries, Zigbee mesh, MQTT broker, and whether those devices are included in Maker API.', 'devices': [i['label'] for i in stale['not_reporting'][:8]]})
    else:
        checks.append({'name': 'Device reporting monitor', 'status': 'success', 'detail': 'No not-reporting devices found by the health engine.', 'recommendation': 'Device health monitor looks clear.', 'devices': []})

    # Energy advisor self-check: verifies it can identify measurable loads.
    energy = energy_waste_candidates()
    if energy:
        checks.append({'name': 'Energy waste monitor', 'status': 'warning', 'detail': f"{len(energy)} device(s) look worth checking for standby or long-running power draw.", 'recommendation': 'Review top loads and add auto-off rules where practical.', 'devices': [i['label'] for i in energy[:8]]})
    else:
        powered = [d for d in devices if isinstance(d.get('power'), (int, float))]
        checks.append({'name': 'Energy waste monitor', 'status': 'success' if powered else 'unknown', 'detail': 'No obvious energy waste found.' if powered else 'No power meter data found, so energy automation cannot be verified.', 'recommendation': 'Add power-reporting devices to Maker API for stronger energy checks.', 'devices': [d.get('label') for d in powered[:8]]})

    score = 100
    score -= 30 * sum(1 for c in checks if c['status'] == 'critical')
    score -= 12 * sum(1 for c in checks if c['status'] == 'warning')
    score -= 5 * sum(1 for c in checks if c['status'] == 'unknown')
    score = max(0, score)
    lines = ['Automation Health:', f'Score: {score}/100']
    for check in checks:
        icon = {'success': '✅', 'warning': '⚠️', 'critical': '🔴', 'unknown': 'ℹ️'}.get(check['status'], '•')
        lines.append(f"{icon} {check['name']}: {check['detail']}")
        if check.get('recommendation'):
            lines.append(f"   Action: {check['recommendation']}")
    return {'success': True, 'intent': 'automation_health', 'score': score, 'message': '\n'.join(lines), 'checks': checks}


def automation_explain_answer(text: str) -> dict[str, Any] | None:
    t = normalise(text)
    if not any(word in t for word in ('automation', 'fan work', 'did the fan', 'fan failed', 'actions successful', 'which automations failed', 'outcome')):
        return None
    health = automation_health_answer()
    if 'fan' in t:
        checks = [c for c in health['checks'] if 'fan' in normalise(c.get('name') or '')]
    elif 'failed' in t:
        checks = [c for c in health['checks'] if c.get('status') in ('critical', 'warning')]
    else:
        checks = health['checks']
    if not checks:
        return {'success': True, 'intent': 'automation_explain', 'message': 'No matching automation issue found.', 'checks': []}
    lines = ['Automation explanation:']
    for c in checks:
        lines.append(f"• {c['name']}: {c['detail']}")
        lines.append(f"  Next: {c['recommendation']}")
    return {'success': True, 'intent': 'automation_explain', 'message': '\n'.join(lines), 'checks': checks}

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



def current_performance_metrics() -> dict[str, Any]:
    now = time.time()
    uptime_seconds = max(1, int(now - float(PERF_STATS.get('started_at') or now)))
    full_refresh_count = int(PERF_STATS.get('full_refresh_count') or 0)
    detail_fetches = int(PERF_STATS.get('detail_fetch_count') or 0)
    maker_get_count = int(PERF_STATS.get('maker_get_count') or 0)
    maker_errors = int(PERF_STATS.get('maker_get_error_count') or 0)
    event_count = int(PERF_STATS.get('event_count') or 0)
    calls_per_hour = round(maker_get_count * 3600 / uptime_seconds, 1)
    legacy_calls_per_hour = round((full_refresh_count + detail_fetches) * 3600 / uptime_seconds, 1)
    return {
        'uptime_seconds': uptime_seconds,
        'devices': count_devices(),
        'maker_get_count': maker_get_count,
        'maker_get_error_count': maker_errors,
        'full_refresh_count': full_refresh_count,
        'detail_fetch_count': detail_fetches,
        'event_count': event_count,
        'event_updated_count': int(PERF_STATS.get('event_updated_count') or 0),
        'calls_per_hour': calls_per_hour,
        'legacy_calls_per_hour': legacy_calls_per_hour,
        'event_rate_per_hour': round(event_count * 3600 / uptime_seconds, 1),
        'last_full_refresh_ms': PERF_STATS.get('full_refresh_last_ms'),
        'last_maker_get_ms': PERF_STATS.get('maker_get_last_ms'),
        'last_maker_path': PERF_STATS.get('maker_get_last_path'),
        'last_refresh_age_seconds': int(now - LAST_REFRESH) if LAST_REFRESH else None,
    }


def save_performance_snapshot(reason: str) -> dict[str, Any]:
    metrics = current_performance_metrics()
    conn = db()
    try:
        conn.execute(
            'INSERT INTO performance_snapshots(reason,devices,maker_get_count,maker_get_error_count,full_refresh_count,detail_fetch_count,event_count,calls_per_hour,json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (
                reason,
                metrics['devices'],
                metrics['maker_get_count'],
                metrics['maker_get_error_count'],
                metrics['full_refresh_count'],
                metrics['detail_fetch_count'],
                metrics['event_count'],
                metrics['calls_per_hour'],
                json.dumps({'metrics': metrics, 'perf': PERF_STATS, 'config': {k: CONFIG.get(k) for k in ('refresh_seconds','min_full_refresh_seconds','device_detail_refresh_seconds','device_detail_refresh_batch','device_detail_refresh_limit')}}),
                int(time.time()),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return metrics


def recent_performance_snapshots(limit: int = 10) -> list[dict[str, Any]]:
    conn = db()
    try:
        rows = conn.execute('SELECT * FROM performance_snapshots ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def performance_baseline_answer(reason: str = 'manual') -> dict[str, Any]:
    metrics = save_performance_snapshot(reason)
    message = '\n'.join([
        'Performance baseline saved.',
        f"Devices cached: {metrics['devices']}",
        f"Maker API calls since start: {metrics['maker_get_count']}",
        f"Estimated Maker API calls/hour: {metrics['calls_per_hour']}",
        f"Hubitat events/hour: {metrics['event_rate_per_hour']}",
        'Compare this tomorrow after checking Hubitat App Stats.',
    ])
    return {'success': True, 'intent': 'performance_baseline', 'message': message, 'metrics': metrics, 'snapshots': recent_performance_snapshots(5)}


def performance_compare_answer() -> dict[str, Any]:
    current = current_performance_metrics()
    snapshots = recent_performance_snapshots(10)
    if not snapshots:
        return performance_baseline_answer('auto-first-baseline')
    baseline = snapshots[-1]
    try:
        base_json = json.loads(baseline['json'])
        base_metrics = base_json.get('metrics') or {}
    except Exception:
        base_metrics = {}
    base_calls = float(base_metrics.get('calls_per_hour') or baseline.get('calls_per_hour') or 0)
    cur_calls = float(current.get('calls_per_hour') or 0)
    change = round(((cur_calls - base_calls) / base_calls) * 100, 1) if base_calls else None
    lines = [
        'Performance comparison:',
        f"Baseline calls/hour: {base_calls}",
        f"Current calls/hour: {cur_calls}",
    ]
    if change is not None:
        direction = 'lower' if change < 0 else 'higher'
        lines.append(f"Change: {abs(change)}% {direction}")
    lines.extend([
        f"Current Maker API calls: {current['maker_get_count']}",
        f"Current Hubitat events/hour: {current['event_rate_per_hour']}",
        f"Snapshots stored: {len(snapshots)}",
    ])
    return {'success': True, 'intent': 'performance_compare', 'message': '\n'.join(lines), 'baseline': baseline, 'current': current, 'change_percent': change, 'snapshots': snapshots}

def performance_advisor_answer() -> dict[str, Any]:
    now = time.time()
    metrics = current_performance_metrics()
    devices = metrics['devices']
    full_refresh_count = metrics['full_refresh_count']
    skipped = int(PERF_STATS.get('full_refresh_skipped') or 0)
    detail_fetches = metrics['detail_fetch_count']
    event_count = metrics['event_count']
    updated = metrics['event_updated_count']
    calls_per_hour = metrics['calls_per_hour']
    event_rate = metrics['event_rate_per_hour']
    last_age = int(now - LAST_REFRESH) if LAST_REFRESH else None
    warnings: list[str] = []
    if int(CONFIG.get('refresh_seconds', 120)) < 60:
        warnings.append('Full refresh interval is under 60 seconds; this can create high Maker API load.')
    if int(CONFIG.get('device_detail_refresh_batch', 5)) > 10:
        warnings.append('Device detail batch is high; lower it if Hubitat busy time rises.')
    if calls_per_hour > 300:
        warnings.append('Maker API request rate is high. Prefer Hubitat event webhooks and cached answers.')
    if LAST_ERROR:
        warnings.append(f'Last Hubitat refresh error: {LAST_ERROR}')
    level = '🟢 Healthy' if not warnings else '🟡 Needs tuning' if calls_per_hour < 600 else '🔴 High load risk'
    lines = [
        'Performance advisor:',
        level,
        f"Devices cached: {devices}",
        f"Full refreshes: {full_refresh_count}",
        f"Skipped refreshes: {skipped}",
        f"Detail fetches: {detail_fetches}",
        f"Hubitat events processed: {event_count} ({updated} cache updates)",
        f"Actual Maker API GETs since start: {metrics['maker_get_count']}",
        f"Estimated Maker API calls/hour since start: {calls_per_hour}",
        f"Event rate/hour since start: {event_rate}",
    ]
    if last_age is not None:
        lines.append(f"Last full refresh: {elapsed_duration_label(last_age)} ago")
    lines.append(f"Refresh interval: {CONFIG.get('refresh_seconds')}s")
    lines.append(f"Minimum full-refresh gap: {CONFIG.get('min_full_refresh_seconds')}s")
    lines.append(f"Detail refresh batch: {CONFIG.get('device_detail_refresh_batch')} every {CONFIG.get('device_detail_refresh_seconds')}s")
    if warnings:
        lines.append('\nWarnings:')
        lines.extend(f"• {w}" for w in warnings)
    else:
        lines.append('\nNo performance warnings detected.')
    lines.append('\nOptimisation active: cached API answers, throttled full refreshes, smaller device-detail batches, and event-driven cache updates.')
    return {
        'success': True,
        'intent': 'performance_advisor',
        'message': '\n'.join(lines),
        'level': level,
        'warnings': warnings,
        'stats': PERF_STATS,
        'metrics': metrics,
        'snapshots': recent_performance_snapshots(5),
        'config': {
            'refresh_seconds': CONFIG.get('refresh_seconds'),
            'min_full_refresh_seconds': CONFIG.get('min_full_refresh_seconds'),
            'device_detail_refresh_seconds': CONFIG.get('device_detail_refresh_seconds'),
            'device_detail_refresh_batch': CONFIG.get('device_detail_refresh_batch'),
            'device_detail_refresh_limit': CONFIG.get('device_detail_refresh_limit'),
        },
    }

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
        return local_datetime(timestamp).strftime('%d %b %Y %H:%M')
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
        'purifyer': 'purifier', 'air purify': 'air purifier', 'bath room': 'bathroom', 'bedroom too': 'bedroom 2', 'bed room too': 'bedroom 2',
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



def spoken_number_room_variants(text: str) -> str:
    t = normalise(text)
    # Common speech/typing ambiguity: "bedroom to light" should usually mean Bedroom 2 Light.
    t = re.sub(r'\bbed\s*room\s+(?:to|too|two|second|2)\b', 'bedroom 2', t)
    t = re.sub(r'\bbedroom\s+(?:to|too|two|second|2)\b', 'bedroom 2', t)
    t = re.sub(r'\bbed\s*room\s+(?:one|first|1)\b', 'bedroom 1', t)
    t = re.sub(r'\bbedroom\s+(?:one|first|1)\b', 'bedroom 1', t)
    t = re.sub(r'\bbed\s*room\s+(?:three|third|3)\b', 'bedroom 3', t)
    t = re.sub(r'\bbedroom\s+(?:three|third|3)\b', 'bedroom 3', t)
    return t


def extract_room_intent(query: str) -> str | None:
    q = spoken_number_room_variants(query)
    patterns = [
        (r'\bbedroom\s*1\b', 'Bedroom 1'),
        (r'\bbedroom\s*2\b', 'Bedroom 2'),
        (r'\bbedroom\s*3\b', 'Bedroom 3'),
        (r'\bsecond\s+bedroom\b', 'Bedroom 2'),
        (r'\bfirst\s+bedroom\b', 'Bedroom 1'),
        (r'\bthird\s+bedroom\b', 'Bedroom 3'),
        (r'\bliving\s+room\b', 'Living Room'),
        (r'\blivingroom\b', 'Living Room'),
        (r'\bkitchen\b', 'Kitchen'),
        (r'\bbathroom\b', 'Bathroom'),
        (r'\bhallway\b', 'Hallway'),
        (r'\btoilet\b', 'Toilet'),
    ]
    for pattern, room in patterns:
        if re.search(pattern, q):
            return room
    return None


def extract_category_intent(query: str, attr: str | None = None) -> str | None:
    q = spoken_number_room_variants(query)
    if re.search(r'\blights?\b|\blamps?\b|\bbulbs?\b', q):
        return 'light'
    if re.search(r'\b(?:plug|socket|switch|appliance)\b', q):
        return 'switch'
    if re.search(r'\b(?:motion|presence|occupancy)\b', q):
        return 'motion_sensor'
    if re.search(r'\b(?:door|window|contact)\b', q):
        return 'contact_sensor'
    if attr == 'switch':
        return None
    return None


def intent_devices(query: str, attr: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Resolve natural phrases like 'bedroom two light' before generic device matching.

    This resolves room first, then device type, so Bedroom 2 Light is not confused
    with Bedroom 1/2/3 lights when the user says 'bedroom two light'.
    """
    q = spoken_number_room_variants(query)
    room = extract_room_intent(q)
    category_hint = category or extract_category_intent(q, attr)
    if room:
        devices = room_devices(room, category_hint)
        if attr:
            devices = [d for d in devices if d.get(attr) is not None]
        if devices:
            # Prefer exact device type matches inside the resolved room.
            if category_hint == 'light':
                lights = [d for d in devices if d.get('category') == 'light' or 'light' in normalise(d.get('label','')) or 'lamp' in normalise(d.get('label',''))]
                if lights:
                    return lights
            return devices
    # If speech produced 'bedroom to light', try again as 'bedroom 2 light'.
    if q != normalise(query):
        matches = find_devices(q, category_hint)
        if attr:
            matches = [d for d in matches if d.get(attr) is not None]
        if matches:
            return matches
    return find_devices(query, category_hint)

def find_devices(query: str, category: str | None = None) -> list[dict[str, Any]]:
    q = normalise(query)
    if not q:
        return []
    devices = all_devices()
    if category:
        devices = [d for d in devices if d['category'] == category]
    exact = [
        d for d in devices
        if q in (
            normalise(d.get('label', '')),
            normalise(d.get('name', '')),
            command_target_text(d.get('label', '')),
            command_target_text(d.get('name', '')),
        )
    ]
    if exact:
        return exact
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
    active = [active_device_phrase(device) for device in devices]
    active = [item for item in active if item]
    if active:
        lines.append('Active now: ' + ', '.join(active[:8]) + ('' if len(active) <= 8 else f", +{len(active) - 8} more"))
    else:
        lines.append('Active now: none')
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
    intelligence = device_intelligence_profile(device)
    if 'unknown_switch_state' in intelligence.get('ignore_checks', []):
        return False
    sensor_categories = {'light_sensor', 'climate_sensor', 'motion_sensor', 'contact_sensor', 'presence_sensor', 'thermostat', 'battery_sensor'}
    sensor_words = ('sensor', 'meter', 'lux', 'camera', 'cam', 'contact', 'motion', 'temperature', 'humidity')
    # Power meters are not switches unless they expose a real switch capability/state
    # or are clearly named like a plug/socket/outlet. This prevents Octopus/energy
    # meters from appearing as broken switch devices.
    switch_capable = 'switch' in caps or category in ('light', 'switch')
    power_child_sensor = category == 'power_device' and 'power' in label and not switch_capable and device.get('switch') is None
    if power_child_sensor:
        return False
    smart_plug_word = any(word in label for word in ('plug', 'socket', 'outlet', 'switch', 'fan', 'dehumidifier', 'humidifier', 'purifier'))
    explicit_switch = switch_capable or {'on', 'off'}.issubset(commands) or (category == 'power_device' and smart_plug_word)
    if category in sensor_categories and not explicit_switch:
        return False
    if any(word in label for word in sensor_words) and not explicit_switch:
        return False
    return explicit_switch or any(word in label for word in ('light', 'dimmer', 'plug', 'socket', 'outlet', 'switch', 'fan', 'dehumidifier', 'humidifier', 'purifier'))


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
    refresh_devices_for_context('command-context')
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


def elapsed_duration_label(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = round(remainder / 60)
    if minutes == 60:
        hours += 1
        minutes = 0
    if hours == 24:
        days += 1
        hours = 0
    parts = []
    if days:
        parts.append(f"{days} day" + ('' if days == 1 else 's'))
    if hours:
        parts.append(f"{hours} hour" + ('' if hours == 1 else 's'))
    if minutes and not days:
        parts.append(f"{minutes} minute" + ('' if minutes == 1 else 's'))
    if not parts:
        return 'less than 1 minute'
    return ' '.join(parts[:2])


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
        refresh_devices_for_context('command-context')
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
    refresh_devices_for_context('command-context')
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
    refresh_devices_for_context('command-context')
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
    refresh_devices_for_context('command-context')
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
    refresh_devices_for_context('command-context')
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
                "refresh or clear the cache, list room devices, read hub logs, check stale devices, run device health, automation health, home health, energy advisor, home timeline, daily briefing, and diagnostics."
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
    if ('unknown switch' in t or 'unknown room' in t or 'what are the unknowns' in t or 'device inspector' in t or 'housekeeping' in t or 'unassigned device' in t or 'duplicate device' in t or 'device intelligence' in t or 'device classifier' in t or 'ai device classifier' in t):
        return device_inspector_answer()
    if 'performance baseline' in t or 'save baseline' in t or 'baseline cpu' in t or 'baseline load' in t:
        return performance_baseline_answer('assistant')
    if 'compare performance' in t or 'performance compare' in t or 'compare cpu' in t or 'compare load' in t:
        return performance_compare_answer()
    if 'performance' in t or 'cpu' in t or 'hub load' in t or 'maker api load' in t or 'busy time' in t:
        return performance_advisor_answer()
    if 'hub health' in t or 'hub info' in t or 'hubitat health' in t:
        return hub_health_answer()
    if 'daily briefing' in t or 'morning briefing' in t or 'home briefing' in t:
        return daily_briefing_answer()
    if 'automation health' in t or 'automation self check' in t or 'automation self-check' in t or 'which automations failed' in t or 'did the fan work' in t:
        return automation_health_answer()
    if 'timeline' in t or 'history' in t or 'what happened' in t:
        return timeline_answer()
    if 'energy advisor' in t or 'energy insight' in t or 'electricity high' in t or 'wasting electricity' in t or 'energy waste' in t:
        return energy_advisor_answer()
    if 'home health' in t or 'house health' in t or 'what needs my attention' in t or 'needs attention' in t:
        return home_health_answer()
    if (
        'stale' in t
        or 'stuck' in t
        or 'left on' in t
        or 'on too long' in t
        or 'active too long' in t
        or 'not reporting' in t
        or 'offline device' in t
    ):
        return stale_devices_answer()
    if 'device health' in t:
        return device_health_answer()
    if 'what changed' in t or 'changed today' in t or 'changed since yesterday' in t:
        return what_changed_answer()
    if 'recommend' in t or 'suggest action' in t or 'what should i do' in t:
        return recommendations_answer()
    room_intel = room_intelligence_answer(t)
    if room_intel:
        return room_intel
    room_answer = room_details_answer(t)
    if room_answer:
        return room_answer
    summary_answer = explain_summary_tile(t)
    if summary_answer:
        return summary_answer
    automation_explain = automation_explain_answer(text) if ('automation' in t or 'fan work' in t or 'which automations failed' in t or 'did the fan' in t) else None
    if automation_explain:
        return automation_explain
    light_explain = active_light_explanation_answer(text) if ('light' in t and ('why' in t or 'explain' in t)) else None
    if light_explain:
        return light_explain
    explain_answer = explain_home_question_answer(text) if 'why' in t or 'explain' in t else None
    if explain_answer:
        return explain_answer
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
            f"Stale issues: {d['stale_issues']}",
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
        count = refresh_devices_for_context('command-context')
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
    m_total_state_duration = re.search(r'^(?:total time|how much time)\s+(?:has\s+)?(?:the\s+)?(.+?)\s+(?:was|has been|been)\s+(on|off|active|inactive|open|closed|locked|unlocked)\s+(today|yesterday|last 24 hours|past 24 hours)(?:\?)?$', t)
    if not m_total_state_duration:
        m_total_state_duration = re.search(r'^how long\s+(?:was|has)\s+(?:the\s+)?(.+?)\s+(?:been\s+)?(on|off|active|inactive|open|closed|locked|unlocked)\s+(today|yesterday|last 24 hours|past 24 hours)(?:\?)?$', t)
    if m_total_state_duration:
        target = m_total_state_duration.group(1).strip()
        state = m_total_state_duration.group(2)
        period = m_total_state_duration.group(3)
        return device_total_state_duration_answer(target, state_name_to_attr(state), state, period)
    m_last_state_duration = re.search(r'^(?:how long was|how long has|when was)\s+(?:the\s+)?(.+?)\s+last\s+(on|off|active|inactive|open|closed|locked|unlocked)(?:\s+for)?(?:\s+.*)?$', t)
    if m_last_state_duration:
        target = m_last_state_duration.group(1).strip()
        state = m_last_state_duration.group(2)
        return device_last_state_duration_answer(target, state_name_to_attr(state), state)
    m_state_duration = re.search(r'^(?:how long has|how long is)\s+(?:the\s+)?(.+?)\s+(?:been\s+)?(on|off|active|inactive|open|closed|locked|unlocked)(?:\s+.*)?$', t)
    if not m_state_duration:
        m_state_duration = re.search(r'^(?:when did|from when did)\s+(?:the\s+)?(.+?)\s+(?:turn|switch|go|get|become)\s+(on|off|active|inactive|open|closed|locked|unlocked)(?:\s+.*)?$', t)
    if m_state_duration:
        target = m_state_duration.group(1).strip()
        state = m_state_duration.group(2)
        return device_state_duration_answer(target, state_name_to_attr(state), state)
    m_room_on = re.search(r"^(?:what(?:'s| is)|which|show|list)\s+(?:devices\s+)?(?:are\s+)?on\s+(?:in|inside)\s+(.+)$", t)
    if not m_room_on:
        m_room_on = re.search(r"^(?:what(?:'s| is)|which|show|list)\s+(?:is\s+)?on\s+(?:in|inside)\s+(.+)$", t)
    if m_room_on:
        return room_on_status_answer(m_room_on.group(1).strip())
    if re.search(r'\b(which|what)\s+lights?\s+(are|is)\s+on\b', t):
        sync_info = live_switch_state_sync('question-lights-on', categories={'light'}, force=False)
        lights = [d['label'] for d in all_devices() if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
        light_devices = [d for d in all_devices() if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
        return {'success': True, 'message': 'Lights on:\n' + ('\n'.join(lights) if lights else 'None'), 'speech': spoken_device_locations(light_devices)}
    if re.search(r'\b(which|what)\s+switch(es)?\s+(are|is)\s+on\b', t):
        sync_info = live_switch_state_sync('question-switches-on', categories={'switch','power_device'}, force=False)
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
        await asyncio.to_thread(refresh_devices, False, 'scheduled')
        await asyncio.to_thread(save_performance_snapshot, 'scheduled')


@app.on_event('startup')
async def startup() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    refresh_devices(True, 'startup')
    rebuild_summary_cache('startup')
    save_performance_snapshot('startup')
    restore_pending_timers()
    asyncio.create_task(refresh_loop())


@app.get('/api/version')
def api_version():
    return {'app': 'HomeBrain OS', 'version': APP_VERSION}


@app.get('/api/status')
def api_status():
    return {'success': True, 'app': 'HomeBrain OS', 'version': APP_VERSION, 'hubitat': CONFIG.get('hubitat_base_url'), 'devices': count_devices(), 'last_refresh': LAST_REFRESH, 'last_hubitat_event': LAST_HUBITAT_EVENT, 'state_event_version': STATE_EVENT_VERSION, 'summary_cache': {'version': SUMMARY_CACHE_VERSION, 'last_rebuild': SUMMARY_CACHE_LAST_REBUILD, 'available': SUMMARY_CACHE is not None, 'sse_clients': SSE_CLIENTS}, 'event_filter': {'dashboard_attrs': sorted(DASHBOARD_EVENT_ATTRS), 'ignored_ui_attrs': sorted(NOISY_EVENT_ATTRS)}, 'event_diagnostics': {'ui_stats': dict(UI_STATS), 'recent_events': list(reversed(EVENT_HISTORY[-5:]))}, 'database': str(DB_PATH), 'error': LAST_ERROR, 'detail_errors': LAST_DETAIL_ERRORS, 'auth_required': api_token_required(), 'hub_health': hub_health_summary(), 'ollama': ollama_health(), 'performance': PERF_STATS}


@app.get('/api/event-diagnostics')
def api_event_diagnostics():
    return event_diagnostics_payload()


@app.get('/api/events')
async def api_events(request: Request):
    global SSE_CLIENTS
    require_event_token(request)

    async def stream():
        global SSE_CLIENTS
        SSE_CLIENTS += 1
        last_summary_seen = SUMMARY_CACHE_VERSION
        last_state_seen = STATE_EVENT_VERSION
        last_heartbeat = time.time()
        try:
            hello_payload = {'version': APP_VERSION, 'state_event_version': last_state_seen, 'dashboard': dashboard_summary(live=False), 'summary_cache_version': last_summary_seen, 'live': True}
            UI_STATS['sse_payloads_sent'] = int(UI_STATS.get('sse_payloads_sent') or 0) + 1
            UI_STATS['last_sse_push_at'] = time.time()
            yield f"event: hello\ndata: {json.dumps(hello_payload)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                if SUMMARY_CACHE_VERSION != last_summary_seen:
                    last_summary_seen = SUMMARY_CACHE_VERSION
                    last_state_seen = STATE_EVENT_VERSION
                    payload = {
                        'state_event_version': last_state_seen,
                        'last_hubitat_event': LAST_HUBITAT_EVENT,
                        'dashboard': dashboard_summary(live=False),
                        'summary_cache_version': last_summary_seen,
                        'live': True,
                    }
                    UI_STATS['sse_payloads_sent'] = int(UI_STATS.get('sse_payloads_sent') or 0) + 1
                    UI_STATS['last_sse_push_at'] = time.time()
                    yield f"event: state\ndata: {json.dumps(payload)}\n\n"
                elif time.time() - last_heartbeat >= 25:
                    last_heartbeat = time.time()
                    payload = {'state_event_version': STATE_EVENT_VERSION, 'summary_cache_version': SUMMARY_CACHE_VERSION, 'live': True}
                    UI_STATS['sse_payloads_sent'] = int(UI_STATS.get('sse_payloads_sent') or 0) + 1
                    UI_STATS['last_sse_push_at'] = time.time()
                    yield f"event: ping\ndata: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.2)
        finally:
            SSE_CLIENTS = max(0, SSE_CLIENTS - 1)

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


@app.get('/api/performance-advisor')
def api_performance_advisor():
    return performance_advisor_answer()


@app.post('/api/performance-baseline')
def api_performance_baseline(request: Request):
    require_api_token(request)
    return performance_baseline_answer('api')


@app.get('/api/performance-compare')
def api_performance_compare():
    return performance_compare_answer()


@app.get('/api/performance-snapshots')
def api_performance_snapshots():
    return {'success': True, 'snapshots': recent_performance_snapshots(50)}



@app.get('/api/device-intelligence')
def api_device_intelligence():
    report = device_inspector_report()
    return {'success': True, 'summary': report['summary'], 'classifications': report['classifications'], 'auto_excluded_switch_false_positives': report['auto_excluded_switch_false_positives']}


@app.get('/api/device-inspector')
def api_device_inspector():
    return device_inspector_answer()

@app.get('/api/stale-devices')
def api_stale_devices():
    return {'success': True, **stale_device_report()}


@app.get('/api/home-health')
def api_home_health():
    return home_health_answer()


@app.get('/api/energy-advisor')
def api_energy_advisor():
    return energy_advisor_answer()


@app.get('/api/timeline')
def api_timeline():
    return timeline_answer()


@app.get('/api/daily-briefing')
def api_daily_briefing():
    return daily_briefing_answer()


@app.get('/api/what-changed')
def api_what_changed():
    return what_changed_answer()


@app.get('/api/recommendations')
def api_recommendations():
    return recommendations_answer()


@app.get('/api/automation-health')
def api_automation_health():
    return automation_health_answer()


@app.get('/api/automation-explain/{name}')
def api_automation_explain(name: str):
    answer = automation_explain_answer('automation ' + name)
    return answer or automation_health_answer()


@app.get('/api/room-intelligence/{room}')
def api_room_intelligence(room: str):
    return room_intelligence_answer('room summary ' + room)


@app.get('/api/ai/context')
def api_ai_context(request: Request):
    require_api_token(request)
    return {'success': True, 'context': ai_context_pack()}


@app.post('/api/refresh')
def api_refresh(request: Request):
    require_api_token(request)
    count = refresh_devices(True, 'manual')
    return {'success': LAST_ERROR is None, 'devices': count, 'error': LAST_ERROR, 'last_refresh': LAST_REFRESH}


@app.get('/api/state-sync')
def api_state_sync_get(request: Request):
    require_api_token(request)
    detail = live_switch_state_sync('manual-state-sync-get', categories={'light','switch','power_device'}, force=True)
    return {'success': True, 'switch_sync': detail}


@app.post('/api/state-sync')
def api_state_sync(request: Request):
    require_api_token(request)
    result = sync_live_states('manual-state-sync')
    detail = live_switch_state_sync('manual-state-sync', categories={'light','switch','power_device'}, force=True)
    return {'success': True, 'full_sync': result, 'switch_sync': detail}


@app.post('/api/cache/clear-refresh')
def api_cache_clear_refresh(request: Request):
    require_api_token(request)
    clear_cache()
    count = refresh_devices(True, 'clear-cache')
    return {'success': LAST_ERROR is None, 'devices': count, 'error': LAST_ERROR, 'last_refresh': LAST_REFRESH}


@app.get('/api/dashboard')
def api_dashboard():
    return {'success': True, **dashboard_summary(live=False)}


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
    # v0.9.7: serve cached/event-driven state. Manual refresh remains available via /api/state-sync.
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
    html = Path('/app/static/index.html').read_text()
    html = html.replace('data-app-version="APP_VERSION"', f'data-app-version="{APP_VERSION}"')
    return HTMLResponse(
        content=html,
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0',
        },
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8787)
