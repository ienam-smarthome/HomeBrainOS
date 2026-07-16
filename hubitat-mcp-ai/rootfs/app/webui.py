from __future__ import annotations

from webui_homebrain import render_homebrain_page


def render_page(title: str, version: str) -> str:
    """Render the HomeBrain-style mobile interface for Hubitat MCP AI."""
    return render_homebrain_page(title, version)
