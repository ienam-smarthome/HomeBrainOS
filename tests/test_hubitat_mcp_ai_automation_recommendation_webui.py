from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_recommendation_webui import (  # noqa: E402
    install_automation_recommendation_webui,
)


def test_recommendation_webui_adds_shortcut_and_route_labels():
    base = (
        '<button class="secondary" data-q="What can Ollama help with?">'
        '🤖 AI question guide</button>'
        "<script>function routeLabel(route){const labels={'error':'Error'};}</script>"
    )
    module = SimpleNamespace(patch_page=lambda page: page)

    install_automation_recommendation_webui(module)
    rendered = module.patch_page(base)

    assert "⚙️ Suggest automation" in rendered
    assert "Suggest one useful automation for the devices I have" in rendered
    assert "Ollama recommendation" in rendered
    assert "Hubitat recommendation (AI fallback)" in rendered
    assert "Hubitat recommendation" in rendered


def test_webui_patch_is_idempotent():
    base = (
        '<button class="secondary" data-q="What can Ollama help with?">'
        '🤖 AI question guide</button>'
        "<script>function routeLabel(route){const labels={'error':'Error'};}</script>"
    )
    module = SimpleNamespace(patch_page=lambda page: page)

    first = install_automation_recommendation_webui(module)
    second = install_automation_recommendation_webui(module)
    rendered = module.patch_page(base)

    assert first is second
    assert rendered.count("⚙️ Suggest automation") == 1
    assert rendered.count("Ollama recommendation") == 1
