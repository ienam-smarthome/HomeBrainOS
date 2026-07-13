# -*- coding: utf-8 -*-
from pathlib import Path
import re

FILES = [
    Path("homebrainos/rootfs/app/main.py"),
    Path("addon/homebrainos/rootfs/app/main.py"),
]

PATCH = r'''
def final_text_cleanup(answer: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(answer, dict):
        return answer
    for key in ('message', 'speech'):
        if key in answer:
            text = str(answer.get(key) or '')
            text = text.replace('Â£', '£')
            text = text.replace('Â·', '·')
            text = text.replace('â€¢', '-')
            text = text.replace('â€”', '-')
            text = text.replace('â€“', '-')
            text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
            text = text.replace('<br/>', '\n').replace('<br>', '\n').replace('</div>', '\n').replace('</p>', '\n')
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            lines = [re.sub(r'\s+', ' ', line).strip() for line in text.replace('\r', '\n').split('\n')]
            answer[key] = '\n'.join(line for line in lines if line)
    return answer


def forced_room_status_answer(question: str) -> dict[str, Any] | None:
    q = normalise(question or '').strip()
    if not q:
        return None

    # Only direct room status questions.
    if not (
        q.endswith(' status')
        or q.startswith('check ')
        or q.startswith('summarise ')
        or q.startswith('summarize ')
        or q.startswith('what is happening in ')
        or q.startswith('what is going on in ')
    ):
        return None

    # Do not steal device-specific health checks.
    if any(word in q for word in ('trv', 'fridge door', 'roborock', 'tuya', 'battery', 'offline')):
        return None

    # Strip command words to get the room/device subject.
    subject = q
    subject = re.sub(r'\b(status|check|summarise|summarize|what|is|happening|going|on|in|the)\b', ' ', subject)
    subject = re.sub(r'\s+', ' ', subject).strip()
    if not subject:
        return None

    subject_c = compact_name(subject)
    matches = []

    for device in all_devices():
        label = device.get('label') or device.get('name') or str(device.get('id'))
        room = device.get('room') or 'Unknown'
        hay = normalise(f'{label} {room}')
        hay_c = compact_name(hay)
        if subject in hay or subject_c in hay_c or any(len(w) >= 3 and compact_name(w) in hay_c for w in subject.split()):
            # Fetch live detail for devices with no useful values.
            attrs = device_attribute_map(device)
            has_value = any(
                device.get(attr) is not None or attrs.get(attr) is not None
                for attr in ('temperature', 'humidity', 'battery', 'power', 'energy', 'motion', 'contact', 'switch')
            )
            if not has_value and device.get('id'):
                fresh = fetch_live_device_detail(str(device.get('id')))
                if fresh:
                    update_cached_device_snapshot(fresh)
                    device = fresh
            matches.append(device)

    if not matches:
        return None

    room_name = None
    for device in matches:
        room = device.get('room')
        if room and normalise(room) != 'unknown':
            room_name = room
            break
    room_name = room_name or subject.title()

    temperatures = []
    humidities = []
    motions = []
    lights_on = []
    switches_on = []
    batteries_low = []
    power_rows = []
    labels = []

    for device in matches:
        label = device.get('label') or device.get('name') or str(device.get('id'))
        labels.append(label)

        temp = safe_float(device.get('temperature') if device.get('temperature') is not None else device_attr_value(device, 'temperature'))
        hum = safe_float(device.get('humidity') if device.get('humidity') is not None else device_attr_value(device, 'humidity'))
        bat = safe_float(device.get('battery') if device.get('battery') is not None else device_attr_value(device, 'battery'))
        power = safe_float(device.get('power') if device.get('power') is not None else device_attr_value(device, 'power'))
        motion = device.get('motion') if device.get('motion') is not None else device_attr_value(device, 'motion')
        switch = device.get('switch') if device.get('switch') is not None else device_attr_value(device, 'switch')

        if temp is not None:
            temperatures.append((label, temp))
        if hum is not None:
            humidities.append((label, hum))
        if motion is not None:
            motions.append((label, str(motion)))
        if bat is not None and bat < 20:
            batteries_low.append((label, bat))
        if power is not None and power > 0:
            power_rows.append((label, power))
        if str(switch).lower() == 'on':
            if 'light' in normalise(label) or str(device.get('category') or '').lower() == 'light':
                lights_on.append(label)
            else:
                switches_on.append(label)

    lines = [f'{room_name} status:']

    if temperatures:
        label, value = sorted(temperatures, key=lambda item: 0 if 'meter' in normalise(item[0]) else 1)[0]
        lines.append(f'Temperature: {value:g}°C ({label})')
    if humidities:
        label, value = sorted(humidities, key=lambda item: 0 if 'meter' in normalise(item[0]) else 1)[0]
        lines.append(f'Humidity: {value:g}% ({label})')
    if motions:
        active = [label for label, value in motions if value.lower() == 'active']
        lines.append('Motion active: ' + ', '.join(active[:5]) if active else 'Motion: inactive')
    if lights_on:
        lines.append('Lights on: ' + ', '.join(lights_on[:8]))
    else:
        if any('light' in normalise(label) for label in labels):
            lines.append('Lights on: none')
    if switches_on:
        lines.append('Other switches on: ' + ', '.join(switches_on[:8]))
    if power_rows:
        total = sum(power for _, power in power_rows)
        top_label, top_power = sorted(power_rows, key=lambda item: item[1], reverse=True)[0]
        lines.append(f'Power: {total:g}W total; top: {top_label} {top_power:g}W')
    if batteries_low:
        lines.append('Low batteries: ' + ', '.join(f'{label} {value:g}%' for label, value in batteries_low[:5]))

    if len(lines) == 1:
        lines.append('Devices found, but no live room values are currently cached.')

    return {
        'success': True,
        'intent': 'room_status',
        'message': '\n'.join(lines),
        'speech': f'{room_name} status ready.',
        'room': room_name,
        'devices': labels,
    }


def safe_weather_shortcut_answer() -> dict[str, Any]:
    try:
        answer = weather_answer()
        return final_text_cleanup(answer)
    except Exception as exc:
        try:
            summary = home_summary()
            weather = summary.get('weather') or summary.get('weather_summary') or summary.get('weather_display')
            if weather:
                return {
                    'success': True,
                    'intent': 'weather',
                    'message': f'Weather: {weather}',
                    'speech': f'Weather: {weather}',
                }
        except Exception:
            pass
        return {
            'success': False,
            'intent': 'weather',
            'message': f'Weather is currently unavailable: {public_error(exc)}',
            'speech': 'Weather is currently unavailable.',
        }

'''

for path in FILES:
    text = path.read_text(encoding="utf-8", errors="replace")

    if "def forced_room_status_answer(" not in text:
        marker = "\ndef assistant(text: str) -> dict[str, Any]:"
        if marker not in text:
            raise SystemExit(f"Could not find assistant marker in {path}")
        text = text.replace(marker, PATCH + marker)

    marker = "def assistant(text: str) -> dict[str, Any]:\n    t = normalise(text)\n"
    early = """def assistant(text: str) -> dict[str, Any]:
    t = normalise(text)

    forced_room = forced_room_status_answer(text)
    if forced_room:
        return with_suggestions(final_text_cleanup(forced_room))

"""
    if marker not in text:
        raise SystemExit(f"Could not find assistant start in {path}")

    if "forced_room = forced_room_status_answer(text)" not in text[text.find("def assistant(text: str)"):text.find("def assistant(text: str)") + 1200]:
        text = text.replace(marker, early)

    text = text.replace("return with_suggestions(shortcut_weather_answer())", "return with_suggestions(safe_weather_shortcut_answer())")
    text = text.replace("return shortcut_weather_answer()", "return safe_weather_shortcut_answer()")
    text = text.replace("return with_suggestions(safe_timeline_answer())", "return with_suggestions(final_text_cleanup(safe_timeline_answer()))")
    text = text.replace("return with_suggestions(shortcut_device_health_answer())", "return with_suggestions(final_text_cleanup(shortcut_device_health_answer()))")
    text = text.replace("return with_suggestions(preflight)", "return with_suggestions(final_text_cleanup(preflight))")
    text = text.replace("return with_suggestions(shortcut_answer_cleanup(preflight))", "return with_suggestions(final_text_cleanup(shortcut_answer_cleanup(preflight)))")

    path.write_text(text, encoding="utf-8")

for config in [Path("homebrainos/config.yaml"), Path("addon/homebrainos/config.yaml")]:
    text = config.read_text(encoding="utf-8")
    text = text.replace("version: '1.9.0-alpha'", "version: '1.9.1-alpha'")
    text = text.replace("version: '1.8.9-alpha'", "version: '1.9.1-alpha'")
    config.write_text(text, encoding="utf-8")

for ni in [
    Path("homebrainos/rootfs/app/natural_intelligence.py"),
    Path("addon/homebrainos/rootfs/app/natural_intelligence.py"),
]:
    text = ni.read_text(encoding="utf-8")
    text = text.replace("VERSION = '1.9.0-alpha'", "VERSION = '1.9.1-alpha'")
    text = text.replace("VERSION = '1.8.9-alpha'", "VERSION = '1.9.1-alpha'")
    ni.write_text(text, encoding="utf-8")
