"""HomeBrain OS v1.5 natural intelligence extension."""
from __future__ import annotations

import re
import sys
import threading
import time
from typing import Any

_PATCHED = False


def _num(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value).replace('%', '').replace('GBP', '').strip())
    except Exception:
        return None


def _text(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def natural_power(value: Any) -> str:
    watts = _num(value)
    if watts is None:
        return 'unknown power'
    if abs(watts) >= 1000:
        return f'{watts / 1000:.1f} kilowatts'
    watts_i = round(watts)
    return f'{watts_i} watt' + ('' if watts_i == 1 else 's')


def natural_energy(value: Any) -> str:
    kwh = _num(value)
    return 'not available' if kwh is None else f'{kwh:.2f} kilowatt-hours'


def natural_money(value: Any) -> str:
    amount = _num(value)
    return 'not available' if amount is None else f'GBP {amount:.2f}'


def _top_consumers(main: Any, limit: int = 5) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for device in main.all_devices():
        power = _num(device.get('power'))
        if power is None or power <= 1:
            continue
        items.append({
            'id': device.get('id'),
            'label': device.get('label') or device.get('name') or str(device.get('id')),
            'room': device.get('room') or 'Unknown',
            'power': power,
            'power_display': natural_power(power),
        })
    return sorted(items, key=lambda item: item['power'], reverse=True)[:limit]


def _replace_route(app: Any, path: str, endpoint: Any) -> None:
    for route in getattr(app, 'routes', []):
        if getattr(route, 'path', None) != path:
            continue
        route.endpoint = endpoint
        try:
            from starlette.routing import request_response
            route.app = request_response(endpoint)
        except Exception:
            pass


def _add_route_once(app: Any, path: str, endpoint: Any) -> None:
    if any(getattr(route, 'path', None) == path for route in getattr(app, 'routes', [])):
        return
    app.add_api_route(path, endpoint, methods=['GET'])


def _energy_recommendation(consumers: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
    if candidates:
        first = candidates[0]
        return f"Check {first.get('label', 'the top device')} first - {first.get('reason', 'it may be wasting energy')}."
    if consumers:
        first = consumers[0]
        return f"The biggest live load is {first['label']} at {first['power_display']}."
    return 'No obvious action needed from the live energy data right now.'


def energy_advisor(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    usage = main.energy_usage_from_meter()
    candidates = main.energy_waste_candidates()
    consumers = _top_consumers(main)
    lines = [
        'Energy advisor',
        f"Right now the home is using {natural_power(summary.get('power_total'))} from {summary.get('power_source_label', 'the energy meter')}.",
    ]
    if usage.get('available'):
        today = usage.get('today') or {}
        yesterday = usage.get('yesterday') or {}
        lines.append(f"Used today so far: {natural_energy(today.get('kwh'))}, {natural_money(today.get('cost_gbp'))}.")
        lines.append(f"Used yesterday: {natural_energy(yesterday.get('kwh'))}, {natural_money(yesterday.get('cost_gbp'))}.")
        today_kwh = _num(today.get('kwh'))
        y_kwh = _num(yesterday.get('kwh'))
        if today_kwh is not None and y_kwh is not None:
            direction = 'higher than' if today_kwh > y_kwh else 'lower than' if today_kwh < y_kwh else 'the same as'
            lines.append(f'Today is {abs(today_kwh - y_kwh):.2f} kilowatt-hours {direction} yesterday so far.')
    else:
        lines.append('Energy totals are not available yet because I could not find the Octopus or whole-house meter.')
    if consumers:
        lines.append('Largest current consumers:')
        lines.extend(f"- {item['label']} ({item['room']}) - {item['power_display']}" for item in consumers)
    lines.append('Recommendation: ' + _energy_recommendation(consumers, candidates))
    return {'success': True, 'intent': 'energy_advisor', 'message': '\n'.join(lines), 'usage': usage, 'current_consumers': consumers, 'candidates': candidates, 'formatter': 'v1.5-natural'}


def home_health(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    diagnostics = main.device_diagnostics()
    stale = main.stale_device_report()
    low_battery = int(summary.get('low_batteries') or 0)
    not_reporting = len(stale.get('not_reporting') or [])
    unknown_room = int(diagnostics.get('unknown_room') or 0)
    deductions: list[str] = []
    if low_battery:
        deductions.append(f'{low_battery} low-battery device' + ('' if low_battery == 1 else 's'))
    if not_reporting:
        deductions.append(f'{not_reporting} device' + ('' if not_reporting == 1 else 's') + ' not reporting normally')
    if unknown_room:
        deductions.append(f'{unknown_room} device' + ('' if unknown_room == 1 else 's') + ' without a clear room')
    if diagnostics.get('last_error'):
        deductions.append('last Hubitat refresh has an error')
    score = max(0, 100 - low_battery * 5 - not_reporting * 8 - unknown_room * 2 - (10 if diagnostics.get('last_error') else 0))
    lines = ['Home health', f'Overall health score: {score}/100.']
    if deductions:
        lines.append('Main deductions:')
        lines.extend('- ' + item for item in deductions[:8])
    else:
        lines.append('No major health deductions found.')
    if stale.get('not_reporting'):
        lines.append('Devices to check first:')
        lines.extend(f"- {item.get('label')} - {item.get('duration')}" for item in stale['not_reporting'][:5])
    lines.append('Recommendation: ' + ('Replace low batteries first.' if low_battery else 'No immediate action needed.'))
    return {'success': True, 'intent': 'home_health', 'message': '\n'.join(lines), 'score': score, 'deductions': deductions, 'formatter': 'v1.5-natural'}


def daily_briefing(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    energy = energy_advisor(main)
    health = home_health(main)
    people = summary.get('people_home_names') or []
    today = energy.get('usage', {}).get('today') or {}
    alerts = list(health.get('deductions') or [])[:3] or ['No urgent alerts']
    lights = int(summary.get('lights_on') or 0)
    lines = [
        'Daily briefing',
        'Occupancy: ' + (', '.join(people) if people else 'No tracked family members home') + '.',
        f"Lights on: {lights} light" + ('' if lights == 1 else 's') + '.',
        f"Energy today: {natural_power(summary.get('power_total'))} right now; {natural_energy(today.get('kwh'))}, {natural_money(today.get('cost_gbp'))}.",
        'Alerts: ' + '; '.join(alerts) + '.',
        'Recommendation: ' + energy['message'].split('Recommendation: ')[-1].split('\n')[0],
    ]
    return {'success': True, 'intent': 'daily_briefing', 'message': '\n'.join(lines), 'energy': energy, 'health': health, 'formatter': 'v1.5-natural'}


def home_context(main: Any) -> dict[str, Any]:
    summary = main.dashboard_summary()
    health = home_health(main)
    energy = energy_advisor(main)
    try:
        rooms = main.api_rooms().get('rooms', [])
    except Exception:
        rooms = []
    active_rooms = [room for room in rooms if int(room.get('lights_on') or 0) or int(room.get('motion_active') or 0)]
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
        'context_source': 'cached-event-state',
    }


def natural_format(value: float, kind: str = 'power') -> dict[str, Any]:
    key = _text(kind)
    if key in ('power', 'w', 'watts'):
        formatted = natural_power(value)
    elif key in ('energy', 'kwh'):
        formatted = natural_energy(value)
    elif key in ('cost', 'gbp', 'money'):
        formatted = natural_money(value)
    else:
        formatted = str(value)
    return {'success': True, 'kind': key, 'value': value, 'formatted': formatted}


def _spent_today(main: Any) -> dict[str, Any]:
    usage = main.energy_usage_from_meter()
    if not usage.get('available'):
        return {'success': False, 'intent': 'energy_spend_today', 'message': 'I cannot see today energy cost yet because the meter totals are not available.'}
    today = usage.get('today') or {}
    return {'success': True, 'intent': 'energy_spend_today', 'message': f"You have spent {natural_money(today.get('cost_gbp'))} on electricity today so far, using {natural_energy(today.get('kwh'))}.", 'usage': usage}


def patch(main: Any) -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    app = getattr(main, 'app', None)
    if app is None:
        return False
    main.APP_VERSION = '1.5.0-alpha'
    main.energy_advisor_answer = lambda: energy_advisor(main)
    main.home_health_answer = lambda: home_health(main)
    main.daily_briefing_answer = lambda: daily_briefing(main)
    main.home_context_answer = lambda: home_context(main)
    original = getattr(main, 'assistant', None)
    if callable(original):
        def assistant(text: str) -> dict[str, Any]:
            t = _text(text)
            if ('spent' in t or 'cost' in t) and 'today' in t:
                return _spent_today(main)
            if 'anything unusual' in t or 'anything wrong' in t:
                hh = home_health(main)
                if not hh.get('deductions'):
                    return {'success': True, 'intent': 'anything_unusual', 'message': 'Nothing unusual stands out right now.'}
                return {'success': True, 'intent': 'anything_unusual', 'message': 'Things to check:\n' + '\n'.join('- ' + x for x in hh['deductions'])}
            return original(text)
        main.assistant = assistant
    _replace_route(app, '/api/energy-advisor', lambda: energy_advisor(main))
    _replace_route(app, '/api/home-health', lambda: home_health(main))
    _replace_route(app, '/api/daily-briefing', lambda: daily_briefing(main))
    _add_route_once(app, '/api/home-context', lambda: home_context(main))
    _add_route_once(app, '/api/briefing', lambda: daily_briefing(main))
    _add_route_once(app, '/api/home-health-score', lambda: home_health(main))
    _add_route_once(app, '/api/natural-format', natural_format)
    _PATCHED = True
    return True


def _wait_and_patch() -> None:
    for _ in range(200):
        main = sys.modules.get('__main__')
        if main is not None and hasattr(main, 'app') and hasattr(main, 'all_devices'):
            try:
                if patch(main):
                    return
            except Exception:
                return
        time.sleep(0.05)


threading.Thread(target=_wait_and_patch, name='homebrain-v15-patch', daemon=True).start()
