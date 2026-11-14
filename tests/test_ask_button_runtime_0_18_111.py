"""Regression: the real command bar Ask path preserves in-page conversation.

Executes production submit() and resetConversation() in Node against a
fictional DOM and network. No Hubitat, HA or provider calls are sent.
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
    page = render_page("HomeBrain", "0.18.460")
    assert "let activeRequest=null,requestSequence=0;" in page
    assert (page.index("let activeRequest=null,requestSequence=0;")
            < page.index("function resetConversation()")
            < page.index("async function submit(text){")
            < page.index("document.getElementById('commandForm').onsubmit"))
    assert "event.preventDefault();void submit()" in page
    assert 'id="chatList"' not in page


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_real_ask_handler_submits_and_new_topic_resets_context(tmp_path):
    page = render_page("HomeBrain", "0.18.460")
    state_start = "let activeRequest=null,requestSequence=0;"
    state = state_start + page.split(state_start, 1)[1].split(
        "function firmwareUpdateAvailable(", 1
    )[0]
    submit = "async function submit(text){" + page.split(
        "async function submit(text){", 1
    )[1].split("document.getElementById('commandForm').onsubmit", 1)[0]

    harness = r"""
const assert=require('node:assert/strict');
let id=0;
const newSessionId=()=>('test-'+(++id));
let sessionId=newSessionId();
const query={value:'Why is the light on?',focus(){},blur(){}};
let answer={hidden:false,textContent:'',classList:{add(){},remove(){}},
  querySelector(){return {textContent:''}}};
const feed={replaceChildren(){},appendChild(){},prepend(){}};
const modelTier={value:'free'};
const resetButton={onclick:null};
const fields={lastRoute:{textContent:''},lastTime:{textContent:''},resetContext:resetButton};
function element(){
  return {textContent:'',id:'',hidden:false,classList:{add(){},remove(){}},
    setAttribute(){},appendChild(){},replaceChildren(){}};
}
const document={
  getElementById(id){if(fields[id])return fields[id];throw Error('Unexpected ID '+id)},
  createElement:element,
};
const calls=[],shown=[];
const MAX_CHAT_PROMPT_CHARS=12000;
let activeTrace=[],currentQuestion='';
function beginExchange(question){currentQuestion=question;answer=element();answer.querySelector=()=>({textContent:''});return answer}
function syncCommandBar(){}
function recordTrace(){}
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
  await submit();
  assert.equal(calls.length,1,'Ask must call live /api/ask');
  assert.equal(calls[0].request.query,'Why is the light on?');
  assert.deepEqual(calls[0].request.history,[]);
  assert.equal(shown.at(-1).message,'Verified live read answer');
  assert.equal(conversationHistory.length,2);

  query.value='And why at night?';
  await submit();
  assert.equal(calls.length,2);
  assert.deepEqual(calls[1].request.history,[
    {role:'user',content:'Why is the light on?'},
    {role:'assistant',content:'Verified live read answer'}
  ]);
  const oldSession=sessionId;
  resetButton.onclick();
  assert.notEqual(sessionId,oldSession);
  assert.equal(conversationHistory.length,0);
  assert.equal(query.value,'');

  query.value='New topic';
  await submit();
  assert.equal(calls.length,3);
  assert.deepEqual(calls[2].request.history,[]);
  assert.equal(calls[2].request.session_id,sessionId);
  process.stdout.write('Ask, follow-up and New topic passed\n');
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
