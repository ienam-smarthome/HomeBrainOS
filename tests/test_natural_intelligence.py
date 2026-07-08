from __future__ import annotations

import importlib.util
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
            {'label': 'Octopus Live Meter', 'category': 'energy', 'attributes': {'power': '304', 'displayCostToday': '2.08', 'displayCostYesterday': '3.59'}},
            {'label': 'Bedroom3 PC (MQTT)', 'category': 'Sockets', 'attributes': {'power': '113'}},
            {'label': 'Fridge', 'category': 'Appliances', 'attributes': {'power': 80}},
            {'label': 'Halo3000x socket power', 'attributes': {'power': 7}},
            {'label': 'Livingroom Light 1', 'category': 'light', 'attributes': {'switch': 'on', 'power': 7}},
            {'label': 'Bedroom 2 Light', 'category': 'light', 'attributes': {'switch': 'off'}},
        ]

    def daily_briefing_answer(self):
        return {'success': True, 'message': 'Good afternoon. Everything looks normal.'}


def test_natural_unit_formatters():
    module = load_natural_intelligence()
    assert module.format_power(304) == '304 watts'
    assert module.format_energy(5.32) == '5.3 kilowatt-hours'
    assert module.format_money('1.48') == '£1.48'


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
    assert 'Fridge is using 80 watts' in answer['message']
    assert 'Octopus Live Meter is using 304 watts' not in answer['message']
    assert 'excluded from the device list' in answer['message']


def test_today_and_yesterday_period_answers_still_work():
    module = load_natural_intelligence()
    today = module.build_intelligence_answer(FakeMain(), 'how much electricity have I used today')
    yesterday = module.build_intelligence_answer(FakeMain(), 'how much electricity did I use yesterday')
    assert today['intent'] == 'energy_today'
    assert 'Total cost including standing charge was £2.08.' in today['message']
    assert yesterday['intent'] == 'energy_yesterday'
    assert 'Total cost including standing charge was £3.59.' in yesterday['message']


def test_energy_advisor_question_still_returns_full_report():
    module = load_natural_intelligence()
    answer = module.build_intelligence_answer(FakeMain(), 'energy advisor')
    assert answer['intent'] == 'energy'
    assert 'Worth checking' in answer['message']


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
    assert fake.APP_VERSION == '1.6.6-alpha'
    assert fake.app.version == '1.6.6-alpha'
