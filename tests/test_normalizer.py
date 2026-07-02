from backend.services.normalizer import normalise_device


def test_normalise_switch():
    raw = {'id': '1', 'name': 'Plug', 'label': 'Test Plug', 'attributes': [{'name': 'switch', 'currentValue': 'on'}]}
    d = normalise_device(raw)
    assert d['id'] == '1'
    assert d['switch'] == 'on'


def test_room_and_climate():
    raw = {'id': '2', 'label': 'Hallway FP300 Humidity', 'attributes': [{'name': 'humidity', 'currentValue': '46'}]}
    d = normalise_device(raw)
    assert d['room'] == 'Hallway'
    assert d['category'] == 'climate_sensor'
    assert d['humidity'] == 46.0


def test_light_category():
    raw = {'id': '3', 'label': 'Bedroom 1 Light', 'attributes': [{'name': 'switch', 'currentValue': 'off'}]}
    d = normalise_device(raw)
    assert d['category'] == 'light'
    assert d['room'] == 'Bedroom 1'


def test_current_states_value_shape():
    raw = {
        'id': '4',
        'label': 'Kitchen Lamp',
        'capabilities': ['SwitchLevel'],
        'currentStates': [
            {'name': 'switch', 'value': 'ON'},
            {'name': 'temperature', 'value': '21.5'},
        ],
    }
    d = normalise_device(raw)
    assert d['category'] == 'light'
    assert d['switch'] == 'ON'
    assert d['temperature'] == 21.5


def test_dict_attribute_shape():
    raw = {
        'id': '5',
        'label': 'Hallway Sensor',
        'attributes': {'humidity': '48%', 'motion': 'active'},
    }
    d = normalise_device(raw)
    assert d['category'] == 'motion_sensor'
    assert d['humidity'] == 48.0
    assert d['motion'] == 'active'


def test_light_sensor_is_not_controllable_light():
    raw = {
        'id': '6',
        'label': 'Aqara Light Sensor T1',
        'capabilities': ['IlluminanceMeasurement'],
        'attributes': [{'name': 'illuminance', 'currentValue': '123'}],
    }
    d = normalise_device(raw)
    assert d['category'] == 'light_sensor'
    assert d['illuminance'] == 123.0


def test_attribute_aliases_and_display_values():
    raw = {
        'id': '7',
        'label': 'Bedroom 2 Sensor',
        'attributes': [
            {'name': 'relativeHumidity', 'displayValue': '55%'},
            {'name': 'lux', 'currentValue': '42'},
            {'name': 'PowerMeter', 'currentValue': '7.5'},
        ],
    }
    d = normalise_device(raw)
    assert d['humidity'] == 55.0
    assert d['illuminance'] == 42.0
    assert d['power'] == 7.5
    assert d['attributes']['relativeHumidity'] == '55%'
    assert d['attributes']['humidity'] == '55%'


def test_capabilities_and_commands_are_preserved():
    raw = {
        'id': '8',
        'label': 'Dehumidifier 2',
        'capabilities': [{'name': 'Switch'}],
        'commands': [{'command': 'on'}, {'command': 'off'}],
        'currentStates': [{'name': 'Switch', 'value': 'off'}],
    }
    d = normalise_device(raw)
    assert d['category'] == 'switch'
    assert d['switch'] == 'off'
    assert d['capabilities'] == ['Switch']
    assert d['commands'] == ['off', 'on']
