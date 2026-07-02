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
