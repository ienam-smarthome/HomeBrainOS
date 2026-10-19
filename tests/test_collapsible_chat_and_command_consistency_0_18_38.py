"""v0.18.38: compact, secure saved Q&A and evidence-consistent command issuer."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))
from webui import render_page
from historical_command_source_contract import (
    focused_command_observation, calibrate_command_causality,
)

QUESTION = (
    "Investigate Bedroom 3 Mesh OFF event on 12 October 2026 at 01:30 BST, "
    "compare possible command issuers. Read-only."
)
ISSUER = "Power saving: Bedroom 3 Mesh off @night"


def _command_rows():
    return [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7103", "since": "2026-10-12T00:20:00Z",
            "until": "2026-10-12T00:40:00Z",
        }},
        "details": {"observedEvents": [{
            "name": "command-off", "type": "command",
            "date": "2026-10-12T01:30:01.743+0100",
            "description": "Command called: off()",
            "producedBy": {"appId": 3950, "name": ISSUER},
        }]},
    }]


def test_collapsible_ui_structure_and_controls():
    page = render_page("HomeBrain", "0.18.38")
    for token in (
        'id="chatTranscript"', 'id="collapseChats"', 'id="expandChats"',
        'id="newChat"', '<details id="currentTurn" class="chat-turn chat-current" hidden>',
        'id="currentTurnSummary"', 'id="answer"',
        'id="modelTier"', 'id="ask"', 'id="speak"',
    ):
        assert token in page
    assert page.index('id="chatTranscript"') < page.index('id="query"')
    assert page.index('id="answer"') > page.index('id="query"')
    assert "function chatSummary(" in page
    assert "turn.className='chat-turn'" in page
    assert "turn.appendChild(chatSummary(" in page
    assert "document.getElementById('collapseChats').onclick" in page
    assert "document.getElementById('expandChats').onclick" in page
    assert ".chat-turn[hidden]{display:none}" in page


def test_all_saved_turns_are_collapsed_by_default_and_safe_markdown_is_shared():
    page = render_page("HomeBrain", "0.18.38")
    section = page.split("function renderTranscript(messages){", 1)[1].split(
        "function stopPendingChatRequest", 1
    )[0]
    assert "document.createElement('details')" in section
    assert "turn.open=true" not in section
    assert "(hasReply?rows.slice(1):rows).forEach" in section
    assert "renderMessage(row.content)" in section
    assert "innerHTML" not in section
    assert "turn.open=open" in section
    assert "if(current&&!current.hidden)current.open=open" in section
    assert ".chat-bubble>strong{" in page
    assert "body.textContent=message.content" not in page


def test_saved_replies_stay_collapsed_without_restoring_actions():
    page = render_page("HomeBrain", "0.18.38")
    assert "current.open=data.route!=='saved-chat'" in page
    assert "latest.hidden=false;latest.open=true" in page
    assert "document.getElementById('currentTurn').hidden=true" in page
    assert "showAnswer({route:'saved-chat',message:rows.at(-1).content})" in page
    assert "suggestedAction=data.route==='saved-chat'?null:" in page
    assert "readAnswers&&data.route!=='saved-chat'" in page
    assert "confirmation_required===true" in page
    assert "session_id:requestSessionId" in page
    assert "conversationHistory=target.messages.slice(-8)" in page
    assert "modelTier.value='free'" in page
    assert "localStorage.setItem(CHAT_STORAGE_KEY,JSON.stringify(safe))" in page


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_browser_turn_accordion_logic_with_minimal_dom(tmp_path):
    page = render_page("HomeBrain", "0.18.38")
    helper = (
        "function chatSummary("
        + page.split("function chatSummary(", 1)[1].split(
            "function stopPendingChatRequest", 1
        )[0]
    )
    node_test = r"""
class Element {
  constructor(name){this.tagName=name.toUpperCase();this.children=[];this.open=false;this.hidden=false;this.className='';this.textContent='';}
  append(...nodes){this.children.push(...nodes)}
  appendChild(node){this.children.push(node);return node}
  replaceChildren(...nodes){this.children=nodes}
  querySelectorAll(q){return this.children.filter(n=>n.tagName==='DETAILS' && n.className==='chat-turn')}
}
const elems={chatTranscript:new Element('div'),collapseChats:new Element('button'),expandChats:new Element('button'),currentTurn:new Element('details')};
const chatTranscript=elems.chatTranscript;
const document={createElement:(name)=>new Element(name),getElementById:(id)=>elems[id]};
const contents=[];
function renderMessage(content){contents.push(content);return new Element('div')}
""";
    node_test += helper
    node_test += r"""
renderTranscript([
  {role:'user',content:'Is Bedroom 3 Mesh offline?'},
  {role:'assistant',content:'**Offline** since Monday.'},
  {role:'user',content:'Which device?'},
  {role:'assistant',content:'Bedroom 3 Mesh.'},
]);
if(chatTranscript.children.length!==2)throw Error('Expected two paired accordions');
if(chatTranscript.children.some(x=>x.open))throw Error('Saved turns must default to collapsed');
if(contents[0]!=='**Offline** since Monday.')throw Error('Markdown must go via shared renderer');
elems.currentTurn.hidden=false;
setAllChatTurns(true);
if(chatTranscript.children.some(x=>!x.open)||!elems.currentTurn.open)throw Error('Expand all failed');
setAllChatTurns(false);
if(chatTranscript.children.some(x=>x.open)||elems.currentTurn.open)throw Error('Collapse all failed');
elems.currentTurn.hidden=true;
setAllChatTurns(true);
if(elems.currentTurn.open)throw Error('Hidden latest turn must not be expanded');
"""
    file = tmp_path / "chat_accordion_test.js"
    file.write_text(node_test, encoding="utf-8")
    result = subprocess.run(["node", str(file)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_positive_same_issuer_reconciles_contradictory_model_denial():
    record = focused_command_observation(QUESTION, _command_rows())
    assert record is not None
    assert record["recordedIssuerAppId"] == "3950"
    assert record["recordedIssuerName"] == ISSUER
    model = (
        'I could not verify the claim about "' + ISSUER
        + '" against evidence actually collected for that device this turn, '
        'so I will not provide an unverified answer.\n\n'
        'The trigger is still unknown.'
    )
    fixed, issues = calibrate_command_causality(model, record, None)
    assert "I could not verify the claim" not in fixed
    assert "**Recorded command verified:**" in fixed
    assert "app 3950" in fixed
    assert "trigger and physical outcome remain unverified" in fixed
    assert "The trigger is still unknown." in fixed
    assert "contradictory_recorded_issuer_denial" in issues


def test_wrong_named_issuer_and_missing_command_never_get_upgraded():
    record = focused_command_observation(QUESTION, _command_rows())
    unrelated = (
        'I could not verify the claim about "Other App" against evidence '
        'actually collected for that device this turn, so I will not '
        'provide an unverified answer.'
    )
    fixed, issues = calibrate_command_causality(unrelated, record, None)
    assert unrelated in fixed
    assert "contradictory_recorded_issuer_denial" not in issues
    assert focused_command_observation(QUESTION, _command_rows()[:-1]) is None
    preserved, issues = calibrate_command_causality(unrelated, None, None)
    assert preserved == unrelated
    assert issues == []
