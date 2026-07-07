from __future__ import annotations

import time
from typing import Any, Callable

VERSION = '1.5.0-alpha'


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


def _route_exists(app: Any, path: str) -> bool:
    return any(getattr(route, 'path', None) == path for route in getattr(app, 'routes', []))


def _device_label(device: dict[str, Any]) -> str:
    return str(device.get('label') or device.get('name') or device.get('id') or 'Unknown device')


def _top_power_consumers(app_module: Any, limit: int = 5) -> list[dict[str, Any]]:
    devices = _safe_call(getattr(app_module, 'all_devices', None), fallback=[])
    if not isinstance(devices, list):
        return []
    consumers: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        attrs = device.get('attributes') or {}
        value = attrs.get('power', device.get('power'))
        watts = _safe_float(value)
        if watts is None or watts <= 0:
            continue
        consumers.append({'label': _device_label(device), 'watts': watts, 'power': format_power(watts)})
    consumers.sort(key=lambda item: item['watts'], reverse=True)
    return consumers[:limit]


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
        'message': health.get('message') or health.get('speech') or 'Home health score is available.',
        'deductions': health.get('deductions') or health.get('issues') or [],
        'health': health,
    }


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

    return app
