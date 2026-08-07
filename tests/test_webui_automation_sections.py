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


def test_automation_status_answer_always_shows_message_text_first():
    page = render_page("Hubitat MCP AI", "0.10.361")

    assert "const text=renderMessage(rawMessage);answer.appendChild(text);" in page


def test_automation_status_items_widget_is_appended_after_message_not_instead_of_it():
    page = render_page("Hubitat MCP AI", "0.10.361")

    assert (
        "if(data.route==='automation-status'&&Array.isArray(data.automation_items)"
        "&&data.automation_items.length)answer.appendChild(renderAutomationItems(data));"
    ) in page
