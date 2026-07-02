from __future__ import annotations

from typing import Any


def attributes_to_map(device: dict[str, Any]) -> dict[str, Any]:
    attrs = {}
    for item in device.get('attributes', []) or []:
        name = item.get('name')
        if name:
            attrs[name] = item.get('currentValue')
    return attrs


def classify_device(device: dict[str, Any], attrs: dict[str, Any]) -> str:
    label = (device.get('label') or device.get('name') or '').lower()
    caps = ' '.join(device.get('capabilities', []) or []).lower()
    if 'light' in label or 'dimmer' in label or 'switchlevel' in caps:
        return 'light'
    if 'thermostat' in caps or 'trv' in label:
        return 'thermostat'
    if 'temperature' in attrs or 'humidity' in attrs:
        return 'climate_sensor'
    if 'presence' in attrs:
        return 'presence_sensor'
    if 'motion' in attrs:
        return 'motion_sensor'
    if 'power' in attrs or 'energy' in attrs:
        return 'power_device'
    if 'switch' in attrs:
        return 'switch'
    return 'device'


def normalise_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = attributes_to_map(device)
    label = device.get('label') or device.get('name') or f"Device {device.get('id')}"
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': str(label),
        'category': classify_device(device, attrs),
        'attributes': attrs,
        'switch': attrs.get('switch'),
        'temperature': attrs.get('temperature'),
        'humidity': attrs.get('humidity'),
        'power': attrs.get('power'),
        'energy': attrs.get('energy'),
        'battery': attrs.get('battery'),
    }
