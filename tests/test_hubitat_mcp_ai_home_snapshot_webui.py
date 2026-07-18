from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from webui import render_page  # noqa: E402


def test_home_snapshot_summary_and_groups_are_rendered():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.1-alpha"))

    assert "answer.display.summary" in page
    assert "result-summary" in page
    assert "result-section" in page
    assert "item.group" in page
    assert page.count("function itemList(items)") == 1


def test_existing_context_and_catalogue_patches_remain_present():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.1-alpha"))

    assert "session_id:clientId" in page
    assert 'id="deviceCatalogue"' in page
    assert 'id="clearConversation"' in page
    assert "/api/conversation-context/clear" in page
