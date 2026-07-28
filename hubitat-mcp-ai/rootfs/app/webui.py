from __future__ import annotations

import html
import json


def render_page(title: str, version: str) -> str:
    """Render the self-contained Home Assistant ingress UI."""

    safe_title = html.escape(title)
    title_json = json.dumps(title)
    version_json = json.dumps(version)
    return (
        r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0b0c">
<title>__SAFE_TITLE__</title>
<style>
:root{color-scheme:dark;--bg:#0b0b0c;--card:#1f1f21;--tile:#303033;--text:#fff;--muted:#b9b9bd;--blue:#2f7df6;--green:#166534;--red:#991b1b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Arial,sans-serif}.wrap{max-width:960px;margin:auto;padding:24px}h1{font-size:36px;margin:8px 0 20px}.card{background:var(--card);border-radius:18px;padding:16px;margin:12px 0}.row,.grid{display:flex;gap:10px;flex-wrap:wrap}.pill{padding:8px 12px;border-radius:999px;background:#3a3a3d}.pill.ok{background:var(--green)}.pill.error{background:var(--red)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.tile{background:var(--tile);border-radius:14px;padding:14px;min-width:0}.big{font-size:22px;font-weight:700;overflow-wrap:anywhere;word-break:break-word}.muted{color:var(--muted);font-size:13px}input,button{width:100%;border:0;border-radius:12px;padding:14px;margin:7px 0;font:inherit}input{background:#fff;color:#111}button{background:var(--blue);color:#fff;cursor:pointer}.secondary{background:#333}.confirm{background:var(--green)}.answer{background:#000;border-radius:12px;padding:14px;min-height:52px;margin-top:8px;white-space:pre-wrap;overflow-wrap:anywhere}.answer-meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.badge{background:#243044;border-radius:999px;padding:4px 8px;font-size:12px}.answer-text{white-space:pre-wrap}.technical{margin-top:12px;color:var(--muted)}.technical summary{cursor:pointer}.technical pre{white-space:pre-wrap;overflow:auto;max-height:260px;background:#111;padding:10px;border-radius:8px}.busy{opacity:.65}
@media(max-width:520px){.wrap{padding:12px}h1{font-size:28px}.card{border-radius:12px;padding:11px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
</head>
<body><main class="wrap">
<h1>🏠 <span id="title"></span> <small id="version"></small></h1>
<section class="card row"><span class="pill" id="mcp">MCP unknown</span><span class="pill" id="ollama">Ollama unknown</span></section>
<section class="card grid">
<button class="tile secondary" data-q="Which lights are on?"><div class="big" id="dashLights">—</div><div>Lights on</div><div class="muted">Tap for live details</div></button>
<button class="tile secondary" data-q="Which motion sensors are active?"><div class="big" id="dashMotion">—</div><div>Motion active</div><div class="muted">Live Hubitat states</div></button>
<button class="tile secondary" data-q="Which switches are on?"><div class="big" id="dashSwitches">—</div><div>Switches on</div><div class="muted">Excludes lights</div></button>
<button class="tile secondary" data-q="Which batteries are low?"><div class="big" id="dashBatteries">—</div><div>Low batteries</div><div class="muted">At or below 20%</div></button>
<div class="tile"><div class="big" id="tools">—</div><div class="muted">MCP tools</div></div>
<div class="tile"><div class="big" id="model">—</div><div class="muted">Ollama model</div></div>
<div class="tile"><div class="big" id="lastRoute">—</div><div class="muted">Last route</div></div>
<div class="tile"><div class="big" id="lastTime">—</div><div class="muted">Response time</div></div>
</section>
<section class="card">
<input id="query" placeholder="Ask your Hubitat…" autocomplete="off">
<button id="ask">Ask</button><button class="secondary" id="speak">🎤 Speak</button>
<label class="muted"><input id="readAnswers" type="checkbox" style="width:auto"> Read answers aloud</label>
<div class="answer" id="answer">Ready</div>
</section>
<section class="card grid" id="shortcuts">
<button class="secondary" data-q="What's happening at home?">🏠 What's happening?</button>
<button class="secondary" data-q="Which lights are on?">💡 Lights</button>
<button class="secondary" data-q="Which batteries are low?">🪫 Low batteries</button>
<button class="secondary" data-q="List my Hubitat rooms">🚪 Rooms</button>
<button class="secondary" data-q="List automation rules">⚙️ Rules</button>
<button class="secondary" data-q="Check the hub health status">🧠 Hub health</button>
<button class="secondary" data-q="Show hub CPU and free memory">📊 Hub resources</button>
<button class="secondary" data-q="List devices that are offline or stale">⚠️ Device health</button>
<button class="secondary" data-q="What is the weather?">🌦️ Weather</button>
<button class="secondary" data-q="Recommend useful automations for my home">✨ Recommendations</button>
<button class="secondary" id="refresh">🧰 Refresh MCP tools</button>
</section>
<p class="muted">Powered by Ollama Online native function calling and Hubitat MCP.</p>
</main>
<script>
const TITLE=__TITLE__,VERSION=__VERSION__;
const newSessionId=()=>globalThis.crypto?.randomUUID?.()||`hmcp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
const sessionId=sessionStorage.getItem('hmcp_session_id')||newSessionId();
sessionStorage.setItem('hmcp_session_id',sessionId);
document.getElementById('title').textContent=TITLE;document.getElementById('version').textContent='v'+VERSION;
const query=document.getElementById('query'),ask=document.getElementById('ask'),answer=document.getElementById('answer');
const apiPath=path=>`${location.pathname.replace(/\/?$/,'/')}${path}`;
function pill(id,ok,text){const node=document.getElementById(id);node.textContent=text;node.className='pill '+(ok?'ok':'error')}
async function jsonResponse(response){const raw=await response.text();try{return JSON.parse(raw)}catch(error){throw new Error(`HTTP ${response.status}: ${raw||'empty response'}`)}}
let readAnswers=localStorage.getItem('hmcp_read_answers')==='true';document.getElementById('readAnswers').checked=readAnswers;document.getElementById('readAnswers').onchange=event=>{readAnswers=event.target.checked;localStorage.setItem('hmcp_read_answers',String(readAnswers))};
function showAnswer(data){answer.replaceChildren();const meta=document.createElement('div');meta.className='answer-meta';[data.route,data.model,data.elapsed_ms===undefined?null:`${(data.elapsed_ms/1000).toFixed(1)}s`].filter(Boolean).forEach(value=>{const badge=document.createElement('span');badge.className='badge';badge.textContent=value;meta.appendChild(badge)});if(meta.children.length)answer.appendChild(meta);const text=document.createElement('div');text.className='answer-text';text.textContent=data.message||data.detail||'No response';answer.appendChild(text);if(/please confirm/i.test(text.textContent)){const confirm=document.createElement('button');confirm.className='confirm';confirm.textContent='Confirm action';confirm.onclick=()=>submit('confirm');answer.appendChild(confirm)}const copy=document.createElement('button');copy.className='secondary';copy.textContent='Copy answer';copy.onclick=()=>navigator.clipboard?.writeText(text.textContent);answer.appendChild(copy);const details=document.createElement('details');details.className='technical';const summary=document.createElement('summary');summary.textContent='Technical details';const pre=document.createElement('pre');pre.textContent=JSON.stringify(data,null,2);details.append(summary,pre);answer.appendChild(details);document.getElementById('lastRoute').textContent=data.route||'—';document.getElementById('lastTime').textContent=data.elapsed_ms===undefined?'—':`${(data.elapsed_ms/1000).toFixed(1)}s`;if(readAnswers&&speechSynthesis&&text.textContent.length<1500){speechSynthesis.cancel();speechSynthesis.speak(new SpeechSynthesisUtterance(text.textContent))}}
async function status(){try{const [data,dash]=await Promise.all([jsonResponse(await fetch(apiPath('api/status'))),jsonResponse(await fetch(apiPath('api/dashboard')))]);pill('mcp',data.mcp?.online,data.mcp?.online?`MCP online · ${data.mcp.tools||0} tools`:`MCP offline · ${data.mcp?.error||'unavailable'}`);pill('ollama',data.ollama?.configured,data.ollama?.configured?`Ollama Online ready · ${data.ollama.model}`:'Ollama Online API key required');document.getElementById('tools').textContent=data.mcp?.tools??'—';document.getElementById('model').textContent=data.ollama?.model||'—';document.getElementById('dashLights').textContent=dash.lights_on??'—';document.getElementById('dashMotion').textContent=dash.motion_active??'—';document.getElementById('dashSwitches').textContent=dash.switches_on??'—';document.getElementById('dashBatteries').textContent=dash.low_batteries??'—'}catch(error){pill('mcp',false,'Status error · '+error.message)}}
async function submit(text){text=(text||query.value).trim();if(!text)return;query.value='';ask.disabled=true;answer.classList.add('busy');answer.textContent='Working…';try{const data=await jsonResponse(await fetch(apiPath('api/ask'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:text,session_id:sessionId})}));showAnswer(data)}catch(error){showAnswer({success:false,route:'error',message:'Request failed: '+error.message})}finally{ask.disabled=false;answer.classList.remove('busy');status()}}
ask.onclick=()=>submit();query.onkeydown=event=>{if(event.key==='Enter')submit()};document.querySelectorAll('[data-q]').forEach(button=>button.onclick=()=>submit(button.dataset.q));
document.getElementById('refresh').onclick=async()=>{try{const data=await jsonResponse(await fetch(apiPath('api/refresh'),{method:'POST'}));answer.textContent=`MCP tools refreshed: ${data.tools}.`;status()}catch(error){answer.textContent='Refresh failed: '+error.message}};
document.getElementById('speak').onclick=()=>{const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition){answer.textContent='Speech recognition is unavailable in this browser.';return}const recognition=new Recognition();recognition.lang='en-GB';recognition.onresult=event=>submit(event.results[0][0].transcript);recognition.start()};
status();setInterval(status,30000);
</script></body></html>"""
        .replace("__SAFE_TITLE__", safe_title)
        .replace("__TITLE__", title_json)
        .replace("__VERSION__", version_json)
    )


__all__ = ["render_page"]
