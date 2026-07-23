from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from runtime_route_bridge import add_apps_shortcut


def test_add_apps_shortcut_places_apps_after_rules():
    page = (
        '<button class="secondary" data-q="List automation rules">⚙️ Rules</button>'
        '<button class="secondary" data-q="Check the hub health status">🧠 Hub health</button>'
    )

    rendered = add_apps_shortcut(page)

    rules = rendered.index('data-q="List automation rules"')
    apps = rendered.index('data-q="List apps"')
    health = rendered.index('data-q="Check the hub health status"')
    assert rules < apps < health
    assert rendered.count('data-q="List apps"') == 1


def test_add_apps_shortcut_is_idempotent():
    page = (
        '<button class="secondary" data-q="List automation rules">⚙️ Rules</button>\n'
        '<button class="secondary" data-q="List apps">🧩 Apps</button>'
    )
    assert add_apps_shortcut(page) == page
