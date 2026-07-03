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


def test_assistant_active_rooms_lists_rooms_not_motion_sensor_detail():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'm1', 'label': 'Kitchen Motion', 'room': 'Kitchen', 'category': 'motion_sensor', 'motion': 'active'},
        {'id': 'm2', 'label': 'Hallway Motion', 'room': 'Hallway', 'category': 'motion_sensor', 'motion': 'inactive'},
        {'id': 'l1', 'label': 'Bedroom Light', 'room': 'Bedroom', 'category': 'light', 'switch': 'on'},
        {'id': 's1', 'label': 'Dehumidifier Socket', 'room': 'Dehumidifier', 'category': 'power_device', 'switch': 'on', 'power': 42},
    ]

    active_rooms = main.assistant('which rooms have motion active')

    assert active_rooms['intent'] == 'active_rooms'
    assert 'Kitchen: 0 lights on, 0 switches on, 1 motion active' in active_rooms['message']
    assert 'Bedroom: 1 lights on, 0 switches on, 0 motion active' in active_rooms['message']
    assert 'Dehumidifier' not in active_rooms['message']


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
    assert 'Free memory: 512 MB' in health['message']


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

    assert 'Free memory: 1.0 GB' in health['message']
    assert 'CPU load: 0.8 / 20.0 %' in health['message']
    assert 'DB size: 199 MB' in health['message']
    assert 'Last restart: 03Jul2026 14:42' in health['message']
    assert 'Uptime: 0d:0h:31m:46s' in health['message']
    assert 'Temperature: 46.2 °C' in health['message']


def test_status_hub_health_summary_colours_cpu_and_memory():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'hub', 'label': 'Hub Info', 'room': 'Hub', 'category': 'device', 'attributes': {'Html': 'Free Mem : 1.0 GB\nCPU Load/Load% : 0.8 / 20.0 %'}},
    ]

    summary = main.hub_health_summary()

    assert summary['level'] == 'ok'
    assert summary['cpu_load_percent'] == 20
    assert summary['free_memory_mb'] == 1024
    assert summary['label'] == 'Hub CPU 20% · Free 1.0 GB'


def test_status_hub_health_summary_warns_on_low_memory_and_high_cpu():
    main = load_addon_main()
    main.all_devices = lambda: [
        {'id': 'hub', 'label': 'Hub Info', 'room': 'Hub', 'category': 'device', 'attributes': {'Html': 'Free Mem : 300 MB\nCPU Load/Load% : 0.8 / 65.0 %'}},
    ]

    assert main.hub_health_summary()['level'] == 'warning'

    main.all_devices = lambda: [
        {'id': 'hub', 'label': 'Hub Info', 'room': 'Hub', 'category': 'device', 'attributes': {'Html': 'Free Mem : 128 MB\nCPU Load/Load% : 0.8 / 85.0 %'}},
    ]

    assert main.hub_health_summary()['level'] == 'error'


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
        {'id': 'k1', 'label': 'Kitchen Plug', 'room': 'Kitchen', 'category': 'switch', 'switch': 'off'},
    ]

    room_names = [room['room'] for room in main.api_rooms()['rooms']]

    assert room_names == ['Bathroom', 'Hallway', 'Dehumidifier', 'Kitchen']


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
