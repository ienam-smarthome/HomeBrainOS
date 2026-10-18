"""0.18.35: chat visibility, session isolation and browser storage UI contracts."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP_DIR))
from webui import render_page


def test_chat_controls_are_visible_above_the_ask_input():
    page=render_page("HomeBrain", "0.18.35")
    assert '<div id="chatList" class="chat-list"' in page
    assert 'id="newChat"' in page
    assert 'id="chatTranscript"' in page
    assert page.index('id="chatList"') < page.index('id="query"')
    assert "Chats are saved in this browser only, not synced or encrypted." in page
    assert "Delete chats on shared devices." in page


def test_browser_history_is_bounded_and_never_persists_technical_receipts():
    page=render_page("HomeBrain", "0.18.35")
    assert "CHAT_STORAGE_KEY='hmcp_chats_v1'" in page
    assert "CHAT_LIMIT=20" in page
    assert "CHAT_MESSAGE_LIMIT=32" in page
    assert "CHAT_CONTENT_LIMIT=6000" in page
    assert "messages:normalizedMessages(chat.messages)" in page
    assert "localStorage.setItem(CHAT_STORAGE_KEY,JSON.stringify(safe))" in page
    assert "sessionStorage.getItem(historyKey)" in page
    assert "function deleteChat(id)" in page
    assert "sessionStorage.removeItem('hmcp_history_'+id)" in page
    assert "JSON.stringify(data,null,2)" in page  # transient current-answer technical copy
    assert "JSON.stringify(safe)" in page     # only bounded visible-text history persisted


def test_new_and_restored_chats_are_separate_fresh_session_contexts():
    page=render_page("HomeBrain", "0.18.35")
    assert "let sessionId=sessionStorage.getItem('hmcp_session_id')||newSessionId()" in page
    assert "sessionId=newSessionId();historyKey='hmcp_history_'+sessionId" in page
    assert "conversationHistory=[];query.value='';modelTier.value='free'" in page
    assert "sessionId=target.id;historyKey='hmcp_history_'+sessionId" in page
    assert "conversationHistory=target.messages.slice(-8)" in page
    assert "session_id:requestSessionId" in page
    assert "const selectedTier=modelTier.value;" in page
    assert "const history=conversationHistory.slice(-8)" in page
    assert "if(sequence===requestSequence&&requestSessionId===sessionId)" in page
    assert "requestSequence++" in page
    assert "activeRequest.abort()" in page


def test_reopen_does_not_restore_live_confirmation_or_auto_speech():
    page=render_page("HomeBrain", "0.18.35")
    assert "showAnswer({route:'saved-chat',message:rows.at(-1).content})" in page
    assert "suggestedAction=data.route==='saved-chat'?null:" in page
    assert "readAnswers&&data.route!=='saved-chat'" in page
    assert "stopAudio();suggestedAction=null" in page
    assert "renderTranscript(hasFinal?rows.slice(0,-2):rows)" in page
    assert "body.textContent=message.content" in page
    assert 'data.confirmation_required===true' in page  # still allowed live


def test_existing_ask_and_provider_choices_remain_unchanged():
    page=render_page("HomeBrain", "0.18.35")
    for token in ('id="ask"','id="answer"','id="speak"','id="modelTier"',
                  '<option value="free">','<option value="claude">',
                  'api/ask','api/status','api/dashboard','api/request-progress',
                  'model_tier:selectedTier'):
        assert token in page
    assert "modelTier.value='free'" in page


@pytest.mark.skipif(shutil.which("node") is None,reason="Node unavailable")
def test_full_homebrain_script_is_valid_javascript(tmp_path):
    page=render_page("HomeBrain", "0.18.35")
    match=re.search(r"<script>([\s\S]*?)</script>",page)
    assert match is not None
    path=tmp_path/"homebrain-inline.js"
    path.write_text(match.group(1),encoding="utf-8")
    result=subprocess.run(["node","--check",str(path)],
                          capture_output=True,text=True,check=False,timeout=15)
    assert result.returncode==0,result.stderr
