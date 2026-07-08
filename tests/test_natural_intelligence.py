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

    def dashboard_summary(self, live=False):
        return {
            'live': live,
            'occupancy': {'summary': 'Everyone is home'},
            'lights': {'on': 3},
            'rooms': ['Living Room'],
        }

    def home_health_answer(self):
        return {'success': True, 'score': 96, 'message': 'Everything looks normal.'}

    def energy_advisor_answer(self):
        return {'success': True, 'message': 'Your home is using 418W and 5.32 kWh today.'}

    def recent_home_timeline(self, limit, hours):
        return [{'label': 'Kitchen motion', 'limit': limit, 'hours': hours}]

    def recommendations_answer(self):
        return {'success': True, 'message': 'Nothing urgent.', 'items': ['Nothing urgent.']}

    def all_devices(self):
        return [
            {'label': 'TV', 'category': 'multimedia', 'attributes': {'power': '86'}},
            {'label': 'Fridge', 'category': 'appliances', 'attributes': {'power': 89}},
            {'label': 'Livingroom Light 1', 'category': 'light', 'attributes': {'switch': 'on', 'power': 7}},
            {'label': 'Bedroom 2 Light', 'category': 'light', 'attributes': {'switch': 'off'}},
            {'label': 'Idle plug', 'attributes': {'power': 0}},
        ]

    def daily_briefing_answer(self):
        return {'success': True, 'message': 'Good afternoon. Everything looks normal.'}


def test_natural_unit_formatters():
    module = load_natural_intelligence()

    assert module.format_power(418) == '418 watts'
    assert module.format_power(1420) == '1.4 kilowatts'
    assert module.format_energy(5.32) == '5.3 kilowatt-hours'
    assert module.format_energy(1) == '1 kilowatt-hour'
    assert module.format_money('1.48') == '£1.48'
    assert module.naturalise_units('Using 418W and 5.32 kWh') == 'Using 418 watts and 5.3 kilowatt-hours'


def test_home_context_facade_uses_existing_app_functions():
    module = load_natural_intelligence()
    fake = FakeMain()

    context = module.build_home_context(fake)

    assert context['success'] is True
    assert context['intent'] == 'home_context'
    assert context['occupancy']['summary'] == 'Everyone is home'
    assert context['lights']['on'] == 3
    assert context['health']['score'] == 96
    assert context['energy']['message'] == 'Your home is using 418W and 5.32 kWh today.'
    assert context['top_power_consumers'][0]['label'] == 'Fridge'
    assert context['top_power_consumers'][0]['power'] == '89 watts'


def test_insight_routes_energy_questions_to_energy_advisor_with_natural_units():
    module = load_natural_intelligence()
    answer = module.build_intelligence_answer(FakeMain(), 'how much electricity have I used today')

    assert answer['intent'] == 'energy'
    assert '418 watts' in answer['message']
    assert '5.3 kilowatt-hours' in answer['message']
    assert answer['top_power_consumers'][0]['label'] == 'Fridge'


def test_insight_explains_why_lights_are_on_without_dumping_all_devices():
    module = load_natural_intelligence()
    answer = module.build_intelligence_answer(FakeMain(), 'why are 3 lights on?')

    assert answer['intent'] == 'why_lights'
    assert answer['lights_on'] == ['Livingroom Light 1']
    assert 'Livingroom Light 1' in answer['message']
    assert 'Fridge' not in answer['message']


def test_light_hours_question_does_not_get_misread_as_command():
    module = load_natural_intelligence()
    answer = module.build_intelligence_answer(FakeMain(), 'lights on time today')

    assert answer['intent'] == 'light_hours'
    assert 'exact light-hours need event history' in answer['message']
    assert answer['lights_on'] == ['Livingroom Light 1']


def test_register_adds_stable_endpoint_aliases_once():
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
    assert fake.APP_VERSION == '1.6.0-alpha'
    assert fake.app.version == '1.6.0-alpha'
