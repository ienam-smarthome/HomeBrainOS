"""0.18.110 compact HomeBrain web UI; retired saved transcripts."""
import sys
import re
import shutil
import subprocess
from pathlib import Path
import pytest
APP_DIR=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP_DIR))
from webui import render_page

def test_minimal_current_answer_controls():
    page=render_page("HomeBrain","0.18.110")
    for required in ('id="query"','id="ask"','id="speak"','id="answer"',
                     'id="modelTier"','id="resetContext"','id="micFab"',
                     "Technical details", "JSON.stringify(data,null,2)"):
        assert required in page
    for retired in ('id="chatList"','id="chatTranscript"','id="newChat"',
                    'id="collapseChats"','id="expandChats"',
                    'id="currentTurn"','renderTranscript(', 'renderChatList()'):
        assert retired not in page
    assert page.index('id="query"')<page.index('id="ask"')<page.index('id="answer"')

def test_bounded_ephemeral_context_without_persisted_chat():
    page=render_page("HomeBrain","0.18.110")
    for text in ("let suggestedAction=null,conversationHistory=[];",
                 "const history=conversationHistory.slice(-8);",
                 "conversationHistory=conversationHistory.slice(-8);",
                 "let sessionId=newSessionId();",
                 "localStorage.removeItem('hmcp_chats_v1')",
                 "key.startsWith('hmcp_history_')"):
        assert text in page
    assert "localStorage.setItem(" not in page
    assert "sessionStorage.setItem(" not in page

def test_new_topic_resets_context_and_keeps_live_confirmation():
    page=render_page("HomeBrain","0.18.110")
    assert "document.getElementById('resetContext').onclick=resetConversation" in page
    assert "conversationHistory=[];sessionId=newSessionId()" in page
    assert "requestSequence++" in page
    assert "activeRequest.abort()" in page
    assert "if(data.confirmation_required===true)" in page
    assert "session_id:requestSessionId" in page
    assert "api/request-progress" in page

@pytest.mark.skipif(shutil.which("node") is None,reason="Node unavailable")
def test_script_is_valid_javascript(tmp_path):
    page=render_page("HomeBrain","0.18.110")
    script=re.search(r"<script>([\s\S]*?)</script>",page)
    assert script
    path=tmp_path/"webui.js"
    path.write_text(script.group(1),encoding="utf-8")
    result=subprocess.run(["node","--check",str(path)],
                          capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
