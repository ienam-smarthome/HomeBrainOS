from __future__ import annotations

import asyncio
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
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

APP_VERSION = '0.6.2-alpha'
CONFIG_PATH = Path('/data/options.json')
DB_PATH = Path('/data/homebrainos.sqlite3')
ROOM_WORDS = [
    'hallway', 'bathroom', 'bedroom 1', 'bedroom 2', 'bedroom 3', 'living room', 'livingroom',
    'kitchen', 'toilet', 'entrance', 'ventilation', 'dehumidifier', 'energy', 'sockets',
    'multimedia', 'office', 'internet', 'router'
]
DEVICE_ATTRS = ['switch','level','temperature','humidity','motion','contact','presence','battery','power','energy','thermostatMode','thermostatOperatingState','heatingSetpoint','coolingSetpoint']


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {
        'hubitat_base_url': os.getenv('HUBITAT_BASE_URL', 'http://192.168.1.239'),
        'maker_api_app_id': os.getenv('MAKER_API_APP_ID', '4143'),
        'maker_api_token': os.getenv('MAKER_API_TOKEN', ''),
        'refresh_seconds': int(os.getenv('REFRESH_SECONDS', '30')),
    }


CONFIG = load_config()
LAST_ERROR: str | None = None
LAST_REFRESH: float | None = None
app = FastAPI(title='HomeBrain OS', version=APP_VERSION)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    return conn


def maker_url(path: str) -> str:
    base = str(CONFIG.get('hubitat_base_url', '')).rstrip('/')
    app_id = quote(str(CONFIG.get('maker_api_app_id', '')).strip(), safe='')
    token = quote(str(CONFIG.get('maker_api_token', '')).strip(), safe='')
    sep = '&' if '?' in path else '?'
    return f'{base}/apps/api/{app_id}/{path}{sep}access_token={token}'


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace('%',''))
    except Exception:
        return None


def caps_text(device: dict[str, Any]) -> str:
    return ' '.join(str(cap) for cap in device.get('capabilities', []) or []).lower()


def state_text(value: Any) -> str:
    return str(value or '').strip().lower()


def is_state(value: Any, *states: str) -> bool:
    return state_text(value) in {state.lower() for state in states}


def attr_map(device: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    sources = (device.get('attributes'), device.get('currentStates'), device.get('states'))
    for source in sources:
        if isinstance(source, dict):
            attrs.update(source)
            continue
        for item in source or []:
            if not isinstance(item, dict):
                continue
            name = item.get('name') or item.get('attribute')
            if name:
                attrs[str(name)] = item.get('currentValue', item.get('value'))
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
    if 'switch' in attrs or 'switch' in caps:
        return 'switch'
    return 'device'


def normalise_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = attr_map(device)
    label = str(device.get('label') or device.get('name') or f"Device {device.get('id')}")
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': label,
        'room': infer_room(label),
        'category': classify(device, attrs),
        'attributes': attrs,
        'switch': attrs.get('switch'),
        'level': attrs.get('level'),
        'temperature': safe_float(attrs.get('temperature')),
        'humidity': safe_float(attrs.get('humidity')),
        'power': safe_float(attrs.get('power')),
        'energy': safe_float(attrs.get('energy')),
        'battery': safe_float(attrs.get('battery')),
        'motion': attrs.get('motion'),
        'contact': attrs.get('contact'),
        'presence': attrs.get('presence'),
        'thermostatMode': attrs.get('thermostatMode'),
        'heatingSetpoint': attrs.get('heatingSetpoint'),
    }


def upsert_devices(devices: list[dict[str, Any]]) -> None:
    now = int(time.time())
    conn = db()
    try:
        for d in devices:
            old = conn.execute('SELECT json FROM devices WHERE id=?', (d['id'],)).fetchone()
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


def refresh_devices() -> int:
    global LAST_ERROR, LAST_REFRESH
    try:
        response = requests.get(maker_url('devices'), timeout=20)
        response.raise_for_status()
        raw = response.json()
        devices = [normalise_device(d) for d in raw]
        upsert_devices(devices)
        LAST_REFRESH = time.time()
        LAST_ERROR = None
        return len(devices)
    except Exception as exc:
        LAST_ERROR = str(exc)
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


def dashboard_summary() -> dict[str, Any]:
    devices = all_devices()
    lights_on = [d for d in devices if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
    switches_on = [d for d in devices if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on')]
    temps = [d['temperature'] for d in devices if isinstance(d.get('temperature'), (int, float))]
    hums = [d['humidity'] for d in devices if isinstance(d.get('humidity'), (int, float))]
    powers = [d['power'] for d in devices if isinstance(d.get('power'), (int, float))]
    low_batt = [d for d in devices if isinstance(d.get('battery'), (int, float)) and d['battery'] <= 20]
    motion_active = [d for d in devices if is_state(d.get('motion'), 'active')]
    people_home = [d for d in devices if is_state(d.get('presence'), 'present')]
    return {
        'devices': len(devices),
        'lights_on': len(lights_on),
        'switches_on': len(switches_on),
        'avg_temperature': round(sum(temps) / len(temps), 1) if temps else None,
        'avg_humidity': round(sum(hums) / len(hums), 1) if hums else None,
        'power_total': round(sum(powers), 1) if powers else 0,
        'low_batteries': len(low_batt),
        'motion_active': len(motion_active),
        'people_home': len(people_home),
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


def switchable_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in devices if d.get('switch') is not None or d['category'] in ('light', 'switch', 'power_device')]


def command_devices(devices: list[dict[str, Any]], command: str) -> dict[str, Any]:
    candidates = switchable_devices(devices)[:10]
    if not candidates:
        labels = [d['label'] for d in devices[:5]]
        suffix = '\nMatched: ' + '\n'.join(labels) if labels else ''
        return {'success': False, 'message': 'No switchable devices found.' + suffix, 'matched': labels}
    changed = []
    errors = []
    for d in candidates:
        try:
            maker_command(d['id'], command)
            changed.append(d['label'])
        except Exception as exc:
            errors.append(f"{d['label']}: {exc}")
    refresh_devices()
    if changed:
        updated = update_cached_switch([d['id'] for d in candidates if d['label'] in changed], command)
        message = f"Turned {command}:\n" + '\n'.join(changed)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
        return {'success': True, 'message': message, 'changed': changed, 'errors': errors, 'devices': updated}
    return {'success': False, 'message': 'Hubitat command failed:\n' + '\n'.join(errors), 'errors': errors}


def answer_attribute(target: str, attr: str) -> dict[str, Any]:
    candidates = room_devices(target) or find_devices(target)
    candidates = [d for d in candidates if d.get(attr) is not None]
    if not candidates:
        return {'success': False, 'message': f'I could not find {attr} for {target}.'}
    d = candidates[0]
    unit = {'temperature': '°C', 'humidity': '%', 'power': 'W', 'battery': '%', 'energy': 'kWh'}.get(attr, '')
    return {'success': True, 'message': f"{d['label']} {attr} is {d[attr]}{unit}", 'device': d, 'attribute': attr, 'value': d[attr]}


def run_command(text: str) -> dict[str, Any]:
    t = normalise(text)
    if t in ('refresh', 'refresh cache', 'reload cache', 'update cache'):
        count = refresh_devices()
        if LAST_ERROR:
            return {'success': False, 'message': f'Refresh failed: {LAST_ERROR}', 'devices': count, 'error': LAST_ERROR}
        return {'success': True, 'message': f'Cache refreshed: {count} devices', 'devices': count, 'last_refresh': LAST_REFRESH}
    if t in ('summary', 'status', 'home summary'):
        s = dashboard_summary()
        return {'success': True, 'message': f"🏠 Home Summary\nDevices: {s['devices']}\nLights on: {s['lights_on']}\nSwitches on: {s['switches_on']}\nAverage temperature: {s['avg_temperature']}°C\nAverage humidity: {s['avg_humidity']}%\nPower total: {s['power_total']} W\nPeople home: {s['people_home']}\nLow batteries: {s['low_batteries']}"}
    if 'which lights are on' in t or 'what lights are on' in t:
        lights = [d['label'] for d in all_devices() if d['category'] == 'light' and is_state(d.get('switch'), 'on')]
        return {'success': True, 'message': 'Lights on:\n' + ('\n'.join(lights) if lights else 'None')}
    if 'which switches are on' in t or 'what switches are on' in t:
        switches = [d['label'] for d in all_devices() if d['category'] != 'light' and d.get('switch') is not None and is_state(d.get('switch'), 'on')]
        return {'success': True, 'message': 'Switches on:\n' + ('\n'.join(switches) if switches else 'None')}
    for attr in ('humidity', 'temperature', 'power', 'battery', 'energy'):
        if attr in t or (attr == 'temperature' and 'temp' in t):
            target = t.replace('what is','').replace("what's",'').replace('level','').replace('the','').replace(attr,'').replace('temp','').strip()
            if not target:
                target = 'home'
            return answer_attribute(target, attr)
    m = re.search(r'(turn on|switch on|turn off|switch off) (.+)', t)
    if m:
        action, target = m.group(1), m.group(2).strip()
        command = 'on' if 'on' in action else 'off'
        if target.endswith('lights') or target.endswith('light'):
            room = target.replace('lights','').replace('light','').strip()
            devices = room_devices(room, 'light')
        else:
            devices = find_devices(target) or room_devices(re.sub(r'\s+\d+$', '', target).strip())
        if not devices:
            return {'success': False, 'message': f'Device not found: {target}'}
        return command_devices(devices, command)
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
    return {'success': True, 'app': 'HomeBrain OS', 'version': APP_VERSION, 'hubitat': CONFIG.get('hubitat_base_url'), 'devices': count_devices(), 'last_refresh': LAST_REFRESH, 'database': str(DB_PATH), 'error': LAST_ERROR}


@app.get('/api/refresh')
def api_refresh():
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
    devices = switchable_devices(devices)
    return {'success': True, 'count': len(devices), 'devices': devices}


@app.get('/api/rooms')
def api_rooms():
    devices = all_devices()
    rooms: dict[str, dict[str, Any]] = {}
    for d in devices:
        room = d.get('room') or 'Unknown'
        rooms.setdefault(room, {'room': room, 'devices': 0, 'lights_on': 0, 'avg_temperature': None, 'avg_humidity': None})
        rooms[room]['devices'] += 1
        if d['category'] == 'light' and is_state(d.get('switch'), 'on'):
            rooms[room]['lights_on'] += 1
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


@app.get('/api/device/{device_id}/command/{command}')
def api_device_command(device_id: str, command: str):
    if command not in ('on', 'off'):
        raise HTTPException(status_code=400, detail='Only on/off commands are supported.')
    matches = [d for d in all_devices() if d['id'] == device_id]
    if not matches:
        raise HTTPException(status_code=404, detail='Device not found.')
    return command_devices(matches, command)


@app.get('/api/ask')
def api_ask(q: str = Query(...)):
    return run_command(q)


@app.get('/', response_class=HTMLResponse)
def index():
    return Path('/app/static/index.html').read_text()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8787)
