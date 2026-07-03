from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import sqlite3
import time
from difflib import get_close_matches
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

APP_VERSION = '0.7.12-alpha'
CONFIG_PATH = Path('/data/options.json')
DB_PATH = Path('/data/homebrainos.sqlite3')
HOUSEHOLD_PEOPLE = ['Enamul', 'Samah', 'Tahmid', 'Muhsena']
POWER_SOURCE_TERMS = ('octopus', 'whole house', 'house power', 'smart meter', 'electricity meter')
ROOM_WORDS = [
    'hallway', 'bathroom', 'bedroom 1', 'bedroom 2', 'bedroom 3', 'living room', 'livingroom',
    'kitchen', 'toilet', 'entrance', 'ventilation', 'dehumidifier', 'energy', 'sockets',
    'multimedia', 'office', 'internet', 'router'
]
DEVICE_ATTRS = ['switch','level','temperature','humidity','illuminance','motion','contact','presence','battery','power','energy','thermostatMode','thermostatOperatingState','heatingSetpoint','coolingSetpoint','lock','water','smoke','carbonMonoxide','tamper','acceleration','valve','windowShade']
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
        'ollama_model': os.getenv('OLLAMA_MODEL', 'llama3.2'),
        'device_detail_refresh_limit': int(os.getenv('DEVICE_DETAIL_REFRESH_LIMIT', '150')),
        'heating_on_delta': float(os.getenv('HEATING_ON_DELTA', '1')),
        'heating_off_setpoint': float(os.getenv('HEATING_OFF_SETPOINT', '12')),
    }


CONFIG = load_config()
LAST_ERROR: str | None = None
LAST_REFRESH: float | None = None
LAST_DETAIL_ERRORS: list[str] = []
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


def api_token_required() -> bool:
    return bool(str(CONFIG.get('api_token', '') or '').strip())


def require_api_token(request: Request) -> None:
    expected = str(CONFIG.get('api_token', '') or '').strip()
    if not expected:
        return
    supplied = request.headers.get('x-homebrain-token', '')
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail='Missing or invalid HomeBrain API token.')


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


def infer_room(label: str) -> str:
    text = normalise(label)
    for room in ROOM_WORDS:
        if room in text:
            return 'Living Room' if room == 'livingroom' else room.title()
    # Common Hubitat labels like "01 Livingroom TRV" or "Bedroom 1 Meter"
    m = re.search(r'(bedroom\s*[123]|hallway|bathroom|living\s*room|livingroom|kitchen|toilet)', text)
    if m:
        return m.group(1).replace('livingroom', 'living room').title()
    return 'Unknown'


def classify(device: dict[str, Any], attrs: dict[str, Any]) -> str:
    label = (device.get('label') or device.get('name') or '').lower()
    caps = caps_text(device)
    commands = commands_text(device)
    climate_attrs = ('thermostatMode', 'thermostatOperatingState', 'heatingSetpoint', 'coolingSetpoint')
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
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': label,
        'room': infer_room(label),
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


def enrich_raw_devices(raw_devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    global LAST_DETAIL_ERRORS
    limit = max(0, int(CONFIG.get('device_detail_refresh_limit', 150)))
    enriched: list[dict[str, Any]] = []
    detail_errors: list[str] = []
    detail_count = 0
    for raw_device in raw_devices:
        device = normalise_device(raw_device)
        should_fetch = detail_count < limit and needs_device_detail(raw_device, device)
        if should_fetch:
            try:
                detail = maker_get(f"devices/{quote(str(device['id']), safe='')}", timeout=8)
                raw_device = merge_raw_device(raw_device, detail)
                detail_count += 1
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
            old = conn.execute('SELECT json FROM devices WHERE id=?', (d['id'],)).fetchone()
            if old and d.get('switch') is None:
                old_d = json.loads(old['json'])
                if old_d.get('switch') is not None:
                    d['switch'] = old_d.get('switch')
                    d.setdefault('attributes', {})['switch'] = old_d.get('switch')
            conn.execute('''
                INSERT INTO devices(id,name,label,room,category,json,switch,temperature,humidity,power,energy,battery,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, label=excluded.label, room=excluded.room, category=excluded.category,
                    json=excluded.json, switch=excluded.switch, temperature=excluded.temperature,
                    humidity=excluded.humidity, power=excluded.power, energy=excluded.energy,
                    battery=excluded.battery, updated_at=excluded.updated_at
            ''', (
                d['id'], d['name'], d['label'], d['room'], d['category'], json.dumps(d),
                d.get('switch'), d.get('temperature'), d.get('humidity'), d.get('power'), d.get('energy'), d.get('battery'), now
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
    lights_on = [d for d in devices if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
    switches_on = [d for d in devices if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on')]
    temps = [d['temperature'] for d in devices if isinstance(d.get('temperature'), (int, float))]
    hums = [d['humidity'] for d in devices if isinstance(d.get('humidity'), (int, float))]
    power_devices = [d for d in devices if isinstance(d.get('power'), (int, float))]
    powers = [d['power'] for d in power_devices]
    power_source = select_power_source(power_devices)
    people = household_people(devices)
    low_batt = [d for d in devices if isinstance(d.get('battery'), (int, float)) and d['battery'] <= 20]
    motion_active = [d for d in devices if is_state(d.get('motion'), 'active')]
    return {
        'devices': len(devices),
        'lights_on': len(lights_on),
        'switches_on': len(switches_on),
        'avg_temperature': round(sum(temps) / len(temps), 1) if temps else None,
        'avg_humidity': round(sum(hums) / len(hums), 1) if hums else None,
        'power_total': round(power_source['power'], 1) if power_source else round(sum(powers), 1) if powers else 0,
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


def format_summary_device(item: dict[str, Any], attr: str | None = None, unit: str = '') -> str:
    detail = ''
    if attr and item.get(attr) is not None:
        detail = f" - {item[attr]}{unit}"
    return f"{item['label']} ({item.get('room') or 'Unknown'}){detail}"


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
        lines = [f"{p['name']}: {p['status']}" for p in summary['people']]
        return {'success': True, 'intent': 'summary_people', 'message': 'People:\n' + '\n'.join(lines), 'people': summary['people']}

    if wants_power:
        source = summary.get('power_source')
        if source:
            message = f"Power is whole-house live power from {source['label']}: {summary['power_total']} W."
        else:
            message = f"Power is shown as whole-house power, but no Octopus meter device was found. Current value: {summary['power_total']} W."
        return {'success': True, 'intent': 'summary_power', 'message': message, 'power_source': source}

    if wants_tiles:
        message = (
            f"Summary tiles: {summary['lights_on']} lights on, {summary['switches_on']} switches on, "
            f"{summary['power_total']} W whole-house power from {summary['power_source_label']}, "
            f"{summary['people_home']} of {summary['people_tracked']} people home, "
            f"{summary['low_batteries']} low batteries, and {summary['motion_active']} active motion sensors."
        )
        return {'success': True, 'intent': 'summary_tiles', 'message': message, 'summary': summary}

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


def normalise(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        'turn of': 'turn off', 'switch of': 'switch off', 'the humidifier': 'dehumidifier',
        'de humidifier': 'dehumidifier', 'humidifier': 'dehumidifier', 'ligth': 'light',
        'lite': 'light', 'livingroom': 'living room', 'one': '1', 'two': '2', 'three': '3'
    }
    for a, b in replacements.items():
        text = re.sub(rf'\b{re.escape(a)}\b', b, text)
    return re.sub(r'\s+', ' ', text).strip()


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
    without_number = re.sub(r'\s+\d+$', '', q).strip()
    if without_number and without_number != q:
        direct = [
            d for d in devices
            if without_number in normalise(d['label'])
            or without_number in normalise(d['name'])
            or without_number == normalise(d.get('room',''))
        ]
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


def switchable_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in devices if is_switchable_device(d)]


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


def controllable_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    for device in switchable_devices(devices) + climate_control_devices(devices):
        controls[device['id']] = device
    return sorted(controls.values(), key=lambda d: d.get('label', ''))


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
        return {'success': True, 'message': message, 'changed': changed, 'errors': errors, 'devices': updated}
    return {'success': False, 'message': 'Hubitat command failed:\n' + '\n'.join(errors), 'errors': errors}


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


def set_heating_mode(mode: str, target: str = 'home') -> dict[str, Any]:
    devices = climate_control_devices(all_devices())
    if target not in ('home', 'house', 'heating', 'heat'):
        matched_ids = {d['id'] for d in room_devices(target)}
        devices = [d for d in devices if d['id'] in matched_ids]
    if not devices:
        return {'success': False, 'message': f'No heating devices found for {target}.'}
    command = 'heat' if mode == 'heat' else 'off'
    on_delta = safe_float(CONFIG.get('heating_on_delta')) or 1
    off_setpoint = safe_float(CONFIG.get('heating_off_setpoint')) or 12
    changed = []
    errors = []
    setpoints: list[str] = []
    for device in devices[:20]:
        try:
            maker_command_value(device['id'], 'setThermostatMode', command)
            temperature = safe_float(device.get('temperature') or device.get('attributes', {}).get('temperature'))
            current_setpoint = safe_float(device.get('heatingSetpoint') or device.get('attributes', {}).get('heatingSetpoint'))
            if command == 'heat':
                if temperature is not None and (current_setpoint is None or current_setpoint <= temperature):
                    new_setpoint = round(temperature + on_delta, 1)
                    maker_command_value(device['id'], 'setHeatingSetpoint', new_setpoint)
                    update_cached_setpoint(device['id'], new_setpoint)
                    setpoints.append(f"{device['label']}: {new_setpoint}°")
            elif current_setpoint is None or current_setpoint > off_setpoint:
                maker_command_value(device['id'], 'setHeatingSetpoint', off_setpoint)
                update_cached_setpoint(device['id'], off_setpoint)
                setpoints.append(f"{device['label']}: {off_setpoint:g}°")
            changed.append(device['label'])
        except Exception as exc:
            errors.append(f"{device['label']}: {public_error(exc)}")
    refresh_devices()
    updated = update_cached_thermostat_mode([d['id'] for d in devices if d['label'] in changed], command)
    if changed:
        message = f"Heating turned {command} for:\n" + '\n'.join(changed)
        if setpoints:
            heading = 'Raised setpoints above room temp:' if command == 'heat' else 'Lowered setpoints for heating off:'
            message += f'\n\n{heading}\n' + '\n'.join(setpoints)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
        return {'success': True, 'message': message, 'changed': changed, 'errors': errors, 'devices': updated}
    return {'success': False, 'message': 'Heating command failed:\n' + '\n'.join(errors), 'errors': errors}


def answer_attribute(target: str, attr: str) -> dict[str, Any]:
    if target in ('home', 'house'):
        summary = dashboard_summary()
        key = {'temperature': 'avg_temperature', 'humidity': 'avg_humidity', 'power': 'power_total'}.get(attr)
        if key and summary.get(key) is not None:
            unit = {'temperature': 'C', 'humidity': '%', 'power': 'W'}.get(attr, '')
            return {'success': True, 'message': f"Home {attr} is {summary[key]}{unit}", 'attribute': attr, 'value': summary[key]}
    candidates = room_devices(target) or find_devices(target)
    candidates = [d for d in candidates if d.get(attr) is not None]
    if not candidates:
        return {'success': False, 'message': f'I could not find {attr} for {target}.'}
    d = candidates[0]
    unit = {'temperature': '°C', 'humidity': '%', 'power': 'W', 'battery': '%', 'energy': 'kWh', 'level': '%', 'illuminance': ' lux'}.get(attr, '')
    return {'success': True, 'message': f"{d['label']} {attr} is {d[attr]}{unit}", 'device': d, 'attribute': attr, 'value': d[attr]}


def ollama_answer(text: str) -> dict[str, Any] | None:
    if not CONFIG.get('ollama_enabled'):
        return None
    devices = all_devices()[:80]
    context = '\n'.join(device_line(d) for d in devices)
    prompt = (
        'You are HomeBrain OS, a concise smart home assistant. '
        'Answer using only the device facts below. Do not invent device states. '
        'If asked to control devices, explain that control is handled by HomeBrain deterministic commands.\n\n'
        f'Device facts:\n{context}\n\nUser: {text}\nAssistant:'
    )
    try:
        response = requests.post(
            str(CONFIG.get('ollama_base_url', '')).rstrip('/') + '/api/generate',
            json={'model': CONFIG.get('ollama_model', 'llama3.2'), 'prompt': prompt, 'stream': False},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        message = str(data.get('response') or '').strip()
        if message:
            return {'success': True, 'message': message, 'intent': 'ollama_answer', 'source': 'ollama'}
    except Exception as exc:
        return {'success': False, 'message': f'Ollama is enabled but did not answer: {exc}', 'intent': 'ollama_error'}
    return None


def assistant(text: str) -> dict[str, Any]:
    t = normalise(text)
    if t in ('help', 'what can you do', 'commands'):
        return {
            'success': True,
            'intent': 'help',
            'message': (
                "I can summarize the home, list lights or switches that are on, answer temperature/humidity/power/battery questions, "
                "control switchable devices, refresh or clear the cache, list room devices, and run diagnostics."
            ),
        }
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
        return {'success': True, 'message': f"Home Summary\nDevices: {s['devices']}\nLights on: {s['lights_on']}\nSwitches on: {s['switches_on']}\nAverage temperature: {s['avg_temperature']}C\nAverage humidity: {s['avg_humidity']}%\nWhole-house power: {s['power_total']} W from {s['power_source_label']}\nPeople home: {s['people_home']}/{s['people_tracked']} ({people})\nLow batteries: {s['low_batteries']}\nMotion active: {s['motion_active']}"}
    if 'which lights are on' in t or 'what lights are on' in t:
        lights = [d['label'] for d in all_devices() if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
        return {'success': True, 'message': 'Lights on:\n' + ('\n'.join(lights) if lights else 'None')}
    if 'which switches are on' in t or 'what switches are on' in t:
        switches = [d['label'] for d in all_devices() if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on')]
        return {'success': True, 'message': 'Switches on:\n' + ('\n'.join(switches) if switches else 'None')}
    m_heat = re.search(r'^(turn on|switch on|enable|start|turn off|switch off|disable|stop)\s+(?:(.+?)\s+)?heating(?:\s+(?:in|for)\s+(.+))?$', t)
    if m_heat:
        action = m_heat.group(1)
        target = (m_heat.group(3) or m_heat.group(2) or 'home').replace('the ', '').replace('all ', '').strip() or 'home'
        mode = 'off' if any(word in action for word in ('off', 'disable', 'stop')) else 'heat'
        return set_heating_mode(mode, target)
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
        explicit_bulk = target in ('all lights', 'all light', 'all switches', 'all switch', 'all devices')
        if target in ('lights', 'light', 'switches', 'switch', 'devices', 'device'):
            return {
                'success': False,
                'message': f"Please specify a room/device, or say 'all {target}' if you mean the whole home.",
            }
        if target in ('all lights', 'all light'):
            devices = [d for d in all_devices() if d.get('category') == 'light']
        elif target in ('all switches', 'all switch'):
            devices = [d for d in all_devices() if d.get('category') != 'light' and d.get('switch') is not None]
        elif target == 'all devices':
            devices = switchable_devices(all_devices())
        elif target.endswith('lights') or target.endswith('light'):
            room = target.replace('lights','').replace('light','').strip()
            devices = room_devices(room, 'light')
        else:
            devices = find_devices(target) or room_devices(re.sub(r'\s+\d+$', '', target).strip())
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
    asyncio.create_task(refresh_loop())


@app.get('/api/status')
def api_status():
    return {'success': True, 'app': 'HomeBrain OS', 'version': APP_VERSION, 'hubitat': CONFIG.get('hubitat_base_url'), 'devices': count_devices(), 'last_refresh': LAST_REFRESH, 'database': str(DB_PATH), 'error': LAST_ERROR, 'detail_errors': LAST_DETAIL_ERRORS, 'auth_required': api_token_required()}


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
        room = d.get('room') or 'Unknown'
        rooms.setdefault(room, {
            'room': room,
            'devices': 0,
            'lights_on': 0,
            'switches_on': 0,
            'motion_active': 0,
            'low_batteries': 0,
            'power_total': 0,
            'avg_temperature': None,
            'avg_humidity': None,
        })
        rooms[room]['devices'] += 1
        if d['category'] == 'light' and is_state(d.get('switch'), 'on'):
            rooms[room]['lights_on'] += 1
        if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on'):
            rooms[room]['switches_on'] += 1
        if is_state(d.get('motion'), 'active'):
            rooms[room]['motion_active'] += 1
        if isinstance(d.get('battery'), (int, float)) and d['battery'] <= 20:
            rooms[room]['low_batteries'] += 1
        if isinstance(d.get('power'), (int, float)):
            rooms[room]['power_total'] = round(rooms[room]['power_total'] + d['power'], 1)
    for room in rooms.values():
        ds = [d for d in devices if (d.get('room') or 'Unknown') == room['room']]
        temps = [d['temperature'] for d in ds if isinstance(d.get('temperature'), (int,float))]
        hums = [d['humidity'] for d in ds if isinstance(d.get('humidity'), (int,float))]
        room['avg_temperature'] = round(sum(temps)/len(temps),1) if temps else None
        room['avg_humidity'] = round(sum(hums)/len(hums),1) if hums else None
    return {'success': True, 'rooms': sorted(rooms.values(), key=lambda x: x['room'])}


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
