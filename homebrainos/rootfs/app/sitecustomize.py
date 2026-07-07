"""HomeBrain OS v1.5 natural intelligence extension.

This module is imported automatically by Python when /app is on sys.path.  It
keeps Sprint 1 changes isolated from the large main.py file while adding safer,
more natural responses and extra briefing/health endpoints.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from typing import Any, Callable

_PATCHED = False


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace('%', '').replace('£', '').strip())
    except Exception:
        return None


def _normalise(text: Any) -> str:
    return re.sub(r'\s+', ' ', str(text or '').strip().lower())


def _fmt_power(value: Any) -> str:
    watts = _safe_float(value)
    if watts is None:
        return 'unknown power'
    if abs(watts) >= 1000:
        return f'{watts / 1000:.1f} kilowatts'
    rounded = round(watts)
    return f'{rounded} watt' + ('' if rounded == 1 else 's')


def _fmt_kwh(value: Any) -> str:
    kwh = _safe_float(value)
    if kwh is None:
        return 'not available'
    return f'{kwh:.2f} kilowatt-hours'


def _fmt_money(value: Any) -> str:
    money = _safe_float(value)
    if money is None:
        return 'not available'
    return f'£{money:.2f}'


def _fmt_count(noun: str, count: int) -> str:
    return f'{count} {noun}' + ('' if count == 1 else 's')


def _set_route(app: Any, path: str, endpoint: Callable[..., Any], methods: set[str] | None = None) -> bool:
    changed = False
    for route in getattr(app, 'routes', []):
        if getattr(route, 'path', None) != path:
            continue
        route_methods = set(getattr(route, 'methods', []) or [])
        if methods and not (route_methods & methods):
            continue
        route.endpoint = endpoint
        route.name = getattr(endpoint, '__name__', route.name)
        try:
            from starlette.routing import request_response
            route.app = request_response(endpoint)
        except Exception:
            pass
        changed = True
    return changed


def _top_current_consumers(main: Any, limit: int = 5) -> list[dict[str, Any]]:
    devices = []
    for device in main.all_devices():
        power = _safe_float(device.get('power'))
        if power is None or power <= 1:
            continue
        devices.append({
            'id': device.get('id'),
            'label': device.get('label') or device.get('name') or str(device.get('id')),
            'room': device.get('room') or 'Unknown',
            'power': power,
            'power_display': _fmt_power(power),
            'switch': device.get('switch'),
        })
    devices.sort(key=lambda item: item['power'], reverse=True)
    return devices[:limit]


def _energy_recommendation(consumers: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
    if candidates:
        first = candidates[0]
        label = first.get('label', 'the top device')
        reason = first.get('reason', 'it may be wasting energy')
        return f'Check {label} first - {reason}.'
    if consumers:
        first = consumers[0]
        if first.get('power', 0) >= 1000:
            return f'{first["label"]} is using {_fmt_power(first["power"])} now; check whether it needs to stay on.'
        return f'The biggest live load is {first["label"]} at {_fmt_power(first["power"])}.'
    return 'No obvious action needed from the live energy data right now.'


def _usage_comparison(usage: dict[str, Any]) -> str | None:
    today = usage.get('today') or {}
    yesterday = usage.get('yesterday') or {}
    today_kwh = _safe_float(today.get('kwh'))
    y_kwh = _safe_float(yesterday.get('kwh'))
    today_cost = _safe_float(today.get('cost_gbp'))
    y_cost = _safe_float(yesterday.get('cost_gbp'))
    if today_kwh is None or y_kwh is None:
        return None
    diff = today_kwh - y_kwh
    direction = 'higher than' if diff > 0 else 'lower than' if diff < 0 else 'the same as'
    cost_bit = ''
    if today_cost is not None and y_cost is not None:
        cost_bit = f' Cost is {_fmt_money(today_cost)} today vs {_fmt_money(y_cost)} yesterday.'
    return f'Today is {abs(diff):.2f} kilowatt-hours {direction} yesterday so far.{cost_bit}'


def natural_energy_advisor(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    usage = main.energy_usage_from_meter()
    candidates = main.energy_waste_candidates()
    consumers = _top_current_consumers(main, 6)
    lines = [
        'Energy advisor',
        f"Right now the home is using {_fmt_power(summary.get('power_total'))} from {summary.get('power_source_label', 'the energy meter')}.",
    ]
    if usage.get('available'):
        today = usage.get('today') or {}
        yesterday = usage.get('yesterday') or {}
        lines.append(f"Used today so far: {_fmt_kwh(today.get('kwh'))}, {_fmt_money(today.get('cost_gbp'))}.")
        lines.append(f"Used yesterday: {_fmt_kwh(yesterday.get('kwh'))}, {_fmt_money(yesterday.get('cost_gbp'))}.")
        comparison = _usage_comparison(usage)
        if comparison:
            lines.append(comparison)
    else:
        lines.append('Energy totals are not available yet because I could not find the Octopus or whole-house meter.')
    if consumers:
        lines.append('Largest current consumers:')
        lines.extend(f"- {item['label']} ({item['room']}) - {item['power_display']}" for item in consumers[:5])
    else:
        lines.append('No live power consumers above 1 watt are currently visible.')
    lines.append('Recommendation: ' + _energy_recommendation(consumers, candidates))
    return {
        'success': True,
        'intent': 'energy_advisor',
        'message': '\n'.join(lines),
        'speech': ' '.join(line.lstrip('- ') for line in lines[:5]),
        'summary': summary,
        'usage': usage,
        'current_consumers': consumers,
        'candidates': candidates,
        'formatter': 'v1.5-natural',
    }


def natural_home_health(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    diagnostics = main.device_diagnostics()
    stale = main.stale_device_report()
    deductions: list[str] = []
    low_battery = int(summary.get('low_batteries') or 0)
    if low_battery:
        deductions.append(f'{low_battery} low-battery device' + ('' if low_battery == 1 else 's'))
    not_reporting = len(stale.get('not_reporting') or [])
    if not_reporting:
        deductions.append(f'{not_reporting} device' + ('' if not_reporting == 1 else 's') + ' not reporting normally')
    unknown_rooms = int(diagnostics.get('unknown_room') or 0)
    if unknown_rooms:
        deductions.append(f'{unknown_rooms} device' + ('' if unknown_rooms == 1 else 's') + ' without a clear room')
    if diagnostics.get('last_error'):
        deductions.append('last Hubitat refresh has an error')
    score = max(0, 100 - low_battery * 5 - not_reporting * 8 - unknown_rooms * 2 - (10 if diagnostics.get('last_error') else 0))
    lines = ['Home health', f'Overall health score: {score}/100.']
    if deductions:
        lines.append('Main deductions:')
        lines.extend('- ' + item for item in deductions[:8])
    else:
        lines.append('No major health deductions found.')
    if stale.get('not_reporting'):
        lines.append('Devices to check first:')
        lines.extend(f"- {item.get('label')} - {item.get('duration')}" for item in stale['not_reporting'][:5])
    rec = 'Replace low batteries first.' if low_battery else 'Keep monitoring event stream and stale devices.' if not_reporting else 'No immediate action needed.'
    lines.append('Recommendation: ' + rec)
    return {'success': True, 'intent': 'home_health', 'message': '\n'.join(lines), 'score': score, 'deductions': deductions, 'summary': summary, 'diagnostics': diagnostics, 'stale': stale, 'formatter': 'v1.5-natural'}


def natural_daily_briefing(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    energy = natural_energy_advisor(main)
    health = natural_home_health(main)
    people = summary.get('people_home_names') or []
    occupancy = ', '.join(people) if people else 'No tracked family members home'
    alerts: list[str] = []
    if summary.get('low_batteries'):
        alerts.append(f"{summary.get('low_batteries')} low batteries")
    stale = health.get('stale') or {}
    if stale.get('not_reporting'):
        alerts.append(f"{len(stale['not_reporting'])} devices not reporting normally")
    if not alerts:
        alerts.append('No urgent alerts')
    today = energy.get('usage', {}).get('today') or {}
    today_energy = f"{_fmt_kwh(today.get('kwh'))}, {_fmt_money(today.get('cost_gbp'))}" if today else 'daily total not available yet'
    recommendation = energy.get('message', '').split('Recommendation: ')[-1].split('\n')[0] if 'Recommendation: ' in energy.get('message', '') else 'Check Home Health if anything looks wrong.'
    lines = [
        'Daily briefing',
        f'Occupancy: {occupancy}.',
        f"Lights on: {_fmt_count('light', int(summary.get('lights_on') or 0))}.",
        f"Energy today: {_fmt_power(summary.get('power_total'))} right now; {today_energy}.",
        'Alerts: ' + '; '.join(alerts[:3]) + '.',
        'Recommendation: ' + recommendation,
    ]
    return {'success': True, 'intent': 'daily_briefing', 'message': '\n'.join(lines), 'summary': summary, 'energy': energy, 'health': health, 'alerts': alerts, 'formatter': 'v1.5-natural'}


def natural_home_context(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    health = natural_home_health(main)
    energy = natural_energy_advisor(main)
    rooms = main.api_rooms().get('rooms', [])
    active_rooms = [room for room in rooms if int(room.get('lights_on') or 0) or int(room.get('motion_active') or 0)]
    timeline = main.recent_home_timeline(limit=12, hours=12)
    recommendations = main.recommendations_answer()
    return {
        'success': True,
        'version': getattr(main, 'APP_VERSION', '1.5.0-alpha'),
        'generated_at': int(time.time()),
        'summary': summary,
        'occupancy': {
            'people_home': summary.get('people_home'),
            'people_tracked': summary.get('people_tracked'),
            'people_home_names': summary.get('people_home_names') or [],
            'active_rooms': active_rooms[:10],
        },
        'energy': energy,
        'health': health,
        'alerts': health.get('deductions') or [],
        'recommendations': recommendations.get('recommendations') or [],
        'timeline': timeline,
        'context_source': 'cached-event-state',
    }


def natural_format_endpoint(value: float, kind: str = 'power') -> dict[str, Any]:
    kind = _normalise(kind)
    if kind in ('power', 'w', 'watts'):
        formatted = _fmt_power(value)
    elif kind in ('energy', 'kwh'):
        formatted = _fmt_kwh(value)
    elif kind in ('cost', 'money', 'gbp'):
        formatted = _fmt_money(value)
    else:
        formatted = str(value)
    return {'success': True, 'kind': kind, 'value': value, 'formatted': formatted}


def _spent_today_answer(main: Any) -> dict[str, Any]:
    usage = main.energy_usage_from_meter()
    if not usage.get('available'):
        return {'success': False, 'intent': 'energy_spend_today', 'message': 'I cannot see today energy cost yet because the meter totals are not available.'}
    today = usage.get('today') or {}
    return {'success': True, 'intent': 'energy_spend_today', 'message': f"You have spent {_fmt_money(today.get('cost_gbp'))} on electricity today so far, using {_fmt_kwh(today.get('kwh'))}.", 'usage': usage}


def _anything_unusual_answer(main: Any) -> dict[str, Any]:
    health = natural_home_health(main)
    energy = natural_energy_advisor(main)
    issues = list(health.get('deductions') or [])
    consumers = energy.get('current_consumers') or []
    if consumers and consumers[0].get('power', 0) >= 1000:
        issues.append(f"{consumers[0]['label']} is using {_fmt_power(consumers[0]['power'])}")
    if not issues:
        return {'success': True, 'intent': 'anything_unusual', 'message': 'Nothing unusual stands out right now. Home health and energy usage look normal from the data I can see.'}
    lines = ['Things that look unusual:', *('- ' + item for item in issues[:6])]
    return {'success': True, 'intent': 'anything_unusual', 'message': '\n'.join(lines), 'issues': issues}


def patch(main: Any) -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    app = getattr(main, 'app', None)
    if app is None:
        return False

    main.APP_VERSION = '1.5.0-alpha'
    main.energy_advisor_answer = lambda: natural_energy_advisor(main)
    main.home_health_answer = lambda: natural_home_health(main)
    main.daily_briefing_answer = lambda: natural_daily_briefing(main)
    main.home_context_answer = lambda: natural_home_context(main)

    original_assistant = getattr(main, 'assistant', None)
    if callable(original_assistant):
        def wrapped_assistant(text: str) -> dict[str, Any]:
            t = _normalise(text)
            if 'spent' in t and ('today' in t or 'so far' in t):
                return _spent_today_answer(main)
            if 'how much' in t and ('cost' in t or 'electric' in t or 'energy' in t) and 'today' in t:
                return _spent_today_answer(main)
            if 'anything unusual' in t or 'anything wrong' in t or 'what looks unusual' in t:
                return _anything_unusual_answer(main)
            return original_assistant(text)
        main.assistant = wrapped_assistant

    _set_route(app, '/api/energy-advisor', lambda: natural_energy_advisor(main), {'GET'})
    _set_route(app, '/api/home-health', lambda: natural_home_health(main), {'GET'})
    _set_route(app, '/api/daily-briefing', lambda: natural_daily_briefing(main), {'GET'})
    try:
        app.add_api_route('/api/home-context', lambda: natural_home_context(main), methods=['GET'])
        app.add_api_route('/api/briefing', lambda: natural_daily_briefing(main), methods=['GET'])
        app.add_api_route('/api/home-health-score', lambda: natural_home_health(main), methods=['GET'])
        app.add_api_route('/api/natural-format', natural_format_endpoint, methods=['GET'])
    except Exception:
        pass
    _PATCHED = True
    return True


def _patch_when_ready() -> None:
    for _ in range(200):
        main = sys.modules.get('__main__')
        if main is not None and hasattr(main, 'app') and hasattr(main, 'all_devices'):
            try:
                if patch(main):
                    return
            except Exception:
                return
        time.sleep(0.05)


threading.Thread(target=_patch_when_ready, name='homebrain-v15-patch', daemon=True).start()
