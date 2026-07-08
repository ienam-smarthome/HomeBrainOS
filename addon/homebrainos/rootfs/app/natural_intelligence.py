from __future__ import annotations

import re
import time
from typing import Any, Callable

VERSION = '1.6.5-alpha'
LOCAL_FIRST_INTENTS = {'energy', 'why_lights', 'light_hours', 'attention', 'health', 'briefing'}
COMMAND_PREFIXES = (
    'turn on', 'turn off', 'switch on', 'switch off', 'set ', 'change ', 'adjust ',
    'dim ', 'brighten ', 'increase ', 'decrease ', 'raise ', 'lower ', 'keep ', 'leave ',
    'refresh', 'reload', 'clear cache', 'cancel timer', 'schedule ',
)


def _safe_call(func: Callable[..., Any] | None, *args: Any, fallback: Any = None, **kwargs: Any) -> Any:
    if func is None:
        return fallback
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        return {'success': False, 'error': str(exc), 'fallback': fallback}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace(',', '').replace('£', '').strip()
            if not cleaned:
                return None
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return None


def format_power(value: Any) -> str:
    watts = _safe_float(value)
    if watts is None:
        return 'not available'
    if watts >= 1000:
        kilowatts = watts / 1000
        return f"{kilowatts:.1f}".rstrip('0').rstrip('.') + ' kilowatts'
    return f"{round(watts):g} watts"


def format_energy(value: Any) -> str:
    kwh = _safe_float(value)
    if kwh is None:
        return 'not available'
    amount = f"{kwh:.1f}".rstrip('0').rstrip('.')
    unit = 'kilowatt-hour' if round(kwh, 1) == 1 else 'kilowatt-hours'
    return f'{amount} {unit}'


def format_money(value: Any) -> str:
    amount = _safe_float(value)
    if amount is None:
        return 'not available'
    return f'£{amount:.2f}'


def _normalise(text: Any) -> str:
    value = str(text or '').lower()
    value = value.replace('bedroom too', 'bedroom 2').replace('bed room too', 'bedroom 2')
    value = value.replace('yeseterday', 'yesterday').replace('kilowatts', 'kilowatt-hours')
    value = re.sub(r'[^a-z0-9£\s.-]', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _normalise_key(text: Any) -> str:
    return re.sub(r'[^a-z0-9]', '', str(text or '').lower())


def naturalise_units(message: Any) -> str:
    text = str(message or '')

    def power_repl(match: re.Match[str]) -> str:
        return format_power(match.group(1))

    def energy_repl(match: re.Match[str]) -> str:
        return format_energy(match.group(1))

    text = re.sub(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*W\b', power_repl, text)
    text = re.sub(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*kWh\b', energy_repl, text, flags=re.IGNORECASE)
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


def _is_light_device(device: dict[str, Any]) -> bool:
    text = ' '.join(str(part or '') for part in [
        device.get('label'), device.get('name'), device.get('room'), device.get('category'),
        ' '.join(device.get('capabilities') or []),
    ]).lower()
    return 'light' in text or 'bulb' in text or device.get('category') == 'light'


def _current_lights_on(app_module: Any) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    lights = []
    for device in devices:
        if not isinstance(device, dict) or not _is_light_device(device):
            continue
        if _is_on(_attrs(device).get('switch')):
            lights.append(device)
    return sorted(lights, key=_device_label)


def _top_power_consumers(app_module: Any, limit: int = 5) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    consumers = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        watts = _safe_float(_attrs(device).get('power'))
        if watts is None or watts <= 0:
            continue
        consumers.append({'label': _device_label(device), 'watts': watts, 'power': format_power(watts)})
    consumers.sort(key=lambda item: item['watts'], reverse=True)
    return consumers[:limit]


def _answer_message(answer: Any, fallback: str = '') -> str:
    if isinstance(answer, dict):
        return str(answer.get('message') or answer.get('speech') or fallback)
    return str(answer or fallback)


def _intent(query: str) -> str:
    q = _normalise(query)
    if not q:
        return 'briefing'
    if any(word in q for word in ('electric', 'energy', 'power', 'cost', 'spent', 'kwh', 'kilowatt')):
        return 'energy'
    if 'today' in q and 'yesterday' in q and any(word in q for word in ('compare', 'comparison', 'versus', 'vs')):
        return 'energy'
    if 'light' in q and any(word in q for word in ('why', 'because', 'reason')):
        return 'why_lights'
    if 'light' in q and any(word in q for word in ('hour', 'hours', 'time', 'long', 'today', 'duration')):
        return 'light_hours'
    if any(word in q for word in ('unusual', 'attention', 'problem', 'issue', 'wrong')):
        return 'attention'
    if any(word in q for word in ('health', 'cpu', 'memory', 'load')):
        return 'health'
    if any(word in q for word in ('briefing', 'happening', 'status', 'summary')):
        return 'briefing'
    return 'home_context'


def _is_command_like(query: str) -> bool:
    q = _normalise(query)
    return any(q.startswith(prefix) for prefix in COMMAND_PREFIXES)


def should_answer_locally(query: str) -> bool:
    if _is_command_like(query):
        return False
    return _intent(query) in LOCAL_FIRST_INTENTS


def _is_period_energy_query(query: str, period: str) -> bool:
    q = _normalise(query)
    if _intent(q) != 'energy' or period not in q:
        return False
    comparison_terms = ('compare', 'comparison', 'versus', 'vs', 'advisor', 'worth checking', 'using now', 'right now', 'currently')
    other_period = 'yesterday' if period == 'today' else 'today'
    if other_period in q or any(term in q for term in comparison_terms):
        return False
    if period == 'today':
        terms = ('used today', 'use today', 'spent today', 'cost today', 'today so far', 'have i used today', 'have we used today')
    else:
        terms = ('used yesterday', 'use yesterday', 'spent yesterday', 'cost yesterday', 'did i use yesterday', 'did we use yesterday')
    return any(term in q for term in terms)


def _is_energy_now_query(query: str) -> bool:
    q = _normalise(query)
    if _intent(q) != 'energy':
        return False
    now_terms = ('now', 'right now', 'currently', 'at the moment', 'using the most', 'highest', 'top')
    return any(term in q for term in now_terms) and any(term in q for term in ('using', 'power', 'electricity', 'watts', 'consumer', 'consuming'))


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
    if not isinstance(devices, list):
        return None
    if period == 'today':
        cost_keys = {'displaycosttoday', 'costtoday', 'todaycost', 'electricitycosttoday'}
    else:
        cost_keys = {'displaycostyesterday', 'costyesterday', 'yesterdaycost', 'electricitycostyesterday'}
    for device in devices:
        if not isinstance(device, dict):
            continue
        label = _device_label(device).lower()
        if 'octopus' not in label and 'live meter' not in label:
            continue
        total = _safe_float(_pick_attr(_attrs(device), cost_keys))
        if total is not None:
            return total
    return None


def _period_line(message: str, period: str) -> tuple[str, str] | None:
    prefix = 'used today' if period == 'today' else 'used yesterday'
    for raw_line in message.splitlines():
        line = raw_line.strip().strip('•').strip()
        if not line.lower().startswith(prefix):
            continue
        detail = line.split(':', 1)[1].strip() if ':' in line else line
        match = re.search(r'(.+?)\s+costing\s+(£?\d+(?:\.\d+)?)', detail, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(), format_money(match.group(2))
        return detail, ''
    return None


def _period_energy_message(answer: Any, period: str, app_module: Any | None = None) -> str:
    message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
    total_cost = _octopus_total_cost(app_module, period) if app_module is not None else None
    found = _period_line(message, period)
    if found is None:
        return message
    usage, energy_cost = found
    intro = 'Today so far you have used' if period == 'today' else 'Yesterday you used'
    if not energy_cost:
        return f'{intro} {usage}.'
    if total_cost is None:
        return f'{intro} {usage}, costing {energy_cost}.'
    if abs(total_cost - (_safe_float(energy_cost) or 0.0)) < 0.01:
        return f'{intro} {usage}, costing {format_money(total_cost)}.'
    return (
        f'{intro} {usage}. '
        f'Energy cost was about {energy_cost}. '
        f'Total cost including standing charge was {format_money(total_cost)}.'
    )


def _energy_compare_message(answer: Any, app_module: Any | None = None) -> str:
    message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
    today = _period_line(message, 'today')
    yesterday = _period_line(message, 'yesterday')
    if today is None or yesterday is None:
        return message
    today_cost = _octopus_total_cost(app_module, 'today') if app_module is not None else None
    yesterday_cost = _octopus_total_cost(app_module, 'yesterday') if app_module is not None else None
    cost_phrase = ''
    if today_cost is not None and yesterday_cost is not None:
        diff = today_cost - yesterday_cost
        if abs(diff) < 0.01:
            cost_phrase = ' Total cost is about the same as yesterday.'
        elif diff > 0:
            cost_phrase = f' Total cost is {format_money(abs(diff))} higher than yesterday.'
        else:
            cost_phrase = f' Total cost is {format_money(abs(diff))} lower than yesterday.'
    return f'Today so far: {today[0]}. Yesterday: {yesterday[0]}.{cost_phrase}'


def _energy_now_message(answer: Any, app_module: Any) -> str:
    message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
    whole_home = None
    for raw_line in message.splitlines():
        line = raw_line.strip()
        if line.lower().startswith('whole-house power now'):
            whole_home = line.split(':', 1)[1].strip() if ':' in line else line
            break
    parts = []
    if whole_home:
        parts.append(f'Whole-house power now is {whole_home}.')
    top = _top_power_consumers(app_module, 5)
    if top:
        device_text = '; '.join(f"{item['label']} is using {item['power']}" for item in top)
        parts.append(f'Top current users: {device_text}.')
    if not parts:
        return 'I cannot see any live power usage right now.'
    return ' '.join(parts)


def build_home_context(app_module: Any) -> dict[str, Any]:
    summary = _safe_call(getattr(app_module, 'dashboard_summary', None), live=False, fallback={})
    if not isinstance(summary, dict):
        summary = {}
    health = _safe_call(getattr(app_module, 'home_health_answer', None), fallback={})
    if not isinstance(health, dict):
        health = {}
    energy = _safe_call(getattr(app_module, 'energy_advisor_answer', None), fallback={})
    if not isinstance(energy, dict):
        energy = {}
    timeline = _safe_call(getattr(app_module, 'recent_home_timeline', None), 12, 12, fallback=[])
    if not isinstance(timeline, list):
        timeline = []
    recommendations = _safe_call(getattr(app_module, 'recommendations_answer', None), fallback={})
    if not isinstance(recommendations, dict):
        recommendations = {}
    return {
        'success': True,
        'intent': 'home_context',
        'version': VERSION,
        'generated_at': int(time.time()),
        'dashboard': summary,
        'occupancy': summary.get('occupancy') or summary.get('people') or {},
        'lights': summary.get('lights') or {},
        'rooms': summary.get('rooms') or [],
        'energy': energy,
        'health': health,
        'timeline': timeline,
        'recommendations': recommendations,
        'top_power_consumers': _top_power_consumers(app_module),
    }


def build_briefing(app_module: Any) -> dict[str, Any]:
    briefing = _safe_call(getattr(app_module, 'daily_briefing_answer', None), fallback={})
    if not isinstance(briefing, dict):
        briefing = {}
    briefing.setdefault('success', True)
    briefing.setdefault('intent', 'briefing')
    briefing.setdefault('version', VERSION)
    briefing['alias_for'] = '/api/daily-briefing'
    if briefing.get('message'):
        briefing['message'] = naturalise_units(briefing['message'])
    return briefing


def build_home_health_score(app_module: Any) -> dict[str, Any]:
    health = _safe_call(getattr(app_module, 'home_health_answer', None), fallback={})
    if not isinstance(health, dict):
        health = {}
    score = health.get('score')
    if score is None:
        score = health.get('health_score')
    if score is None:
        score = 100 if health.get('success') else 0
    return {
        'success': True,
        'intent': 'home_health_score',
        'version': VERSION,
        'score': score,
        'message': naturalise_units(health.get('message') or health.get('speech') or 'Home health score is available.'),
        'deductions': health.get('deductions') or health.get('issues') or [],
        'health': health,
    }


def build_intelligence_answer(app_module: Any, query: str = '') -> dict[str, Any]:
    intent = _intent(query)
    if intent == 'energy':
        answer = _safe_call(getattr(app_module, 'energy_advisor_answer', None), fallback={})
        if _is_period_energy_query(query, 'today'):
            message = _period_energy_message(answer, 'today', app_module)
            return {'success': True, 'intent': 'energy_today', 'query': query, 'message': message, 'answer': answer, 'period_only': True}
        if _is_period_energy_query(query, 'yesterday'):
            message = _period_energy_message(answer, 'yesterday', app_module)
            return {'success': True, 'intent': 'energy_yesterday', 'query': query, 'message': message, 'answer': answer, 'period_only': True}
        if _is_energy_compare_query(query):
            message = _energy_compare_message(answer, app_module)
            return {'success': True, 'intent': 'energy_compare', 'query': query, 'message': message, 'answer': answer}
        if _is_energy_now_query(query):
            message = _energy_now_message(answer, app_module)
            return {'success': True, 'intent': 'energy_now', 'query': query, 'message': message, 'answer': answer, 'top_power_consumers': _top_power_consumers(app_module)}
        message = naturalise_units(_answer_message(answer, 'Energy information is not available yet.'))
        return {'success': True, 'intent': intent, 'query': query, 'message': message, 'answer': answer, 'top_power_consumers': _top_power_consumers(app_module)}

    if intent == 'why_lights':
        lights = _current_lights_on(app_module)
        if lights:
            names = ', '.join(_device_label(device) for device in lights)
            message = f"{len(lights)} light{' is' if len(lights) == 1 else 's are'} on because these devices currently report as on: {names}."
        else:
            message = 'I cannot see any lights currently reporting as on. If the dashboard still shows lights on, run a live refresh from Hubitat.'
        return {'success': True, 'intent': intent, 'query': query, 'message': message, 'lights_on': [_device_label(device) for device in lights]}

    if intent == 'light_hours':
        delegate = getattr(app_module, 'light_hours_answer', None) or getattr(app_module, 'state_duration_answer', None)
        delegated = _safe_call(delegate, query, fallback=None) if delegate else None
        if isinstance(delegated, dict) and delegated.get('message'):
            return {'success': True, 'intent': intent, 'query': query, 'message': naturalise_units(delegated['message']), 'answer': delegated}
        lights = _current_lights_on(app_module)
        names = ', '.join(_device_label(device) for device in lights[:8]) or 'none currently on'
        message = 'I can see which lights are currently on, but exact light-hours need event history. Currently on: ' + names + '.'
        return {'success': True, 'intent': intent, 'query': query, 'message': message, 'lights_on': [_device_label(device) for device in lights]}

    if intent == 'attention':
        health = build_home_health_score(app_module)
        recs = _safe_call(getattr(app_module, 'recommendations_answer', None), fallback={})
        rec_msg = _answer_message(recs, '')
        message = health['message']
        if rec_msg:
            message = f"{message}\n{rec_msg}"
        return {'success': True, 'intent': intent, 'query': query, 'message': naturalise_units(message), 'health': health, 'recommendations': recs}
    if intent == 'health':
        return build_home_health_score(app_module) | {'query': query}
    if intent == 'briefing':
        return build_briefing(app_module) | {'query': query}
    context = build_home_context(app_module)
    lights = context.get('lights') or {}
    occupancy = context.get('occupancy') or {}
    message = 'Home context is ready.'
    if lights or occupancy:
        message = f"Home context is ready. Lights: {lights}. Occupancy: {occupancy}."
    return context | {'query': query, 'message': message}


def wrap_assistant(app_module: Any) -> None:
    existing = getattr(app_module, 'assistant', None)
    if not callable(existing) or getattr(existing, '_homebrain_local_first', False):
        return

    def local_first_assistant(query: str) -> dict[str, Any]:
        if should_answer_locally(query):
            answer = build_intelligence_answer(app_module, query)
            answer.setdefault('success', True)
            answer['local_first'] = True
            return answer
        return existing(query)

    local_first_assistant._homebrain_local_first = True  # type: ignore[attr-defined]
    app_module.assistant = local_first_assistant


def register(app_module: Any) -> Any:
    app_module.APP_VERSION = VERSION
    app = app_module.app
    app.version = VERSION
    wrap_assistant(app_module)
    if not _route_exists(app, '/api/home-context'):
        def api_home_context() -> dict[str, Any]:
            return build_home_context(app_module)
        app.add_api_route('/api/home-context', api_home_context, methods=['GET'])
    if not _route_exists(app, '/api/briefing'):
        def api_briefing() -> dict[str, Any]:
            return build_briefing(app_module)
        app.add_api_route('/api/briefing', api_briefing, methods=['GET'])
    if not _route_exists(app, '/api/home-health-score'):
        def api_home_health_score() -> dict[str, Any]:
            return build_home_health_score(app_module)
        app.add_api_route('/api/home-health-score', api_home_health_score, methods=['GET'])
    if not _route_exists(app, '/api/insight'):
        def api_insight(q: str = '') -> dict[str, Any]:
            return build_intelligence_answer(app_module, q)
        app.add_api_route('/api/insight', api_insight, methods=['GET'])
    if not _route_exists(app, '/api/why'):
        def api_why(q: str = '') -> dict[str, Any]:
            return build_intelligence_answer(app_module, q or 'why')
        app.add_api_route('/api/why', api_why, methods=['GET'])
    return app
