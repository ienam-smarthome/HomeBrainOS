import importlib.util
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
