from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from agent_prompt_policy import render_device_manifest  # noqa: E402


DEVICE = {
    "id": "42",
    "label": "Kitchen Switch",
    "room": "Kitchen",
    "capabilities": ["Switch"],
    "attributes": {"switch": "on"},
}


def test_render_device_manifest_includes_state_by_default():
    manifest = render_device_manifest([DEVICE])

    assert "Kitchen Switch" in manifest
    assert "Current:" in manifest
    assert "switch=on" in manifest


def test_render_device_manifest_can_omit_state_for_speculative_prompts():
    manifest = render_device_manifest([DEVICE], include_state=False)

    assert "Kitchen Switch" in manifest
    assert "Capabilities: Switch" in manifest
    assert "Current:" not in manifest
    assert "switch=on" not in manifest


def test_render_device_manifest_surfaces_valuestr_only_sensors():
    """Regression test: Octopus Energy (and similar Home-Assistant-bridged)
    sensors report their live reading only as valueStr, with value always
    null -- these attribute names were not recognised at all before, so
    such a device's manifest entry never showed a Current: section, making
    it look state-less even though the reading is right there.
    """

    device = {
        "id": "7434",
        "label": "Octopus Meter Current Power",
        "room": "Octopus Energy",
        "capabilities": ["Refresh", "HealthCheck"],
        "attributes": {"value": None, "valueStr": "231 W", "unit": "none"},
    }

    manifest = render_device_manifest([device])

    assert "Octopus Meter Current Power" in manifest
    assert "Current:" in manifest
    assert "valueStr=231 W" in manifest
