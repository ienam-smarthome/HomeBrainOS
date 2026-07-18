from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from fast_fallback_device_index import FastFallbackRouter  # noqa: E402
from webui import render_page  # noqa: E402


class DummyClient:
    configured = True


class DummyIndex:
    pass


def test_top_level_router_accepts_control_verification_settings_at_startup():
    router = FastFallbackRouter(
        DummyClient(),
        device_index=DummyIndex(),
        attention_stale_hours=48,
        cpu_probe_enabled=False,
        control_verification_timeout_seconds=7,
        control_verification_initial_delay_seconds=0.2,
    )

    assert router.device_index is not None
    assert router.control_verification_timeout_seconds == 7
    assert router.control_verification_initial_delay_seconds == 0.2


def test_home_assistant_ingress_is_enabled_in_addon_config():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "version: '0.4.3-alpha'" in config
    assert "ingress: true" in config
    assert "ingress_port: 8788" in config
    assert "panel_title: Hubitat MCP AI" in config
    assert "panel_icon: mdi:home-assistant" in config


def test_rendered_web_ui_uses_relative_api_paths_for_ingress():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.3-alpha"))

    assert "fetch('/api/" not in page
    assert 'fetch("/api/' not in page
    assert "fetch('api/status')" in page
    assert "fetch('api/ask'" in page
    assert "fetch('api/conversation-context/clear'" in page
