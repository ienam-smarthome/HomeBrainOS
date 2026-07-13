from __future__ import annotations

import html as html_lib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

LOCAL_FIRST_INTENTS = {'energy', 'why_lights', 'light_hours', 'attention', 'health', 'briefing'}
COMMAND_PREFIXES = ('turn on', 'turn off', 'switch on', 'switch off', 'set ', 'change ', 'adjust ', 'dim ', 'brighten ', 'increase ', 'decrease ', 'raise ', 'lower ', 'keep ', 'leave ', 'refresh', 'reload', 'clear cache', 'cancel timer', 'schedule ')
NUMBER_WORDS = {'one': '1', 'two': '2', 'too': '2', 'to': '2', 'three': '3', 'four': '4'}


def app_version(app_module: Any) -> str:
    """Return the host application's authoritative version."""
    return str(getattr(app_module, 'APP_VERSION', 'unknown'))



ROOM_ALIASES = {
    'livingroom': 'Living Room',
    'living room': 'Living Room',
    'hall': 'Hallway',
    'hallway': 'Hallway',
    'bathroom': 'Bathroom',
    'toilet': 'Toilet',
    'kitchen': 'Kitchen',
    'entrance': 'Entrance',
    'office': 'Office',
    'bedroom 1': 'Bedroom 1',
    'bedroom1': 'Bedroom 1',
    'bedroom 2': 'Bedroom 2',
    'bedroom2': 'Bedroom 2',
    'bedroom 3': 'Bedroom 3',
    'bedroom3': 'Bedroom 3',
}

DETAIL_TERMS = ('detailed', 'detail', 'full status', 'all devices', 'everything')
DIAGNOSTIC_TERMS = ('diagnose', 'diagnostic', 'raw status', 'raw attributes', 'debug')


@dataclass(frozen=True)
class IntentResult:
    intent: str
    action: str = 'query'
    room: str | None = None
    device_type: str | None = None
    detail_level: str = 'glance'
    confidence: float = 0.75
    needs_clarification: bool = False
    reason: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {
            'intent': self.intent,
            'action': self.action,
            'room': self.room,
            'device_type': self.device_type,
            'detail_level': self.detail_level,
            'confidence': round(self.confidence, 2),
            'needs_clarification': self.needs_clarification,
            'reason': self.reason,
        }


def _extract_room(query: str) -> str | None:
    q = _normalise(query)
    # Longest aliases first so "bedroom 1" wins over partial matches.
    for alias in sorted(ROOM_ALIASES, key=len, reverse=True):
        if re.search(rf'\b{re.escape(alias)}\b', q):
            return ROOM_ALIASES[alias]
    return None


def _detail_level(query: str) -> str:
    q = _normalise(query)
    if any(term in q for term in DIAGNOSTIC_TERMS):
        return 'diagnostic'
    if any(term in q for term in DETAIL_TERMS):
        return 'detailed'
    return 'glance'


def _looks_like_device_power_query(query: str) -> bool:
    """Distinguish a device named/presented as a power switch from energy usage."""
    q = _normalise(query)
    device_terms = ('switch', 'socket', 'plug', 'light', 'lamp', 'tv', 'fan', 'heater', 'dehumidifier')
    state_terms = ('on', 'off', 'state', 'status', 'working')
    return 'power' in q and any(term in q for term in device_terms) and any(term in q for term in state_terms)


def classify_intent(query: str) -> IntentResult:
    q = _normalise(query)
    room = _extract_room(q)
    detail = _detail_level(q)

    if not q:
        return IntentResult('briefing', confidence=0.98, reason='empty query')

    command_match = re.match(
        r'^(turn|switch|set|change|adjust|dim|brighten|increase|decrease|raise|lower|keep|leave|refresh|reload|clear|cancel|schedule)\b',
        q,
    )
    if command_match:
        return IntentResult(
            'command',
            action='command',
            room=room,
            detail_level=detail,
            confidence=0.99,
            reason='explicit command prefix',
        )

    if room and (
        any(term in q for term in ('status', 'summary', 'what is happening', 'whats happening', 'how is'))
        or q in {_normalise(room), f'{_normalise(room)} status'}
        or detail != 'glance'
    ):
        return IntentResult(
            'room_status',
            room=room,
            detail_level=detail,
            confidence=0.97,
            reason='room plus status wording',
        )

    if any(term in q for term in ('heating status', 'heating state', 'heat status', 'thermostat status')):
        return IntentResult('home_context', room=room, detail_level=detail, confidence=0.95, reason='heating status')

    if _looks_like_device_power_query(q):
        return IntentResult(
            'device_state',
            room=room,
            device_type='switch',
            detail_level=detail,
            confidence=0.94,
            reason='power describes a device/switch rather than energy usage',
        )

    if any(word in q for word in ('electric', 'energy', 'cost', 'spent', 'kwh', 'kilowatt')) or (
        'power' in q and any(term in q for term in ('usage', 'using', 'consume', 'consuming', 'watts', 'whole house', 'octopus'))
    ):
        return IntentResult('energy', room=room, detail_level=detail, confidence=0.94, reason='energy usage wording')

    if 'today' in q and 'yesterday' in q and any(word in q for word in ('compare', 'comparison', 'versus', 'vs')):
        return IntentResult('energy', room=room, detail_level=detail, confidence=0.96, reason='energy comparison wording')

    if 'light' in q and any(word in q for word in ('why', 'because', 'reason')):
        return IntentResult('why_lights', room=room, detail_level=detail, confidence=0.95, reason='light cause question')

    if 'light' in q and any(word in q for word in ('hour', 'hours', 'time', 'long', 'today', 'yesterday', 'duration')):
        return IntentResult('light_hours', room=room, detail_level=detail, confidence=0.95, reason='light duration question')

    if any(word in q for word in ('unusual', 'attention', 'problem', 'issue', 'wrong')):
        return IntentResult('attention', room=room, detail_level=detail, confidence=0.88, reason='problem/attention wording')

    if any(word in q for word in ('health', 'cpu', 'memory', 'load')):
        return IntentResult('health', room=room, detail_level=detail, confidence=0.94, reason='health metric wording')

    if any(word in q for word in ('briefing', 'happening', 'status', 'summary')):
        return IntentResult('briefing', room=room, detail_level=detail, confidence=0.78, reason='general status wording')

    return IntentResult('home_context', room=room, detail_level=detail, confidence=0.65, reason='general home question')

def _safe_call(func: Callable[..., Any] | None, *args: Any, fallback: Any = None, **kwargs: Any) -> Any:
    if func is None:
        return fallback
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        return {'success': False, 'error': str(exc), 'fallback': fallback}


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace(',', '').replace('£', '').replace('\u00c2£', '').strip())
    except (TypeError, ValueError):
        return None


def format_power(value: Any) -> str:
    watts = _safe_float(value)
    if watts is None:
        return 'not available'
    if watts >= 1000:
        return f"{watts / 1000:.1f}".rstrip('0').rstrip('.') + ' kilowatts'
    return f"{round(watts):g} watts"


def format_energy(value: Any) -> str:
    kwh = _safe_float(value)
    if kwh is None:
        return 'not available'
    amount = f"{kwh:.1f}".rstrip('0').rstrip('.')
    return f"{amount} {'kilowatt-hour' if round(kwh, 1) == 1 else 'kilowatt-hours'}"


def format_money(value: Any) -> str:
    amount = _safe_float(value)
    return 'not available' if amount is None else f'£{amount:.2f}'


def _normalise(text: Any) -> str:
    value = str(text or '').lower()
    replacements = {
        'bedroom too': 'bedroom 2', 'bed room too': 'bedroom 2', 'bedroom two': 'bedroom 2', 'bed room two': 'bedroom 2',
        'yeseterday': 'yesterday', 'kilowatts': 'kilowatt-hours',
        'humidify': 'dehumidifier', 'dehumidify': 'dehumidifier', 'de humidifier': 'dehumidifier', 'humidifier': 'dehumidifier',
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r'\b(one|two|too|to|three|four)\b', lambda m: NUMBER_WORDS.get(m.group(1), m.group(1)), value)
    value = re.sub(r'[^a-z0-9£\s.-]', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _normalise_key(text: Any) -> str:
    return re.sub(r'[^a-z0-9]', '', _normalise(text))


def naturalise_units(message: Any) -> str:
    text = str(message or '')
    text = text.replace('\u00c2£', '£').replace('\u00c2°C', '°C').replace('\u00c2°', '°')
    text = re.sub(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*W\b', lambda m: format_power(m.group(1)), text)
    text = re.sub(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*kWh\b', lambda m: format_energy(m.group(1)), text, flags=re.IGNORECASE)
    return text.replace(' / £', ' costing £').replace('£/month', 'per month')


def _route_exists(app: Any, path: str) -> bool:
    return any(getattr(route, 'path', None) == path for route in getattr(app, 'routes', []))


def _device_label(device: dict[str, Any]) -> str:
    return str(device.get('label') or device.get('name') or device.get('id') or 'Unknown device')


def _attrs(device: dict[str, Any]) -> dict[str, Any]:
    attrs = dict(device.get('attributes') or {})
    for key, value in device.items():
        if key not in ('attributes', 'capabilities', 'commands'):
            attrs.setdefault(key, value)
    return attrs


def _is_on(value: Any) -> bool:
    return str(value or '').strip().lower() in {'on', 'true', 'active', 'open'}


def _device_text(device: dict[str, Any]) -> str:
    attrs = _attrs(device)
    capabilities = ' '.join(
        str(value.get('name') or value.get('displayName') or '')
        if isinstance(value, dict)
        else str(value or '')
        for value in (device.get('capabilities') or [])
    )
    return ' '.join(str(part or '') for part in [
        device.get('label'),
        device.get('name'),
        device.get('room'),
        device.get('category'),
        capabilities,
        ' '.join(str(key) for key in attrs.keys()),
    ]).lower()


def _is_aggregate_energy_meter(device: dict[str, Any]) -> bool:
    text = _device_text(device)
    if any(term in text for term in ('octopus live meter', 'live meter', 'whole-house', 'whole house', 'whole-home', 'whole home', 'smart meter', 'electricity meter', 'meter total', 'home total', 'house total', 'aggregate')):
        return True
    return 'octopus' in text and any(term in text for term in ('meter', 'import', 'export', 'tariff', 'rate'))


def _is_light_device(device: dict[str, Any]) -> bool:
    text = _device_text(device)
    return 'light' in text or 'bulb' in text or device.get('category') == 'light'


def _all_light_devices(app_module: Any) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    return sorted([d for d in devices if isinstance(d, dict) and _is_light_device(d)], key=_device_label) if isinstance(devices, list) else []


def _current_lights_on(app_module: Any) -> list[dict[str, Any]]:
    return [d for d in _all_light_devices(app_module) if _is_on(_attrs(d).get('switch'))]


def _light_query_targets(app_module: Any, query: str) -> list[dict[str, Any]]:
    lights = _all_light_devices(app_module)
    target_text = _normalise(query)
    for word in ('lights', 'light', 'on', 'time', 'today', 'yesterday', 'how', 'long', 'has', 'have', 'been', 'for', 'hours', 'hour', 'duration'):
        target_text = re.sub(rf'\b{word}\b', ' ', target_text)
    target_text = re.sub(r'\s+', ' ', target_text).strip()
    if not target_text or target_text in {'all', 'all the'}:
        return lights
    compact_target = _normalise_key(target_text)
    matches = []
    for device in lights:
        label = _normalise(_device_label(device))
        room = _normalise(device.get('room'))
        if target_text in label or target_text in room or compact_target in _normalise_key(label) or (room and compact_target in _normalise_key(room)):
            matches.append(device)
    return matches or lights


def _period_from_query(query: str) -> str:
    return 'yesterday' if 'yesterday' in _normalise(query) else 'today'


def _period_start_timestamp(period: str = 'today') -> int:
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    if period == 'yesterday':
        start -= timedelta(days=1)
    return int(start.timestamp())


def _period_end_timestamp(period: str = 'today') -> int:
    return _period_start_timestamp('today') if period == 'yesterday' else int(time.time())


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, minutes = seconds // 3600, (seconds % 3600) // 60
    if hours and minutes:
        return f'{hours} hour{"s" if hours != 1 else ""} {minutes} minute{"s" if minutes != 1 else ""}'
    if hours:
        return f'{hours} hour{"s" if hours != 1 else ""}'
    return f'{minutes} minute{"s" if minutes != 1 else ""}'


def _device_switch_events(app_module: Any, device_id: str, start: int, end: int) -> tuple[str | None, list[tuple[int, str]]]:
    db_func = getattr(app_module, 'db', None)
    if not callable(db_func):
        return None, []
    conn = db_func()
    try:
        before = conn.execute("SELECT value FROM hubitat_events WHERE device_id=? AND attr='switch' AND created_at < ? ORDER BY created_at DESC LIMIT 1", (str(device_id), start)).fetchone()
        rows = conn.execute("SELECT created_at, value FROM hubitat_events WHERE device_id=? AND attr='switch' AND created_at >= ? AND created_at <= ? ORDER BY created_at ASC", (str(device_id), start, end)).fetchall()
    finally:
        conn.close()
    before_value = before['value'] if before is not None and hasattr(before, 'keys') else (before[0] if before is not None else None)
    events = []
    for row in rows:
        created = row['created_at'] if hasattr(row, 'keys') else row[0]
        value = row['value'] if hasattr(row, 'keys') else row[1]
        events.append((int(created), str(value)))
    return str(before_value) if before_value is not None else None, events


def _light_on_seconds(app_module: Any, device: dict[str, Any], start: int, end: int) -> int:
    before_state, events = _device_switch_events(app_module, str(device.get('id')), start, end)
    state_on = _is_on(before_state) if before_state is not None else (_is_on(_attrs(device).get('switch')) if not events else False)
    last = start
    total = 0
    for created, value in events:
        created = max(start, min(end, int(created)))
        if state_on and created > last:
            total += created - last
        state_on = _is_on(value)
        last = created
    if state_on and end > last:
        total += end - last
    return total


def _light_hours_history_answer(app_module: Any, query: str) -> dict[str, Any] | None:
    q = _normalise(query)
    if 'today' not in q and 'yesterday' not in q:
        return None
    period = _period_from_query(query)
    targets = _light_query_targets(app_module, query)
    if not targets:
        return {'success': False, 'message': 'I could not find any light devices to check.'}
    start, end = _period_start_timestamp(period), _period_end_timestamp(period)
    rows = []
    for device in targets[:20]:
        seconds = _light_on_seconds(app_module, device, start, end)
        currently = 'currently on' if _is_on(_attrs(device).get('switch')) else 'currently off'
        if seconds > 0 or len(targets) <= 5 or (period == 'today' and currently == 'currently on'):
            rows.append({'label': _device_label(device), 'seconds': seconds, 'duration': _format_duration(seconds), 'currently': currently})
    period_label = "Yesterday's" if period == 'yesterday' else "Today's"
    if not rows:
        return {'success': True, 'intent': 'light_hours', 'message': f'No light-on time recorded {period} for the matched lights.', 'lights': [], 'period': period}
    rows.sort(key=lambda item: item['seconds'], reverse=True)
    lines = [f"• {item['label']}: {item['duration']}" + (f" ({item['currently']})" if period == 'today' else '') for item in rows]
    message = f"{period_label} light-on time:\n" + '\n'.join(lines)
    if len(rows) > 1:
        message += f"\nTotal across listed lights: {_format_duration(sum(int(item['seconds']) for item in rows))}."
    return {'success': True, 'intent': 'light_hours', 'message': message, 'lights': rows, 'period': period}


def _top_power_consumers(app_module: Any, limit: int = 5, *, include_aggregates: bool = False) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    consumers = []
    for device in devices:
        if not isinstance(device, dict) or (not include_aggregates and _is_aggregate_energy_meter(device)):
            continue
        watts = _safe_float(_attrs(device).get('power'))
        if watts is not None and watts > 0:
            consumers.append({'label': _device_label(device), 'watts': watts, 'power': format_power(watts)})
    return sorted(consumers, key=lambda item: item['watts'], reverse=True)[:limit]


def _answer_message(answer: Any, fallback: str = '') -> str:
    return str(answer.get('message') or answer.get('speech') or fallback) if isinstance(answer, dict) else str(answer or fallback)


def _intent(query: str) -> str:
    """Backward-compatible intent name used by existing answer builders."""
    result = classify_intent(query)
    # Existing command execution remains in the deterministic main assistant.
    return 'home_context' if result.intent in {'command', 'device_state', 'room_status'} else result.intent

def should_answer_locally(query: str) -> bool:
    q = _normalise(query)
    return not any(q.startswith(prefix) for prefix in COMMAND_PREFIXES) and _intent(query) in LOCAL_FIRST_INTENTS


def _is_period_energy_query(query: str, period: str) -> bool:
    q = _normalise(query)
    if _intent(q) != 'energy' or period not in q:
        return False
    other = 'yesterday' if period == 'today' else 'today'
    if other in q or any(term in q for term in ('compare', 'comparison', 'versus', 'vs', 'advisor', 'worth checking', 'using now', 'right now', 'currently')):
        return False
    terms = ('used today', 'use today', 'spent today', 'cost today', 'today so far', 'have i used today', 'have we used today') if period == 'today' else ('used yesterday', 'use yesterday', 'spent yesterday', 'cost yesterday', 'did i use yesterday', 'did we use yesterday')
    return any(term in q for term in terms)


def _is_energy_now_query(query: str) -> bool:
    q = _normalise(query)
    return _intent(q) == 'energy' and any(term in q for term in ('now', 'right now', 'currently', 'at the moment', 'using the most', 'highest', 'top')) and any(term in q for term in ('using', 'power', 'electricity', 'watts', 'consumer', 'consuming'))


def _is_energy_compare_query(query: str) -> bool:
    q = _normalise(query)
    return _intent(q) == 'energy' and 'today' in q and 'yesterday' in q and any(term in q for term in ('compare', 'comparison', 'versus', 'vs', 'more', 'less'))


def _pick_attr(attrs: dict[str, Any], names: set[str]) -> Any:
    normalised = {_normalise_key(key): value for key, value in attrs.items()}
    for name in names:
        if name in normalised:
            return normalised[name]
    return None


def _octopus_total_cost(app_module: Any, period: str) -> float | None:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    keys = {'displaycosttoday', 'costtoday', 'todaycost', 'electricitycosttoday'} if period == 'today' else {'displaycostyesterday', 'costyesterday', 'yesterdaycost', 'electricitycostyesterday'}
    if not isinstance(devices, list):
        return None
    for device in devices:
        if isinstance(device, dict) and _is_aggregate_energy_meter(device):
            total = _safe_float(_pick_attr(_attrs(device), keys))
            if total is not None:
                return total
    return None


def _period_line(message: str, period: str) -> tuple[str, str] | None:
    prefix = 'used today' if period == 'today' else 'used yesterday'
    for raw_line in message.splitlines():
        line = raw_line.strip().strip('•').strip()
        if line.lower().startswith(prefix):
            detail = line.split(':', 1)[1].strip() if ':' in line else line
            match = re.search(r'(.+?)\s+costing\s+(£?\d+(?:\.\d+)?)', detail, flags=re.IGNORECASE)
            return (match.group(1).strip(), format_money(match.group(2))) if match else (detail, '')
    return None


def _period_energy_message(answer: Any, period: str, app_module: Any | None = None) -> str:
    message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
    found = _period_line(message, period)
    if found is None:
        return message
    usage, energy_cost = found
    intro = 'Today so far you have used' if period == 'today' else 'Yesterday you used'
    total_cost = _octopus_total_cost(app_module, period) if app_module is not None else None
    if not energy_cost:
        return f'{intro} {usage}.'
    if total_cost is None or abs(total_cost - (_safe_float(energy_cost) or 0.0)) < 0.01:
        return f'{intro} {usage}, costing {format_money(total_cost) if total_cost is not None else energy_cost}.'
    return f'{intro} {usage}. Energy cost was about {energy_cost}. Total cost including standing charge was {format_money(total_cost)}.'


def _energy_compare_message(answer: Any, app_module: Any | None = None) -> str:
    message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
    today, yesterday = _period_line(message, 'today'), _period_line(message, 'yesterday')
    if today is None or yesterday is None:
        return message
    today_cost = _octopus_total_cost(app_module, 'today') if app_module is not None else None
    yesterday_cost = _octopus_total_cost(app_module, 'yesterday') if app_module is not None else None
    cost_phrase = ''
    if today_cost is not None and yesterday_cost is not None:
        diff = today_cost - yesterday_cost
        cost_phrase = ' Total cost is about the same as yesterday.' if abs(diff) < 0.01 else f' Total cost is {format_money(abs(diff))} {"higher" if diff > 0 else "lower"} than yesterday.'
    return f'Today so far: {today[0]}. Yesterday: {yesterday[0]}.{cost_phrase}'


def _energy_now_message(answer: Any, app_module: Any) -> str:
    message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
    whole_home = next((line.split(':', 1)[1].strip() for line in message.splitlines() if line.strip().lower().startswith('whole-house power now') and ':' in line), None)
    parts = []
    if whole_home:
        parts.append(f'Whole-house power now is {whole_home}.')
    top = _top_power_consumers(app_module, 5)
    if top:
        parts.append('Top measured device loads: ' + '; '.join(f"{item['label']} is using {item['power']}" for item in top) + '.')
    if whole_home:
        parts.append('Note: Octopus Live Meter is the whole-house total, so it is excluded from the device list.')
    return ' '.join(parts) if parts else 'I cannot see any live power usage right now.'


def _is_switchable(device: dict[str, Any]) -> bool:
    attrs = _attrs(device)
    caps = ' '.join(str(c) for c in (device.get('capabilities') or [])).lower()
    commands = {str(c).lower() for c in (device.get('commands') or [])}
    return attrs.get('switch') is not None or device.get('category') in ('light', 'switch', 'power_device') or 'switch' in caps or 'on' in commands or 'off' in commands


def _voice_dehumidifier_command(app_module: Any, query: str) -> dict[str, Any] | None:
    q = _normalise(query)
    match = re.match(r'^(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+)$', q)
    if not match or 'dehumidifier' not in match.group(2):
        return None
    command, target = match.group(1), match.group(2)
    requested_numbers = set(re.findall(r'\b\d+\b', target))
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return None
    candidates = []
    for device in devices:
        if not isinstance(device, dict) or not _is_switchable(device):
            continue
        label = _normalise(_device_label(device))
        if 'dehumidifier' not in label:
            continue
        label_numbers = set(re.findall(r'\b\d+\b', label))
        if requested_numbers and not requested_numbers.intersection(label_numbers):
            continue
        candidates.append(device)
    if len(candidates) != 1:
        return None
    controller = getattr(app_module, 'command_devices', None)
    if not callable(controller):
        return {'success': False, 'intent': 'voice_device_command', 'message': f'I understood {_device_label(candidates[0])}, but device control is unavailable.'}
    result = controller(candidates, command)
    if isinstance(result, dict):
        result.setdefault('intent', 'voice_device_command')
        result.setdefault('resolved_device', _device_label(candidates[0]))
        result['voice_alias'] = query
        return result
    return {'success': True, 'intent': 'voice_device_command', 'message': f'{_device_label(candidates[0])} turned {command}.', 'result': result}


def _clean_display_text(value: Any) -> str:
    """Normalise HTML entities, mojibake and whitespace."""
    text = html_lib.unescape(str(value or ''))

    degree = chr(176)
    pound = chr(163)

    replacements = {
        chr(226) + chr(8364) + chr(162): '-',          # â€¢
        chr(226) + chr(8364) + chr(8220): '-',         # â€“
        chr(226) + chr(8364) + chr(8221): '-',         # â€”
        chr(226) + chr(8364) + chr(8482): "'",         # â€™
        chr(194) + chr(163): pound,                     # Â£
        chr(194) + chr(176) + 'C': degree + 'C',       # Â°C
        chr(194) + chr(176): degree,                    # Â°
    }

    for _ in range(3):
        previous = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        if text == previous:
            break

    text = re.sub(
        r'<script\b[^>]*>.*?</script>',
        ' ',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(
        r'<style\b[^>]*>.*?</style>',
        ' ',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(
        r'</(?:div|p|li|tr|h[1-6])>',
        '\n',
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r'<[^>]+>', ' ', text)

    lines = [
        re.sub(r'\s+', ' ', line).strip()
        for line in text.splitlines()
    ]
    return '\n'.join(line for line in lines if line).strip()

def _room_matches(device: dict[str, Any], room: str) -> bool:
    wanted = _normalise_key(room)
    assigned = _normalise_key(device.get('room'))
    if assigned and assigned == wanted:
        return True
    label = _normalise_key(_device_label(device))
    return bool(wanted and (label.startswith(wanted) or wanted in label))


def _room_devices(app_module: Any, room: str) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    matched = [device for device in devices if isinstance(device, dict) and _room_matches(device, room)]
    return sorted(matched, key=lambda item: _device_label(item).lower())


def _numeric_values(devices: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for device in devices:
        value = _safe_float(_attrs(device).get(key))
        if value is not None:
            values.append(value)
    return values


def _format_number(value: float, decimals: int = 1) -> str:
    rounded = round(value, decimals)
    return f'{rounded:g}'


def _active_room_fact(device: dict[str, Any]) -> str | None:
    attrs = _attrs(device)
    label = _clean_display_text(_device_label(device))
    switch = str(attrs.get('switch') or '').lower()
    motion = str(attrs.get('motion') or '').lower()
    contact = str(attrs.get('contact') or '').lower()
    presence = str(attrs.get('presence') or '').lower()
    lock = str(attrs.get('lock') or '').lower()
    water = str(attrs.get('water') or '').lower()
    smoke = str(attrs.get('smoke') or '').lower()
    carbon = str(attrs.get('carbonMonoxide') or '').lower()
    operating = str(attrs.get('thermostatOperatingState') or '').lower()
    power = _safe_float(attrs.get('power'))
    battery = _safe_float(attrs.get('battery'))

    if water in {'wet', 'detected', 'active'}:
        return f'{label}: leak detected'
    if smoke not in {'', 'clear', 'tested', 'false', '0'}:
        return f'{label}: smoke alert'
    if carbon not in {'', 'clear', 'false', '0'}:
        return f'{label}: carbon monoxide alert'
    if battery is not None and battery <= 20:
        return f'{label}: battery {_format_number(battery, 0)} percent'
    if contact == 'open':
        return f'{label}: open'
    if lock == 'unlocked':
        return f'{label}: unlocked'
    if motion in {'active', 'motion', 'true'}:
        return f'{label}: motion active'
    if presence in {'present', 'occupied', 'active'}:
        return f'{label}: occupied'
    if operating in {'heating', 'pending heat'}:
        return f'{label}: heating'
    if switch == 'on':
        if power is not None and power >= 1:
            return f'{label}: on, using {format_power(power)}'
        return f'{label}: on'
    if power is not None and power >= 5:
        return f'{label}: using {format_power(power)}'
    return None


def _concise_device_state(device: dict[str, Any]) -> str:
    attrs = _attrs(device)
    label = _clean_display_text(_device_label(device))
    parts: list[str] = []

    for key in ('switch', 'motion', 'contact', 'presence', 'lock', 'water', 'thermostatOperatingState'):
        value = attrs.get(key)
        if value not in (None, ''):
            parts.append(_clean_display_text(value))

    temp = _safe_float(attrs.get('temperature'))
    humidity = _safe_float(attrs.get('humidity'))
    power = _safe_float(attrs.get('power'))
    battery = _safe_float(attrs.get('battery'))
    setpoint = _safe_float(attrs.get('heatingSetpoint'))

    if temp is not None:
        parts.append(f'{_format_number(temp)}Â°C')
    if humidity is not None:
        parts.append(f'{_format_number(humidity)}% humidity')
    if setpoint is not None:
        parts.append(f'set to {_format_number(setpoint)}Â°C')
    if power is not None:
        parts.append(format_power(power))
    if battery is not None:
        parts.append(f'{_format_number(battery, 0)}% battery')

    clean_parts: list[str] = []
    for part in parts:
        if part and part not in clean_parts:
            clean_parts.append(part)
    return f"{label}: {', '.join(clean_parts) if clean_parts else 'no useful state reported'}"


def _diagnostic_device_state(device: dict[str, Any]) -> str:
    attrs = _attrs(device)
    useful_keys = (
        'switch', 'level', 'temperature', 'humidity', 'motion', 'contact', 'presence',
        'battery', 'power', 'energy', 'thermostatMode', 'thermostatOperatingState',
        'heatingSetpoint', 'lock', 'water', 'smoke', 'carbonMonoxide',
    )
    values = []
    for key in useful_keys:
        value = attrs.get(key)
        if value not in (None, ''):
            values.append(f'{key}={_clean_display_text(value)}')
    category = _clean_display_text(device.get('category') or 'device')
    updated = device.get('last_activity_at') or device.get('updated_at')
    if updated not in (None, ''):
        values.append(f'updated={updated}')
    return f"{_clean_display_text(_device_label(device))} [{category}]: " + (', '.join(values) or 'no useful attributes')


def focused_room_status_answer(app_module: Any, query: str) -> dict[str, Any] | None:
    route = classify_intent(query)
    if route.intent != 'room_status' or not route.room:
        return None

    devices = _room_devices(app_module, route.room)
    if not devices:
        # Preserve compatibility with the existing main room-status engine.
        # The caller will delegate when the focused layer has no matched devices.
        return None

    temperatures = _numeric_values(devices, 'temperature')
    humidities = _numeric_values(devices, 'humidity')
    climate: list[str] = []
    if temperatures:
        climate.append(f'{_format_number(sum(temperatures) / len(temperatures))}Â°C')
    if humidities:
        climate.append(f'{_format_number(sum(humidities) / len(humidities))}% humidity')

    active = []
    for device in devices:
        fact = _active_room_fact(device)
        if fact and fact not in active:
            active.append(fact)

    if route.detail_level == 'diagnostic':
        lines = [_diagnostic_device_state(device) for device in devices]
        message = f'{route.room} diagnostic status:\n' + '\n'.join(f'â€¢ {line}' for line in lines)
    elif route.detail_level == 'detailed':
        lines = [_concise_device_state(device) for device in devices]
        intro = f"{route.room}: {', '.join(climate)}." if climate else f'{route.room} detailed status.'
        message = intro + '\n' + '\n'.join(f'â€¢ {line}' for line in lines)
    else:
        parts = []
        if climate:
            parts.append(', '.join(climate))
        if active:
            parts.append('; '.join(active[:8]))
        if not parts:
            parts.append('no active devices or important issues')
        message = f"{route.room}: " + '. '.join(parts).rstrip('.') + '.'

    return {
        'success': True,
        'intent': 'room_status',
        'room': route.room,
        'detail_level': route.detail_level,
        'routing': route.as_dict(),
        'message': naturalise_units(_clean_display_text(message) if route.detail_level == 'glance' else message),
        'active_facts': active,
        'device_count': len(devices),
        'devices': devices if route.detail_level != 'glance' else [],
    }

def _room_status_answer(app_module: Any, query: str) -> dict[str, Any] | None:
    focused = focused_room_status_answer(app_module, query)
    if isinstance(focused, dict):
        return focused

    route = classify_intent(query)
    delegate = getattr(app_module, 'room_status_answer', None)
    answer = _safe_call(delegate, query, fallback=None) if callable(delegate) else None
    if isinstance(answer, dict) and answer.get('message'):
        answer = dict(answer)
        answer['message'] = naturalise_units(_clean_display_text(answer['message']))
        answer.setdefault('intent', 'room_status')
        answer['routing'] = route.as_dict()
        answer['detail_level'] = route.detail_level
        if route.room:
            answer.setdefault('room', route.room)
        return answer
    return None

def _delegate_main_assistant_first(query: str) -> bool:
    q = _normalise(query)
    return any(term in q for term in (
        'ai status',
        'ai running',
        'ollama status',
        'local ai',
        'required setting',
        'settings enabled',
        'addon options',
        'add-on options',
        'heating status',
        'heating state',
        'heat status',
        'thermostat status',
        'which batteries are low',
        'what batteries are low',
        'low batteries',
        'hub health',
        'hubitat health',
        'device health',
        'device status',
        'device check',
        'device report',
    ))


HUB_INFO_CACHE: dict[str, Any] = {'checked_at': 0.0, 'data': None, 'error': None}
HUB_INFO_CACHE_SECONDS = 60


def _html_text(value: Any, *, separators: bool = False) -> str:
    text = str(value or '')
    if separators:
        text = re.sub(r'</(?:td|th|tr|div|p|br|li)>', ' | ', text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', ' | ', text, flags=re.IGNORECASE)
    cleaner = globals().get('_clean_display_text')
    if callable(cleaner):
        return cleaner(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', text).strip()


def _hub_base_url(app_module: Any) -> str:
    config = getattr(app_module, 'CONFIG', {}) or {}
    base = str(config.get('hubitat_base_url') or '').strip().rstrip('/')
    match = re.match(r'^(https?://[^/]+)', base, flags=re.IGNORECASE)
    return match.group(1) if match else base


def _parse_hub_info_html(html: str) -> dict[str, str]:
    cells = re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', html, flags=re.IGNORECASE | re.DOTALL)
    clean = [_html_text(cell) for cell in cells]
    data: dict[str, str] = {}
    for index in range(0, len(clean) - 1, 2):
        key = clean[index].strip()
        value = clean[index + 1].strip()
        if key and value:
            data[key] = value

    if data:
        return data

    # Fallback for plain/preformatted responses.
    labels = (
        'Name', 'Version', 'IP Addr', 'Free Mem', 'CPU Load/Load%', 'DB Size',
        'Last Restart', 'Uptime', 'Temperature', 'ZB Channel', 'ZW Radio/SDK',
        'Matter Enabled/Status',
    )
    plain = _html_text(html, separators=True)
    for label in labels:
        pattern = rf'{re.escape(label)}\s*[|:\-]*\s*(.*?)(?=\s*(?:{"|".join(re.escape(item) for item in labels)})\b|$)'
        match = re.search(pattern, plain, flags=re.IGNORECASE)
        if match:
            data[label] = match.group(1).strip(' |')
    return data


def fetch_hub_info(app_module: Any, *, force: bool = False) -> dict[str, Any]:
    now = time.time()
    cached = HUB_INFO_CACHE.get('data')
    if not force and cached and now - float(HUB_INFO_CACHE.get('checked_at') or 0) < HUB_INFO_CACHE_SECONDS:
        return {'success': True, 'source': 'cache', 'data': cached}

    base = _hub_base_url(app_module)
    if not base:
        return {'success': False, 'message': 'Hubitat base URL is not configured.', 'data': {}}

    requests_module = getattr(app_module, 'requests', None)
    if requests_module is None or not hasattr(requests_module, 'get'):
        return {'success': False, 'message': 'HTTP client is unavailable.', 'data': {}}

    url = base + '/local/hubInfoOutput.html'
    try:
        response = requests_module.get(url, timeout=5)
        response.raise_for_status()
        data = _parse_hub_info_html(response.text)
        if not data:
            raise ValueError('Hub Info page did not contain recognised fields.')
        HUB_INFO_CACHE.update({'checked_at': now, 'data': data, 'error': None})
        return {'success': True, 'source': url, 'data': data}
    except Exception as exc:
        HUB_INFO_CACHE.update({'checked_at': now, 'data': None, 'error': str(exc)})
        return {'success': False, 'message': str(exc), 'source': url, 'data': {}}


def _hub_field(data: dict[str, str], *names: str) -> str | None:
    normalised = {_normalise_key(key): value for key, value in data.items()}
    for name in names:
        value = normalised.get(_normalise_key(name))
        if value:
            return value
    return None


def hub_cpu_advisor_answer(app_module: Any, query: str = '') -> dict[str, Any] | None:
    q = _normalise(query)
    if not any(term in q for term in ('cpu advisor', 'hub status', 'hub cpu', 'hubitat status', 'hub information', 'hub info')):
        return None

    result = fetch_hub_info(app_module)
    if not result.get('success'):
        return {
            'success': False,
            'intent': 'hub_status',
            'message': 'I could not read live Hubitat Hub Info: ' + str(result.get('message') or 'unknown error'),
            'hub_info': {},
        }

    data = result['data']
    name = _hub_field(data, 'Name') or 'Hubitat hub'
    version = _hub_field(data, 'Version')
    cpu = _hub_field(data, 'CPU Load/Load%', 'CPU Load')
    free_mem = _hub_field(data, 'Free Mem', 'Free Memory')
    temperature = _hub_field(data, 'Temperature')
    db_size = _hub_field(data, 'DB Size')
    uptime = _hub_field(data, 'Uptime')
    last_restart = _hub_field(data, 'Last Restart')
    matter = _hub_field(data, 'Matter Enabled/Status')

    headline = f'{name} status from live Hub Info'
    if version:
        headline += f' ({version})'

    facts = []
    if cpu:
        facts.append(f'CPU load: {cpu}')
    if free_mem:
        facts.append(f'Free memory: {free_mem}')
    if temperature:
        facts.append(f'Temperature: {temperature}')
    if db_size:
        facts.append(f'Database size: {db_size}')
    if uptime:
        facts.append(f'Uptime: {uptime}')
    if last_restart:
        facts.append(f'Last restart: {last_restart}')
    if matter:
        facts.append(f'Matter: {matter}')

    advisory = []
    cpu_percent = None
    if cpu:
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', cpu)
        if matches:
            cpu_percent = float(matches[-1])
    temp_number = _safe_float(re.search(r'(\d+(?:\.\d+)?)', temperature or '').group(1)) if re.search(r'(\d+(?:\.\d+)?)', temperature or '') else None
    if cpu_percent is not None:
        if cpu_percent >= 80:
            advisory.append('CPU is very high; reduce polling and inspect busy apps.')
        elif cpu_percent >= 50:
            advisory.append('CPU is elevated; monitor Maker API and app activity.')
        else:
            advisory.append('CPU is within a reasonable range.')
    if temp_number is not None and temp_number >= 65:
        advisory.append('Hub temperature is high.')
    elif temp_number is not None:
        advisory.append('Hub temperature is within a reasonable range.')

    message = headline + ':\n' + '\n'.join(f'- {fact}' for fact in facts)
    if advisory:
        message += '\nAssessment: ' + ' '.join(advisory)

    return {
        'success': True,
        'intent': 'hub_status',
        'message': _clean_display_text(message),
        'hub_info': data,
        'source': result.get('source'),
    }


def _weather_devices(app_module: Any) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    matches = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        attrs = _attrs(device)
        text = _device_text(device)
        if (
            'weather' in text
            or 'open-meteo' in text
            or any(key in attrs for key in ('weatherSummary', 'weatherSummaryLine', 'threedayfcstTile', 'precipitationToday'))
        ):
            matches.append(device)
    return sorted(matches, key=lambda item: ('open-meteo' not in _device_text(item), _device_label(item).lower()))


def _weather_device(app_module: Any) -> dict[str, Any] | None:
    return _authoritative_weather_device(app_module)

def _weather_period(query: str) -> str:
    q = _normalise(query)
    if any(term in q for term in ('tomorrow', 'next day')):
        return 'tomorrow'
    if any(term in q for term in ('right now', 'currently', 'current weather', 'weather now', 'raining now', 'rain now', 'now')):
        return 'now'
    if 'today' in q:
        return 'today'
    return 'overview'


def _rain_question(query: str) -> bool:
    q = _normalise(query)
    return any(term in q for term in ('rain', 'raining', 'umbrella', 'precipitation', 'wet weather'))


def _weather_summary_values(attrs: dict[str, Any]) -> dict[str, Any]:
    summary = _html_text(attrs.get('weatherSummary'))
    line = _html_text(attrs.get('weatherSummaryLine'))
    combined = ' '.join(value for value in (summary, line) if value)

    def find(pattern: str) -> str | None:
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    return {
        'summary': summary,
        'line': line,
        'condition': find(r'(?:updated at \d{1,2}:\d{2}[.,]?\s*)?([A-Za-z][A-Za-z ]+?)\s+with a high'),
        'high': find(r'high of?\s*(\d+(?:\.\d+)?)\s*C'),
        'low': find(r'low of?\s*(\d+(?:\.\d+)?)\s*C'),
        'current': find(r'current temperature is\s*(\d+(?:\.\d+)?)\s*C'),
        'feels': find(r'feels like\s*(\d+(?:\.\d+)?)\s*C'),
        'precip_now': find(r'precipitation now is\s*([A-Za-z ]+\s+\d+(?:\.\d+)?\s*mm)'),
        'chance': find(r'chance of precipitation is\s*(\d+(?:\.\d+)?)\s*%'),
    }


def _forecast_tokens(raw: Any) -> list[str]:
    # Extract visible text tokens from Hubitat weather tile HTML.
    from html.parser import HTMLParser

    source = html_lib.unescape(str(raw or ''))
    if not source:
        return []

    source = (
        source.replace('\\u003c', '<')
        .replace('\\u003e', '>')
        .replace('\\n', '\n')
        .replace('\\t', ' ')
    )

    class _VisibleTextParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.tokens: list[str] = []
            self._ignore_depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() in {'script', 'style'}:
                self._ignore_depth += 1

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() in {'script', 'style'} and self._ignore_depth:
                self._ignore_depth -= 1

        def handle_data(self, data: str) -> None:
            if self._ignore_depth:
                return
            value = _clean_display_text(data)
            if value:
                self.tokens.extend(
                    part.strip()
                    for part in value.splitlines()
                    if part.strip()
                )

    parser = _VisibleTextParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception:
        return [
            part.strip()
            for part in re.split(r'[|\n]+', _clean_display_text(source))
            if part.strip()
        ]

    return parser.tokens



def _tomorrow_forecast(attrs: dict[str, Any]) -> dict[str, Any]:
    # Parse tomorrow from either row-major or day-block forecast tiles.
    tokens = _forecast_tokens(attrs.get('threedayfcstTile'))
    tomorrow_key = (datetime.now() + timedelta(days=1)).strftime('%a').lower()

    day_aliases = {
        'tod': 'today',
        'today': 'today',
        'mon': 'mon',
        'monday': 'mon',
        'tue': 'tue',
        'tues': 'tue',
        'tuesday': 'tue',
        'wed': 'wed',
        'wednesday': 'wed',
        'thu': 'thu',
        'thur': 'thu',
        'thurs': 'thu',
        'thursday': 'thu',
        'fri': 'fri',
        'friday': 'fri',
        'sat': 'sat',
        'saturday': 'sat',
        'sun': 'sun',
        'sunday': 'sun',
    }

    def day_key(token: str) -> str | None:
        return day_aliases.get(_normalise(token))

    def condition_value(token: str) -> str | None:
        match = re.fullmatch(
            r'(Sunny|Clear|Mostly sunny|Partly cloudy|Mostly cloudy|Cloudy|'
            r'Overcast|Light rain|Rain|Heavy rain|Showers|Light showers|'
            r'Drizzle|Thunderstorms?|Snow|Sleet|Fog|Mist)',
            re.sub(r'\s+', ' ', token).strip(),
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else None

    def high_low_value(token: str) -> tuple[str, str] | None:
        match = re.search(
            r'(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C\s*/\s*'
            r'(-?\d+(?:\.\d+)?)\s*(?:°\s*)?C',
            token,
            flags=re.IGNORECASE,
        )
        return (match.group(1), match.group(2)) if match else None

    result = {
        'label': 'Tomorrow',
        'available': False,
        'condition': None,
        'high': None,
        'low': None,
        'chance': None,
        'amount': None,
        'raw': _clean_display_text(attrs.get('threedayfcstTile')),
        'tokens': tokens,
    }

    headers = [
        (index, key)
        for index, token in enumerate(tokens)
        for key in [day_key(token)]
        if key
    ]
    if not headers:
        return result

    tomorrow_column = next(
        (column for column, (_, key) in enumerate(headers) if key == tomorrow_key),
        None,
    )
    if tomorrow_column is None:
        return result

    day_count = len(headers)
    tail = tokens[headers[-1][0] + 1:]

    conditions = [
        value
        for token in tail
        for value in [condition_value(token)]
        if value
    ]
    high_lows = [
        value
        for token in tail
        for value in [high_low_value(token)]
        if value
    ]
    chances = []
    amounts = []
    for token in tail:
        chance = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%\s*', token)
        if chance:
            chances.append(chance.group(1))
        amount = re.fullmatch(
            r'\s*(\d+(?:\.\d+)?)\s*mm\s*',
            token,
            flags=re.IGNORECASE,
        )
        if amount:
            amounts.append(amount.group(1))

    if len(conditions) >= day_count:
        result['condition'] = conditions[tomorrow_column]
    if len(high_lows) >= day_count:
        result['high'], result['low'] = high_lows[tomorrow_column]
    if len(chances) >= day_count:
        result['chance'] = chances[tomorrow_column]
    if len(amounts) >= day_count:
        result['amount'] = amounts[tomorrow_column]

    if not any(result.get(key) for key in ('condition', 'high', 'low', 'chance', 'amount')):
        start = headers[tomorrow_column][0] + 1
        end = headers[tomorrow_column + 1][0] if tomorrow_column + 1 < day_count else len(tokens)
        segment = tokens[start:end]
        for token in segment:
            if result['condition'] is None:
                result['condition'] = condition_value(token)
            if result['high'] is None:
                pair = high_low_value(token)
                if pair:
                    result['high'], result['low'] = pair
            if result['chance'] is None:
                chance = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%\s*', token)
                if chance:
                    result['chance'] = chance.group(1)
            if result['amount'] is None:
                amount = re.fullmatch(
                    r'\s*(\d+(?:\.\d+)?)\s*mm\s*',
                    token,
                    flags=re.IGNORECASE,
                )
                if amount:
                    result['amount'] = amount.group(1)

    result['available'] = any(
        result.get(key) not in (None, '')
        for key in ('condition', 'high', 'low', 'chance', 'amount')
    )
    return result


def improved_weather_answer(app_module: Any, query: str) -> dict[str, Any] | None:
    q = _normalise(query)
    if not any(term in q for term in ('weather', 'rain', 'raining', 'umbrella', 'precipitation', 'forecast')):
        return None

    device = _weather_device(app_module)
    if device is None:
        return {'success': False, 'intent': 'weather', 'message': 'I could not find a weather device.'}

    attrs = _attrs(device)
    values = _weather_summary_values(attrs)
    tomorrow = _tomorrow_forecast(attrs)
    period = _weather_period(query)
    rain_only = _rain_question(query)
    if rain_only and period == 'overview':
        period = 'today'

    source = _device_label(device)
    degree = chr(176)

    current_temp = values.get('current')
    if not current_temp:
        current_number = _safe_float(attrs.get('temperature'))
        current_temp = f'{current_number:g}' if current_number is not None else None

    current_condition = values.get('condition') or values.get('line')
    precip_now = values.get('precip_now')
    today_chance = values.get('chance')
    today_high = values.get('high')
    today_low = values.get('low')

    def rain_answer(label: str, chance: Any, amount: Any, current: str | None = None) -> str:
        chance_number = _safe_float(chance)
        amount_number = _safe_float(amount)

        if amount_number is None and current:
            amount_match = re.search(r'(\d+(?:\.\d+)?)\s*mm', current, flags=re.IGNORECASE)
            if amount_match:
                amount_number = float(amount_match.group(1))

        if chance_number is None and amount_number is None:
            return f'Rain information for {label.lower()} is not available from the weather device.'

        wet = (
            (amount_number is not None and amount_number > 0)
            or (chance_number is not None and chance_number >= 50)
        )
        possible = not wet and chance_number is not None and chance_number > 0

        if wet:
            message = f'{label}: Rain is likely.'
        elif possible:
            message = f'{label}: Rain is possible.'
        else:
            message = f'{label}: No rain is expected.'

        details = []
        if chance_number is not None:
            details.append(f'rain chance {chance_number:g}%')
        if amount_number is not None:
            if label.lower() == 'tomorrow':
                details.append(f'forecast rain {amount_number:g} mm')
            else:
                details.append(f'rainfall {amount_number:g} mm')
        if details:
            message += ' ' + '; '.join(details) + '.'
        if current:
            message += f' It is currently {current}.'
        return message

    if period == 'now':
        if rain_only:
            message = rain_answer('Now', today_chance, None, precip_now)
        else:
            parts = []
            if current_condition:
                parts.append(str(current_condition).rstrip('.,'))
            if current_temp:
                parts.append(f'{current_temp}{degree}C now')
            if values.get('feels'):
                parts.append(f"feels like {values['feels']}{degree}C")
            if precip_now:
                parts.append(f'precipitation now: {precip_now}')
            message = 'Now: ' + '. '.join(parts).rstrip('.') + '.'

    elif period == 'today':
        if rain_only:
            message = rain_answer('Today', today_chance, None, precip_now)
        else:
            parts = []
            if current_condition:
                parts.append(str(current_condition).rstrip('.,'))
            if today_high and today_low:
                parts.append(f'high {today_high}{degree}C, low {today_low}{degree}C')
            if today_chance:
                parts.append(f'rain chance {today_chance}%')
            if precip_now:
                parts.append(f'currently {precip_now}')
            message = 'Today: ' + '. '.join(parts).rstrip('.') + '.'

    elif period == 'tomorrow':
        if rain_only:
            message = rain_answer('Tomorrow', tomorrow.get('chance'), tomorrow.get('amount'))
            extras = []
            if tomorrow.get('condition'):
                extras.append(f"conditions {tomorrow['condition']}")
            if tomorrow.get('high') and tomorrow.get('low'):
                extras.append(
                    f"high {tomorrow['high']}{degree}C, "
                    f"low {tomorrow['low']}{degree}C"
                )
            if extras:
                message += ' ' + '; '.join(extras) + '.'
        else:
            parts = []
            if tomorrow.get('condition'):
                parts.append(str(tomorrow['condition']))
            if tomorrow.get('high') and tomorrow.get('low'):
                parts.append(
                    f"high {tomorrow['high']}{degree}C, "
                    f"low {tomorrow['low']}{degree}C"
                )
            if tomorrow.get('chance') is not None:
                parts.append(f"rain chance {tomorrow['chance']}%")
            if tomorrow.get('amount') is not None:
                parts.append(f"forecast rain {tomorrow['amount']} mm")
            if parts:
                message = 'Tomorrow: ' + '. '.join(parts).rstrip('.') + '.'
            else:
                message = "Tomorrow's forecast is not available from the weather device."

    else:
        lines = []
        now_parts = []
        if current_condition:
            now_parts.append(str(current_condition).rstrip('.,'))
        if current_temp:
            now_parts.append(f'{current_temp}{degree}C')
        if now_parts:
            lines.append('Now: ' + ', '.join(now_parts) + '.')

        today_parts = []
        if today_high and today_low:
            today_parts.append(f'high {today_high}{degree}C, low {today_low}{degree}C')
        if today_chance:
            today_parts.append(f'rain chance {today_chance}%')
        if today_parts:
            lines.append('Today: ' + ', '.join(today_parts) + '.')

        tomorrow_parts = []
        if tomorrow.get('condition'):
            tomorrow_parts.append(str(tomorrow['condition']))
        if tomorrow.get('high') and tomorrow.get('low'):
            tomorrow_parts.append(
                f"high {tomorrow['high']}{degree}C, "
                f"low {tomorrow['low']}{degree}C"
            )
        if tomorrow.get('chance') is not None:
            tomorrow_parts.append(f"rain chance {tomorrow['chance']}%")
        if tomorrow_parts:
            lines.append('Tomorrow: ' + ', '.join(tomorrow_parts) + '.')

        message = '\n'.join(lines) or values.get('summary') or values.get('line') or 'Weather information is unavailable.'

    return {
        'success': True,
        'intent': 'weather',
        'period': period,
        'message': _clean_display_text(message),
        'weather_source': source,
        'now': values,
        'tomorrow': tomorrow,
    }


def _normalise_detail_attributes(detail: Any) -> dict[str, Any]:
    """Convert Maker API detail payloads into a simple attribute dictionary."""
    if not isinstance(detail, dict):
        return {}
    result: dict[str, Any] = {}
    raw = detail.get('attributes')
    if isinstance(raw, dict):
        result.update(raw)
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get('name') or item.get('attribute')
            if not name:
                continue
            value = item.get('currentValue')
            if value is None:
                value = item.get('value')
            result[str(name)] = value
    for key, value in detail.items():
        if key in {
            'attributes', 'commands', 'capabilities', 'id', 'name', 'label',
            'type', 'deviceNetworkId', 'date', 'model', 'manufacturer',
        }:
            continue
        if isinstance(value, (str, int, float, bool)) and key not in result:
            result[key] = value
    return result


def _refresh_device_detail(app_module: Any, device: dict[str, Any]) -> dict[str, Any]:
    """Fetch one device from Maker API and merge it without changing the cache."""
    device_id = device.get('id')
    getter = getattr(app_module, 'maker_get', None)
    if not device_id or not callable(getter):
        return device
    try:
        detail = getter(f'devices/{device_id}', timeout=8)
    except TypeError:
        try:
            detail = getter(f'devices/{device_id}')
        except Exception:
            return device
    except Exception:
        return device
    if not isinstance(detail, dict):
        return device

    merged = dict(device)
    merged_attrs = dict(_attrs(device))
    merged_attrs.update(_normalise_detail_attributes(detail))
    merged['attributes'] = merged_attrs
    for key in ('label', 'name', 'room', 'category', 'capabilities', 'commands'):
        if detail.get(key) not in (None, ''):
            merged[key] = detail[key]
    return merged


def _authoritative_weather_device(app_module: Any) -> dict[str, Any] | None:
    devices = _weather_devices(app_module)
    if not devices:
        return None
    # Weather summaries and forecast tiles are commonly omitted from the cached list.
    for device in devices:
        refreshed = _refresh_device_detail(app_module, device)
        attrs = _attrs(refreshed)
        if any(attrs.get(key) not in (None, '') for key in (
            'weatherSummary', 'weatherSummaryLine', 'threedayfcstTile',
            'precipitationToday', 'temperature',
        )):
            return refreshed
    return _refresh_device_detail(app_module, devices[0])


def _person_home_from_device(device: dict[str, Any]) -> bool:
    attrs = _attrs(device)
    presence = _normalise(attrs.get('presence'))
    if presence in {'present', 'home', 'at home', 'occupied'}:
        return True

    for key in ('place', 'currentPlace', 'locationName', 'status', 'address1'):
        value = _normalise(attrs.get(key))
        if value in {'home', 'at home'} or value.startswith('at home '):
            return True

    # Life360 custom drivers often expose the authoritative state in tile HTML.
    for key in ('tile', 'html', 'map', 'display', 'summary'):
        raw = _clean_display_text(attrs.get(key))
        if re.search(r'\bat home since\b', raw, flags=re.IGNORECASE):
            return True
        first_lines = ' '.join(raw.splitlines()[:3])
        if re.search(r'\bat home\b', first_lines, flags=re.IGNORECASE):
            return True
    return False


def authoritative_people_home(app_module: Any, refresh_live: bool = False) -> dict[str, Any]:
    household = list(getattr(app_module, 'HOUSEHOLD_PEOPLE', None) or ('Enamul', 'Samah', 'Tahmid', 'Muhsena'))
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    devices = devices if isinstance(devices, list) else []
    home: list[str] = []
    evidence: dict[str, str] = {}

    for person in household:
        person_key = _normalise_key(person)
        candidates = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            label_key = _normalise_key(_device_label(device))
            name_key = _normalise_key(device.get('name'))
            if label_key.startswith(person_key) or name_key.startswith(person_key):
                candidates.append(device)

        # Prefer devices that look like Life360/presence devices.
        candidates.sort(
            key=lambda d: (
                'life360' not in _device_text(d),
                'presence' not in _device_text(d),
                len(_device_label(d)),
            )
        )

        for candidate in candidates:
            current = _refresh_device_detail(app_module, candidate) if refresh_live else candidate
            if _person_home_from_device(current):
                home.append(person)
                evidence[person] = _device_label(current)
                break

    return {
        'home': home,
        'count': len(home),
        'total': len(household),
        'away': [person for person in household if person not in home],
        'evidence': evidence,
    }


def authoritative_family_answer(app_module: Any, query: str) -> dict[str, Any] | None:
    q = _normalise(query)
    if not any(term in q for term in ('who is home', 'whos home', 'who s home', 'people home', 'family home', 'is everyone home')):
        return None
    result = authoritative_people_home(app_module)
    names = result['home']
    if result['count'] == result['total'] and result['total']:
        message = 'Everyone is home: ' + ', '.join(names) + '.'
    elif names:
        message = f"{result['count']}/{result['total']} people are home: " + ', '.join(names) + '.'
        if result['away']:
            message += ' Away: ' + ', '.join(result['away']) + '.'
    else:
        message = 'I cannot confirm anyone as home from the current presence devices.'
    return {
        'success': True,
        'intent': 'family_presence',
        'source': 'event_cache',
        'message': message,
        'people_home': names,
        'people_away': result['away'],
        'count': result['count'],
        'total': result['total'],
        'evidence': result['evidence'],
    }


def _status_report_device(app_module: Any, refresh: bool = True) -> dict[str, Any] | None:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return None

    report_names = {
        'reporthtml', 'report_html', 'reporttext', 'report_text',
        'currentreport', 'devicestatusreport', 'statussummary',
        'overallstatus', 'lowbatterycount', 'low_battery_count',
    }

    def report_payload(device: dict[str, Any]) -> Any:
        attrs = _attrs(device)
        lowered = {_normalise_key(key): value for key, value in attrs.items()}
        for name in (
            'reporthtml', 'report_html', 'reporttext', 'report_text',
            'currentreport', 'devicestatusreport', 'statussummary',
            'overallstatus',
        ):
            value = lowered.get(_normalise_key(name))
            if value not in (None, ''):
                return value
        return None

    candidates = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        attrs = _attrs(device)
        attr_names = {_normalise_key(key) for key in attrs}
        text = _device_text(device)
        if (
            'device status report' in text
            or bool(attr_names & report_names)
            or 'low battery report' in text
        ):
            candidates.append(device)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            report_payload(item) in (None, ''),
            'device status report display' not in _device_text(item),
            'device status report' not in _device_text(item),
            _device_label(item).lower(),
        )
    )

    first = None
    for candidate in candidates:
        current = _refresh_device_detail(app_module, candidate) if refresh else candidate
        if first is None:
            first = current
        if report_payload(current) not in (None, ''):
            return current

    return first



def _extract_low_battery_report(report_html: Any) -> list[dict[str, Any]]:
    raw = html_lib.unescape(str(report_html or ''))
    if not raw:
        return []

    text = _clean_display_text(raw)
    if not text:
        return []

    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    section_lines: list[str] = []
    active = False

    stop_headings = (
        'offline', 'no change', 'motion', 'stale', 'info',
        'ok', 'online', 'report summary', 'device report',
    )

    for line in lines:
        if not line:
            continue

        heading_text = re.sub(r'[^a-z0-9 ]+', ' ', line.lower())
        heading_text = re.sub(r'\s+', ' ', heading_text).strip()

        low_match = re.match(
            r'^\s*[\[\(\{]?\s*low\s+batter(?:y|ies)\s*[\]\)\}]?\s*[:\-]?\s*(.*)$',
            line,
            flags=re.IGNORECASE,
        )
        if low_match:
            active = True
            remainder = low_match.group(1).strip()
            # Hubitat commonly labels the section "[LOW BATTERY] Below 20%".
            # That is a threshold, not a device named "Below" with 20%.
            threshold_label = re.fullmatch(
                r'(?:below|under|less\s+than|threshold)?\s*\d+(?:\.\d+)?\s*%?',
                remainder,
                flags=re.IGNORECASE,
            )
            if remainder and not threshold_label:
                section_lines.append(remainder)
            continue

        if active and any(heading_text.startswith(value) for value in stop_headings):
            break

        if active:
            section_lines.append(line)

    if not section_lines:
        match = re.search(
            r'(?:\[|\b)LOW\s+BATTER(?:Y|IES)(?:\]|\b)(.*?)(?='
            r'(?:\[|\b)(?:OFFLINE|NO\s+CHANGE|MOTION|STALE|INFO|OK|ONLINE|REPORT)(?:\]|\b)|$)',
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            section_lines = [
                re.sub(r'\s+', ' ', line).strip()
                for line in _clean_display_text(match.group(1)).splitlines()
                if re.sub(r'\s+', ' ', line).strip()
            ]

    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    patterns = (
        r'^(?P<label>.+?)\s*[-:–—]\s*(?P<value>\d+(?:\.\d+)?)\s*%(?:\s*battery)?(?:\s|$)',
        r'^(?P<label>.+?)\s+(?:battery\s*)?(?P<value>\d+(?:\.\d+)?)\s*%(?:\s|$)',
        r'^(?P<value>\d+(?:\.\d+)?)\s*%(?:\s*battery)?\s*[-:–—]\s*(?P<label>.+)$',
    )

    for line in section_lines:
        cleaned = re.sub(r'^[\s•●▪◦*\-–—]+', '', line).strip()
        cleaned = cleaned.replace('🪫', '').replace('🔋', '').strip()
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if not match:
                continue

            label = re.sub(r'\s+', ' ', match.group('label')).strip(' -:–—')
            label = re.sub(
                r'^(?:low\s+batter(?:y|ies)|battery)\s*[:\-]?\s*',
                '',
                label,
                flags=re.IGNORECASE,
            ).strip()

            key = _normalise_key(label)
            if not key or key in seen:
                break

            seen.add(key)
            items.append({
                'label': label,
                'battery': float(match.group('value')),
                'source': 'Device Status Report',
                'sources': ['Device Status Report'],
            })
            break

    return sorted(items, key=lambda item: (item['battery'], item['label'].lower()))



def _battery_refresh_candidate(device: dict[str, Any]) -> bool:
    attrs = _attrs(device)
    battery_names = {'battery', 'batterylevel', 'battery_level', 'batterypercent'}

    if device.get('battery') not in (None, ''):
        return True
    if any(_normalise_key(key) in battery_names for key in attrs):
        return True

    capabilities = ' '.join(
        str(value.get('name') if isinstance(value, dict) else value)
        for value in (device.get('capabilities') or [])
    ).lower()
    if 'battery' in capabilities:
        return True

    text = _device_text(device)
    terms = (
        'trv', 'thermostat', 'radiator', 'heating', 'contact', 'motion',
        'remote', 'button', 'sensor', 'door', 'window', 'lock', 'valve',
        'smoke', 'temperature', 'humidity', 'presence', 'leak', 'water',
        'switchbot', 'aqara', 'zigbee',
    )
    return any(term in text for term in terms)



def authoritative_low_batteries(
    app_module: Any,
    refresh_live: bool = True,
) -> list[dict[str, Any]]:
    now = time.time()
    cached_result = getattr(app_module, '_homebrain_low_battery_cache', None)
    if not refresh_live and isinstance(cached_result, dict):
        age = now - float(cached_result.get('at') or 0)
        ttl = float(cached_result.get('ttl') or 0)
        rows = cached_result.get('rows')
        if age >= 0 and age < ttl and isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, dict)]

    config = getattr(app_module, 'CONFIG', None)
    config = config if isinstance(config, dict) else {}

    try:
        threshold = float(config.get('low_battery_threshold', 20))
    except Exception:
        threshold = 20.0

    merged: dict[str, dict[str, Any]] = {}

    def battery_value(device: dict[str, Any]) -> float | None:
        attrs = _attrs(device)
        candidates = (
            device.get('battery'),
            attrs.get('battery'),
            attrs.get('batteryLevel'),
            attrs.get('battery_level'),
            attrs.get('batteryPercent'),
        )
        for value in candidates:
            number = _safe_float(value)
            if number is not None:
                return number
        return None

    def add_item(
        label: Any,
        battery: Any,
        source: str,
        device: dict[str, Any] | None = None,
    ) -> None:
        value = _safe_float(battery)
        clean_label = re.sub(r'\s+', ' ', str(label or '')).strip()
        if not clean_label or value is None or value > threshold:
            return

        key = _normalise_key(clean_label)
        if not key:
            return

        existing = merged.get(key)
        if existing is None:
            existing = {
                'label': clean_label,
                'battery': value,
                'source': source,
                'sources': [source],
            }
            merged[key] = existing
        else:
            if value < float(existing.get('battery') or 101):
                existing['battery'] = value
            sources = list(existing.get('sources') or [existing.get('source')])
            if source not in sources:
                sources.append(source)
            existing['sources'] = [item for item in sources if item]
            if existing.get('source') != 'Device Status Report' and source == 'Device Status Report':
                existing['source'] = source

        if isinstance(device, dict):
            existing['id'] = device.get('id')
            existing['room'] = device.get('room') or 'Unknown'
            existing['category'] = device.get('category')

    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    devices = [item for item in devices if isinstance(item, dict)] if isinstance(devices, list) else []

    report_device = _status_report_device(app_module, refresh=refresh_live)
    report_items: list[dict[str, Any]] = []
    if report_device:
        attrs = _attrs(report_device)
        lowered = {_normalise_key(key): value for key, value in attrs.items()}
        report = None
        for name in (
            'reportHtml', 'report_html', 'reportText', 'report_text',
            'currentReport', 'deviceStatusReport', 'statusSummary',
            'overallStatus', 'report', 'html',
        ):
            value = lowered.get(_normalise_key(name))
            if value not in (None, ''):
                report = value
                break

        report_items = _extract_low_battery_report(report)
        for item in report_items:
            add_item(item.get('label'), item.get('battery'), 'Device Status Report')

    # Include every low value already present in the normal Maker API cache.
    for device in devices:
        add_item(
            _device_label(device),
            battery_value(device),
            'cached Maker API',
            device,
        )

    updater = getattr(app_module, 'update_cached_device_snapshot', None)

    # Attach IDs/rooms to report rows even when the cached battery value is missing,
    # and copy the authoritative value into the normal device cache so every
    # dashboard/room consumer sees the same battery state.
    for device in devices:
        key = _normalise_key(_device_label(device))
        if key in merged:
            merged[key]['id'] = device.get('id')
            merged[key]['room'] = device.get('room') or 'Unknown'
            merged[key]['category'] = device.get('category')
            if 'Device Status Report' in (merged[key].get('sources') or []):
                cache_device = dict(device)
                cache_device['battery'] = merged[key]['battery']
                cache_attrs = dict(_attrs(cache_device))
                cache_attrs['battery'] = merged[key]['battery']
                cache_device['attributes'] = cache_attrs
                if callable(updater):
                    try:
                        updater(cache_device)
                    except Exception:
                        pass

    # A populated Device Status Report is authoritative and avoids dozens of
    # serial Maker API calls. Detail sampling is only a fallback when no report
    # payload is available.
    if refresh_live and not report_items:
        try:
            limit = min(12, max(1, int(config.get('battery_detail_refresh_limit', 8))))
        except Exception:
            limit = 8

        def candidate_priority(device: dict[str, Any]) -> tuple[Any, ...]:
            text = _device_text(device)
            capabilities = ' '.join(
                str(value.get('name') if isinstance(value, dict) else value)
                for value in (device.get('capabilities') or [])
            ).lower()
            important = any(
                term in text
                for term in (
                    'trv', 'thermostat', 'radiator', 'lock', 'smoke',
                    'door', 'window', 'contact', 'remote', 'button',
                )
            )
            has_battery_capability = 'battery' in capabilities
            cached = battery_value(device)
            return (
                0 if important else 1,
                0 if has_battery_capability else 1,
                0 if cached is not None else 1,
                cached if cached is not None else 101,
                _device_label(device).lower(),
            )

        candidates = [
            device for device in devices
            if _battery_refresh_candidate(device)
        ]
        candidates.sort(key=candidate_priority)

        cursor = int(getattr(app_module, '_homebrain_low_battery_cursor', 0) or 0)
        if candidates:
            cursor %= len(candidates)
        ordered = candidates[cursor:] + candidates[:cursor]
        selected = ordered[:limit]
        try:
            setattr(app_module, '_homebrain_low_battery_cursor', (cursor + len(selected)) % max(1, len(candidates)))
        except Exception:
            pass

        for device in selected:
            refreshed = _refresh_device_detail(app_module, device)
            value = battery_value(refreshed)
            if value is None:
                continue

            if value <= threshold:
                add_item(
                    _device_label(refreshed),
                    value,
                    'live Maker API',
                    refreshed,
                )

            if callable(updater):
                cache_device = dict(refreshed)
                cache_device['battery'] = value
                cache_attrs = dict(_attrs(cache_device))
                cache_attrs['battery'] = value
                cache_device['attributes'] = cache_attrs
                try:
                    updater(cache_device)
                except Exception:
                    pass

    rows = sorted(
        merged.values(),
        key=lambda item: (float(item.get('battery') or 101), str(item.get('label') or '').lower()),
    )

    cache_payload = {
        'at': now,
        'ttl': 300,
        'rows': [dict(item) for item in rows],
    }
    try:
        setattr(app_module, '_homebrain_low_battery_cache', cache_payload)
    except Exception:
        pass

    return rows


def authoritative_low_battery_answer(app_module: Any, query: str, refresh_live: bool = True) -> dict[str, Any] | None:
    q = _normalise(query)
    if not (
        ('battery' in q or 'batteries' in q)
        and any(term in q for term in ('low', 'which', 'need replacing', 'replace', 'status'))
    ):
        return None

    rows = authoritative_low_batteries(app_module, refresh_live=refresh_live)
    if not rows:
        message = 'No low-battery devices are currently reported.'
        sources: list[str] = []
    else:
        message = 'Low battery devices:\n' + '\n'.join(
            f"- {item['label']}: {item['battery']:g}%"
            for item in rows
        )
        sources = []
        for item in rows:
            for source in item.get('sources') or [item.get('source')]:
                if source and source not in sources:
                    sources.append(source)

        source_labels = {
            'Device Status Report': 'Hubitat Device Status Report',
            'cached Maker API': 'cached Maker API device states',
            'live Maker API': 'live Maker API device details',
        }
        if sources:
            message += '\nSource: ' + ', '.join(
                source_labels.get(item, item)
                for item in sources
            ) + '.'

    # Live detail reads above update HomeBrain's device cache. Rebuild the
    # dashboard summary immediately so the low-battery tile uses those values
    # instead of waiting for a later event or scheduled refresh.
    dashboard = None
    rebuild_error = None
    rebuilder = getattr(app_module, 'rebuild_summary_cache', None)
    if callable(rebuilder):
        try:
            dashboard = rebuilder('low-battery-answer')
        except TypeError:
            try:
                dashboard = rebuilder()
            except Exception as exc:
                rebuild_error = str(exc)
        except Exception as exc:
            rebuild_error = str(exc)

    config = getattr(app_module, 'CONFIG', None)
    config = config if isinstance(config, dict) else {}
    try:
        threshold = float(config.get('low_battery_threshold', 20))
    except Exception:
        threshold = 20.0

    return {
        'success': True,
        'intent': 'low_batteries',
        'message': message,
        'low_batteries': rows,
        'count': len(rows),
        'source': ', '.join(sources) if sources else None,
        'sources': sources,
        'threshold': threshold,
        'dashboard': dashboard if isinstance(dashboard, dict) else None,
        'dashboard_refresh_error': rebuild_error,
    }




def _patch_people_summary_value(value: Any, result: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        patched = dict(value)
        for key in ('count', 'home_count', 'people_home_count'):
            if key in patched:
                patched[key] = result['count']
        for key in ('total', 'people_total'):
            if key in patched:
                patched[key] = result['total']
        for key in ('names', 'home', 'people_home'):
            if key in patched:
                patched[key] = result['home']
        return patched
    if isinstance(value, list):
        return result['home']
    if isinstance(value, int):
        return result['count']
    if isinstance(value, str):
        return ', '.join(result['home'])
    return value


def wrap_dashboard_low_batteries(app_module: Any) -> None:
    existing = getattr(app_module, 'dashboard_summary', None)
    if not callable(existing) or getattr(existing, '_homebrain_low_battery_fixed', False):
        return

    def dashboard_with_authoritative_low_batteries(*args: Any, **kwargs: Any) -> Any:
        # Low-battery enrichment is useful, but it must never take the whole
        # dashboard API offline. Preserve the original summary on any error.
        summary = existing(*args, **kwargs)
        if not isinstance(summary, dict):
            return summary

        try:
            rows = authoritative_low_batteries(app_module, refresh_live=False)
        except Exception as exc:
            try:
                setattr(app_module, '_homebrain_low_battery_last_error', str(exc))
            except Exception:
                pass
            return summary

        # Keep the original dashboard values until the authoritative source
        # returns at least one row. This avoids replacing a valid cached count
        # with zero during startup or temporary Hubitat/report unavailability.
        if not rows:
            return summary

        patched = dict(summary)
        patched['low_batteries'] = len(rows)
        patched['low_battery_devices'] = [
            {
                'id': item.get('id'),
                'label': item.get('label'),
                'room': item.get('room') or 'Unknown',
                'battery': item.get('battery'),
                'source': item.get('source'),
            }
            for item in rows
        ]
        patched['low_battery_sources'] = sorted({
            source
            for item in rows
            for source in (item.get('sources') or [item.get('source')])
            if source
        })
        return patched

    dashboard_with_authoritative_low_batteries._homebrain_low_battery_fixed = True  # type: ignore[attr-defined]
    app_module.dashboard_summary = dashboard_with_authoritative_low_batteries


def wrap_dashboard_presence(app_module: Any) -> None:
    existing = getattr(app_module, 'dashboard_summary', None)
    if not callable(existing) or getattr(existing, '_homebrain_presence_fixed', False):
        return

    def dashboard_with_authoritative_presence(*args: Any, **kwargs: Any) -> Any:
        summary = existing(*args, **kwargs)
        if not isinstance(summary, dict):
            return summary
        result = authoritative_people_home(app_module)
        patched = dict(summary)

        for key in ('people_home', 'home_people', 'people_home_names', 'home_count'):
            if key in patched:
                patched[key] = _patch_people_summary_value(patched[key], result)

        for key in ('people', 'occupancy', 'presence'):
            if key in patched:
                patched[key] = _patch_people_summary_value(patched[key], result)

        # Add explicit fields without disturbing existing consumers.
        patched['authoritative_people_home'] = result['home']
        patched['authoritative_people_home_count'] = result['count']
        patched['authoritative_people_total'] = result['total']
        return patched

    dashboard_with_authoritative_presence._homebrain_presence_fixed = True  # type: ignore[attr-defined]
    app_module.dashboard_summary = dashboard_with_authoritative_presence

def build_home_context(app_module: Any) -> dict[str, Any]:
    summary = _safe_call(getattr(app_module, 'dashboard_summary', None), live=False, fallback={})
    summary = summary if isinstance(summary, dict) else {}
    health = _safe_call(getattr(app_module, 'home_health_answer', None), fallback={})
    health = health if isinstance(health, dict) else {}
    energy = _safe_call(getattr(app_module, 'energy_advisor_answer', None), fallback={})
    energy = energy if isinstance(energy, dict) else {}
    return {'success': True, 'intent': 'home_context', 'version': app_version(app_module), 'generated_at': int(time.time()), 'dashboard': summary, 'occupancy': summary.get('occupancy') or summary.get('people') or {}, 'lights': summary.get('lights') or {}, 'rooms': summary.get('rooms') or [], 'energy': energy, 'health': health, 'timeline': _safe_call(getattr(app_module, 'recent_home_timeline', None), 12, 12, fallback=[]), 'recommendations': _safe_call(getattr(app_module, 'recommendations_answer', None), fallback={}), 'top_power_consumers': _top_power_consumers(app_module)}


def build_briefing(app_module: Any) -> dict[str, Any]:
    briefing = _safe_call(getattr(app_module, 'daily_briefing_answer', None), fallback={})
    briefing = briefing if isinstance(briefing, dict) else {}
    briefing.setdefault('success', True); briefing.setdefault('intent', 'briefing'); briefing.setdefault('version', app_version(app_module)); briefing['alias_for'] = '/api/daily-briefing'
    if briefing.get('message'):
        briefing['message'] = naturalise_units(briefing['message'])
    return briefing


def build_home_health_score(app_module: Any) -> dict[str, Any]:
    health = _safe_call(getattr(app_module, 'home_health_answer', None), fallback={})
    health = health if isinstance(health, dict) else {}
    score = health.get('score') or health.get('health_score') or (100 if health.get('success') else 0)
    return {'success': True, 'intent': 'home_health_score', 'version': app_version(app_module), 'score': score, 'message': naturalise_units(health.get('message') or health.get('speech') or 'Home health score is available.'), 'deductions': health.get('deductions') or health.get('issues') or [], 'health': health}


def build_intelligence_answer(app_module: Any, query: str = '') -> dict[str, Any]:
    intent = _intent(query)
    if intent == 'energy':
        answer = _safe_call(getattr(app_module, 'energy_advisor_answer', None), fallback={})
        if _is_period_energy_query(query, 'today'):
            return {'success': True, 'intent': 'energy_today', 'query': query, 'message': _period_energy_message(answer, 'today', app_module), 'answer': answer, 'period_only': True}
        if _is_period_energy_query(query, 'yesterday'):
            return {'success': True, 'intent': 'energy_yesterday', 'query': query, 'message': _period_energy_message(answer, 'yesterday', app_module), 'answer': answer, 'period_only': True}
        if _is_energy_compare_query(query):
            return {'success': True, 'intent': 'energy_compare', 'query': query, 'message': _energy_compare_message(answer, app_module), 'answer': answer}
        if _is_energy_now_query(query):
            return {'success': True, 'intent': 'energy_now', 'query': query, 'message': _energy_now_message(answer, app_module), 'answer': answer, 'top_power_consumers': _top_power_consumers(app_module)}
        return {'success': True, 'intent': intent, 'query': query, 'message': naturalise_units(_answer_message(answer, 'Energy information is not available yet.')), 'answer': answer, 'top_power_consumers': _top_power_consumers(app_module)}
    if intent == 'why_lights':
        lights = _current_lights_on(app_module); names = ', '.join(_device_label(device) for device in lights)
        message = f"{len(lights)} light{' is' if len(lights) == 1 else 's are'} on because these devices currently report as on: {names}." if lights else 'I cannot see any lights currently reporting as on. If the dashboard still shows lights on, run a live refresh from Hubitat.'
        return {'success': True, 'intent': intent, 'query': query, 'message': message, 'lights_on': [_device_label(device) for device in lights]}
    if intent == 'light_hours':
        delegate = getattr(app_module, 'light_hours_answer', None) or getattr(app_module, 'state_duration_answer', None)
        delegated = _safe_call(delegate, query, fallback=None) if delegate else None
        if isinstance(delegated, dict) and delegated.get('message'):
            return {'success': True, 'intent': intent, 'query': query, 'message': naturalise_units(delegated['message']), 'answer': delegated}
        history = _light_hours_history_answer(app_module, query)
        if isinstance(history, dict) and history.get('message'):
            return history | {'query': query}
        lights = _current_lights_on(app_module); names = ', '.join(_device_label(device) for device in lights[:8]) or 'none currently on'
        return {'success': True, 'intent': intent, 'query': query, 'message': 'I can see which lights are currently on, but exact light-hours need event history. Currently on: ' + names + '.', 'lights_on': [_device_label(device) for device in lights]}
    if intent == 'attention':
        health = build_home_health_score(app_module); recs = _safe_call(getattr(app_module, 'recommendations_answer', None), fallback={}); rec_msg = _answer_message(recs, '')
        return {'success': True, 'intent': intent, 'query': query, 'message': naturalise_units(health['message'] + (f"\n{rec_msg}" if rec_msg else '')), 'health': health, 'recommendations': recs}
    if intent == 'health':
        return build_home_health_score(app_module) | {'query': query}
    if intent == 'briefing':
        return build_briefing(app_module) | {'query': query}
    return build_home_context(app_module) | {'query': query, 'message': 'Home context is ready.'}


def wrap_assistant(app_module: Any) -> None:
    existing = getattr(app_module, 'assistant', None)
    if not callable(existing) or getattr(existing, '_homebrain_local_first', False):
        return
    def local_first_assistant(query: str) -> dict[str, Any]:
        family_answer = authoritative_family_answer(app_module, query)
        if family_answer:
            family_answer['local_first'] = True
            return family_answer
        battery_answer = authoritative_low_battery_answer(app_module, query, refresh_live=False)
        if battery_answer:
            battery_answer['local_first'] = True
            return battery_answer
        hub_answer = hub_cpu_advisor_answer(app_module, query)
        if hub_answer:
            hub_answer['local_first'] = True
            return hub_answer
        weather_answer = improved_weather_answer(app_module, query)
        if weather_answer:
            weather_answer['local_first'] = True
            return weather_answer
        route = classify_intent(query)
        if route.intent == 'room_status':
            room_answer = _room_status_answer(app_module, query)
            if room_answer:
                room_answer.setdefault('success', True)
                room_answer['local_first'] = True
                return room_answer
        voice_command = _voice_dehumidifier_command(app_module, query)
        if voice_command:
            voice_command.setdefault('success', True)
            voice_command['local_first'] = True
            return voice_command
        room_status = _room_status_answer(app_module, query)
        if room_status:
            room_status.setdefault('success', True)
            room_status['local_first'] = True
            return room_status
        if _delegate_main_assistant_first(query):
            return existing(query)
        if should_answer_locally(query):
            answer = build_intelligence_answer(app_module, query); answer.setdefault('success', True); answer['local_first'] = True; return answer
        return existing(query)
    local_first_assistant._homebrain_local_first = True  # type: ignore[attr-defined]
    app_module.assistant = local_first_assistant


def register(app_module: Any) -> Any:
    wrap_dashboard_presence(app_module)
    wrap_dashboard_low_batteries(app_module)
    app_module.refresh_authoritative_low_batteries = lambda: authoritative_low_batteries(app_module, refresh_live=True)
    app_module._homebrain_weather_query_answer = lambda query: improved_weather_answer(app_module, query)
    app = app_module.app; app.version = app_version(app_module); wrap_assistant(app_module)
    if not _route_exists(app, '/api/home-context'):
        app.add_api_route('/api/home-context', lambda: build_home_context(app_module), methods=['GET'])
    if not _route_exists(app, '/api/briefing'):
        app.add_api_route('/api/briefing', lambda: build_briefing(app_module), methods=['GET'])
    if not _route_exists(app, '/api/home-health-score'):
        app.add_api_route('/api/home-health-score', lambda: build_home_health_score(app_module), methods=['GET'])
    if not _route_exists(app, '/api/insight'):
        app.add_api_route('/api/insight', lambda q='': build_intelligence_answer(app_module, q), methods=['GET'])
    if not _route_exists(app, '/api/why'):
        app.add_api_route('/api/why', lambda q='': build_intelligence_answer(app_module, q or 'why'), methods=['GET'])
    return app
