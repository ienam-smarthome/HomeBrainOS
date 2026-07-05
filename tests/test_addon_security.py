import importlib.util
import tempfile
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


def test_ollama_answer_uses_structured_context_and_control_guardrails():
    main = load_addon_main()
    main.CONFIG['ollama_enabled'] = True
    main.CONFIG['ollama_include_hub_logs'] = False
    main.CONFIG['ollama_base_url'] = 'http://ollama.local:11434'
    main.CONFIG['ollama_model'] = 'qwen2.5:3b'
    main.CONFIG['ollama_timeout_seconds'] = 75
    main.CONFIG['ollama_num_predict'] = 90
    main.all_devices = lambda: [
        {'id': 'w1', 'label': 'Weather Open-Meteo', 'room': 'Weather', 'category': 'weather', 'weatherSummaryLine': 'Clear'},
    ]
    captured = {}

    class HealthResponse:
        def raise_for_status(self):
            return None

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {'response': 'The home looks stable.'}

    def post(url, json, timeout=20):
        captured['url'] = url
        captured['json'] = json
        captured['timeout'] = timeout
        return Response()

    main.requests.get = lambda url, timeout=2: HealthResponse()
    main.requests.post = post

    answer = main.ollama_answer('anything unusual?')

    prompt = captured['json']['prompt']
    assert answer['intent'] == 'ollama_answer'
    assert captured['url'] == 'http://ollama.local:11434/api/generate'
    assert captured['timeout'] == 75
    assert captured['json']['model'] == 'qwen2.5:3b'
    assert captured['json']['options']['num_predict'] == 90
    assert 'Context JSON' in prompt
    assert '"weather"' in prompt
    assert '\n  "weather"' not in prompt
    assert 'Device control is handled before you are called' in prompt
    assert 'complete sentences' in prompt
    assert answer['speech'] == 'The home looks stable.'


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
    assert 'Hallway Light on' in answer['message']
    assert 'Hallway TRV heating' in answer['message']
    assert 'Hallway Plug' not in answer['message']
    assert 'Bedroom Light' not in answer['message']
    assert answer['speech'] == 'Hallway: Hallway Light on and Hallway TRV heating.'


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


def test_assistant_active_rooms_lists_only_active_device_names():
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

    assert active_rooms['intent'] == 'active_rooms'
    assert 'Kitchen: Kitchen Motion active' in active_rooms['message']
    assert 'Bedroom: Bedroom Light on at 30%' in active_rooms['message']
    assert 'Dehumidifier: Dehumidifier Socket on, using 42W' in active_rooms['message']
    assert '0 lights on' not in active_rooms['message']
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
    assert 'armVoiceStation(15000)' in html
    assert "['no-speech','aborted'].includes" in html
    assert "urlParams.get('station')==='1'" in html
    assert 'r.continuous=true' in html


def test_dashboard_tiles_have_visible_click_feedback():
    html = (Path(__file__).resolve().parents[1] / 'homebrainos' / 'rootfs' / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

    assert '.metric.summary-tile.selected,.room.selected' in html
    assert "content:'Loading'" not in html
    assert '.metric.summary-tile.loading:after' not in html
    assert 'function markActiveControl' in html
    assert "setOutput('Running: '+text+'...')" in html
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
