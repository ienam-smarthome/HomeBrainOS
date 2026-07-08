from __future__ import annotations

import re
import time
from typing import Any, Callable

VERSION = '1.6.0-alpha'


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
    lights: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict) or not _is_light_device(device):
            continue
        attrs = _attrs(device)
        if _is_on(attrs.get('switch')):
            lights.append(device)
    return sorted(lights, key=_device_label)


def _top_power_consumers(app_module: Any, limit: int = 5) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    consumers: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        attrs = _attrs(device)
        watts = _safe_float(attrs.get('power'))
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


def register(app_module: Any) -> Any:
    app_module.APP_VERSION = VERSION
    app = app_module.app
    app.version = VERSION

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
