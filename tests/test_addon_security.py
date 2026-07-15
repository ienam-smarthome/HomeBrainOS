import importlib.util
import json
import sys
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def load_addon_main():
    path = Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'main.py'
    spec = importlib.util.spec_from_file_location('homebrainos_addon_main', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_public_error_redacts_tokens():
    main = load_addon_main()
    main.CONFIG['maker_api_token'] = 'maker-secret'
    main.CONFIG['api_token'] = 'dashboard-secret'

    message = main.public_error(
        RuntimeError('GET /devices?access_token=maker-secret failed with dashboard-secret')
    )

    assert 'maker-secret' not in message
    assert 'dashboard-secret' not in message
    assert 'access_token=REDACTED' in message


def test_maker_get_reports_empty_hubitat_response():
    main = load_addon_main()
    main.CONFIG['hubitat_base_url'] = 'http://hubitat.local'
    main.CONFIG['maker_api_app_id'] = '123'
    main.CONFIG['maker_api_token'] = 'maker-secret'

    class Response:
        text = ''
        headers = {'content-type': 'text/plain'}
        def raise_for_status(self):
            return None
        def json(self):
            raise AssertionError('json should not be called for an empty response')

    main.requests.get = lambda *_args, **_kwargs: Response()

    try:
        main.maker_get('devices')
    except RuntimeError as exc:
        message = main.public_error(exc)
    else:
        raise AssertionError('Expected RuntimeError')

    assert 'empty response' in message
    assert 'devices' in message
    assert 'maker-secret' not in message


def test_maker_get_reports_non_json_hubitat_response():
    main = load_addon_main()
    main.CONFIG['hubitat_base_url'] = 'http://hubitat.local'
    main.CONFIG['maker_api_app_id'] = '123'
    main.CONFIG['maker_api_token'] = 'maker-secret'

    class Response:
        text = '<html>Login required</html>'
        headers = {'content-type': 'text/html'}
        def raise_for_status(self):
            return None
        def json(self):
            raise ValueError('Expecting value: line 1 column 1 (char 0)')

    main.requests.get = lambda *_args, **_kwargs: Response()

    try:
        main.maker_get('devices')
    except RuntimeError as exc:
        message = main.public_error(exc)
    else:
        raise AssertionError('Expected RuntimeError')

    assert 'non-JSON' in message
    assert 'text/html' in message
    assert 'Login required' in message
    assert 'Expecting value' not in message
    assert 'maker-secret' not in message


def test_generic_room_targets_do_not_match_every_device():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': '1', 'label': 'Hallway Light', 'room': 'Hallway', 'category': 'light', 'switch': 'off'},
    ]

    assert main.find_devices('') == []
    assert main.room_devices('', 'light') == []
    assert main.room_devices('all', 'light') == []


def test_summary_uses_octopus_power_and_named_people():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'p1', 'label': 'Octopus Energy Live Meter', 'room': 'Energy', 'category': 'power_device', 'power': 1456.7},
        {'id': 'p2', 'label': 'Kitchen Plug', 'room': 'Kitchen', 'category': 'switch', 'power': 12.3},
        {'id': 'e', 'label': 'Enamul Presence', 'room': 'People', 'category': 'presence_sensor', 'presence': 'present'},
        {'id': 's', 'label': 'Samah Presence', 'room': 'People', 'category': 'presence_sensor', 'presence': 'not present'},
    ]

    summary = main.dashboard_summary()

    assert summary['power_total'] == 1456.7
    assert summary['power_display'] == '1.5kW'
    assert summary['power_source_label'] == 'Octopus Energy Live Meter'
    assert summary['people_home'] == 1
    assert summary['people_tracked'] == 4
    assert summary['people_home_names'] == ['Enamul']


def test_summary_counts_life360_home_members_as_home():
    main = load_addon_main()
    main.SUMMARY_CACHE = None
    main.all_devices = lambda: [
        {'id': 'e', 'label': 'Enamul Khan', 'name': 'Life360 Member', 'room': 'Life360', 'category': 'presence_sensor', 'attributes': {'tile': 'Enamul Khan At Home since yesterday 5:31 PM Updated: 5:31 PM'}},
        {'id': 'm', 'label': 'Muhsena Khan', 'name': 'Life360 Member', 'room': 'Life360', 'category': 'presence_sensor', 'attributes': {'currentPlace': 'Home'}},
        {'id': 's', 'label': 'Samah Khan', 'name': 'Life360 Member', 'room': 'Life360', 'category': 'presence_sensor', 'presence': 'present'},
        {'id': 't', 'label': 'Tahmid Khan', 'name': 'Life360 Member', 'room': 'Life360', 'category': 'presence_sensor', 'presence': 'home'},
    ]

    summary = main.dashboard_summary()
    answer = main.assistant('who is home')

    assert summary['people_home'] == 4
    assert summary['people_tracked'] == 4
    assert summary['people_home_names'] == ['Enamul', 'Samah', 'Tahmid', 'Muhsena']
    assert 'Enamul' in answer['message']
    assert 'Muhsena' in answer['message']


def test_assistant_explains_low_battery_and_motion_summary_tiles():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'b1', 'label': 'Hallway Contact', 'room': 'Hallway', 'category': 'contact_sensor', 'battery': 12},
        {'id': 'm1', 'label': 'Kitchen Motion', 'room': 'Kitchen', 'category': 'motion_sensor', 'motion': 'active'},
        {'id': 'p1', 'label': 'Octopus Energy Live Meter', 'room': 'Energy', 'category': 'power_device', 'power': 300},
    ]

    low_battery = main.assistant('which batteries are low')
    motion = main.assistant('which motion sensors are active')
    power = main.assistant('explain power tile')

    assert 'Hallway Contact' in low_battery['message']
    assert 'Kitchen Motion' in motion['message']
    assert 'Octopus Energy Live Meter' in power['message']


def test_which_batteries_are_low_merges_authoritative_status_report():
    main = load_addon_main()
    main.SUMMARY_CACHE = None
    main.all_devices = lambda: [
        {'id': 'b1', 'label': 'Livingroom TRV', 'room': 'Living Room', 'category': 'battery_sensor', 'battery': 12},
        {
            'id': 'report',
            'label': 'Device Status Report',
            'room': 'Hub',
            'category': 'device',
            'attributes': {
                'offlineCount': 0,
                'lowBatteryCount': 2,
                'motionAlertCount': 0,
                'reportText': '[LOW BATTERY]\nLivingroom TRV - 12% battery\nFridge Door - 19% battery',
            },
        },
    ]

    answer = main.assistant('which batteries are low')

    assert answer['intent'] == 'summary_low_batteries'
    assert 'Livingroom TRV' in answer['message']
    assert 'Fridge Door' in answer['message']
    assert answer['count'] == 2


def test_assistant_uses_natural_speech_units_for_summary_attributes():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 't1', 'label': 'Hallway Sensor', 'room': 'Hallway', 'category': 'climate_sensor', 'temperature': 28.4, 'humidity': 41},
        {'id': 'p1', 'label': 'Octopus Energy Live Meter', 'room': 'Energy', 'category': 'power_device', 'power': 319},
    ]

    temperature = main.assistant('home temperature')
    power = main.assistant('explain power tile')

    assert temperature['message'] == 'Home temperature is 28.4C'
    assert temperature['speech'] == 'Home temperature is 28.4 degrees.'
    assert power['message'] == 'Power is whole-house live power from Octopus Energy Live Meter: 319W.'
    assert power['speech'] == 'Power is whole-house live power from Octopus Energy Live Meter: 319 watts.'


def test_assistant_answers_singular_light_question_with_direct_speech():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Bedroom 2 Light', 'room': 'Bedroom 2', 'category': 'light', 'switch': 'on'},
        {'id': 'l2', 'label': 'Hallway Light', 'room': 'Hallway', 'category': 'light', 'switch': 'off'},
    ]

    answer = main.assistant('what light is on')

    assert answer['message'] == 'Lights on:\nBedroom 2 Light'
    assert answer['speech'] == 'Bedroom 2.'


def test_assistant_targets_numbered_light_device_and_speaks_confirmation():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Livingroom Light 1', 'name': 'Livingroom Light 1', 'room': 'Living Room', 'category': 'light', 'switch': 'off'},
        {'id': 'l2', 'label': 'Livingroom Light 2', 'name': 'Livingroom Light 2', 'room': 'Living Room', 'category': 'light', 'switch': 'off'},
    ]
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_switch = lambda device_ids, switch: []

    answer = main.assistant('turn on livingroom light 1')

    assert commands == [('l1', 'on')]
    assert answer['changed'] == ['Livingroom Light 1']
    assert answer['speech'] == 'Livingroom Light 1 turned on.'


def test_assistant_controls_device_with_voice_articles_and_punctuation_before_ai():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.all_devices = lambda: [
        {'id': 'p1', 'label': 'Air Purifier', 'name': 'Air Purifier', 'room': 'Appliances', 'category': 'switch', 'switch': 'on'},
    ]
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_switch = lambda device_ids, switch: []
    main.ollama_answer = lambda text: (_ for _ in ()).throw(AssertionError('Ollama should not handle deterministic device commands'))

    answer = main.assistant('turn off the air purifier.')

    assert commands == [('p1', 'off')]
    assert answer['changed'] == ['Air Purifier']
    assert answer['speech'] == 'Air Purifier turned off.'


def test_assistant_controls_room_qualified_fuzzy_device_target():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'd1', 'label': 'Dehumidifier 1', 'name': 'Dehumidifier 1', 'room': 'Bathroom', 'category': 'switch', 'switch': 'off'},
        {'id': 'd2', 'label': 'Dehumidifier 2', 'name': 'Dehumidifier 2', 'room': 'Bedroom', 'category': 'switch', 'switch': 'off'},
    ]
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_switch = lambda device_ids, switch: []

    answer = main.assistant('turn on dehumidifer in the bathroom')

    assert commands == [('d1', 'on')]
    assert answer['changed'] == ['Dehumidifier 1']
    assert answer['speech'] == 'Dehumidifier 1 turned on.'


def test_assistant_ignores_trailing_voice_filler_in_device_target():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'd1', 'label': 'Dehumidifier 1', 'name': 'Dehumidifier 1', 'room': 'Bathroom', 'category': 'switch', 'switch': 'on'},
    ]
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_switch = lambda device_ids, switch: []

    answer = main.assistant('turn off dehumidifier to')

    assert commands == [('d1', 'off')]
    assert answer['changed'] == ['Dehumidifier 1']
    assert answer['speech'] == 'Dehumidifier 1 turned off.'


def test_hubitat_event_updates_cached_device_attribute():
    main = load_addon_main()
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        start_version = main.STATE_EVENT_VERSION
        main.upsert_devices([
            {'id': 'd1', 'name': 'Bathroom Light', 'label': 'Bathroom Light', 'room': 'Bathroom', 'category': 'light', 'switch': 'off', 'attributes': {'switch': 'off'}},
        ])

        result = main.record_hubitat_events({'deviceId': 'd1', 'name': 'switch', 'value': 'on', 'displayName': 'Bathroom Light'})
        device = main.all_devices()[0]
        status = main.api_status()

    assert result['success'] is True
    assert result['events'] == 1
    assert result['updated'] == 1
    assert main.STATE_EVENT_VERSION == start_version + 1
    assert status['state_event_version'] == main.STATE_EVENT_VERSION
    assert device['switch'] == 'on'
    assert device['attributes']['switch'] == 'on'


def test_stale_device_report_flags_long_running_states():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            old = now - 8 * 3600
            main.CONFIG['stale_motion_active_minutes'] = 30
            main.CONFIG['stale_light_on_hours'] = 4
            main.CONFIG['stale_device_report_hours'] = 6
            main.upsert_devices([
                {'id': 'm1', 'name': 'Hallway Motion', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'active', 'attributes': {'motion': 'active'}},
                {'id': 'l1', 'name': 'Bedroom Light', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on', 'attributes': {'switch': 'on'}},
                {'id': 's1', 'name': 'Fresh Light', 'label': 'Fresh Light', 'room': 'Kitchen', 'category': 'light', 'switch': 'on', 'attributes': {'switch': 'on'}},
                {'id': 'b1', 'name': 'Bedroom Battery', 'label': 'Bedroom Battery', 'room': 'Bedroom', 'category': 'battery_sensor', 'battery': 55, 'attributes': {'battery': 55}},
            ])
            conn = main.db()
            try:
                conn.execute('UPDATE devices SET updated_at=? WHERE id IN (?, ?, ?)', (old, 'm1', 'l1', 'b1'))
                conn.commit()
            finally:
                conn.close()

            report = main.stale_device_report()
            answer = main.assistant('stale devices')

        assert [item['label'] for item in report['motion_active_too_long']] == ['Hallway Motion']
        assert [item['label'] for item in report['lights_on_too_long']] == ['Bedroom Light']
        assert 'Bedroom Battery' in [item['label'] for item in report['not_reporting']]
        assert report['motion_active_too_long'][0]['duration'] == '8 hours'
        assert report['lights_on_too_long'][0]['duration'] == '8 hours'
        assert 'Fresh Light' not in answer['message']
        assert 'Motion active too long' in answer['message']
        assert 'Lights on too long' in answer['message']
        assert 'Hallway Motion (Hallway) for 8 hours' in answer['message']
        assert 'Bedroom Light on for 8 hours' in answer['speech']
        assert 'Bedroom Battery not reporting for 8 hours' in answer['speech']
        assert answer['intent'] == 'stale_devices'
    finally:
        main.DB_PATH = original_db_path



def test_stale_device_report_uses_real_activity_not_cache_refresh():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            old_activity = now - 30 * 3600
            main.CONFIG['stale_device_report_hours'] = 24
            main.upsert_devices([
                {
                    'id': 'b1',
                    'name': 'Bedroom Battery',
                    'label': 'Bedroom Battery',
                    'room': 'Bedroom',
                    'category': 'battery_sensor',
                    'battery': 55,
                    'attributes': [{'name': 'battery', 'currentValue': 55, 'date': old_activity}],
                },
            ])
            conn = main.db()
            try:
                conn.execute('UPDATE devices SET updated_at=? WHERE id=?', (now, 'b1'))
                conn.commit()
            finally:
                conn.close()

            report = main.stale_device_report()

        assert [item['label'] for item in report['not_reporting']] == ['Bedroom Battery']
        assert report['not_reporting'][0]['confidence'] == 'high'
        assert report['not_reporting'][0]['last_activity_source'] == 'hubitat attribute timestamp or value change'
    finally:
        main.DB_PATH = original_db_path


def test_stale_device_report_ignores_old_matching_state_if_newer_opposite_event_exists():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            main.CONFIG['stale_motion_active_minutes'] = 30
            main.upsert_devices([
                {'id': 'm1', 'name': 'Hallway Motion', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'active', 'attributes': {'motion': 'active'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', ('m1', 'motion', 'active', now - 4 * 3600))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('m1', 'Hallway Motion', 'motion', 'inactive', '{}', now - 60))
                conn.commit()
            finally:
                conn.close()

            report = main.stale_device_report()

        assert report['motion_active_too_long'] == []
    finally:
        main.DB_PATH = original_db_path

def test_device_state_duration_uses_latest_matching_state_change():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            main.upsert_devices([
                {'id': 'tv1', 'name': 'TV', 'label': 'TV', 'room': 'Multimedia', 'category': 'switch', 'switch': 'on', 'attributes': {'switch': 'on'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', ('tv1', 'switch', 'on', now - 5 * 86400))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'off', '{}', now - 1800))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'on', '{}', now - 960))
                conn.commit()
            finally:
                conn.close()

            answer = main.assistant('how long has the tv been on and from when')

        assert answer['intent'] == 'device_state_duration'
        assert 'TV has been on for 16 minutes' in answer['message']
        assert '5 days' not in answer['message']
        assert answer['speech'] == answer['message']
    finally:
        main.DB_PATH = original_db_path


def test_device_state_duration_prefers_exact_tv_label_over_computer():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            main.upsert_devices([
                {'id': 'pc1', 'name': 'Computer', 'label': 'Computer', 'room': 'Multimedia', 'category': 'switch', 'switch': 'on', 'attributes': {'switch': 'on'}},
                {'id': 'tv1', 'name': 'TV', 'label': 'TV', 'room': 'Multimedia', 'category': 'switch', 'switch': 'on', 'attributes': {'switch': 'on'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('pc1', 'Computer', 'switch', 'on', '{}', now - 4 * 3600))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'on', '{}', now - 600))
                conn.commit()
            finally:
                conn.close()

            answer = main.assistant('how long has the tv been on')

        assert answer['intent'] == 'device_state_duration'
        assert answer['device']['label'] == 'TV'
        assert 'TV has been on for 10 minutes' in answer['message']
        assert 'Computer' not in answer['message']
    finally:
        main.DB_PATH = original_db_path


def test_device_last_state_duration_answers_completed_session():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            main.upsert_devices([
                {'id': 'tv1', 'name': 'TV', 'label': 'TV', 'room': 'Multimedia', 'category': 'switch', 'switch': 'off', 'attributes': {'switch': 'off'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'on', '{}', now - 1800))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'off', '{}', now - 1140))
                conn.commit()
            finally:
                conn.close()

            answer = main.assistant('how long was the tv last on for')

        assert answer['intent'] == 'device_state_duration'
        assert answer['device']['label'] == 'TV'
        assert 'TV was last on for 11 minutes' in answer['message']
    finally:
        main.DB_PATH = original_db_path


def test_display_since_uses_configured_london_timezone():
    main = load_addon_main()
    original_time = main.time.time
    original_tz = main.CONFIG.get('time_zone')
    try:
        main.CONFIG['time_zone'] = 'Europe/London'
        event_time = datetime(2026, 7, 6, 16, 49, tzinfo=timezone.utc).timestamp()
        main.time.time = lambda: datetime(2026, 7, 6, 20, 0, tzinfo=timezone.utc).timestamp()

        assert main.display_since(int(event_time)) == '5:49 pm today'
    finally:
        main.time.time = original_time
        main.CONFIG['time_zone'] = original_tz


def test_device_total_state_duration_answers_today_for_exact_tv():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    original_time = main.time.time
    original_tz = main.CONFIG.get('time_zone')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            main.CONFIG['time_zone'] = 'Europe/London'
            main.time.time = lambda: datetime(2026, 7, 6, 20, 0, tzinfo=timezone.utc).timestamp()
            main.upsert_devices([
                {'id': 'pc1', 'name': 'Computer', 'label': 'Computer', 'room': 'Multimedia', 'category': 'switch', 'switch': 'off', 'attributes': {'switch': 'off'}},
                {'id': 'tv1', 'name': 'TV', 'label': 'TV', 'room': 'Multimedia', 'category': 'switch', 'switch': 'off', 'attributes': {'switch': 'off'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('pc1', 'Computer', 'switch', 'on', '{}', int(datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'off', '{}', int(datetime(2026, 7, 5, 22, 0, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'on', '{}', int(datetime(2026, 7, 6, 16, 49, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'off', '{}', int(datetime(2026, 7, 6, 17, 50, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'on', '{}', int(datetime(2026, 7, 6, 18, 10, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'off', '{}', int(datetime(2026, 7, 6, 18, 20, tzinfo=timezone.utc).timestamp())))
                conn.commit()
            finally:
                conn.close()

            answer = main.assistant('total time tv was on today?')

        assert answer['intent'] == 'device_total_state_duration'
        assert answer['device']['label'] == 'TV'
        assert answer['total_seconds'] == 4260
        assert answer['message'] == 'TV was on for 1 hour 11 minutes today.'
        assert answer['speech'] == answer['message']
        assert 'Computer' not in answer['message']
    finally:
        main.DB_PATH = original_db_path
        main.time.time = original_time
        main.CONFIG['time_zone'] = original_tz


def test_light_on_time_today_routes_before_direct_switch_lookup():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    original_time = main.time.time
    original_tz = main.CONFIG.get('time_zone')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            main.CONFIG['time_zone'] = 'Europe/London'
            main.time.time = lambda: datetime(2026, 7, 6, 20, 0, tzinfo=timezone.utc).timestamp()
            main.upsert_devices([
                {'id': 'pc1', 'name': 'Computer', 'label': 'Computer', 'room': 'Multimedia', 'category': 'switch', 'switch': 'on', 'attributes': {'switch': 'on'}},
                {'id': 'l1', 'name': 'Bedroom Light', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'off', 'attributes': {'switch': 'off'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('pc1', 'Computer', 'switch', 'on', '{}', int(datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('l1', 'Bedroom Light', 'switch', 'on', '{}', int(datetime(2026, 7, 6, 16, 0, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('l1', 'Bedroom Light', 'switch', 'off', '{}', int(datetime(2026, 7, 6, 17, 30, tzinfo=timezone.utc).timestamp())))
                conn.commit()
            finally:
                conn.close()

            answer = main.assistant('lights on time today')
            fast_answer = main.cache_first_assistant_answer('lights on time today')
            preflight_answer = main.assistant_preflight_answer('lights on time today')

        assert answer['intent'] == 'state_usage_summary'
        assert 'Light-on time today' in answer['message']
        assert 'Bedroom Light' in answer['message']
        assert 'Computer' not in answer['message']
        assert answer['total_seconds'] == 5400
        assert fast_answer['intent'] == 'state_usage_summary'
        assert 'Bedroom Light' in fast_answer['message']
        assert 'Computer' not in fast_answer['message']
        assert preflight_answer['intent'] == 'state_usage_summary'
        assert 'Bedroom Light' in preflight_answer['message']
        assert 'Computer' not in preflight_answer['message']
    finally:
        main.DB_PATH = original_db_path
        main.time.time = original_time
        main.CONFIG['time_zone'] = original_tz


def test_device_total_state_duration_clips_session_from_before_midnight():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    original_time = main.time.time
    original_tz = main.CONFIG.get('time_zone')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            main.CONFIG['time_zone'] = 'Europe/London'
            main.time.time = lambda: datetime(2026, 7, 6, 8, 0, tzinfo=timezone.utc).timestamp()
            main.upsert_devices([
                {'id': 'tv1', 'name': 'TV', 'label': 'TV', 'room': 'Multimedia', 'category': 'switch', 'switch': 'off', 'attributes': {'switch': 'off'}},
            ])
            conn = main.db()
            try:
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'on', '{}', int(datetime(2026, 7, 5, 22, 30, tzinfo=timezone.utc).timestamp())))
                conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('tv1', 'TV', 'switch', 'off', '{}', int(datetime(2026, 7, 5, 23, 30, tzinfo=timezone.utc).timestamp())))
                conn.commit()
            finally:
                conn.close()

            answer = main.assistant('how long was the tv on today')

        assert answer['intent'] == 'device_total_state_duration'
        assert answer['total_seconds'] == 1800
        assert answer['message'] == 'TV was on for 30 minutes today.'
    finally:
        main.DB_PATH = original_db_path
        main.time.time = original_time
        main.CONFIG['time_zone'] = original_tz


def test_device_state_duration_reports_current_state_mismatch():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'tv1', 'name': 'TV', 'label': 'TV', 'room': 'Multimedia', 'category': 'switch', 'switch': 'off', 'attributes': {'switch': 'off'}},
    ]

    answer = main.assistant('how long has the tv been on')

    assert answer['intent'] == 'device_state_duration'
    assert answer['message'] == 'TV is currently off, not on.'


def test_hubitat_event_parser_accepts_events_array():
    main = load_addon_main()
    events = main.event_records_from_payload({'events': [
        {'device_id': 123, 'attribute': 'power', 'value': 42, 'label': 'Desk Plug'},
    ]})

    assert events == [{'device_id': '123', 'attr': 'power', 'value': 42, 'label': 'Desk Plug', 'raw': {'device_id': 123, 'attribute': 'power', 'value': 42, 'label': 'Desk Plug'}}]


def test_assistant_asks_when_singular_light_target_is_ambiguous():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Livingroom Light 1', 'name': 'Livingroom Light 1', 'room': 'Living Room', 'category': 'light', 'switch': 'off'},
        {'id': 'l2', 'label': 'Livingroom Light 2', 'name': 'Livingroom Light 2', 'room': 'Living Room', 'category': 'light', 'switch': 'off'},
    ]
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))

    answer = main.assistant('turn on livingroom light')

    assert answer['success'] is False
    assert answer['intent'] == 'disambiguation'
    assert commands == []
    assert 'Livingroom Light 1' in answer['message']
    assert 'Livingroom Light 2' in answer['message']


def test_assistant_controls_plural_room_lights_as_group():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Livingroom Light 1', 'name': 'Livingroom Light 1', 'room': 'Living Room', 'category': 'light', 'switch': 'off'},
        {'id': 'l2', 'label': 'Livingroom Light 2', 'name': 'Livingroom Light 2', 'room': 'Living Room', 'category': 'light', 'switch': 'off'},
        {'id': 'h1', 'label': 'Hallway Light 1', 'name': 'Hallway Light 1', 'room': 'Hallway', 'category': 'light', 'switch': 'off'},
    ]
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_switch = lambda device_ids, switch: []

    answer = main.assistant('turn on livingroom lights')

    assert answer['success'] is True
    assert commands == [('l1', 'on'), ('l2', 'on')]
    assert answer['changed'] == ['Livingroom Light 1', 'Livingroom Light 2']


def test_assistant_sets_light_level_with_percent_command():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Bedroom 1 Light', 'name': 'Bedroom 1 Light', 'room': 'Bedroom 1', 'category': 'light', 'switch': 'off', 'level': 10},
    ]
    values = []
    switches = []
    main.maker_command_value = lambda device_id, command, value: values.append((device_id, command, value))
    main.maker_command = lambda device_id, command: switches.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_level = lambda device_id, level: {'id': device_id, 'level': level}

    answer = main.assistant('set bedroom 1 light to 30 percent')

    assert answer['success'] is True
    assert values == [('l1', 'setLevel', 30)]
    assert switches == [('l1', 'on')]
    assert answer['speech'] == 'Bedroom 1 Light set to 30 percent.'


def test_assistant_reads_weather_summary_from_weather_device():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'w1',
            'label': 'Weather Open-Meteo',
            'room': 'Weather',
            'category': 'weather',
            'weatherSummary': 'Weather summary for Lewisham, SE13 updated at 22:19. Clear with a high of 27C and a low of 15C. Current temperature is 23C.',
            'attributes': {},
        },
    ]

    answer = main.assistant("what's the weather")

    assert answer['intent'] == 'weather'
    assert 'Weather summary for Lewisham' in answer['message']
    assert '27 degrees' in answer['speech']
    assert 'S E 13' in answer['speech']


def test_weather_answer_includes_open_meteo_current_and_forecast_tile():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'w1',
            'label': 'Weather Open-Meteo',
            'room': 'Weather',
            'category': 'weather',
            'temperature': 22.5,
            'humidity': 61,
            'attributes': {
                'weatherSummaryLine': 'Sunny, High 28C, Low 19C, Current 23C',
                'weatherSummary': 'Weather summary for Lewisham, SE13 updated at 09:49. Sunny with a high of 28C and a low of 19C. Current temperature is 23C and feels like 23C. Precipitation now is Dry 0.00mm. Chance of precipitation is 0%.',
                'threedayfcstTile': 'Lewisham SE13 Daily Icon Cond H/L Chance Rain Tod Overcast 28C/19C 0% 0mm Sun Overcast 29C/18C 0% 0mm Mon Overcast 28C/16C 0% 0mm',
                'windSpeed': 8.1,
                'wind_gust': 17.7,
                'seaLevelPressure': 1021.3,
                'precipitationToday': 0,
                'chanceOfRain': 0,
            },
        },
    ]

    answer = main.assistant("what's the weather")

    assert answer['intent'] == 'weather'
    assert 'Sunny, High 28C, Low 19C, Current 23C' in answer['message']
    assert 'Now: current 22.5°C' in answer['message']
    assert 'rain chance 0%' in answer['message']
    assert 'wind 8.1, gust 17.7' in answer['message']
    assert 'Next: Today 28°C/19°C, Sun 29°C/18°C, Mon 28°C/16°C' in answer['message']
    assert '22.5 degrees' in answer['speech']


def test_rain_question_uses_weather_summary_precipitation_text():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'w1',
            'label': 'Weather Open-Meteo',
            'room': 'Weather',
            'category': 'weather',
            'temperature': 23.7,
            'humidity': 59,
            'attributes': {
                'weatherSummaryLine': 'Sunny, High 28C, Low 19C, Current 24C',
                'weatherSummary': 'Weather summary for Lewisham, SE13 updated at 10:34. Sunny with a high of 28C and a low of 19C. Current temperature is 24C and feels like 24C. Precipitation now is Dry 0.00mm. Chance of precipitation is 0%.',
                'threedayfcstTile': 'Lewisham SE13 Daily Icon Cond H/L Chance Rain Tod Overcast 28C/19C 0% 0mm Sun Overcast 29C/18C 0% 0mm',
                'windSpeed': 8.7,
                'seaLevelPressure': 1021.3,
            },
        },
    ]

    answer = main.assistant('will it rain today?')

    assert answer['intent'] == 'weather'
    assert 'rain today 0mm' in answer['message']
    assert 'rain chance 0%' in answer['message']
    assert 'wind 8.7' in answer['message']


def test_weather_answer_prefers_populated_weather_device():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'empty-weather',
            'label': 'Weather Open-Meteo',
            'room': 'Weather',
            'category': 'weather',
            'attributes': {},
        },
        {
            'id': 'real-weather',
            'label': 'Weather Open-Meteo',
            'room': 'Weather',
            'category': 'weather',
            'temperature': 24,
            'attributes': {
                'weatherSummaryLine': 'Sunny, High 28C, Low 19C, Current 24C',
                'weatherSummary': 'Weather summary for Lewisham. Precipitation now is Dry 0.00mm. Chance of precipitation is 0%.',
            },
        },
    ]

    answer = main.assistant('what is the weather')

    assert answer['intent'] == 'weather'
    assert 'Sunny, High 28C' in answer['message']
    assert answer['device']['id'] == 'real-weather'


def test_weather_answer_polls_detail_when_cached_summary_missing():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'weather1',
            'label': 'Weather Open-Meteo',
            'room': 'Weather',
            'category': 'weather',
            'attributes': {},
        },
    ]
    updates = []
    main.fetch_live_device_detail = lambda device_id: {
        'id': device_id,
        'label': 'Weather Open-Meteo',
        'room': 'Weather',
        'category': 'weather',
        'temperature': 24,
        'attributes': {
            'weatherSummaryLine': 'Sunny, High 28C, Low 19C, Current 24C',
            'weatherSummary': 'Weather summary for Lewisham. Precipitation now is Dry 0.00mm. Chance of precipitation is 0%.',
        },
    }
    main.update_cached_device_snapshot = lambda device: updates.append(device)

    answer = main.assistant('will it rain today?')

    assert answer['intent'] == 'weather'
    assert 'Sunny, High 28C' in answer['message']
    assert 'rain chance 0%' in answer['message']
    assert updates and updates[0]['id'] == 'weather1'


def test_assistant_understands_anything_offline_alias():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'report',
            'label': 'Device Status Report',
            'room': 'Hub',
            'category': 'device',
            'attributes': {
                'offlineCount': 2,
                'lowBatteryCount': 0,
                'motionAlertCount': 0,
                'reportText': '[OFFLINE]\nRoborock Q7 Max - last seen 1d ago\nTuya Remote (bedroom 3) - last seen 1d ago',
            },
        },
    ]

    answer = main.assistant('anything offline?')

    assert answer['intent'] == 'device_health'
    assert 'Offline devices: 2' in answer['message']
    assert 'Roborock Q7 Max' in answer['message']


def test_assistant_increases_room_brightness_for_room_lights():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'h1', 'label': 'Hallway Light 1', 'name': 'Hallway Light 1', 'room': 'Hallway', 'category': 'light', 'switch': 'on', 'level': 20},
        {'id': 'h2', 'label': 'Hallway Light 2', 'name': 'Hallway Light 2', 'room': 'Hallway', 'category': 'light', 'switch': 'on', 'level': 40},
        {'id': 'b1', 'label': 'Bedroom Light', 'name': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on', 'level': 10},
    ]
    values = []
    switches = []
    main.maker_command_value = lambda device_id, command, value: values.append((device_id, command, value))
    main.maker_command = lambda device_id, command: switches.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_level = lambda device_id, level: {'id': device_id, 'level': level}

    answer = main.assistant('increase brightness in hallway')

    assert answer['success'] is True
    assert values == [('h1', 'setLevel', 50), ('h2', 'setLevel', 50)]
    assert switches == [('h1', 'on'), ('h2', 'on')]


def test_hub_logs_diagnostics_summarizes_errors_and_redacts_tokens():
    main = load_addon_main()
    main.CONFIG['hubitat_base_url'] = 'http://hubitat.local'
    main.CONFIG['hubitat_logs_path'] = '/logs/past'
    main.CONFIG['maker_api_token'] = 'maker-secret'
    main.all_devices = lambda: [
        {'id': 'h1', 'label': 'Hallway Light 1', 'room': 'Hallway', 'category': 'light'},
    ]

    class Response:
        text = ''
        def raise_for_status(self):
            return None
        def json(self):
            return [
                {'level': 'error', 'name': 'Hallway Light 1', 'message': 'Failed command access_token=maker-secret'},
                {'level': 'info', 'message': 'Everything else is fine'},
            ]

    main.requests.get = lambda url, timeout=12: Response()

    answer = main.assistant('hub logs')

    assert answer['intent'] == 'hub_logs'
    assert 'Errors: 1' in answer['message']
    assert 'Hallway Light 1: 1' in answer['message']
    assert 'maker-secret' not in answer['message']
    assert 'access_token=REDACTED' in answer['message']


def test_ai_context_pack_includes_summary_weather_and_safety_policy():
    main = load_addon_main()
    main.CONFIG['ollama_include_hub_logs'] = False
    main.all_devices = lambda: [
        {'id': 'w1', 'label': 'Weather Open-Meteo', 'room': 'Weather', 'category': 'weather', 'weatherSummaryLine': 'Clear, High 27C, Low 15C'},
        {'id': 'l1', 'label': 'Hallway Light', 'room': 'Hallway', 'category': 'light', 'switch': 'on', 'level': 60},
        {'id': 'p1', 'label': 'Octopus Energy Live Meter', 'room': 'Energy', 'category': 'power_device', 'power': 319},
    ]

    context = main.ai_context_pack()

    assert context['summary']['lights_on'] == 1
    assert context['summary']['power_source_label'] == 'Octopus Energy Live Meter'
    assert context['weather']['label'] == 'Weather Open-Meteo'
    assert 'AI should answer and advise only' in context['safety']['control_policy']
    assert any(device['label'] == 'Hallway Light' for device in context['devices'])


def test_ollama_answer_uses_bounded_read_tools_for_home_questions():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.CONFIG['ollama_tool_calling_enabled'] = True
    main.CONFIG['ollama_base_url'] = 'http://ollama.local:11434'
    main.CONFIG['ollama_model'] = 'qwen2.5:3b'
    main.CONFIG['ollama_timeout_seconds'] = 75
    main.CONFIG['ollama_tool_timeout_seconds'] = 18
    main.CONFIG['ollama_num_predict'] = 90
    main.all_devices = lambda: [
        {'id': 'w1', 'label': 'Weather Open-Meteo', 'room': 'Weather', 'category': 'weather', 'weatherSummaryLine': 'Clear'},
    ]
    captured = []

    class HealthResponse:
        def raise_for_status(self):
            return None

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self.payload

    def post(url, json, timeout=20):
        captured.append({'url': url, 'json': json, 'timeout': timeout})
        if len(captured) == 1:
            return Response({
                'message': {
                    'role': 'assistant',
                    'content': '',
                    'tool_calls': [{
                        'function': {'name': 'home_get_summary', 'arguments': {}},
                    }],
                },
            })
        return Response({'message': {'role': 'assistant', 'content': 'The home looks stable.'}})

    main.requests.get = lambda url, timeout=2: HealthResponse()
    main.requests.post = post

    answer = main.ollama_answer('anything unusual?')

    assert answer['intent'] == 'ollama_tool_answer'
    assert answer['source'] == 'ollama_tools'
    assert answer['tools_used'] == ['home_get_summary']
    assert [call['url'] for call in captured] == [
        'http://ollama.local:11434/api/chat',
        'http://ollama.local:11434/api/chat',
    ]
    assert all(call['timeout'] == 18 for call in captured)
    assert len(captured[0]['json']['tools']) == 8
    assert 'tools' not in captured[1]['json']
    tool_message = captured[1]['json']['messages'][-1]
    assert tool_message['role'] == 'tool'
    assert tool_message['tool_name'] == 'home_get_summary'
    assert 'lights_on' in tool_message['content']
    assert answer['speech'] == 'The home looks stable.'


def test_ollama_tool_selection_falls_back_to_generate_when_no_tool_is_called():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.CONFIG['ollama_tool_calling_enabled'] = True
    main.CONFIG['ollama_base_url'] = 'http://ollama.local:11434'
    main.CONFIG['ollama_model'] = 'qwen2.5:3b'
    main.all_devices = lambda: []
    calls = []

    class HealthResponse:
        def raise_for_status(self):
            return None

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self.payload

    def post(url, json, timeout=20):
        calls.append(url)
        if url.endswith('/api/chat'):
            return Response({'message': {'role': 'assistant', 'content': 'No tool selected.'}})
        return Response({'response': 'I cannot see a matching live home fact.'})

    main.requests.get = lambda url, timeout=2: HealthResponse()
    main.requests.post = post

    answer = main.ollama_answer('is anything unusual at home?')

    assert answer['intent'] == 'ollama_answer'
    assert calls == [
        'http://ollama.local:11434/api/chat',
        'http://ollama.local:11434/api/generate',
    ]


def test_ollama_answer_skips_fast_when_health_check_is_offline():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.CONFIG['ollama_base_url'] = 'http://offline.local:11434'
    main.CONFIG['ollama_model'] = 'qwen2.5:3b'
    main.CONFIG['ollama_health_timeout_seconds'] = 1
    post_called = {'value': False}

    def get(url, timeout=2):
        raise RuntimeError('host unreachable')

    def post(url, json, timeout=20):
        post_called['value'] = True
        raise AssertionError('generate should not be called when health is offline')

    main.requests.get = get
    main.requests.post = post

    answer = main.ollama_answer('anything unusual?')

    assert answer['intent'] == 'ollama_offline'
    assert answer['success'] is False
    assert 'Basic HomeBrain commands are still available' in answer['message']
    assert answer['ollama']['online'] is False
    assert post_called['value'] is False


def test_ollama_health_disabled_message_points_to_addon_options():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = False
    main.CONFIG['ollama_base_url'] = 'http://192.168.1.199:11434'

    health = main.ollama_health(force=True)

    assert health['online'] is False
    assert 'disabled in HomeBrain OS add-on options' in health['message']
    assert 'ollama_enabled' in health['message']
    assert health['base_url'] == 'http://192.168.1.199:11434'


def test_assistant_reports_required_settings_state():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = False
    main.CONFIG['auto_live_sync_enabled'] = False
    main.CONFIG['ollama_base_url'] = 'http://homeassistant.local:11434'

    answer = main.assistant('are required settings enabled?')

    assert answer['intent'] == 'settings_check'
    assert 'Local AI: disabled' in answer['message']
    assert 'Auto live sync: disabled' in answer['message']
    assert 'ollama_enabled' in answer['message']


def test_event_diagnostics_has_distinct_answer():
    main = load_addon_main()
    main.UI_STATS['events_received'] = 4
    main.UI_STATS['events_ui_relevant'] = 2
    main.UI_STATS['events_ignored_for_ui'] = 1
    main.UI_STATS['last_event_at'] = time.time()

    answer = main.assistant('event diagnostics')

    assert answer['intent'] == 'event_diagnostics'
    assert 'Device event diagnostics:' in answer['message']
    assert 'Events received: 4' in answer['message']


def test_event_diagnostics_formats_recent_events():
    main = load_addon_main()
    main.EVENT_HISTORY[:] = [
        {'device_id': '7107', 'label': 'Washing Machine (MQTT)', 'attr': 'power', 'value': '101', 'ui_relevant': True},
    ]

    answer = main.assistant('device events')

    assert answer['intent'] == 'event_diagnostics'
    assert 'Washing Machine (MQTT) power 101 (UI)' in answer['message']
    assert "{'device_id'" not in answer['message']


def test_heating_status_uses_control_mode_when_thermostat_mode_missing():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'trv1',
            'label': 'Livingroom TRV',
            'category': 'thermostat',
            'temperature': 28,
            'attributes': {
                'controlMode': 'onOff',
                'heatingSetpoint': 12,
            },
        },
    ]

    answer = main.assistant('heating status')

    assert answer['intent'] == 'heating_status'
    assert 'Livingroom TRV: mode onOff' in answer['message']


def test_heating_status_polls_detail_when_mode_missing():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'trv1',
            'label': 'Livingroom TRV',
            'category': 'thermostat',
            'temperature': 28,
            'attributes': {
                'heatingSetpoint': 12,
            },
        },
    ]
    updates = []
    main.fetch_live_device_detail = lambda device_id: {
        'id': device_id,
        'label': 'Livingroom TRV',
        'category': 'thermostat',
        'temperature': 28,
        'attributes': {
            'controlMode': 'onOff',
            'heatingSetpoint': 12,
        },
    }
    main.update_cached_device_snapshot = lambda device: updates.append(device)

    answer = main.assistant('heating status')

    assert answer['intent'] == 'heating_status'
    assert 'Livingroom TRV: mode onOff' in answer['message']
    assert updates and updates[0]['id'] == 'trv1'


def test_ai_status_checks_ollama_before_room_status():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.CONFIG['ollama_base_url'] = 'http://192.168.1.199:11434'
    main.CONFIG['ollama_model'] = 'qwen2.5:3b'
    main.OLLAMA_HEALTH.update({
        'checked_at': time.time(),
        'online': True,
        'message': 'Local AI is online',
        'base_url': 'http://192.168.1.199:11434',
        'model': 'qwen2.5:3b',
    })
    main.all_devices = lambda: [
        {
            'id': 'fan1',
            'label': 'Ventilation Fan',
            'room': 'Ventilation',
            'category': 'switch',
            'attributes': {},
        },
    ]

    answer = main.assistant('AI status')

    assert answer['intent'] == 'ai_status'
    assert 'Ollama: online' in answer['message']
    assert 'qwen2.5:3b' in answer['message']


def test_ollama_answer_marks_truncated_responses():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.CONFIG['ollama_include_hub_logs'] = False
    main.CONFIG['ollama_base_url'] = 'http://ollama.local:11434'
    main.CONFIG['ollama_model'] = 'qwen2.5:3b'
    main.CONFIG['ollama_timeout_seconds'] = 75
    main.CONFIG['ollama_num_predict'] = 90
    main.all_devices = lambda: []

    class HealthResponse:
        def raise_for_status(self):
            return None

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {'response': 'The home looks stable but the living room', 'done_reason': 'length'}

    main.requests.get = lambda url, timeout=2: HealthResponse()
    main.requests.post = lambda url, json, timeout=20: Response()

    answer = main.ollama_answer('summary')

    assert answer['intent'] == 'ollama_answer'
    assert answer['truncated'] is True
    assert answer['message'].endswith('...')
    assert answer['speech'].endswith('...')


def test_unknown_question_falls_back_to_local_ai():
    main = load_addon_main()
    main.all_devices = lambda: []
    asked = []
    main.ollama_answer = lambda text: asked.append(text) or {'success': True, 'intent': 'ollama_answer', 'message': 'AI fallback answered.'}

    answer = main.assistant('could the house be more comfortable later?')

    assert asked == ['could the house be more comfortable later?']
    assert answer['intent'] == 'ollama_answer'
    assert answer['message'] == 'AI fallback answered.'


def test_failed_control_request_does_not_fall_back_to_ai():
    main = load_addon_main()
    main.all_devices = lambda: []
    main.ollama_answer = lambda text: (_ for _ in ()).throw(AssertionError('Control failures should not go to AI'))

    answer = main.assistant('turn on imaginary lamp')

    assert answer['success'] is False
    assert 'Device not found' in answer['message']


def test_heating_commands_adjust_setpoints_without_thermostat_mode():
    main = load_addon_main()
    devices = [
        {
            'id': 'trv1',
            'label': 'Hallway TRV',
            'name': 'Hallway TRV',
            'room': 'Hallway',
            'category': 'thermostat',
            'temperature': 20,
            'heatingSetpoint': 19,
        },
    ]
    main.all_devices = lambda: devices
    commands = []
    main.maker_command_value = lambda device_id, command, value: commands.append((device_id, command, value))
    main.refresh_devices = lambda: None
    main.update_cached_setpoint = lambda device_id, setpoint: None

    on_answer = main.set_heating_mode('heat', 'hallway')
    devices[0]['heatingSetpoint'] = 22
    off_answer = main.set_heating_mode('off', 'hallway')

    command_names = [command for _, command, _ in commands]
    assert 'setThermostatMode' not in command_names
    assert ('trv1', 'setHeatingSetpoint', 21) in commands
    assert ('trv1', 'setHeatingSetpoint', 12) in commands
    assert 'Heating setpoints raised' in on_answer['message']
    assert 'Heating setpoints lowered' in off_answer['message']


def test_assistant_sets_room_heating_to_explicit_setpoint():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'trv1',
            'label': 'Hallway TRV',
            'name': 'Hallway TRV',
            'room': 'Hallway',
            'category': 'thermostat',
            'temperature': 20,
            'heatingSetpoint': 18,
        },
        {
            'id': 'trv2',
            'label': 'Bedroom 1 TRV',
            'name': 'Bedroom 1 TRV',
            'room': 'Bedroom 1',
            'category': 'thermostat',
            'temperature': 20,
            'heatingSetpoint': 18,
        },
    ]
    commands = []
    main.maker_command_value = lambda device_id, command, value: commands.append((device_id, command, value))
    main.refresh_devices = lambda: None
    main.update_cached_setpoint = lambda device_id, setpoint: {'id': device_id, 'heatingSetpoint': setpoint}

    answer = main.assistant('set hallway heating to 21')

    assert answer['success'] is True
    assert commands == [('trv1', 'setHeatingSetpoint', 21.0)]
    assert answer['speech'] == 'Hallway TRV set to 21 degrees.'


def test_assistant_reports_active_devices_in_named_room():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Hallway Light', 'room': 'Hallway', 'category': 'light', 'switch': 'on'},
        {'id': 's1', 'label': 'Hallway Plug', 'room': 'Hallway', 'category': 'switch', 'switch': 'off'},
        {
            'id': 'trv1',
            'label': 'Hallway TRV',
            'room': 'Hallway',
            'category': 'thermostat',
            'thermostatOperatingState': 'heating',
            'heatingSetpoint': 22,
        },
        {'id': 'b1', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on'},
    ]

    answer = main.assistant('what is on in hallway')

    assert answer['intent'] == 'room_on_status'
    assert 'Hallway active now:' in answer['message']
    assert 'Lights on: Hallway Light' in answer['message']
    assert 'Hallway TRV heating' in answer['message']
    assert 'Hallway Plug' not in answer['message']
    assert 'Bedroom Light' not in answer['message']
    assert answer['speech'] == 'Hallway: Hallway Light on and Hallway TRV heating.'


def test_exact_tv_state_never_selects_unrelated_switch():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'tv', 'label': 'TV', 'name': 'Innr SP 242 Power Metering SmartPlug', 'room': 'Multimedia', 'category': 'device', 'switch': 'off'},
        {'id': 'vac', 'label': 'Roborock Q7 Max', 'name': 'Roborock Q7 Max', 'room': 'Appliances', 'category': 'device', 'switch': 'on'},
    ]

    answer = main.cache_first_assistant_answer('is the tv on')
    assert answer['intent'] == 'named_switch_state'
    assert answer['message'] == 'TV is off.'
    assert answer['device'] == 'TV'


def test_voice_dtv_alias_resolves_exact_tv_state():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'tv', 'label': 'TV', 'name': 'Innr SP 242 Power Metering SmartPlug', 'room': 'Multimedia', 'category': 'device', 'switch': 'off'},
        {'id': 'vac', 'label': 'Roborock Q7 Max', 'name': 'Roborock Q7 Max', 'room': 'Appliances', 'category': 'device', 'switch': 'on'},
    ]

    answer = main.cache_first_assistant_answer('is dtv on')
    assert answer['message'] == 'TV is off.'


def test_contracted_bathroom_on_query_uses_logical_room_devices():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Bathroom Light 1', 'room': 'Bathroom', 'category': 'light', 'switch': 'off'},
        {'id': 'l2', 'label': 'Bathroom Light 2', 'room': 'Bathroom', 'category': 'light', 'switch': 'on'},
        {'id': 'm1', 'label': 'Aqara Bathroom Motion', 'room': 'Bathroom', 'category': 'motion_sensor', 'motion': 'inactive'},
        {'id': 'meter', 'label': 'Bathroom meter', 'room': 'Ventilation', 'category': 'climate_sensor', 'temperature': 24.5, 'humidity': 52},
        {'id': 'other', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on'},
    ]

    answer = main.assistant("what's on in the bathroom?")
    assert answer['intent'] == 'room_on_status'
    assert 'Lights on: Bathroom Light 2' in answer['message']
    assert 'Bedroom Light' not in answer['message']


def test_metering_smartplug_dehumidifier_is_controllable():
    main = load_addon_main()
    device = {
        'id': '5313',
        'label': 'Dehumidifier 1',
        'name': 'Tuya Zigbee Metering SmartPlug',
        'room': 'Dehumidifier',
        'category': 'device',
    }
    commands = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.verify_device_attribute = lambda *_args, **_kwargs: {'status': 'skipped', 'confirmed': False}
    main.update_cached_switch = lambda device_ids, switch: [{'id': device_id, 'switch': switch} for device_id in device_ids]

    assert main.is_switchable_device(device) is True
    answer = main.command_devices([device], 'on')

    assert answer['success'] is True
    assert commands == [('5313', 'on')]
    assert 'Turned on:' in answer['message']
    assert 'Dehumidifier 1' in answer['message']


def test_bedroom_activity_is_room_scoped_lists_all_states_and_power():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Bedroom 1 Light 1', 'room': 'Bedroom 1', 'category': 'light', 'switch': 'on'},
        {'id': 'l2', 'label': 'Bedroom 1 Light 2', 'room': 'Bedroom 1', 'category': 'light', 'switch': 'off'},
        {'id': 's1', 'label': 'Bedroom1 (MQTT)', 'room': 'Sockets', 'category': 'switch', 'switch': 'on'},
        {'id': 'p1', 'label': 'Bedroom1 (MQTT) power', 'room': 'Sockets', 'category': 'power_device', 'power': 4},
        {'id': 'p3', 'label': 'Bedroom3 PC (MQTT)', 'room': 'Sockets', 'category': 'power_device', 'switch': 'on', 'power': 49},
    ]

    answer = main.cache_first_assistant_answer("what's on in bedroom 1")

    assert answer['intent'] == 'room_on_status'
    assert 'Lights on: Bedroom 1 Light 1' in answer['message']
    assert 'Other switches on: Bedroom1 (MQTT)' in answer['message']
    assert 'Bedroom1 (MQTT) power: 4W' in answer['message']
    assert 'Bedroom 1 Light 2' not in answer['message']
    assert 'Bedroom3 PC' not in answer['message']


def test_living_room_activity_cannot_fall_through_to_global_power_lookup():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'lr1', 'label': 'Livingroom Light 1', 'room': 'Living Room', 'category': 'light', 'switch': 'on'},
        {'id': 'lr2', 'label': 'Livingroom socket', 'room': 'Sockets', 'category': 'switch', 'switch': 'on', 'power': 7},
        {'id': 'p3', 'label': 'Bedroom3 PC (MQTT)', 'room': 'Sockets', 'category': 'power_device', 'switch': 'on', 'power': 49},
    ]

    answer = main.cache_first_assistant_answer("what's on in the livingroom")

    assert answer['intent'] == 'room_on_status'
    assert 'Livingroom Light 1' in answer['message']
    assert 'Livingroom socket' in answer['message']
    assert 'Livingroom socket: 7W' in answer['message']
    assert 'Bedroom3 PC' not in answer['message']


def test_assistant_turns_device_on_for_duration_and_schedules_off():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'fan1', 'label': 'Desk Fan', 'name': 'Desk Fan', 'room': 'Office', 'category': 'switch', 'switch': 'off'},
    ]
    commands = []
    timers = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.refresh_devices = lambda: None
    main.update_cached_switch = lambda device_ids, switch: [{'id': device_id, 'switch': switch} for device_id in device_ids]
    main.schedule_delayed_command = lambda device_ids, command, seconds, labels: timers.append((device_ids, command, seconds, labels)) or {'due_at': 123}

    answer = main.assistant('turn on desk fan for 10 minutes')

    assert answer['success'] is True
    assert commands == [('fan1', 'on')]
    assert timers == [(['fan1'], 'off', 600, ['Desk Fan'])]
    assert 'Scheduled off in 10 minutes.' in answer['message']


def test_assistant_schedules_room_lights_with_in_duration_phrase():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'h1', 'label': 'Hallway Light 1', 'name': 'Hallway Light 1', 'room': 'Hallway', 'category': 'light', 'switch': 'off'},
        {'id': 'h2', 'label': 'Hallway Light 2', 'name': 'Hallway Light 2', 'room': 'Hallway', 'category': 'light', 'switch': 'off'},
        {'id': 'b1', 'label': 'Bedroom Light', 'name': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'off'},
    ]
    commands = []
    timers = []
    main.maker_command = lambda device_id, command: commands.append((device_id, command))
    main.schedule_delayed_command = lambda device_ids, command, seconds, labels: timers.append((device_ids, command, seconds, labels)) or {'due_at': 123}

    answer = main.assistant('turn on hallway lights in 15 seconds')

    assert answer['success'] is True
    assert answer['intent'] == 'scheduled_command'
    assert commands == []
    assert timers == [(['h1', 'h2'], 'on', 15, ['Hallway Light 1', 'Hallway Light 2'])]
    assert 'Scheduled on in 15 seconds' in answer['message']


def test_scheduled_timers_are_persisted_and_cancelled():
    main = load_addon_main()

    class FakeTimer:
        def __init__(self, seconds, function, args=()):
            self.seconds = seconds
            self.function = function
            self.args = args
            self.cancelled = False
            self.started = False

        def start(self):
            self.started = True

        def cancel(self):
            self.cancelled = True

    original_timer = main.threading.Timer
    original_db_path = main.DB_PATH
    main.threading.Timer = FakeTimer
    main.ACTIVE_TIMER_THREADS.clear()
    main.PENDING_DEVICE_TIMERS.clear()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'

            timer = main.schedule_delayed_command(['fan1'], 'off', 600, ['Desk Fan'])
            records = main.pending_timer_records()

            assert len(records) == 1
            assert records[0]['id'] == timer['id']
            assert records[0]['labels'] == ['Desk Fan']
            assert records[0]['command'] == 'off'
            assert main.ACTIVE_TIMER_THREADS[timer['id']].started is True

            result = main.cancel_timer(timer['id'])

            assert result['success'] is True
            assert main.pending_timer_records() == []
            assert timer['id'] not in main.PENDING_DEVICE_TIMERS
    finally:
        main.threading.Timer = original_timer
        main.DB_PATH = original_db_path
        main.ACTIVE_TIMER_THREADS.clear()
        main.PENDING_DEVICE_TIMERS.clear()


def test_assistant_lists_only_people_home():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'e', 'label': 'Enamul Presence', 'room': 'People', 'category': 'presence_sensor', 'presence': 'present'},
        {'id': 's', 'label': 'Samah Presence', 'room': 'People', 'category': 'presence_sensor', 'presence': 'not present'},
        {'id': 't', 'label': 'Tahmid Presence', 'room': 'People', 'category': 'presence_sensor', 'presence': 'away'},
    ]

    people = main.assistant('who is home')

    assert 'Enamul' in people['message']
    assert 'Samah' not in people['message']
    assert 'Tahmid' not in people['message']


def test_fridge_meter_is_excluded_from_temperature_and_humidity_averages():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'sensor', 'label': 'Hallway Sensor', 'room': 'Hallway', 'category': 'climate_sensor', 'temperature': 20, 'humidity': 40},
        {'id': 'fridge', 'label': 'Fridge Meter', 'room': 'Kitchen', 'category': 'climate_sensor', 'temperature': 4, 'humidity': 80},
    ]

    summary = main.dashboard_summary()
    rooms = main.api_rooms()['rooms']
    kitchen = next(room for room in rooms if room['room'] == 'Kitchen')

    assert summary['avg_temperature'] == 20
    assert summary['avg_humidity'] == 40
    assert kitchen['avg_temperature'] is None
    assert kitchen['avg_humidity'] is None


def test_dashboard_and_rooms_include_numeric_string_climate_values_immediately():
    main = load_addon_main()
    main.SUMMARY_CACHE = None
    main.all_devices = lambda: [
        {
            'id': 'hallway', 'label': 'Hallway Sensor', 'room': 'Hallway',
            'category': 'climate_sensor', 'temperature': '24.5', 'humidity': '42',
        },
        {
            'id': 'living', 'label': 'Living Room Sensor', 'room': 'Living Room',
            'category': 'climate_sensor', 'temperature': 25.5, 'humidity': 48,
        },
        {
            'id': 'weather', 'label': 'Weather Open-Meteo', 'room': 'Weather',
            'category': 'climate_sensor', 'temperature': '17', 'humidity': '90',
        },
    ]

    summary = main.compute_dashboard_summary({'synced': False, 'reason': 'startup-cache'})
    rooms = main.api_rooms()['rooms']
    hallway = next(room for room in rooms if room['room'] == 'Hallway')

    assert summary['avg_temperature'] == 25
    assert summary['avg_humidity'] == 45
    assert hallway['avg_temperature'] == 24.5
    assert hallway['avg_humidity'] == 42


def test_room_intelligence_includes_numeric_string_climate_values():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'bathroom', 'label': 'Bathroom Meter', 'room': 'Bathroom',
        'category': 'climate_sensor', 'temperature': '23.4', 'humidity': '61',
    }]

    answer = main.room_intelligence_answer('room summary bathroom')

    assert answer is not None
    assert 'Temperature: 23.4°C' in answer['message']
    assert 'Humidity: 61.0%' in answer['message']


def test_assistant_motion_rooms_lists_only_active_motion_sensors():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'm1', 'label': 'Kitchen Motion', 'room': 'Kitchen', 'category': 'motion_sensor', 'motion': 'active'},
        {'id': 'm2', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'inactive'},
        {'id': 'l1', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on', 'level': 30},
        {'id': 'l2', 'label': 'Bedroom Lamp', 'room': 'Bedroom', 'category': 'light', 'switch': 'off'},
        {'id': 's1', 'label': 'Dehumidifier Socket', 'room': 'Dehumidifier', 'category': 'power_device', 'switch': 'on', 'power': 42},
        {'id': 'p1', 'label': 'Enamul', 'room': 'Life360', 'category': 'presence_sensor', 'presence': 'present'},
    ]

    active_rooms = main.assistant('which rooms have motion active')

    assert active_rooms['intent'] == 'active_motion_rooms'
    assert 'Kitchen: Kitchen Motion' in active_rooms['message']
    assert 'Bedroom Light' not in active_rooms['message']
    assert 'Dehumidifier Socket' not in active_rooms['message']
    assert 'Hallway Motion' not in active_rooms['message']
    assert 'Bedroom Lamp' not in active_rooms['message']
    assert 'Life360' not in active_rooms['message']


def test_assistant_device_health_reports_low_batteries():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'b1', 'label': 'Hallway Contact', 'room': 'Hallway', 'category': 'contact_sensor', 'battery': 12},
        {'id': 's1', 'label': 'Lamp', 'room': 'Living Room', 'category': 'switch', 'switch': None},
    ]

    health = main.assistant('device health')

    assert health['intent'] == 'device_health'
    assert 'Low batteries: 1' in health['message']
    assert 'Hallway Contact' in health['message']


def test_room_summary_distinguishes_sockets_from_lights_and_keeps_power():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'd1', 'label': 'Dehumidifier Socket', 'room': 'Dehumidifier', 'category': 'power_device', 'switch': 'off', 'power': 0},
        {'id': 'd2', 'label': 'Dehumidifier Meter', 'room': 'Dehumidifier', 'category': 'power_device', 'switch': 'on', 'power': 12.4},
        {'id': 'l1', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on'},
        {'id': 'k1', 'label': 'Kitchen Plug', 'room': 'Kitchen', 'category': 'switch', 'switch': 'off', 'power': 0},
    ]

    rooms = main.api_rooms()['rooms']
    room_names = [room['room'] for room in rooms]
    dehumidifier = next(room for room in rooms if room['room'] == 'Dehumidifier')
    bedroom = next(room for room in rooms if room['room'] == 'Bedroom')

    assert room_names[0] == 'Bedroom'
    assert room_names.index('Dehumidifier') < room_names.index('Kitchen')
    assert dehumidifier['lights_total'] == 0
    assert dehumidifier['sockets_total'] == 2
    assert dehumidifier['sockets_on'] == 1
    assert dehumidifier['motion_total'] == 0
    assert dehumidifier['power_devices'] == 2
    assert dehumidifier['power_total'] == 12.4
    assert bedroom['lights_total'] == 1
    assert bedroom['switches_total'] == 0


def test_room_summary_shows_motion_capable_devices_with_missing_state():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'm1',
            'label': 'Bedroom 3 Light Sensor',
            'room': 'Bedroom 3',
            'category': 'light_sensor',
            'capabilities': ['MotionSensor', 'IlluminanceMeasurement'],
            'attributes': {'motion': None, 'illuminance': 269},
            'motion': None,
        },
        {'id': 'l1', 'label': 'Bedroom 3 Light', 'room': 'Bedroom 3', 'category': 'light', 'switch': 'off'},
    ]

    bedroom = next(room for room in main.api_rooms()['rooms'] if room['room'] == 'Bedroom 3')

    assert bedroom['lights_total'] == 1
    assert bedroom['motion_total'] == 1
    assert bedroom['motion_active'] == 0


def test_room_summary_does_not_show_presence_as_room_signal():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'p1', 'label': 'Enamul', 'room': 'Life360', 'category': 'presence_sensor', 'presence': 'present'},
        {'id': 'p2', 'label': 'Samah', 'room': 'Life360', 'category': 'presence_sensor', 'presence': 'not present'},
    ]

    life360 = next(room for room in main.api_rooms()['rooms'] if room['room'] == 'Life360')

    assert 'presence_total' not in life360
    assert main.room_visible_signals(life360) == []


def test_room_details_explain_visible_signals_and_devices():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'l1', 'label': 'Bedroom 3 Light', 'room': 'Bedroom 3', 'category': 'light', 'switch': 'off'},
        {
            'id': 'm1',
            'label': 'Bedroom 3 Motion',
            'room': 'Bedroom 3',
            'category': 'motion_sensor',
            'capabilities': ['MotionSensor'],
            'motion': None,
            'attributes': {'motion': None},
        },
    ]

    details = main.room_details_payload('Bedroom 3')

    assert details['room']['lights_total'] == 1
    assert details['room']['motion_total'] == 1
    assert details['visible_signals'] == ['lights', 'motion']
    assert 'Active now: none' in details['explanation']
    assert 'Signals: lights, motion' in details['explanation']
    assert [device['label'] for device in details['devices']] == ['Bedroom 3 Light', 'Bedroom 3 Motion']


def test_room_details_explain_empty_signal_rooms():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'app1', 'label': 'Calendar App', 'room': 'Apps', 'category': 'device'},
    ]

    details = main.room_details_payload('Apps')

    assert details['visible_signals'] == []
    assert 'Active now: none' in details['explanation']
    assert 'No summarized signals yet' in details['explanation']
    assert details['devices'][0]['label'] == 'Calendar App'


def test_assistant_explains_named_room_tile():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'p1', 'label': 'Enamul', 'room': 'Life360', 'category': 'presence_sensor', 'presence': 'present'},
    ]

    answer = main.assistant('explain Life360 room')

    assert answer['intent'] == 'room_details'
    assert 'Life360: 1 devices' in answer['message']
    assert 'No summarized signals yet' in answer['message']


def test_assistant_hub_health_reads_hub_info_device_metrics():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'hub',
            'label': 'Hub Info',
            'room': 'Hub',
            'category': 'device',
            'attributes': {'cpuPct': 12.5, 'freeMemory': '512 MB', 'uptime': '2 days'},
        },
    ]

    health = main.assistant('hub health')

    assert health['intent'] == 'hub_health'
    assert 'CPU load: 12.5' in health['message']
    assert 'Free memory: 512MB' in health['message']


def test_assistant_hub_health_reads_hub_info_html_labels():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'hub',
            'label': 'Hub Info',
            'room': 'Hub',
            'category': 'device',
            'attributes': {
                'Html': '''
                    Free Mem : 1.0 GB
                    CPU Load/Load% : 0.8 / 20.0 %
                    DB Size : 199 MB
                    Last Restart : 03Jul2026 14:42
                    Uptime : 0d:0h:31m:46s
                    Temperature : 46.2 °C
                ''',
            },
        },
    ]

    health = main.assistant('hub health')

    assert 'Free memory: 1GB' in health['message']
    assert 'CPU load: 0.8 / 20.0 %' in health['message']
    assert 'DB size: 199 MB' in health['message']
    assert 'Last restart: 03 Jul 2026 14:42' in health['message']
    assert 'Uptime: 31m 46s' in health['message']
    assert 'Temperature: 46.2 °C' in health['message']


def test_status_hub_health_summary_colours_cpu_and_memory():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'hub',
            'label': 'Hub Info',
            'room': 'Hub',
            'category': 'device',
            'attributes': {
                'freeMemory': 1.01,
                'cpu': 16.75,
                'Html': 'Free Mem : 1018.46 MB\nCPU Load/Load% : 0.88 / 22.0 %',
            },
        },
    ]

    summary = main.hub_health_summary()

    assert summary['level'] == 'ok'
    assert summary['cpu_load_percent'] == 22
    assert summary['free_memory_mb'] == 1018.46
    assert summary['label'] == 'Hub CPU 22% · Free 1.02GB'


def test_status_hub_health_summary_prefers_live_hub_info_page():
    main = load_addon_main()
    main.CONFIG['hubitat_base_url'] = 'http://192.168.1.239:8080'
    main.CONFIG['hub_info_refresh_seconds'] = 30
    main.LIVE_HUB_INFO_CACHE = {'checked_at': 0.0, 'device': None, 'error': None}
    main.all_devices = lambda: [
        {
            'id': 'hub',
            'label': 'Hub Info',
            'room': 'Hub',
            'category': 'device',
            'attributes': {'freeMemory': '846.06 MB', 'cpu': 24.5},
        },
    ]

    class Response:
        text = '''
        <table>
            <tr><td>Free Mem</td><td>1011.44 MB</td></tr>
            <tr><td>CPU Load/Load%</td><td>0.44 / 14.75 %</td></tr>
        </table>
        '''

        def raise_for_status(self):
            return None

    calls = []

    def get(url, timeout=3):
        calls.append((url, timeout))
        return Response()

    main.requests.get = get

    summary = main.hub_health_summary()

    assert summary['source'] == 'live_hub_info'
    assert summary['cpu_load_percent'] == 14.75
    assert summary['free_memory_mb'] == 1011.44
    assert summary['label'].startswith('Hub CPU 14.75%')
    assert summary['label'].endswith('Free 1.01GB')
    assert calls == [('http://192.168.1.239:8080/local/hubInfoOutput.html', 3)]


def test_status_hub_health_summary_falls_back_to_cached_hub_info_when_live_unavailable():
    main = load_addon_main()
    main.CONFIG['hubitat_base_url'] = 'http://hubitat.local'
    main.LIVE_HUB_INFO_CACHE = {'checked_at': 0.0, 'device': None, 'error': None}
    main.all_devices = lambda: [
        {
            'id': 'hub',
            'label': 'Hub Info',
            'room': 'Hub',
            'category': 'device',
            'attributes': {'Html': 'Free Mem : 846.06 MB\nCPU Load/Load% : 0.88 / 24.5 %'},
        },
    ]

    def get(*_args, **_kwargs):
        raise RuntimeError('offline')

    main.requests.get = get

    summary = main.hub_health_summary()

    assert summary['source'] == 'event_cache'
    assert summary['cpu_load_percent'] == 24.5
    assert summary['free_memory_mb'] == 846.06
    assert 'offline' in str(summary.get('error'))


def test_status_hub_health_summary_treats_small_plain_memory_as_gb():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'hub', 'label': 'Hub Info', 'room': 'Hub', 'category': 'device', 'attributes': {'freeMemory': 1.01, 'cpu': 16.75}},
    ]

    summary = main.hub_health_summary()

    assert summary['level'] == 'ok'
    assert summary['free_memory_mb'] == 1010
    assert summary['label'] == 'Hub CPU 16.75% · Free 1.01GB'


def test_assistant_hub_health_formats_epoch_restart_and_uptime_seconds():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'hub',
            'label': 'Hub Info',
            'room': 'Hub',
            'category': 'device',
            'attributes': {'lastRestart': 1783086156033, 'uptime': 4615, 'freeMemory': 1.01, 'cpu': 16.75},
        },
    ]

    health = main.assistant('hub health')

    assert 'Free memory: 1.01GB' in health['message']
    assert 'Last restart: 03 Jul 2026' in health['message']
    assert 'Uptime: 1h 16m 55s' in health['message']


def test_status_hub_health_summary_warns_on_low_memory_and_high_cpu():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'hub', 'label': 'Hub Info', 'room': 'Hub', 'category': 'device', 'attributes': {'Html': 'Free Mem : 300 MB\nCPU Load/Load% : 0.8 / 65.0 %'}},
    ]

    summary = main.hub_health_summary()
    assert summary['level'] == 'warning'
    assert summary['label'] == 'Hub CPU 65% · Free 300MB'

    main.all_devices = lambda: [
        {'id': 'hub', 'label': 'Hub Info', 'room': 'Hub', 'category': 'device', 'attributes': {'Html': 'Free Mem : 128 MB\nCPU Load/Load% : 0.8 / 85.0 %'}},
    ]

    assert main.hub_health_summary()['level'] == 'error'


def test_controllable_devices_sort_active_first_then_alphabetical():
    main = load_addon_main()
    devices = [
        {'id': 'off-z', 'label': 'Zeta Socket', 'name': 'Zeta Socket', 'room': 'Room', 'category': 'power_device', 'switch': 'off'},
        {'id': 'on-b', 'label': 'Bedroom Light', 'name': 'Bedroom Light', 'room': 'Room', 'category': 'light', 'switch': 'on'},
        {'id': 'off-a', 'label': 'Air Purifier', 'name': 'Air Purifier', 'room': 'Room', 'category': 'switch', 'switch': 'off'},
        {'id': 'on-a', 'label': 'Appliance Plug', 'name': 'Appliance Plug', 'room': 'Room', 'category': 'power_device', 'switch': 'on'},
    ]

    ordered = main.controllable_devices(devices)

    assert [device['label'] for device in ordered] == ['Appliance Plug', 'Bedroom Light', 'Air Purifier', 'Zeta Socket']


def test_controllable_devices_tolerates_null_switch_state():
    main = load_addon_main()
    devices = [
        {'id': 'unknown', 'label': 'Unknown Socket', 'name': 'Unknown Socket', 'room': 'Room', 'category': 'switch', 'switch': None},
        {'id': 'active', 'label': 'Active Light', 'name': 'Active Light', 'room': 'Room', 'category': 'light', 'switch': 'on'},
    ]

    ordered = main.controllable_devices(devices)

    assert [device['label'] for device in ordered] == ['Active Light', 'Unknown Socket']


def test_room_summary_merges_compact_and_spaced_numbered_bedrooms():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'b1', 'label': 'Bedroom1 Socket', 'room': 'Bedroom1', 'category': 'power_device', 'switch': 'on', 'power': 6},
        {'id': 'b2', 'label': 'Bedroom 1 Light', 'room': 'Bedroom 1', 'category': 'light', 'switch': 'on'},
        {'id': 'b3', 'label': 'Bedroom2 Socket', 'room': 'Bedroom2', 'category': 'power_device', 'switch': 'off', 'power': 2},
        {'id': 'b4', 'label': 'Bedroom 2 Sensor', 'room': 'Bedroom 2', 'category': 'climate_sensor', 'temperature': 21},
    ]

    rooms = main.api_rooms()['rooms']
    names = [room['room'] for room in rooms]
    bedroom_1 = next(room for room in rooms if room['room'] == 'Bedroom 1')
    bedroom_2 = next(room for room in rooms if room['room'] == 'Bedroom 2')

    assert 'Bedroom1' not in names
    assert 'Bedroom2' not in names
    assert bedroom_1['devices'] == 2
    assert bedroom_1['lights_on'] == 1
    assert bedroom_1['sockets_on'] == 1
    assert bedroom_2['devices'] == 2


def test_room_summary_sorts_active_rooms_alphabetically_and_ignores_socket_activity():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'z1', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'active'},
        {'id': 'a1', 'label': 'Bathroom Light', 'room': 'Bathroom', 'category': 'light', 'switch': 'on'},
        {'id': 's1', 'label': 'Dehumidifier Socket', 'room': 'Dehumidifier', 'category': 'power_device', 'switch': 'on', 'power': 22},
        {'id': 'p1', 'label': 'Family Presence', 'room': 'Climate', 'category': 'presence_sensor', 'presence': 'present'},
        {'id': 'k1', 'label': 'Kitchen Plug', 'room': 'Kitchen', 'category': 'switch', 'switch': 'off'},
    ]

    room_names = [room['room'] for room in main.api_rooms()['rooms']]
    summary = main.compute_dashboard_summary({'synced': False})
    active_answer = main.active_rooms_answer()

    assert room_names == ['Bathroom', 'Hallway', 'Climate', 'Dehumidifier', 'Kitchen']
    assert summary['active_rooms'] == 2
    assert summary['active_room_names'] == ['Bathroom', 'Hallway']
    assert active_answer['rooms'] == [
        {'room': 'Bathroom', 'active_devices': ['Bathroom Light on'], 'active_count': 1},
        {'room': 'Hallway', 'active_devices': ['Hallway Motion active'], 'active_count': 1},
    ]
    assert 'Dehumidifier' not in active_answer['message']
    assert 'Climate' not in active_answer['message']


def test_normalise_device_prefers_hubitat_room_assignment_over_label_inference():
    main = load_addon_main()

    device = main.normalise_device({
        'id': '1',
        'name': 'Bedroom 1 Plug',
        'label': 'Bedroom 1 Plug',
        'roomName': 'Office',
        'attributes': {'switch': 'off'},
    })
    nested = main.normalise_device({
        'id': '2',
        'name': 'Hallway Sensor',
        'label': 'Hallway Sensor',
        'room': {'name': 'Kitchen'},
        'attributes': {'motion': 'inactive'},
    })

    assert device['room'] == 'Office'
    assert nested['room'] == 'Kitchen'


def test_enrich_raw_devices_refreshes_stale_detail_batch():
    main = load_addon_main()
    now = int(main.time.time())
    main.CONFIG['device_detail_refresh_seconds'] = 60
    main.CONFIG['device_detail_refresh_batch'] = 1
    main.CONFIG['device_detail_refresh_limit'] = 10
    main.cached_detail_refresh_times = lambda: {'fresh': now, 'stale': now - 120}
    calls = []

    def fake_maker_get(path, timeout=20):
        calls.append(path)
        return {'id': 'stale', 'label': 'Stale Light', 'room': 'Hallway', 'attributes': {'switch': 'on'}}

    main.maker_get = fake_maker_get

    enriched = main.enrich_raw_devices([
        {'id': 'fresh', 'label': 'Fresh Light', 'room': 'Hallway', 'attributes': {'switch': 'off'}},
        {'id': 'stale', 'label': 'Stale Light', 'room': 'Hallway', 'attributes': {'switch': 'off'}},
        {'id': 'later', 'label': 'Later Light', 'room': 'Hallway', 'attributes': {'switch': 'off'}},
    ])
    normalised = {device['id']: device for device in [main.normalise_device(raw) for raw in enriched]}

    assert calls == ['devices/stale']
    assert normalised['fresh']['switch'] == 'off'
    assert normalised['stale']['switch'] == 'on'
    assert normalised['later']['switch'] == 'off'


def test_room_summary_treats_app_and_multimedia_switches_as_sockets():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'a1', 'label': 'Server Switch', 'room': 'Apps', 'category': 'switch', 'switch': 'off'},
        {'id': 'm1', 'label': 'TV Switch', 'room': 'Multimedia', 'category': 'switch', 'switch': 'on', 'power': 4},
    ]

    rooms = main.api_rooms()['rooms']
    apps = next(room for room in rooms if room['room'] == 'Apps')
    multimedia = next(room for room in rooms if room['room'] == 'Multimedia')

    assert apps['sockets_total'] == 1
    assert apps['sockets_on'] == 0
    assert apps['motion_total'] == 0
    assert multimedia['sockets_total'] == 1
    assert multimedia['sockets_on'] == 1
    assert multimedia['power_total'] == 4


def test_dashboard_orders_rooms_before_collapsible_controllable_devices():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert html.index('<h2>Rooms</h2>') < html.index('<summary>Controllable Devices</summary>')
    assert '<details class="card collapsible">' in html


def test_dashboard_has_mobile_voice_shortcut_controls():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'id="micFab"' in html
    assert 'id="voiceOverlay"' in html
    assert "get('voice')==='1'" in html


def test_dashboard_has_voice_station_mode():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'id="stationStart"' in html
    assert 'id="stationStop"' in html
    assert 'function wakePhraseCommand' in html
    assert 'function stationCommandFromTranscript' in html
    assert 'Hey HomeBrain' in html
    assert 'function stationIsArmed' in html
    assert 'function stationListeningStatus' in html
    assert 'function armVoiceStation' in html
    assert 'armVoiceStation(18000)' in html
    assert "['no-speech','aborted'].includes" in html
    assert "urlParams.get('station')==='1'" in html
    assert 'r.continuous=true' in html
    assert 'function commandLooksComplete' in html
    assert 'stationCommandFromTranscript(transcript, result.isFinal)' in html
    assert 'stationSpeechUntil' in html
    assert 'Answering. Listening will resume in a moment' in html
    assert 'stationRestartDelay=Math.min(3500, stationRestartDelay+600)' in html
    assert 'home brain os' in html


def test_dashboard_tiles_have_visible_click_feedback():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert '.metric.summary-tile.selected,.room.selected' in html
    assert "content:'Loading'" not in html
    assert '.metric.summary-tile.loading:after' not in html
    assert 'function markActiveControl' in html
    assert "setOutput('Thinking: '+text+' (0s)')" in html
    assert "quick('summary', this)" in html


def test_dashboard_has_persisted_audio_mute_toggle():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'id="audioMuted"' in html
    assert 'homebrainos_audio_muted' in html
    assert 'function setAudioMuted' in html
    assert 'if(!audioMuted &&' in html
    assert 'Listening silently...' in html
    assert 'Audio responses are muted.' in html


def test_dashboard_has_scheduled_timer_panel():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'id="timersCard"' in html
    assert 'id="timers"' in html
    assert 'function loadTimers' in html
    assert '/api/timers' in html
    assert '/cancel' in html
    assert 'data-action="cancel-timer"' in html


def test_dashboard_room_details_output_is_compact():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'function formatRoomDetails' in html
    assert 'Active: ${active.slice' in html
    assert 'Devices: ${names.slice' in html
    assert '[${device.category}]' not in html
    assert 'Object.entries(device.attributes' not in html
    assert "setOutput('Loading '+roomName+' room details...')" not in html


def test_v08_presence_style_motion_is_not_reported_as_stale_motion():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            now = int(main.time.time())
            old = now - 3 * 3600
            main.CONFIG['stale_motion_active_minutes'] = 30
            main.CONFIG['presence_occupied_interesting_hours'] = 1
            main.upsert_devices([
                {'id': 'fp300', 'name': 'Bedroom 1 FP300', 'label': 'Bedroom 1 FP300', 'room': 'Bedroom 1', 'category': 'motion_sensor', 'motion': 'active', 'attributes': {'motion': 'active'}},
                {'id': 'pir1', 'name': 'Hallway Motion', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'active', 'attributes': {'motion': 'active'}},
            ])
            conn = main.db()
            try:
                conn.execute('UPDATE devices SET updated_at=? WHERE id IN (?, ?)', (old, 'fp300', 'pir1'))
                conn.commit()
            finally:
                conn.close()

            report = main.stale_device_report()
            answer = main.assistant('stale devices')

        assert [item['label'] for item in report['motion_active_too_long']] == ['Hallway Motion']
        assert [item['label'] for item in report['occupied_long']] == ['Bedroom 1 FP300']
        assert 'Normal occupancy, not stale' in answer['message']
        assert 'Bedroom 1 FP300 (Bedroom 1) occupied for 3 hours' in answer['message']
    finally:
        main.DB_PATH = original_db_path


def test_maker_api_event_parser_accepts_json_event_shape():
    main = load_addon_main()
    records = main.event_records_from_payload({
        'name': 'switch',
        'value': 'on',
        'displayName': 'Livingroom Light 1',
        'deviceId': '1234',
    })

    assert records == [{
        'device_id': '1234',
        'attr': 'switch',
        'value': 'on',
        'label': 'Livingroom Light 1',
        'raw': {
            'name': 'switch',
            'value': 'on',
            'displayName': 'Livingroom Light 1',
            'deviceId': '1234',
        },
    }]


def test_maker_api_event_parser_accepts_form_encoded_body():
    main = load_addon_main()
    records = main.event_records_from_payload({
        'body': 'name=motion&value=active&displayName=Kitchen+Linptech&deviceId=5386'
    })

    assert len(records) == 1
    assert records[0]['device_id'] == '5386'
    assert records[0]['attr'] == 'motion'
    assert records[0]['value'] == 'active'
    assert records[0]['label'] == 'Kitchen Linptech'


def test_cached_metric_router_is_lazy_and_does_not_hijack_open_questions():
    main = load_addon_main()
    main.dashboard_summary = lambda live=False: (_ for _ in ()).throw(
        AssertionError('Unrelated questions must not build the dashboard summary')
    )

    assert main.cached_summary_metric_answer('which lights are on') is None
    assert main.cached_summary_metric_answer('why does a room feel humid') is None


def test_open_knowledge_question_reaches_ollama_instead_of_temperature_rules():
    main = load_addon_main()
    main.all_devices = lambda: []
    asked = []
    main.ollama_answer = lambda text: asked.append(text) or {
        'success': True,
        'intent': 'ollama_answer',
        'source': 'ollama',
        'message': 'Condensation forms when moist air meets a cold surface.',
    }

    answer = main.assistant('Why does condensation form on a cold window?')

    assert asked == ['Why does condensation form on a cold window?']
    assert answer['intent'] == 'ollama_answer'


def test_battery_report_event_is_persisted_and_invalidates_authoritative_cache():
    main = load_addon_main()
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        main.upsert_devices([{
            'id': 'report1',
            'name': 'Device Status Report',
            'label': 'Device Status Report',
            'room': 'System',
            'category': 'device',
            'attributes': {},
        }])
        main._homebrain_low_battery_cache = {'at': time.time(), 'ttl': 300, 'rows': []}

        result = main.record_hubitat_events({
            'deviceId': 'report1',
            'name': 'reportHtml',
            'value': '[LOW BATTERY] Hallway Contact - 12% battery',
            'displayName': 'Device Status Report',
        })
        cached = main.all_devices()[0]
        conn = main.db()
        try:
            row = conn.execute("SELECT attr, value FROM hubitat_events WHERE attr='reportHtml'").fetchone()
        finally:
            conn.close()

    assert result['events'] == 1
    assert result['updated'] == 1
    assert row['attr'] == 'reportHtml'
    assert 'Hallway Contact' in row['value']
    assert 'Hallway Contact' in cached['attributes']['reportHtml']
    assert not hasattr(main, '_homebrain_low_battery_cache')


def test_event_history_indexes_are_created_for_duration_queries():
    main = load_addon_main()
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        conn = main.db()
        try:
            indexes = {
                row['name']
                for table in ('history', 'hubitat_events')
                for row in conn.execute(f'PRAGMA index_list({table})').fetchall()
            }
        finally:
            conn.close()

    assert 'idx_history_device_attr_created' in indexes
    assert 'idx_hubitat_events_device_attr_created' in indexes


def test_sensitive_event_raw_payload_is_redacted_before_persistence_helpers():
    main = load_addon_main()
    redacted = main.redact_event_raw('tile', {
        'name': 'tile',
        'value': '<div>Map pin 51.501234,-0.141234</div>',
        'location': '51.501234,-0.141234',
        'displayName': 'Life360 Person',
    })

    assert '[tile payload omitted]' in redacted['value']
    assert '[location payload omitted]' in redacted['location']
    assert 'Life360 Person' in redacted['displayName']
    assert '51.501234' not in json.dumps(redacted)


def test_prune_event_history_removes_old_rows_and_keeps_recent_rows():
    main = load_addon_main()
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        main.CONFIG['event_retention_days'] = 30
        main.LAST_EVENT_PRUNE_AT = 0
        now = int(time.time())
        old = now - 40 * 86400
        recent = now - 2 * 86400
        conn = main.db()
        try:
            conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', ('old', 'switch', 'on', old))
            conn.execute('INSERT INTO history(device_id,attr,value,created_at) VALUES(?,?,?,?)', ('new', 'switch', 'off', recent))
            conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('old', 'Old', 'switch', 'on', '{}', old))
            conn.execute('INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)', ('new', 'New', 'switch', 'off', '{}', recent))
            conn.commit()
        finally:
            conn.close()

        result = main.prune_event_history('test', force=True)

        conn = main.db()
        try:
            history_ids = [row['device_id'] for row in conn.execute('SELECT device_id FROM history ORDER BY device_id').fetchall()]
            event_ids = [row['device_id'] for row in conn.execute('SELECT device_id FROM hubitat_events ORDER BY device_id').fetchall()]
        finally:
            conn.close()

    assert result['history_rows'] == 1
    assert result['event_rows'] == 1
    assert history_ids == ['new']
    assert event_ids == ['new']


def test_assistant_output_is_next_to_prompt_and_reports_elapsed_time():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert html.count('id="out"') == 1
    assert html.index('id="out"') < html.index('id="shortcutsCard"')
    assert "details.push(elapsed+'s')" in html


def test_integrated_dashboard_handles_event_cached_status_report():
    main = load_addon_main()
    natural_path = Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'natural_intelligence.py'
    spec = importlib.util.spec_from_file_location('homebrainos_natural_integration', natural_path)
    natural = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = natural
    spec.loader.exec_module(natural)

    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        main.upsert_devices([
            {'id': '7182', 'name': 'Device Status Report Display', 'label': 'Device Status Report Display', 'room': 'Apps', 'category': 'device', 'capabilities': [{'name': 'Refresh'}, {'name': 'Actuator'}], 'attributes': {}},
            {'id': '4718', 'name': 'Tuya TRV602Z TRV', 'label': 'Livingroom TRV', 'room': 'Thermostat Trv S', 'category': 'thermostat', 'attributes': {}},
            {'id': '5401', 'name': 'Zigbee Door Contact', 'label': 'Fridge Door', 'room': 'Appliances', 'category': 'device', 'attributes': {}},
        ])
        main.rebuild_summary_cache('test')
        natural.register(main)
        main.record_hubitat_events({
            'deviceId': '7182',
            'name': 'reportText',
            'displayName': 'Device Status Report Display',
            'value': 'Device Status Notifier - Current Status\n\n[LOW BATTERY] Below 20%\nLivingroom TRV - 12% battery - last seen 25m ago\nFridge Door - 19% battery - last seen 2h ago\n\n[OK]\nNone',
        })

        summary = main.dashboard_summary(live=False)
        context = main.ai_context_pack()

    assert summary['low_batteries'] == 2, summary['low_battery_devices']
    assert [item['label'] for item in summary['low_battery_devices']] == ['Livingroom TRV', 'Fridge Door']
    assert context['summary']['low_batteries'] == 2


def test_partial_full_refresh_preserves_event_backed_attributes():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            main.upsert_devices([{
                'id': 'report1', 'name': 'Device Status Report', 'label': 'Device Status Report',
                'room': 'System', 'category': 'device', 'motion': 'active',
                'attributes': {
                    'motion': 'active',
                    'reportText': '[LOW BATTERY]\nHallway Contact - 12% battery\n[OK]\nNone',
                },
            }])
            main.upsert_devices([{
                'id': 'report1', 'name': 'Device Status Report', 'label': 'Device Status Report',
                'room': 'System', 'category': 'device', 'motion': None, 'attributes': {},
            }])
            cached = main.all_devices()[0]

        assert cached['motion'] == 'active'
        assert 'Hallway Contact' in cached['attributes']['reportText']
    finally:
        main.DB_PATH = original_db_path


def test_dashboard_merges_low_batteries_from_cached_status_report():
    main = load_addon_main()
    main.SUMMARY_CACHE = None
    main.all_devices = lambda: [
        {
            'id': 'report1', 'name': 'Device Status Report', 'label': 'Device Status Report',
            'room': 'System', 'category': 'device',
            'attributes': {'reportText': '[LOW BATTERY]\nHallway Contact - 12% battery\n[OK]\nNone'},
        },
        {'id': 'contact1', 'name': 'Hallway Contact', 'label': 'Hallway Contact', 'room': 'Hallway', 'category': 'contact_sensor', 'attributes': {}},
    ]

    summary = main.compute_dashboard_summary({'synced': False})

    assert summary['low_batteries'] == 1
    assert summary['low_battery_devices'][0]['label'] == 'Hallway Contact'
    assert summary['low_battery_devices'][0]['battery'] == 12


def test_cache_first_device_health_never_starts_live_detail_scan():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'report1', 'name': 'Device Status Report', 'label': 'Device Status Report',
        'room': 'System', 'category': 'device',
        'attributes': {
            'offlineCount': 0,
            'lowBatteryCount': 1,
            'reportText': '[LOW BATTERY]\nHallway Contact - 12% battery\n[OK]\nNone',
        },
    }]
    main.refresh_health_device_details = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('live scan called'))

    answer = main.cache_first_assistant_answer('device health')

    assert answer['intent'] == 'device_health'
    assert 'Hallway Contact' in answer['message']


def test_cached_weather_does_not_repeat_current_temperature():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'weather1', 'name': 'Weather', 'label': 'Weather Open-Meteo',
        'room': 'Weather', 'category': 'weather',
        'attributes': {
            'weatherSummaryLine': 'Overcast, High 27C, Low 16C, Current 22C',
            'temperature': 21.9,
            'humidity': 65,
        },
    }]

    answer = main.cached_weather_answer()

    assert answer['message'].lower().count('current') == 1
    assert 'current 21.9' not in answer['message'].lower()


def test_event_diagnostics_omits_rich_location_payloads():
    main = load_addon_main()
    main.EVENT_HISTORY[:] = [{
        'device_id': 'life1',
        'label': 'Family member',
        'attr': 'tile',
        'value': '<div>Moving near home</div><a href="https://maps.example/?q=51.4671883,-0.0175467">map</a>',
        'ui_relevant': False,
    }]

    answer = main.event_diagnostics_answer()

    assert '[tile payload omitted]' in answer['message']
    assert 'maps.example' not in answer['message']
    assert '51.4671883' not in answer['message']
    assert 'maps.example' not in str(answer['diagnostics'])


def test_ai_timeline_omits_rich_payloads_and_background_telemetry():
    main = load_addon_main()
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        now = int(time.time())
        conn = main.db()
        try:
            conn.executemany(
                'INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)',
                [
                    ('person', 'Family member', 'tile', '<a href="https://maps.example">map</a>', '{}', now),
                    ('sensor', 'Hallway Sensor', 'voltage', '241', '{}', now),
                    ('light', 'Hallway Light', 'switch', 'on', '{}', now),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        timeline = main.recent_home_timeline(limit=10, hours=1)

    assert len(timeline) == 1
    assert timeline[0]['label'] == 'Hallway Light'
    assert timeline[0]['attr'] == 'switch'
    assert 'maps.example' not in str(timeline)


def test_room_sensor_cache_answer_never_scans_live_devices():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'lr-climate',
        'label': 'Livingroom temp & humidity',
        'room': 'Climate',
        'category': 'climate_sensor',
        'temperature': 28.2,
        'humidity': 50,
        'attributes': {'temperature': 28.2, 'humidity': 50},
    }]
    main.fetch_live_device_detail = lambda *_args: (_ for _ in ()).throw(AssertionError('live detail scan called'))

    temperature = main.cache_first_assistant_answer('livingroom temp')
    humidity = main.cache_first_assistant_answer('what is livingroom humidity')

    assert temperature['value'] == 28.2
    assert humidity['value'] == 50
    assert temperature['source'] == 'event_cache'
    assert humidity['source'] == 'event_cache'


def test_direct_value_refreshes_at_most_one_matching_device():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'one', 'label': 'Bathroom climate', 'room': 'Bathroom', 'category': 'climate_sensor', 'attributes': {}},
        {'id': 'two', 'label': 'Bathroom mirror', 'room': 'Bathroom', 'category': 'device', 'attributes': {}},
    ]
    calls = []
    main.fetch_live_device_detail = lambda device_id: calls.append(device_id) or {
        'id': device_id, 'label': 'Bathroom climate', 'room': 'Bathroom',
        'category': 'climate_sensor', 'humidity': 61, 'attributes': {'humidity': 61},
    }
    main.update_cached_device_snapshot = lambda _device: None

    answer = main.direct_value_lookup_answer('bathroom humidity')

    assert answer['value'] == 61
    assert len(calls) == 1


def test_find_all_is_cache_only_and_bounded():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': str(index), 'label': f'Device {index}', 'room': 'Room', 'category': 'device', 'attributes': {}}
        for index in range(40)
    ]
    main.fetch_live_device_detail = lambda *_args: (_ for _ in ()).throw(AssertionError('inventory must be cache-only'))

    answer = main.find_device_answer('find all devices')

    assert answer['source'] == 'event_cache'
    assert len(answer['matches']) == 40
    assert 'Cached device inventory: 40 devices' in answer['message']
    assert answer['message'].count('\n- ') == 25


def test_short_device_search_does_not_match_across_word_boundaries():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'fan', 'label': 'Fan Boost', 'room': 'Ventilation', 'category': 'switch', 'switch': 'off', 'attributes': {'switch': 'off'}},
        {'id': 'tv', 'label': 'TV', 'room': 'Multimedia', 'category': 'climate_sensor', 'switch': 'off', 'attributes': {'switch': 'off'}},
    ]

    answer = main.find_device_answer('find tv')

    assert [item['label'] for item in answer['matches']] == ['TV']


def test_switch_state_makes_tv_controllable_without_capability_metadata():
    main = load_addon_main()
    tv = {
        'id': 'tv', 'label': 'TV', 'name': 'Smart plug', 'room': 'Multimedia',
        'category': 'climate_sensor', 'switch': 'off', 'attributes': {'switch': 'off'},
        'capabilities': [], 'commands': [],
    }

    assert main.is_switchable_device(tv) is True
    assert main.switchable_devices([tv]) == [tv]


def test_period_energy_question_is_immediate_cache_answer():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy', 'category': 'power_device',
        'power': 591,
        'attributes': {'energyYesterday': 12.34, 'costYesterdayEnergy': 3.21},
    }]
    main.dashboard_summary = lambda live=False: (_ for _ in ()).throw(AssertionError('Dashboard summary should not be needed for a successful energy answer'))

    answer = main.cache_first_assistant_answer('energy used yesterday')

    assert answer['intent'] == 'energy_yesterday'
    assert answer['source'] == 'event_cache'
    assert '12.34 kWh' in answer['message']
    assert 'dashboard' not in answer
    assert '£3.21' in answer['message']


def test_period_energy_yesterday_derives_from_octopus_cumulative_history():
    main = load_addon_main()
    main.CONFIG['electricity_unit_rate_gbp'] = 0.30
    timezone_obj = main.local_timezone()
    now = datetime.now(timezone_obj) if timezone_obj else datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start.timestamp() - 86400
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        conn = main.db()
        try:
            conn.execute(
                'INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)',
                ('meter', 'Octopus Live Meter', 'energy', '1000.0', '{}', int(yesterday_start)),
            )
            conn.execute(
                'INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)',
                ('meter', 'Octopus Live Meter', 'energy', '1012.34', '{}', int(today_start.timestamp())),
            )
            conn.commit()
        finally:
            conn.close()
        main.all_devices = lambda: [{
            'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy', 'category': 'power_device',
            'power': 3, 'energy': 1013.0, 'attributes': {'energy': 1013.0},
        }]
        main.dashboard_summary = lambda live=False: (_ for _ in ()).throw(AssertionError('Dashboard summary should not be needed for a successful energy answer'))

        answer = main.cache_first_assistant_answer('energy usage yesterday')

    assert answer['intent'] == 'energy_yesterday'
    assert answer['source'] == 'event_cache'
    assert answer['usage']['yesterday']['source'] == 'cumulative_history'
    assert answer['usage']['yesterday']['kwh'] == 12.34
    assert '12.34 kWh' in answer['message']
    assert 'Estimated energy cost' in answer['message']
    assert '£3.70' in answer['message'] or 'Â£3.70' in answer['message']
    assert 'Derived from cumulative Octopus meter history' in answer['message']
    assert 'dashboard' not in answer
    assert 'not cached' not in answer['message']


def test_period_energy_uses_octopus_display_child_devices_first():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy', 'category': 'power_device',
            'energy': 8273.88, 'attributes': {},
        },
        {
            'id': 'today', 'label': 'Octopus Live Meter Display Today', 'room': 'Octopus Energy',
            'category': 'device', 'value': '3.70 kWh (\u00a31.44)',
            'attributes': {'value': '3.70 kWh (\u00a31.44)', 'friendly_name': 'Octopus Live Meter Display Today'},
        },
        {
            'id': 'month', 'label': 'Octopus Live Meter Display Month', 'room': 'Octopus Energy',
            'category': 'device', 'value': '125.59 kWh (\u00a341.06)',
            'attributes': {'valueStr': '125.59 kWh (\u00a341.06)', 'friendly_name': 'Octopus Live Meter Display Month'},
        },
    ]
    main.dashboard_summary = lambda live=False: (_ for _ in ()).throw(AssertionError('Dashboard summary should not be needed for a successful energy answer'))

    today = main.cache_first_assistant_answer('energy usage today')
    month = main.cache_first_assistant_answer('energy usage and cost this month')

    assert today['intent'] == 'energy_today'
    assert today['usage']['today']['source'] == 'octopus_display_device'
    assert today['usage']['today']['kwh'] == 3.70
    assert today['usage']['today']['cost_gbp'] == 1.44
    assert '3.70 kWh' in today['message']
    assert '1.44' in today['message']
    assert 'Octopus Live Meter Display Today' in today['message']
    assert month['intent'] == 'energy_month'
    assert month['usage']['month']['source'] == 'octopus_display_device'
    assert month['usage']['month']['kwh'] == 125.59
    assert month['usage']['month']['cost_gbp'] == 41.06
    assert '125.59 kWh' in month['message']
    assert '41.06' in month['message']
    assert 'month-start baseline' not in month['message']


def test_week_energy_uses_octopus_display_child_device():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'week', 'label': 'Octopus Live Meter Display Week', 'room': 'Octopus Energy',
        'category': 'device', 'value': '28.40 kWh (\u00a39.10)',
        'attributes': {'value': '28.40 kWh (\u00a39.10)', 'friendly_name': 'Octopus Live Meter Display Week'},
    }]
    main.dashboard_summary = lambda live=False: (_ for _ in ()).throw(AssertionError('Dashboard summary should not be needed for a successful energy answer'))

    answer = main.cache_first_assistant_answer('energy cost this week')

    assert answer['intent'] == 'energy_week'
    assert answer['usage']['week']['source'] == 'octopus_display_device'
    assert answer['usage']['week']['kwh'] == 28.40
    assert answer['usage']['week']['cost_gbp'] == 9.10
    assert 'Week to date' in answer['message']
    assert '28.40 kWh' in answer['message']


def test_period_energy_missing_total_does_not_invoke_ai():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy', 'category': 'power_device',
        'power': 591, 'attributes': {},
    }]
    main.dashboard_summary = lambda live=False: {'power_display': '591W'}
    main.ollama_answer = lambda *_args: (_ for _ in ()).throw(AssertionError('Ollama should not be called'))

    answer = main.cache_first_assistant_answer('energy used yesterday')

    assert 'not cached' in answer['message']
    assert '591W' in answer['message']


def test_high_power_device_does_not_label_small_load_as_high_or_use_octopus_meter():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy',
            'category': 'power_device', 'power': 204, 'attributes': {'power': 204},
        },
        {
            'id': 'plug', 'label': 'Halo3000x socket power', 'room': 'Sockets',
            'category': 'power_device', 'power': 6.9, 'attributes': {'power': 6.9},
        },
    ]

    answer = main.cache_first_assistant_answer('high power device')

    assert answer['intent'] == 'high_power_devices'
    assert 'No high-power devices are currently cached' in answer['message']
    assert 'Halo3000x socket power' in answer['message']
    assert '6.9W' in answer['message']
    assert answer['devices'] == []


def test_highest_power_device_ranking_excludes_whole_house_meter():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy',
            'category': 'power_device', 'power': 204, 'attributes': {'power': 204},
        },
        {
            'id': 'fridge', 'label': 'Fridge', 'room': 'Appliances',
            'category': 'power_device', 'power': 86, 'attributes': {'power': 86},
        },
    ]

    answer = main.cache_first_assistant_answer('device with highest power consumption')

    assert answer['intent'] == 'top_power_devices'
    assert 'Fridge' in answer['message']
    assert 'Octopus Live Meter' not in answer['message']


def test_dashboard_power_prefers_octopus_display_power_child():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'old-meter', 'label': 'Octopus Live Meter', 'room': 'Energy',
            'category': 'power_device', 'power': 111, 'attributes': {'power': 111},
        },
        {
            'id': 'display-power', 'label': 'Octopus Live Meter Display Power', 'room': 'Octopus Energy',
            'category': 'device', 'value': '1.99 kW',
            'attributes': {'valueStr': '1.99 kW', 'friendly_name': 'Octopus Live Meter Display Power'},
        },
    ]
    main.merged_low_battery_devices = lambda devices: []

    summary = main.compute_dashboard_summary({'synced': False})

    assert summary['power_total'] == 1990
    assert summary['power_display'] == '2kW'
    assert summary['power_source_label'] == 'Octopus Live Meter Display Power'


def test_refresh_prioritises_octopus_display_detail_values():
    main = load_addon_main()
    original_db_path = main.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
            raw_devices = [
                {'id': f'filler-{idx}', 'label': f'Generic Device {idx}', 'name': f'Generic Device {idx}'}
                for idx in range(8)
            ] + [
                {'id': 'display-power', 'label': 'Octopus Live Meter Display Power', 'name': 'Octopus Live Meter Display Power'},
                {'id': 'display-month', 'label': 'Octopus Live Meter Display Month', 'name': 'Octopus Live Meter Display Month'},
                {'id': 'display-rates', 'label': 'Octopus Live Meter Display Rates Compact', 'name': 'Octopus Live Meter Display Rates Compact'},
                {'id': 'display-previous-rate', 'label': 'Octopus Live Meter Display Previous Rate', 'name': 'Octopus Live Meter Display Previous Rate'},
                {'id': 'meter', 'label': 'Octopus Live Meter', 'name': 'Octopus Live Meter', 'attributes': {'power': 111, 'energy': 8277.7}},
            ]
            detail_calls = []

            def fake_maker_get(path, timeout=20):
                if path == 'devices':
                    return raw_devices
                detail_calls.append(path)
                if path == 'devices/display-power':
                    return {
                        'id': 'display-power',
                        'label': 'Octopus Live Meter Display Power',
                        'name': 'Octopus Live Meter Display Power',
                        'attributes': {'friendly_name': 'Octopus Live Meter Display Power'},
                        'currentStates': [{'name': 'value', 'value': '1.99 kW'}],
                    }
                if path == 'devices/display-month':
                    return {
                        'id': 'display-month',
                        'label': 'Octopus Live Meter Display Month',
                        'name': 'Octopus Live Meter Display Month',
                        'attributes': {'friendly_name': 'Octopus Live Meter Display Month'},
                        'currentStates': [{'name': 'value', 'value': '125.59 kWh (\u00a341.06)'}],
                    }
                if path == 'devices/display-rates':
                    return {
                        'id': 'display-rates',
                        'label': 'Octopus Live Meter Display Rates Compact',
                        'name': 'Octopus Live Meter Display Rates Compact',
                        'attributes': {'friendly_name': 'Octopus Live Meter Display Rates Compact'},
                        'currentStates': [{'name': 'value', 'value': 'Now 27.81p | Next 27.81p'}],
                    }
                if path == 'devices/display-previous-rate':
                    return {
                        'id': 'display-previous-rate',
                        'label': 'Octopus Live Meter Display Previous Rate',
                        'name': 'Octopus Live Meter Display Previous Rate',
                        'attributes': {'friendly_name': 'Octopus Live Meter Display Previous Rate'},
                        'currentStates': [{'name': 'value', 'value': '27.81 p/kWh'}],
                    }
                return {'id': path.rsplit('/', 1)[-1], 'currentStates': []}

            main.maker_get = fake_maker_get
            count = main.refresh_devices(True, 'test')
            devices = main.all_devices()
            summary = main.compute_dashboard_summary({'synced': True})
            month = main.cache_first_assistant_answer('energy usage this month')

        display_power = next(device for device in devices if device['id'] == 'display-power')
        display_month = next(device for device in devices if device['id'] == 'display-month')
        display_rates = next(device for device in devices if device['id'] == 'display-rates')
        display_previous_rate = next(device for device in devices if device['id'] == 'display-previous-rate')
        assert count == len(raw_devices)
        assert 'devices/display-power' in detail_calls
        assert 'devices/display-month' in detail_calls
        assert 'devices/display-rates' in detail_calls
        assert 'devices/display-previous-rate' in detail_calls
        assert display_power['attributes']['value'] == '1.99 kW'
        assert display_month['attributes']['value'] == '125.59 kWh (\u00a341.06)'
        assert display_rates['attributes']['value'] == 'Now 27.81p | Next 27.81p'
        assert display_previous_rate['attributes']['value'] == '27.81 p/kWh'
        assert summary['power_total'] == 1990
        assert summary['power_source_label'] == 'Octopus Live Meter Display Power'
        assert month['usage']['month']['source'] == 'octopus_display_device'
        assert '125.59 kWh' in month['message']
    finally:
        main.DB_PATH = original_db_path


def test_octopus_rate_question_uses_display_child_devices():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'rates', 'label': 'Octopus Live Meter Display Rates Compact',
            'category': 'device',
            'attributes': {'valueStr': 'Now 27.81p | Next 27.81p', 'friendly_name': 'Octopus Live Meter Display Rates Compact'},
        },
        {
            'id': 'previous-rate', 'label': 'Octopus Live Meter Display Previous Rate',
            'category': 'device',
            'attributes': {'valueStr': '27.81 p/kWh', 'friendly_name': 'Octopus Live Meter Display Previous Rate'},
        },
    ]

    answer = main.cache_first_assistant_answer('what is the electricity rate')

    assert answer['intent'] == 'octopus_rates'
    assert 'Rates Compact: Now 27.81p | Next 27.81p' in answer['message']
    assert 'Previous Rate: 27.81 p/kWh' in answer['message']


def test_category_inventory_lists_humidity_sensors():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'bath', 'label': 'Bathroom Sensor', 'room': 'Bathroom',
            'category': 'climate_sensor', 'humidity': 52, 'attributes': {'humidity': 52},
        },
        {
            'id': 'hall', 'label': 'Hallway Temperature', 'room': 'Hallway',
            'category': 'climate_sensor', 'temperature': 21, 'attributes': {'temperature': 21},
        },
    ]

    answer = main.cache_first_assistant_answer('list humidity sensors')

    assert answer['intent'] == 'humidity_sensors'
    assert 'Humidity sensors: 1 cached' in answer['message']
    assert 'Bathroom Sensor (Bathroom) - 52%' in answer['message']
    assert 'Hallway Temperature' not in answer['message']


def test_category_inventory_lists_all_lights():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'bed', 'label': 'Bedroom Light', 'room': 'Bedroom 1',
            'category': 'light', 'switch': 'on', 'attributes': {'switch': 'on'},
        },
        {
            'id': 'plug', 'label': 'Desk Plug', 'room': 'Office',
            'category': 'power_device', 'switch': 'on', 'attributes': {'switch': 'on'},
        },
        {
            'id': 'floor', 'label': 'My Floor Lamp', 'room': 'Bedroom 1',
            'category': 'device', 'switch': 'off',
            'attributes': {'switch': 'off', 'level': 5},
        },
    ]

    answer = main.cache_first_assistant_answer('show all lights')

    assert answer['intent'] == 'lights'
    assert 'Lights: 2 cached' in answer['message']
    assert 'Bedroom Light (Bedroom 1) - on' in answer['message']
    assert 'My Floor Lamp (Bedroom 1) - off' in answer['message']
    assert 'Desk Plug' not in answer['message']


def test_named_lamp_switch_counts_as_light_not_switch_in_summary():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'floor', 'label': 'My Floor Lamp', 'room': 'Bedroom 1',
            'category': 'device', 'switch': 'on',
            'attributes': {'switch': 'on'},
        },
    ]
    main.merged_low_battery_devices = lambda devices: []

    summary = main.compute_dashboard_summary({'synced': False})

    assert summary['lights_on'] == 1
    assert summary['switches_on'] == 0
    assert summary['lights_on_devices'][0]['label'] == 'My Floor Lamp'


def test_monthly_energy_question_returns_native_meter_total_directly():
    main = load_addon_main()
    main.CONFIG['electricity_unit_rate_gbp'] = 0.25
    main.all_devices = lambda: [{
        'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy', 'category': 'power_device',
        'energy': 8273.88,
        'attributes': {'energyThisMonth': 42.5, 'costThisMonth': 10.75},
    }]
    main.dashboard_summary = lambda live=False: {'power_display': '289W'}
    main.ollama_answer = lambda *_args: (_ for _ in ()).throw(AssertionError('Ollama should not be called'))

    answer = main.cache_first_assistant_answer('energy usage and cost this month')

    assert answer['intent'] == 'energy_month'
    assert answer['source'] == 'event_cache'
    assert answer['usage']['month']['source'] == 'meter_attribute'
    assert answer['usage']['month']['cost_estimated'] is False
    assert answer['message'] == 'Month to date: 42.50 kWh costing £10.75 from Octopus Live Meter.'
    assert 'AI Energy Advisor' not in answer['message']
    assert 'Worth checking' not in answer['message']


def test_monthly_energy_derives_usage_from_cumulative_history_and_labels_cost_estimate():
    main = load_addon_main()
    main.CONFIG['electricity_unit_rate_gbp'] = 0.30
    timezone = main.local_timezone()
    now = datetime.now(timezone) if timezone else datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    baseline_at = int(month_start.timestamp()) + 60
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        conn = main.db()
        try:
            conn.execute(
                'INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)',
                ('meter', 'Octopus Live Meter', 'energy', '1000.0', '{}', baseline_at),
            )
            conn.commit()
        finally:
            conn.close()
        main.all_devices = lambda: [{
            'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy',
            'category': 'power_device', 'energy': 1012.5, 'attributes': {'energy': 1012.5},
        }]
        main.dashboard_summary = lambda live=False: {'power_display': '289W'}

        answer = main.cache_first_assistant_answer('how much electricity have I used this month and what did it cost')

    month = answer['usage']['month']
    assert answer['intent'] == 'energy_month'
    assert month['source'] == 'cumulative_history'
    assert month['coverage_complete'] is True
    assert month['kwh'] == 12.5
    assert month['cost_gbp'] == 3.75
    assert month['cost_estimated'] is True
    assert 'Estimated energy cost: £3.75 at £0.300/kWh' in answer['message']
    assert 'standing charges are not included' in answer['message']


def test_monthly_energy_without_baseline_gives_direct_data_limitation():
    main = load_addon_main()
    with tempfile.TemporaryDirectory() as tmp:
        main.DB_PATH = Path(tmp) / 'homebrainos.sqlite3'
        main.all_devices = lambda: [{
            'id': 'meter', 'label': 'Octopus Live Meter', 'room': 'Energy',
            'category': 'power_device', 'energy': 8273.88, 'attributes': {'energy': 8273.88},
        }]
        main.dashboard_summary = lambda live=False: {'power_display': '289W'}

        answer = main.cache_first_assistant_answer('energy usage and cost this month')

    assert answer['intent'] == 'energy_month'
    assert 'Month-to-date energy is not available' in answer['message']
    assert '8273.88 kWh' in answer['message']
    assert 'month-start baseline' in answer['message']
    assert 'Worth checking' not in answer['message']


def test_forecast_query_refreshes_only_weather_device_once():
    main = load_addon_main()
    cached = {
        'id': 'weather', 'label': 'Weather Open-Meteo', 'name': 'Weather',
        'room': 'Climate', 'category': 'weather', 'temperature': 21.4,
        'humidity': 68, 'attributes': {'temperature': 21.4, 'humidity': 68},
    }
    main.all_devices = lambda: [cached]
    calls = []
    main.fetch_live_device_detail = lambda device_id: calls.append(device_id) or {
        **cached,
        'attributes': {'temperature': 21.4, 'humidity': 68, 'forecastTomorrow': 'Rain, high 22C'},
    }
    main.update_cached_device_snapshot = lambda _device: None
    main._homebrain_weather_query_answer = lambda query: {
        'success': True, 'intent': 'weather', 'message': f'Tomorrow: rain expected ({query}).'
    }

    answer = main.cached_weather_answer('weather tomorrow')

    assert answer['message'].startswith('Tomorrow:')
    assert calls == ['weather']


def test_generic_weather_refreshes_detail_and_uses_complete_briefing():
    main = load_addon_main()
    cached = {
        'id': 'weather', 'label': 'Weather Open-Meteo', 'name': 'Weather',
        'room': 'Climate', 'category': 'weather', 'temperature': 20,
        'humidity': 72, 'attributes': {'temperature': 20, 'humidity': 72},
    }
    main.all_devices = lambda: [cached]
    calls = []
    main.fetch_live_device_detail = lambda device_id: calls.append(device_id) or {
        **cached,
        'attributes': {
            'temperature': 20, 'humidity': 72,
            'weatherSummary': 'Partly cloudy with a high of 27C and a low of 16C.',
            'threedayfcstTile': 'Tomorrow Overcast 30C/18C Chance Rain 10% 1mm',
        },
    }
    main.update_cached_device_snapshot = lambda _device: None
    main._homebrain_weather_query_answer = lambda _query: {
        'success': True,
        'intent': 'weather',
        'message': 'Now: Partly cloudy, 20°C.\nToday: high 27°C, low 16°C, rain chance 10%.\nTomorrow: Overcast, high 30°C, low 18°C, rain chance 20%.',
    }

    answer = main.cached_weather_answer('what is the weather')

    assert calls == ['weather']
    assert 'Today:' in answer['message']
    assert 'Tomorrow:' in answer['message']
    assert answer['source'] == 'live_device_cache'


def test_bare_devices_query_uses_cached_inventory_not_ollama():
    main = load_addon_main()
    main.all_devices = lambda: [{
        'id': 'one', 'label': 'Hallway Light', 'room': 'Hallway',
        'category': 'light', 'switch': 'off', 'attributes': {'switch': 'off'},
    }]
    main.ollama_answer = lambda *_args: (_ for _ in ()).throw(AssertionError('Ollama should not be called'))

    answer = main.cache_first_assistant_answer('devices')

    assert answer['intent'] == 'find_device'
    assert answer['source'] == 'event_cache'
    assert 'Hallway Light' in answer['message']


def test_switches_off_uses_real_cached_state_and_never_ollama():
    main = load_addon_main()
    devices = [
        {
            'id': 'nest', 'label': 'Google Nest Hub', 'room': 'Unknown',
            'category': 'device', 'switch': None,
            'attributes': {'networkStatus': 'online', 'ipAddress': '192.168.1.133'},
        },
        {
            'id': 'halo', 'label': 'Halo3000x socket', 'room': 'Sockets',
            'category': 'device', 'switch': 'on', 'attributes': {'switch': 'on'},
        },
        {
            'id': 'dehum', 'label': 'Dehumidifier 1', 'room': 'Dehumidifier',
            'category': 'device', 'switch': 'off', 'attributes': {'switch': 'off'},
        },
        {
            'id': 'light', 'label': 'Bathroom Light 1', 'room': 'Bathroom',
            'category': 'light', 'switch': 'off', 'attributes': {'switch': 'off'},
        },
    ]
    main.all_devices = lambda: devices
    main.dashboard_summary = lambda live=False: {'switches_on': 1, 'switches_on_devices': [devices[1]]}
    main.ollama_answer = lambda *_args: (_ for _ in ()).throw(AssertionError('Ollama should not be called'))

    answer = main.cache_first_assistant_answer('which switches are off')

    assert answer['intent'] == 'cached_switches_off'
    assert answer['source'] == 'event_cache'
    assert answer['count'] == 1
    assert [device['label'] for device in answer['devices']] == ['Dehumidifier 1']
    assert 'Google Nest Hub' not in answer['message']
    assert 'Halo3000x socket' not in answer['message']
    assert 'Bathroom Light 1' not in answer['message']


def test_filtered_device_inventory_applies_state_projection_and_pagination():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'nest', 'label': 'Google Nest Hub', 'room': 'Unknown',
            'category': 'device', 'switch': None,
            'attributes': {'networkStatus': 'online'},
        },
        {
            'id': 'halo', 'label': 'Halo3000x socket', 'room': 'Sockets',
            'category': 'device', 'switch': 'on', 'attributes': {'switch': 'on'},
        },
        {
            'id': 'dehum', 'label': 'Dehumidifier 1', 'room': 'Bathroom',
            'category': 'device', 'switch': 'off', 'attributes': {'switch': 'off'},
        },
        {
            'id': 'light', 'label': 'Bathroom Light 1', 'room': 'Bathroom',
            'category': 'light', 'switch': 'off', 'attributes': {'switch': 'off'},
        },
    ]

    off_switches = main.filtered_device_inventory(
        category='switch', state='off', fields={'label', 'switch'}
    )
    first_page = main.filtered_device_inventory(query='all devices', limit=2, offset=0)

    assert off_switches['total'] == 1
    assert off_switches['devices'] == [{'label': 'Dehumidifier 1', 'switch': 'off'}]
    assert first_page['count'] == 2
    assert first_page['total'] == 4
    assert first_page['next_offset'] == 2


def test_home_tool_room_metric_uses_cached_label_when_driver_room_is_generic():
    main = load_addon_main()
    main.all_devices = lambda: [
        {
            'id': 'living', 'label': 'Livingroom temp & humidity', 'room': 'Climate',
            'category': 'climate_sensor', 'temperature': 24.5, 'humidity': 51,
        },
        {
            'id': 'outside', 'label': 'Weather Open-Meteo', 'room': 'Climate',
            'category': 'weather', 'temperature': 18, 'humidity': 90,
        },
    ]

    result = main.execute_home_tool('home_get_room_metric', {
        'room': 'living room', 'metric': 'humidity',
    })

    assert result['success'] is True
    assert result['average'] == 51
    assert result['source'] == 'event_cache'
    assert [sensor['label'] for sensor in result['sensors']] == ['Livingroom temp & humidity']


def test_verify_device_attribute_accepts_event_cache_confirmation_without_polling():
    main = load_addon_main()
    main.CONFIG.update({
        'hubitat_base_url': 'http://hub.local',
        'maker_api_app_id': '1',
        'maker_api_token': 'secret',
    })
    main.all_devices = lambda: [
        {'id': 'plug', 'label': 'Plug', 'category': 'switch', 'switch': 'on'},
    ]
    main.fetch_live_device_detail = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError('confirmed event cache must not poll Maker API')
    )

    result = main.verify_device_attribute(['plug'], 'switch', 'on', timeout_seconds=0.1)

    assert result['confirmed'] is True
    assert result['source'] == 'event_cache'
    assert result['detail_reads'] == 0


def test_verify_device_attribute_uses_one_targeted_read_after_event_wait():
    main = load_addon_main()
    main.CONFIG.update({
        'hubitat_base_url': 'http://hub.local',
        'maker_api_app_id': '1',
        'maker_api_token': 'secret',
    })
    devices = [{'id': 'plug', 'label': 'Plug', 'category': 'switch', 'switch': 'off'}]
    main.all_devices = lambda: devices
    reads = []
    main.fetch_live_device_detail = lambda device_id, timeout=6: reads.append(device_id) or {
        'id': 'plug', 'label': 'Plug', 'category': 'switch', 'switch': 'on',
    }
    main.update_cached_device_snapshot = lambda fresh: devices.__setitem__(0, fresh)

    result = main.verify_device_attribute(['plug'], 'switch', 'on', timeout_seconds=0.01)

    assert result['confirmed'] is True
    assert result['source'] == 'targeted_read'
    assert result['detail_reads'] == 1
    assert reads == ['plug']


def test_command_devices_does_not_write_optimistic_state_when_hubitat_is_unconfirmed():
    main = load_addon_main()
    device = {'id': 'plug', 'label': 'Plug', 'category': 'switch', 'switch': 'off'}
    main.maker_command = lambda *_args: None
    main.all_devices = lambda: [device]
    main.verify_device_attribute = lambda *_args, **_kwargs: {
        'status': 'unconfirmed', 'confirmed': False, 'requested_ids': ['plug'],
        'confirmed_ids': [], 'unconfirmed_ids': ['plug'], 'source': 'targeted_read',
    }
    main.update_cached_switch = lambda *_args: (_ for _ in ()).throw(
        AssertionError('unconfirmed commands must not overwrite the cache')
    )

    answer = main.command_devices([device], 'on')

    assert answer['success'] is True
    assert answer['confirmed'] is False
    assert answer['devices'][0]['switch'] == 'off'
    assert 'has not confirmed' in answer['message']


def test_switch_state_questions_support_on_off_and_polite_phrasing():
    main = load_addon_main()
    devices = [
        {'id': 'on', 'label': 'TV', 'room': 'Multimedia', 'category': 'power_device', 'switch': 'on', 'attributes': {'switch': 'on'}},
        {'id': 'off', 'label': 'Iron', 'room': 'Appliances', 'category': 'device', 'switch': 'off', 'attributes': {'switch': 'off'}},
    ]
    main.all_devices = lambda: devices
    main.dashboard_summary = lambda live=False: {'switches_on': 1, 'switches_on_devices': [devices[0]]}

    on_answer = main.cache_first_assistant_answer('what switches are on')
    off_answer = main.cache_first_assistant_answer('could you show me which switches are currently off please')
    singular = main.cache_first_assistant_answer('what switch is off')

    assert [device['label'] for device in on_answer['devices']] == ['TV']
    assert [device['label'] for device in off_answer['devices']] == ['Iron']
    assert [device['label'] for device in singular['devices']] == ['Iron']


def test_inventory_queries_do_not_fall_into_direct_value_lookup():
    main = load_addon_main()
    main.SUMMARY_CACHE = None
    main.all_devices = lambda: [
        {'id': 'tv', 'label': 'TV', 'room': 'Multimedia', 'category': 'device', 'switch': 'off', 'power': 0},
        {'id': 'fan', 'label': 'Air Purifier', 'room': 'Ventilation', 'category': 'switch', 'switch': 'off'},
        {'id': 'halo', 'label': 'Halo3000x socket power', 'room': 'Sockets', 'category': 'power_device', 'switch': 'on', 'power': 7.2},
        {'id': 'plug', 'label': 'Desk Plug', 'room': 'Office', 'category': 'power_device', 'switch': 'off', 'power': 0.4},
        {'id': 'motion', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'inactive'},
    ]

    rooms = main.cache_first_assistant_answer('show rooms')
    power_devices = main.cache_first_assistant_answer('power devices')
    top_power = main.cache_first_assistant_answer('device with highest power consumption')
    ventilation = main.cache_first_assistant_answer('find ventilation')

    assert rooms['intent'] == 'room_inventory'
    assert 'Rooms:' in rooms['message']
    assert 'Living Room status' not in rooms['message']
    assert power_devices['intent'] == 'power_device_inventory'
    assert 'Halo3000x socket power' in power_devices['message']
    assert 'Power is shown as whole-house power' not in power_devices['message']
    assert top_power['intent'] == 'top_power_devices'
    assert top_power['message'].splitlines()[1].startswith('- Halo3000x socket power')
    assert 'Device: Halo3000x socket power' not in top_power['message']
    assert ventilation['intent'] == 'find_device'
    assert 'Air Purifier' in ventilation['message']
    assert 'Switch: off' not in ventilation['message']


def test_assistant_understands_inventory_and_power_paraphrases():
    main = load_addon_main()
    main.SUMMARY_CACHE = None
    main.all_devices = lambda: [
        {'id': 'fan', 'label': 'Air Purifier', 'room': 'Ventilation', 'category': 'switch', 'switch': 'off'},
        {'id': 'halo', 'label': 'Halo3000x socket power', 'room': 'Sockets', 'category': 'power_device', 'switch': 'on', 'power': 7.2},
        {'id': 'pc', 'label': 'Bedroom PC', 'room': 'Bedroom 3', 'category': 'power_device', 'switch': 'on', 'power': 5.1},
        {'id': 'motion', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'inactive'},
    ]

    room_phrases = ['what rooms are there', 'can you show me the rooms', 'list all rooms']
    power_inventory_phrases = ['what devices have power readings', 'show me energy devices', 'which are power devices']
    top_power_phrases = ['what is using the most power', 'which device is drawing most power', 'top electricity consumers']
    find_phrases = ['where is ventilation', 'locate air purifier', 'what devices match ventilation']

    for phrase in room_phrases:
        answer = main.cache_first_assistant_answer(phrase)
        assert answer['intent'] == 'room_inventory'
        assert 'Ventilation' in answer['message']

    for phrase in power_inventory_phrases:
        answer = main.cache_first_assistant_answer(phrase)
        assert answer['intent'] == 'power_device_inventory'
        assert 'Halo3000x socket power' in answer['message']

    for phrase in top_power_phrases:
        answer = main.cache_first_assistant_answer(phrase)
        assert answer['intent'] == 'top_power_devices'
        assert answer['message'].splitlines()[1].startswith('- Halo3000x socket power')

    for phrase in find_phrases:
        answer = main.cache_first_assistant_answer(phrase)
        assert answer['intent'] == 'find_device'
        assert 'Air Purifier' in answer['message']


def test_ai_context_is_cache_only_by_default():
    main = load_addon_main()
    main.all_devices = lambda: []
    main.dashboard_summary = lambda live=False: {
        'devices': 0, 'lights_on': 0, 'switches_on': 0, 'avg_temperature': None,
        'avg_humidity': None, 'power_total': 0, 'power_source_label': 'None',
        'people_home_names': [], 'low_batteries': 0, 'motion_active': 0,
    }
    main.hub_logs_diagnostics = lambda: (_ for _ in ()).throw(AssertionError('hub logs network call'))

    context = main.ai_context_pack()

    assert 'hub_logs' not in context


def test_answer_dashboard_snapshot_is_applied_by_web_ui():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert 'if(j.dashboard) applyDashboard(j.dashboard);' in html
