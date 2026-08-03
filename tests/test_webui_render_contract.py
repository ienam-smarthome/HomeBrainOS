from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui import render_page  # noqa: E402


def test_webui_core_controls_and_routes_remain_present() -> None:
    page = render_page("HomeBrain", "0.10.318")

    for token in (
        "id=\"query\"",
        "id=\"ask\"",
        "id=\"answer\"",
        "id=\"micFab\"",
        "api/ask",
        "api/status",
        "api/dashboard",
        "api/refresh",
        "function showAnswer(data)",
        "function renderAutomationItems(data)",
        "function startVoice()",
    ):
        assert token in page


def test_webui_title_is_html_escaped_and_script_values_are_json_encoded() -> None:
    page = render_page('</title><script>alert("x")</script>', "1.2.3")

    assert '<title>&lt;/title&gt;&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;</title>' in page
    assert 'const TITLE="</title><script>alert(\\"x\\")</script>",VERSION="1.2.3";' in page
