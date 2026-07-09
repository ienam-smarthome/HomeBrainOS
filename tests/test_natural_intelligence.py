from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace


def load_natural_intelligence():
    path = Path('homebrainos/rootfs/app/natural_intelligence.py')
    spec = importlib.util.spec_from_file_location('natural_intelligence', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeApp:
    def __init__(self):
        self.routes = []
        self.version = 'old'

    def add_api_route(self, path, endpoint, methods):
        self.routes.append(SimpleNamespace(path=path, endpoint=endpoint, methods=methods))


class FakeMain:
    def __init__(self):
        self.app = FakeApp()
        self.APP_VERSION = 'old'
        self.fallback_called = False
        db_file = tempfile.NamedTemporaryFile(delete=False)
        db_file.close()
        self.db_path = db_file.name
        conn = self.db()
        conn.execute('CREATE TABLE hubitat_events (device_id TEXT, label TEXT, attr TEXT, value TEXT, raw TEXT, created_at INTEGER)')
        conn.executemany(
            'INSERT INTO hubitat_events(device_id,label,attr,value,raw,created_at) VALUES(?,?,?,?,?,?)',
            [
                ('l1', 'Livingroom Light 1', 'switch', 'on', '{}', -1000),
                ('l1', 'Livingroom Light 1', 'switch', 'off', '{}', 800),
                ('l2', 'Bedroom 2 Light', 'switch', 'on', '{}', -50000),
                ('l2', 'Bedroom 2 Light', 'switch', 'off', '{}', -46400),
                ('l1', 'Livingroom Light 1', 'switch', 'on', '{}', 1600),
                ('l1', 'Livingroom Light 1', 'switch', 'off', '{}', 3400),
                ('l2', 'Bedroom 2 Light', 'switch', 'on', '{}', 2200),
                ('l2', 'Bedroom 2 Light', 'switch', 'off', '{}', 4000),
                ('l2', 'Bedroom 2 Light', 'switch', 'on', '{}', 7000),
            ],
        )
        conn.commit()
        conn.close()

    def db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def assistant(self, query):
        self.fallback_called = True
        return {'success': False, 'message': 'Local AI is offline. Basic HomeBrain commands are still available.'}

    def dashboard_summary(self, live=False):
        return {'live': live, 'occupancy': {'summary': 'Everyone is home'}, 'lights': {'on': 3}, 'rooms': ['Living Room']}

    def home_health_answer(self):
        return {'success': True, 'score': 96, 'message': 'Everything looks normal.'}

    def energy_advisor_answer(self):
        return {
            'success': True,
            'message': (
                'AI Energy Advisor:\n'
                'Whole-house power now: 304W from Octopus Live Meter\n'
                'Used today so far: 5.32 kWh costing £1.48\n'
                'Used yesterday: 11.46 kWh costing £3.18\n'
                'Worth checking:\n'
                '• Fridge — 89W, on for unknown duration'
            ),
        }

    def recent_home_timeline(self, limit, hours):
        return [{'label': 'Kitchen motion', 'limit': limit, 'hours': hours}]

    def recommendations_answer(self):
        return {'success': True, 'message': 'Nothing urgent.', 'items': ['Nothing urgent.']}

    def all_devices(self):
        return [
            {'id': 'octo', 'label': 'Octopus Live Meter', 'category': 'energy', 'attributes': {'power': '304', 'displayCostToday': '2.08', 'displayCostYesterday': '3.59'}},
            {'id': 'pc1', 'label': 'Bedroom3 PC (MQTT)', 'category': 'Sockets', 'attributes': {'power': '113'}},
            {'id': 'fridge', 'label': 'Fridge', 'category': 'Appliances', 'attributes': {'power': 80}},
            {'id': 'halo', 'label': 'Halo3000x socket power', 'attributes': {'power': 7}},
            {'id': 'l1', 'label': 'Livingroom Light 1', 'category': 'light', 'attributes': {'switch': 'off', 'power': 7}},
            {'id': 'l2', 'label': 'Bedroom 2 Light', 'room': 'Bedroom 2', 'category': 'light', 'attributes': {'switch': 'on'}},
        ]

    def daily_briefing_answer(self):
        return {'success': True, 'message': 'Good afternoon. Everything looks normal.'}


def freeze_light_hours_clock(module):
    module._period_start_timestamp = lambda period='today': 1000 if period == 'today' else -85400
    module.time.time = lambda: 10000


def test_natural_unit_formatters():
    module = load_natural_intelligence()
    assert module.format_power(304) == '304 watts'
    assert module.format_energy(5.32) == '5.3 kilowatt-hours'
    assert module.format_money('1.48') == '£1.48'


def test_light_hours_uses_hubitat_event_history_for_all_lights():
    module = load_natural_intelligence()
    freeze_light_hours_clock(module)
    answer = module.build_intelligence_answer(FakeMain(), 'lights on time today')
    assert answer['intent'] == 'light_hours'
    assert "Today's light-on time" in answer['message']
    assert 'Bedroom 2 Light: 1 hour 20 minutes' in answer['message']
    assert 'Livingroom Light 1: 30 minutes' in answer['message']
    assert 'exact light-hours need event history' not in answer['message']


def test_light_hours_can_target_bedroom_two_light():
    module = load_natural_intelligence()
    freeze_light_hours_clock(module)
    answer = module.build_intelligence_answer(FakeMain(), 'how long has bedroom two light been on today')
    assert answer['intent'] == 'light_hours'
    assert 'Bedroom 2 Light: 1 hour 20 minutes' in answer['message']
    assert 'Livingroom Light 1' not in answer['message']


def test_light_hours_can_answer_yesterday():
    module = load_natural_intelligence()
    freeze_light_hours_clock(module)
    answer = module.build_intelligence_answer(FakeMain(), 'lights on time yesterday')
    assert answer['intent'] == 'light_hours'
    assert answer['period'] == 'yesterday'
    assert "Yesterday's light-on time" in answer['message']
    assert 'Bedroom 2 Light: 1 hour' in answer['message']
    assert 'Livingroom Light 1: 30 minutes' in answer['message']
    assert 'currently on' not in answer['message']


def test_light_hours_can_target_yesterday_bedroom_two():
    module = load_natural_intelligence()
    freeze_light_hours_clock(module)
    answer = module.build_intelligence_answer(FakeMain(), 'bedroom two light on time yesterday')
    assert answer['intent'] == 'light_hours'
    assert answer['period'] == 'yesterday'
    assert 'Bedroom 2 Light: 1 hour' in answer['message']
    assert 'Livingroom Light 1' not in answer['message']


def test_top_power_consumers_excludes_aggregate_meter():
    module = load_natural_intelligence()
    consumers = module._top_power_consumers(FakeMain(), 5)
    labels = [item['label'] for item in consumers]
    assert 'Octopus Live Meter' not in labels
    assert labels[:2] == ['Bedroom3 PC (MQTT)', 'Fridge']


def test_energy_now_excludes_octopus_from_device_users_but_keeps_whole_home_total():
    module = load_natural_intelligence()
    answer = module.build_intelligence_answer(FakeMain(), 'what is using the most electricity now')
    assert answer['intent'] == 'energy_now'
    assert 'Whole-house power now is 304 watts from Octopus Live Meter.' in answer['message']
    assert 'Bedroom3 PC (MQTT) is using 113 watts' in answer['message']
    assert 'Octopus Live Meter is using 304 watts' not in answer['message']


def test_today_and_yesterday_period_answers_still_work():
    module = load_natural_intelligence()
    today = module.build_intelligence_answer(FakeMain(), 'how much electricity have I used today')
    yesterday = module.build_intelligence_answer(FakeMain(), 'how much electricity did I use yesterday')
    assert today['intent'] == 'energy_today'
    assert 'Total cost including standing charge was £2.08.' in today['message']
    assert yesterday['intent'] == 'energy_yesterday'
    assert 'Total cost including standing charge was £3.59.' in yesterday['message']


def test_register_adds_routes_once_and_updates_version():
    module = load_natural_intelligence()
    fake = FakeMain()
    module.register(fake)
    module.register(fake)
    paths = [route.path for route in fake.app.routes]
    assert paths.count('/api/home-context') == 1
    assert paths.count('/api/briefing') == 1
    assert paths.count('/api/home-health-score') == 1
    assert paths.count('/api/insight') == 1
    assert paths.count('/api/why') == 1
    # Keep the runtime version aligned with the add-on release version.
    assert fake.APP_VERSION == '1.7.1-alpha'
    assert fake.app.version == '1.7.1-alpha'
