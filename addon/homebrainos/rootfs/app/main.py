import json
import os
from pathlib import Path
from typing import Any

import requests
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

CONFIG_PATH = Path('/data/options.json')


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
DEVICES: list[dict[str, Any]] = []
LAST_ERROR: str | None = None

app = FastAPI(title='HomeBrain OS', version='0.4.0-alpha')


def maker_url(path: str) -> str:
    base = str(CONFIG.get('hubitat_base_url', '')).rstrip('/')
    app_id = str(CONFIG.get('maker_api_app_id', '')).strip()
    token = str(CONFIG.get('maker_api_token', '')).strip()
    sep = '&' if '?' in path else '?'
    return f'{base}/apps/api/{app_id}/{path}{sep}access_token={token}'


def attr_map(device: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for item in device.get('attributes', []) or []:
        name = item.get('name')
        if not name:
            continue
        attrs[name] = item.get('currentValue')
    return attrs


def classify(device: dict[str, Any], attrs: dict[str, Any]) -> str:
    name = (device.get('label') or device.get('name') or '').lower()
    caps = ' '.join(device.get('capabilities', []) or []).lower()
    if 'light' in name or 'dimmer' in name or 'switchlevel' in caps:
        return 'light'
    if 'thermostat' in caps or 'trv' in name:
        return 'thermostat'
    if 'temperature' in attrs or 'humidity' in attrs:
        return 'climate_sensor'
    if 'motion' in attrs:
        return 'motion_sensor'
    if 'presence' in attrs:
        return 'presence_sensor'
    if 'power' in attrs or 'energy' in attrs:
        return 'power_device'
    if 'switch' in attrs:
        return 'switch'
    return 'device'


def normalise_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = attr_map(device)
    label = device.get('label') or device.get('name') or f"Device {device.get('id')}"
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': str(label),
        'category': classify(device, attrs),
        'attributes': attrs,
        'switch': attrs.get('switch'),
        'temperature': attrs.get('temperature'),
        'humidity': attrs.get('humidity'),
        'power': attrs.get('power'),
        'energy': attrs.get('energy'),
        'battery': attrs.get('battery'),
    }


def refresh_devices() -> None:
    global DEVICES, LAST_ERROR
    try:
        response = requests.get(maker_url('devices'), timeout=15)
        response.raise_for_status()
        raw = response.json()
        DEVICES = [normalise_device(d) for d in raw]
        LAST_ERROR = None
    except Exception as exc:
        LAST_ERROR = str(exc)


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(value)
    except Exception:
        return None


def dashboard_summary() -> dict[str, Any]:
    lights_on = [d for d in DEVICES if d['category'] == 'light' and d.get('switch') == 'on']
    switches_on = [d for d in DEVICES if d['category'] in ('switch', 'power_device') and d.get('switch') == 'on']
    temps = [v for d in DEVICES if (v := safe_float(d.get('temperature'))) is not None]
    hums = [v for d in DEVICES if (v := safe_float(d.get('humidity'))) is not None]
    powers = [v for d in DEVICES if (v := safe_float(d.get('power'))) is not None]
    low_batt = [d for d in DEVICES if (v := safe_float(d.get('battery'))) is not None and v <= 20]
    return {
        'devices': len(DEVICES),
        'lights_on': len(lights_on),
        'switches_on': len(switches_on),
        'avg_temperature': round(sum(temps) / len(temps), 1) if temps else None,
        'avg_humidity': round(sum(hums) / len(hums), 1) if hums else None,
        'power_total': round(sum(powers), 1) if powers else 0,
        'low_batteries': len(low_batt),
    }


def find_devices(query: str) -> list[dict[str, Any]]:
    q = query.lower().strip()
    return [d for d in DEVICES if q in d['label'].lower() or q in d['name'].lower()]


@app.on_event('startup')
def startup() -> None:
    refresh_devices()


@app.get('/api/status')
def api_status():
    return {
        'success': True,
        'app': 'HomeBrain OS',
        'version': '0.4.0-alpha',
        'hubitat': CONFIG.get('hubitat_base_url'),
        'devices': len(DEVICES),
        'error': LAST_ERROR,
    }


@app.get('/api/refresh')
def api_refresh():
    refresh_devices()
    return api_status()


@app.get('/api/dashboard')
def api_dashboard():
    return {'success': True, **dashboard_summary()}


@app.get('/api/devices')
def api_devices():
    return {'success': True, 'count': len(DEVICES), 'devices': DEVICES}


@app.get('/api/device/{device_id}')
def api_device(device_id: str):
    for d in DEVICES:
        if d['id'] == device_id:
            return {'success': True, 'device': d}
    return {'success': False, 'message': 'Device not found'}


@app.get('/api/ask')
def api_ask(q: str = Query(...)):
    text = q.lower().strip().replace('the humidifier', 'dehumidifier').replace('humidifier', 'dehumidifier')
    if text in ('summary', 'status'):
        s = dashboard_summary()
        return {'success': True, 'message': f"Devices: {s['devices']}\nLights on: {s['lights_on']}\nSwitches on: {s['switches_on']}\nAverage temperature: {s['avg_temperature']}°C\nAverage humidity: {s['avg_humidity']}%\nPower total: {s['power_total']} W\nLow batteries: {s['low_batteries']}"}
    if 'which lights are on' in text:
        lights = [d['label'] for d in DEVICES if d['category'] == 'light' and d.get('switch') == 'on']
        return {'success': True, 'message': 'Lights on:\n' + ('\n'.join(lights) if lights else 'None')}
    if 'hallway humidity' in text:
        matches = [d for d in find_devices('hallway') if d.get('humidity') is not None]
        if matches:
            return {'success': True, 'message': f"{matches[0]['label']} humidity is {matches[0]['humidity']}%"}
    if 'hallway temperature' in text:
        matches = [d for d in find_devices('hallway') if d.get('temperature') is not None]
        if matches:
            return {'success': True, 'message': f"{matches[0]['label']} temperature is {matches[0]['temperature']}°C"}
    return {'success': False, 'message': f'I did not understand yet: {q}'}


@app.get('/', response_class=HTMLResponse)
def index():
    return Path('/app/static/index.html').read_text()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8787)
