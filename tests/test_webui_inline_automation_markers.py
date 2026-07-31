from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui import render_page  # noqa: E402


def test_webui_colours_embedded_paused_and_broken_markers_red():
    page = render_page("Hubitat MCP AI", "0.10.255")

    assert ".inline-critical{color:#f87171;font-weight:700}" in page
    assert "\\(Paused\\)" in page
    assert "\\*BROKEN\\*" in page
    assert "warning.className='inline-critical'" in page
    assert "?'(Paused)':'BROKEN'" in page
