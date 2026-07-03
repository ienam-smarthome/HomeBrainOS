from backend.models.device import Device


def test_device_attributes_default_is_not_shared():
    first = Device(id='1', name='One', label='One')
    second = Device(id='2', name='Two', label='Two')

    first.attributes['switch'] = 'on'

    assert second.attributes == {}
