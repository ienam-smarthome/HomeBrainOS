from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from webui import render_page  # noqa: E402


def test_mobile_voice_is_time_bounded_and_submits_after_pause():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.4-alpha"))

    assert "recognition.interimResults=true" in page
    assert "recognition.continuous=false" in page
    assert "activeVoiceStop" in page
    assert "hardTimer=setTimeout" in page
    assert "},9000)" in page
    assert "Listening… speak now. It will send after you pause." in page
    assert "silenceTimer=setTimeout" in page
    assert "submit(heard)" in page
    assert "recognition.interimResults=false" not in page


def test_voice_button_can_stop_and_never_remains_permanently_listening():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.4-alpha"))

    assert "if(activeVoiceStop){activeVoiceStop();return}" in page
    assert "voiceUi(false)" in page
    assert "recognition.abort()" in page
    assert "Listening timed out. Tap Speak and try again." in page
    assert "Microphone permission is blocked" in page
    assert page.count("function startVoice()") == 1
