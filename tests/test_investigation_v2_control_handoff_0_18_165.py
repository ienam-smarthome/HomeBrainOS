"""v0.18.165 control handoff remains navigational, never authorises writes."""
from __future__ import annotations
import sys
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.test_webui import render_v2_test_page
from investigation_v2.intent_boundary import incompatible_v2_control_request

def test_control_handoff_is_visible_without_scrolling_to_top():
    page=render_v2_test_page()
    assert '<a class="actionLink" href="./" id="mainAskDirect">' in page
    assert '<a class="actionLink" href="./" id="mainAskAfterRejection">' in page
    assert 'id="copyControlQuestion"' in page
    assert 'id="controlHelp" hidden' in page
    assert "Copy control request" in page

def test_v2_refusal_surfaces_navigational_handoff_without_forwarding_credentials():
    page=render_v2_test_page()
    assert "response.status===409&&data?.detail?.code==='v2_control_not_supported'" in page
    assert "el('controlHelp').hidden=false" in page
    assert "el('controlReason').textContent=explanation" in page
    assert "el('output').hidden=true;el('controlHelp').hidden=true;" in page
    assert "await copyTestText(el('question').value.trim())" in page
    assert "fetch(authUrl('api/ask')" not in page
    assert "fetch(authUrl('api/chat')" not in page
    assert "location.href=" not in page
    assert "secret=" not in page
    assert "innerHTML" not in page
    assert "localStorage" not in page
    assert "sessionStorage" not in page

def test_imperative_remains_refused_while_status_question_remains_read_only():
    assert incompatible_v2_control_request("Turn on Livingroom Light 2.") is True
    assert incompatible_v2_control_request("Is Livingroom Light 2 on?") is False
