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
