from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Callable

VERSION = '1.9.7-alpha'
LOCAL_FIRST_INTENTS = {'energy', 'why_lights', 'light_hours', 'attention', 'health', 'briefing'}
COMMAND_PREFIXES = ('turn on', 'turn off', 'switch on', 'switch off', 'set ', 'change ', 'adjust ', 'dim ', 'brighten ', 'increase ', 'decrease ', 'raise ', 'lower ', 'keep ', 'leave ', 'refresh', 'reload', 'clear cache', 'cancel timer', 'schedule ')
NUMBER_WORDS = {'one': '1', 'two': '2', 'too': '2', 'to': '2', 'three': '3', 'four': '4'}


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
    return ' '.join(str(part or '') for part in [device.get('label'), device.get('name'), device.get('room'), device.get('category'), ' '.join(device.get('capabilities') or []), ' '.join(attrs.keys())]).lower()


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
    q = _normalise(query)
    if not q:
        return 'briefing'
    if any(term in q for term in ('heating status', 'heating state', 'heat status', 'thermostat status')):
        return 'home_context'
    if any(word in q for word in ('electric', 'energy', 'power', 'cost', 'spent', 'kwh', 'kilowatt')):
        return 'energy'
    if 'today' in q and 'yesterday' in q and any(word in q for word in ('compare', 'comparison', 'versus', 'vs')):
        return 'energy'
    if 'light' in q and any(word in q for word in ('why', 'because', 'reason')):
        return 'why_lights'
    if 'light' in q and any(word in q for word in ('hour', 'hours', 'time', 'long', 'today', 'yesterday', 'duration')):
        return 'light_hours'
    if any(word in q for word in ('unusual', 'attention', 'problem', 'issue', 'wrong')):
        return 'attention'
    if any(word in q for word in ('health', 'cpu', 'memory', 'load')):
        return 'health'
    if any(word in q for word in ('briefing', 'happening', 'status', 'summary')):
        return 'briefing'
    return 'home_context'


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


def _room_status_answer(app_module: Any, query: str) -> dict[str, Any] | None:
    delegate = getattr(app_module, 'room_status_answer', None)
    answer = _safe_call(delegate, query, fallback=None) if callable(delegate) else None
    if isinstance(answer, dict) and answer.get('message'):
        answer = dict(answer)
        answer['message'] = naturalise_units(answer['message'])
        answer.setdefault('intent', 'room_status')
        return answer
    return None


def _delegate_main_assistant_first(query: str) -> bool:
    q = _normalise(query)
    return any(term in q for term in (
        'heating status',
        'heating state',
        'heat status',
        'thermostat status',
        'which batteries are low',
        'what batteries are low',
        'low batteries',
    ))


def build_home_context(app_module: Any) -> dict[str, Any]:
    summary = _safe_call(getattr(app_module, 'dashboard_summary', None), live=False, fallback={})
    summary = summary if isinstance(summary, dict) else {}
    health = _safe_call(getattr(app_module, 'home_health_answer', None), fallback={})
    health = health if isinstance(health, dict) else {}
    energy = _safe_call(getattr(app_module, 'energy_advisor_answer', None), fallback={})
    energy = energy if isinstance(energy, dict) else {}
    return {'success': True, 'intent': 'home_context', 'version': VERSION, 'generated_at': int(time.time()), 'dashboard': summary, 'occupancy': summary.get('occupancy') or summary.get('people') or {}, 'lights': summary.get('lights') or {}, 'rooms': summary.get('rooms') or [], 'energy': energy, 'health': health, 'timeline': _safe_call(getattr(app_module, 'recent_home_timeline', None), 12, 12, fallback=[]), 'recommendations': _safe_call(getattr(app_module, 'recommendations_answer', None), fallback={}), 'top_power_consumers': _top_power_consumers(app_module)}


def build_briefing(app_module: Any) -> dict[str, Any]:
    briefing = _safe_call(getattr(app_module, 'daily_briefing_answer', None), fallback={})
    briefing = briefing if isinstance(briefing, dict) else {}
    briefing.setdefault('success', True); briefing.setdefault('intent', 'briefing'); briefing.setdefault('version', VERSION); briefing['alias_for'] = '/api/daily-briefing'
    if briefing.get('message'):
        briefing['message'] = naturalise_units(briefing['message'])
    return briefing


def build_home_health_score(app_module: Any) -> dict[str, Any]:
    health = _safe_call(getattr(app_module, 'home_health_answer', None), fallback={})
    health = health if isinstance(health, dict) else {}
    score = health.get('score') or health.get('health_score') or (100 if health.get('success') else 0)
    return {'success': True, 'intent': 'home_health_score', 'version': VERSION, 'score': score, 'message': naturalise_units(health.get('message') or health.get('speech') or 'Home health score is available.'), 'deductions': health.get('deductions') or health.get('issues') or [], 'health': health}


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
    app_module.APP_VERSION = VERSION
    app = app_module.app; app.version = VERSION; wrap_assistant(app_module)
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
