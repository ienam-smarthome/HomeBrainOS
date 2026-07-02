from backend.services.normalizer import normalise_device


def test_normalise_switch():
    raw = {'id': '1', 'name': 'Plug', 'label': 'Test Plug', 'attributes': [{'name': 'switch', 'currentValue': 'on'}]}
    d = normalise_device(raw)
    assert d['id'] == '1'
    assert d['switch'] == 'on'
