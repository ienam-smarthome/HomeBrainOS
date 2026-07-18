from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from webui import render_page  # noqa: E402


def test_context_webui_reuses_existing_client_id_and_sends_session_id():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.0-alpha"))

    assert page.count("let clientId=") == 1
    assert "session_id:clientId" in page
    assert "'X-HMCP-Client':clientId" in page
    assert 'id="clearConversation"' in page
    assert "/api/conversation-context/clear" in page


def test_context_webui_keeps_device_and_mcp_catalogue_buttons():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.0-alpha"))

    assert 'id="mcpToolCatalogue"' in page
    assert 'id="deviceCatalogue"' in page
    assert 'id="clearConversation"' in page
    assert 'id="refreshMcp"' in page
