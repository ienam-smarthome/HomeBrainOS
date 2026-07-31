from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui import render_page  # noqa: E402


def test_webui_renders_collapsible_filtered_automation_status_view():
    page = render_page("Hubitat MCP AI", "0.10.257")

    assert "function renderAutomationItems(data)" in page
    assert "Search apps and rules" in page
    assert "Expand all" in page
    assert "Collapse all" in page
    assert "AUTOMATION_STATUSES=['active','disabled','paused','broken','unknown']" in page
    assert "details.open=['paused','broken','unknown'].includes(status)" in page
    assert "data.route==='automation-status'" in page
    assert "cleanAutomationName(item.name)" in page
    assert "item.type==='rule'?'Rule Machine':'App'" in page
