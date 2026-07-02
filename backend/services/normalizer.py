from __future__ import annotations

import re
from typing import Any

ROOM_WORDS = ['hallway','bathroom','bedroom 1','bedroom 2','bedroom 3','living room','livingroom','kitchen','toilet','entrance','ventilation','dehumidifier','energy','sockets','multimedia','office','internet','router']
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


def attributes_to_map(device: dict[str, Any]) -> dict[str, Any]:
    attrs = {}
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
    text = label.lower().replace('livingroom','living room')
    for room in ROOM_WORDS:
        if room in text:
            return 'Living Room' if room == 'livingroom' else room.title()
    m = re.search(r'(bedroom\s*[123]|hallway|bathroom|living\s*room|kitchen|toilet)', text)
    return m.group(1).replace('livingroom','living room').title() if m else 'Unknown'


def classify_device(device: dict[str, Any], attrs: dict[str, Any]) -> str:
    label = (device.get('label') or device.get('name') or '').lower()
    caps = ' '.join(list_names(device.get('capabilities'), ('name', 'capability', 'id'))).lower()
    commands = ' '.join(list_names(device.get('commands'), ('name', 'command'))).lower()
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
    if 'switch' in attrs or 'switch' in caps or ('on' in commands and 'off' in commands):
        return 'switch'
    return 'device'


def normalise_device(device: dict[str, Any]) -> dict[str, Any]:
    attrs = attributes_to_map(device)
    label = str(device.get('label') or device.get('name') or f"Device {device.get('id')}")
    capabilities = list_names(device.get('capabilities'), ('name', 'capability', 'id'))
    commands = list_names(device.get('commands'), ('name', 'command'))
    return {
        'id': str(device.get('id')),
        'name': str(device.get('name') or label),
        'label': label,
        'room': infer_room(label),
        'category': classify_device(device, attrs),
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
