from __future__ import annotations

import importlib.util
from pathlib import Path


def load_addon_main():
    path = Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'main.py'
    spec = importlib.util.spec_from_file_location('homebrainos_prayer_times_main', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def prayer_device(attributes=None):
    return {
        'id': '6752',
        'name': 'Prayer Times Device',
        'label': 'Pray times',
        'room': 'Apps',
        'category': 'device',
        'attributes': attributes or {},
    }


PRAYER_ATTRIBUTES = {
    'fajr': '03:08',
    'sunrise': '04:58',
    'dhuhr': '13:12',
    'asr': '18:37',
    'maghrib': '21:15',
    'isha': '22:23',
    'lastUpdated': '02:30 15/07',
}


def test_full_prayer_times_are_answered_from_cached_device():
    main = load_addon_main()
    main.all_devices = lambda: [prayer_device(PRAYER_ATTRIBUTES)]

    answer = main.cache_first_assistant_answer("what are today's prayer times?")

    assert answer['intent'] == 'prayer_times'
    assert answer['source'] == 'prayer_times_device'
    for label, value in (
        ('Fajr', '03:08'), ('Sunrise', '04:58'), ('Dhuhr', '13:12'),
        ('Asr', '18:37'), ('Maghrib', '21:15'), ('Isha', '22:23'),
    ):
        assert f'{label}: {value}' in answer['message']
    assert 'Updated: 02:30 15/07' in answer['message']


def test_individual_prayer_and_spelling_aliases_are_direct_answers():
    main = load_addon_main()
    main.all_devices = lambda: [prayer_device(PRAYER_ATTRIBUTES)]

    assert main.cache_first_assistant_answer('what time is fajr?')['message'] == 'Fajr is at 03:08 today.'
    assert main.cache_first_assistant_answer('when is sunrise?')['message'] == 'Sunrise is at 04:58 today.'
    assert main.cache_first_assistant_answer('what time is zuhr?')['message'] == 'Dhuhr is at 13:12 today.'
    assert main.cache_first_assistant_answer('when is magrib?')['message'] == 'Maghrib is at 21:15 today.'


def test_empty_summary_cache_fetches_live_prayer_device_detail():
    main = load_addon_main()
    cached = prayer_device()
    fresh = prayer_device(PRAYER_ATTRIBUTES)
    refreshed = []
    main.all_devices = lambda: [cached]
    main.fetch_live_device_detail = lambda device_id: fresh if device_id == '6752' else None
    main.update_cached_device_snapshot = lambda device: refreshed.append(device['id'])

    answer = main.prayer_times_answer('fajr time')

    assert answer['message'] == 'Fajr is at 03:08 today.'
    assert refreshed == ['6752']


def test_sunrise_automation_command_is_not_stolen_by_prayer_query():
    main = load_addon_main()
    assert main._prayer_time_query('turn on the hallway light at sunrise') is False
