from __future__ import annotations

import asyncio
from types import SimpleNamespace

import hybrid_assistant_mode
import shared_power_summary_bridge as bridge
from control_focus_mode import ControlFocusMode


class FakeAccounting:
    def __init__(self, application):
        self.application = application

    async def answer(self, query):
        return {
            "success": True,
            "active_power_readings": [
                {"id": "1", "label": "Fridge", "room": "Appliances", "value": 72.0}
            ],
            "technical": {
                "targeted_fallback_used": True,
                "targeted_detail": {"candidate_count": 8, "numeric_power_reading_count": 2},
                "idle_readings": [
                    {"id": "2", "label": "TV", "room": "Multimedia", "value": 0.0}
                ],
            },
        }


def test_shared_summary_reuses_accounting_discovery(monkeypatch):
    monkeypatch.setattr(bridge, "PowerAccountingService", FakeAccounting)
    service = ControlFocusMode(
        SimpleNamespace(VERSION="test"),
        metric_executor=SimpleNamespace(),
        enabled=False,
    )

    answer = asyncio.run(bridge.shared_power_summary(service, "show power devices"))

    assert answer["route"] == "mcp-power-summary"
    assert answer["active_power_total_w"] == 72.0
    assert answer["numeric_reading_count"] == 2
    assert answer["active_power_readings"][0]["label"] == "Fridge"
    assert answer["idle_power_readings"][0]["label"] == "TV"
    assert answer["technical"]["shared_power_discovery"] is True
    assert answer["technical"]["targeted_fallback_used"] is True


def test_install_patches_existing_service_and_repairs_octopus_export():
    bridge.install_shared_power_summary_bridge()

    assert ControlFocusMode.power_summary is bridge.shared_power_summary
    assert hybrid_assistant_mode.OctopusEnergySummary is hybrid_assistant_mode.OctopusLiveMeterSummary


def test_dashboard_and_current_summary_share_power_accounting_source():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dashboard = (root / "hubitat-mcp-ai" / "rootfs" / "app" / "dashboard_api.py").read_text(encoding="utf-8")
    entrypoint = (root / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py").read_text(encoding="utf-8")

    assert "power_accounting=PowerAccountingService(application)" in dashboard
    assert "install_shared_power_summary_bridge()" in entrypoint
