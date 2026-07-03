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
