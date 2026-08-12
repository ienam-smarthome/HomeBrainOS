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


def test_webui_dashboard_tiles_drop_switches_and_reorder_the_remaining_four() -> None:
    """The "Switches on" stat tile was removed at the user's request, and
    the remaining four reordered to Active rooms, Lights on, Motion
    active, Low batteries. The JS status() function updates each tile's
    DOM node in one try block -- if any referenced element id no longer
    exists, getElementById() returns null and the assignment throws,
    silently aborting every subsequent update in that same block (a real
    risk when removing a tile, not just a cosmetic change), so this also
    confirms no leftover "dashSwitches" reference remains in the script.
    """

    page = render_page("HomeBrain", "0.10.417")

    assert "Switches on" not in page
    assert "dashSwitches" not in page
    assert "switches_on" not in page

    order = [
        page.index(">Active rooms<"),
        page.index(">Lights on<"),
        page.index(">Motion active<"),
        page.index(">Low batteries<"),
    ]
    assert order == sorted(order), order


def test_webui_shortcuts_drop_hub_resources_device_health_and_weather() -> None:
    """These three shortcuts were plain NLP-query buttons with no live
    data behind them (unlike the stat tile row) and were removed at the
    user's request in favour of more directly useful shortcuts."""

    page = render_page("HomeBrain", "0.10.417")

    assert "Hub resources" not in page
    assert "Device health" not in page
    assert "🌦️ Weather" not in page
    assert "Open sensors" in page
    assert "Firmware update" in page
    # "Hub health" (a distinct, pre-existing shortcut) must survive --
    # confirms the removal targeted the right three buttons, not a
    # substring match that also caught this one.
    assert "Hub health" in page


def test_webui_title_is_html_escaped_and_script_values_are_json_encoded() -> None:
    page = render_page('</title><script>alert("x")</script>', "1.2.3")

    assert '<title>&lt;/title&gt;&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;</title>' in page
    # Every "</" inside the JSON-encoded value is escaped to "<\/" before
    # being interpolated into the inline <script> block below -- see the
    # dedicated escape-gap regression test for why.
    assert 'const TITLE="<\\/title><script>alert(\\"x\\")<\\/script>",VERSION="1.2.3";' in page


def test_webui_title_cannot_break_out_of_the_inline_script_tag() -> None:
    """Regression test (Tier 3 finding #14): json.dumps() does not escape a
    literal "</script>" sequence inside the string it encodes. Both title
    and version are interpolated directly into an inline <script> block, so
    an unescaped "</script>" in either value would close the script tag
    early, letting anything that followed it be parsed as raw HTML instead
    of a JS string literal. Both values now have every "</" escaped to
    "<\\/" so the browser's HTML parser never sees the literal closing-tag
    byte sequence, while the JS engine still reads the exact same string
    (a backslash before "/" is a harmless, standard JS string escape).
    """

    payload = '</script><img src=x onerror=alert(1)>'
    page = render_page(payload, "1.0.0")

    assert "</script><img" not in page
    assert "<\\/script><img" in page

    # A malicious version string must be defended identically.
    page_via_version = render_page("HomeBrain", payload)
    assert "</script><img" not in page_via_version
    assert "<\\/script><img" in page_via_version
