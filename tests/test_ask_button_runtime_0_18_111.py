"""Regression: clicking Ask and New topic in the history-free UI must work.

Executes the production submit() handler in Node with fake DOM/network.
No calls are made to Home Assistant, Hubitat, or the selected AI provider.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from webui import render_page


def test_request_state_is_initialized_before_click_handlers():
    page = render_page("HomeBrain", "0.18.111")
    assert "let activeRequest=null,requestSequence=0;" in page
    assert (page.index("let activeRequest=null,requestSequence=0;")
            < page.index("function resetConversation()")
            < page.index("async function submit(text){")
            < page.index("ask.onclick=()=>submit();"))
    assert 'id="chatList"' not in page


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_real_ask_handler_submits_and_new_topic_resets_context(tmp_path):
    page = render_page("HomeBrain", "0.18.111")
    state_start = "let activeRequest=null,requestSequence=0;"
    state = state_start + page.split(state_start, 1)[1].split(
        "function firmwareUpdateAvailable(", 1
    )[0]
    submit = "async function submit(text){" + page.split(
        "async function submit(text){", 1
    )[1].split("ask.onclick=()=>submit();", 1)[0] + "ask.onclick=()=>submit();"

    harness = r"""
const assert=require('node:assert/strict');
let id=0;
const newSessionId=()=>('test-'+(++id));
let sessionId=newSessionId();
const query={value:'Why is the light on?',focus(){}};
const ask={onclick:null};
const answer={textContent:'',classList:{add(){},remove(){}}};
const modelTier={value:'free'};
const resetButton={onclick:null};
const document={
  getElementById(id){
    if(id==='resetContext')return resetButton;
    if(id==='lastRoute'||id==='lastTime')return {textContent:''};
    throw Error('Unexpected document ID '+id)
  },
};
const calls=[],shown=[];
const MAX_CHAT_PROMPT_CHARS=12000;
function stopAudio(){}
function showAnswer(data){shown.push(data);answer.textContent=data.message}
function status(){}
function apiPath(route){return route}
async function jsonResponse(response){return response.json()}
function askApiErrorMessage(){return 'Bad response'}
async function fetch(route,options={}){
  if(route==='api/ask'){
    calls.push({route,request:JSON.parse(options.body)});
    return {ok:true,json:async()=>({success:true,message:'Verified live read answer'})};
  }
  return {ok:true,json:async()=>({completed:true})};
}
"""
    scenario = r"""
(async()=>{
  assert.equal(typeof ask.onclick,'function','Ask must have a click handler');
  await ask.onclick();
  assert.equal(calls.length,1,'Ask click must call the live API');
  assert.equal(calls[0].request.query,'Why is the light on?');
  assert.deepEqual(calls[0].request.history,[]);
  assert.equal(shown.at(-1).message,'Verified live read answer');
  assert.equal(conversationHistory.length,2);

  query.value='And why at night?';
  await ask.onclick();
  assert.equal(calls.length,2);
  assert.deepEqual(calls[1].request.history,[
    {role:'user',content:'Why is the light on?'},
    {role:'assistant',content:'Verified live read answer'}
  ]);
  const oldSession=sessionId;
  resetButton.onclick();
  assert.notEqual(sessionId,oldSession);
  assert.equal(conversationHistory.length,0);
  assert.equal(answer.textContent,'Ready for a new topic.');

  query.value='New topic';
  await ask.onclick();
  assert.equal(calls.length,3);
  assert.deepEqual(calls[2].request.history,[]);
  assert.equal(calls[2].request.session_id,sessionId);
  process.stdout.write('Ask, follow-up and New topic passed\\n');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    script = tmp_path / "ask_handler.js"
    script.write_text(harness + state + "\n" + submit + "\n" + scenario,
                      encoding="utf-8")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True,
        check=False, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Ask, follow-up and New topic passed" in result.stdout
