from __future__ import annotations

import re
from typing import Any

ROOM_WORDS = ['hallway','bathroom','bedroom 1','bedroom 2','bedroom 3','living room','livingroom','kitchen','toilet','entrance','ventilation']


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace('%',''))
    except Exception:
        return None


def attributes_to_map(device: dict[str, Any]) -> dict[str, Any]:
    attrs = {}
    for item in device.get('attributes', []) or []:
        name = item.get('name')
        if name:
            attrs[name] = item.get('currentValue')
    return attrs


def infer_room(label: str) -> str:
    text = label.lower().replace('livingroom','living room')
    for room in ROOM_WORDS:
        if room in text:
            return 'Living Room' if room == 'livingroom' else room.title()
    m = re.search(r'(bedroom\s*[123]|hallway|bathroom|living\s*room|kitchen|toilet)', text)
    return m.group(1).replace('livingroom','living room').title() if m else 'Unknown'


def classify_device(device: dict[str, Any], attrs: dict[str, Any]) -> str:
    label = (device.get('label') or device.get('name') or '').lower()
    caps = ' '.join(device.get('capabilities', []) or []).lower()
    if 'light' in label or 'dimmer' in label or 'switchlevel' in caps:
        return 'light'
    if 'thermostat' in caps or 'trv' in label or 'heatingsetpoint' in attrs:
        return 'thermostat'
    if 'presence' in attrs:
        return 'presence_sensor'
    if 'motion' in attrs:
        return 'motion_sensor'
    if 'contact' in attrs:
        return 'contact_sensor'
    if 'temperature' in attrs or 'humidity' in attrs:
        return 'climate_sensor'
    if 'power' in attrs or 'energy' in attrs:
        return 'power_device'
    if 'switch' in attrs:
        return 'switch'
    return 'device'


def normalise_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = attributes_to_map(device)
    label = str(device.get('label') or device.get('name') or f"Device {device.get('id')}")
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': label,
        'room': infer_room(label),
        'category': classify_device(device, attrs),
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
