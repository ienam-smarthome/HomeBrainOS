from backend.integrations.hubitat_maker import HubitatMakerApi, MakerApiConfig


def test_maker_url_encodes_app_id_and_token():
    api = HubitatMakerApi(
        MakerApiConfig(
            base_url='http://hubitat.local/',
            app_id='app 42',
            token='abc/123?x=1&y=2',
        )
    )

    assert api._url('devices') == (
        'http://hubitat.local/apps/api/app%2042/devices'
        '?access_token=abc%2F123%3Fx%3D1%26y%3D2'
    )


def test_maker_url_keeps_existing_query_separator():
    api = HubitatMakerApi(
        MakerApiConfig(
            base_url='http://hubitat.local',
            app_id='4143',
            token='token',
        )
    )

    assert api._url('devices/1/setLevel/50?secondary=true').endswith(
        '&access_token=token'
    )
