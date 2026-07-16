from __future__ import annotations

import json


def render_page(title: str, version: str) -> str:
    title_json = json.dumps(title)
    version_json = json.dumps(version)
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#08090b">
<title>""" + title + r"""</title>
<style>
:root{color-scheme:dark;--bg:#08090b;--panel:#1d1e22;--panel2:#2b2d31;--text:#f7f8fa;--muted:#b7bdc8;--blue:#347ff0;--green:#13a85b;--red:#b3262d;--amber:#d98b18;--border:#353840}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}
main{width:min(1120px,100%);margin:auto;padding:20px}.header{display:flex;align-items:center;gap:14px;margin:8px 4px 20px}.header h1{font-size:clamp(27px,4vw,43px);margin:0}.logo{font-size:42px}
.panel{background:var(--panel);border:1px solid #202228;border-radius:24px;padding:20px;margin:14px 0;box-shadow:0 12px 28px #0005}
.statusbar{display:flex;flex-wrap:wrap;gap:9px}.pill{border-radius:999px;padding:9px 14px;background:var(--panel2);font-size:14px}.pill.online{background:#116934}.pill.offline{background:#8c1f25}.pill.warn{background:#7d5312}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card{background:var(--panel2);padding:18px;border-radius:18px;min-height:96px}.card b{display:block;font-size:28px}.card span{color:var(--muted)}
.chat{display:flex;flex-direction:column;gap:12px;max-height:48vh;overflow:auto;padding-right:4px}.bubble{padding:14px 16px;border-radius:18px;white-space:pre-wrap;line-height:1.42}.bubble.user{background:#18365d;align-self:flex-end;max-width:85%}.bubble.assistant{background:#111214;border:1px solid #245f3b;align-self:stretch}.bubble.meta{font-size:12px;color:var(--muted);background:transparent;padding:0 4px}
.inputrow{display:grid;grid-template-columns:1fr auto;gap:10px;margin-top:14px}input{width:100%;padding:18px;border:0;border-radius:16px;background:white;color:#111;font-size:18px}button{border:0;border-radius:16px;padding:15px 20px;background:var(--blue);color:white;font-size:17px;cursor:pointer}button:disabled{opacity:.55}.speak{background:#176f3a}.quick{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.quick button{background:var(--panel2);min-height:64px}.footer{color:var(--muted);font-size:12px;text-align:center;padding:16px}
@media(max-width:760px){main{padding:12px}.panel{border-radius:20px;padding:14px}.grid,.quick{grid-template-columns:repeat(2,minmax(0,1fr))}.inputrow{grid-template-columns:1fr}.header h1{font-size:29px}.logo{font-size:34px}.chat{max-height:44vh}}
</style>
</head>
<body>
<main>
  <div class="header"><div class="logo">🏠</div><h1><span id="title"></span> <small id="version"></small></h1></div>
  <section class="panel"><div class="statusbar">
    <span id="overall" class="pill warn">Starting…</span>
    <span id="mcp" class="pill">MCP unknown</span>
    <span id="ollama" class="pill">Ollama unknown</span>
    <span id="route" class="pill">Route: automatic</span>
  </div></section>

  <section class="panel">
    <div class="grid">
      <div class="card"><b id="tools">—</b><span>MCP tools</span></div>
      <div class="card"><b id="model">—</b><span>Ollama model</span></div>
      <div class="card"><b id="fallback">—</b><span>Fallback</span></div>
      <div class="card"><b id="lastRoute">—</b><span>Last response route</span></div>
    </div>
  </section>

  <section class="panel">
    <div id="chat" class="chat"><div class="bubble assistant">Ready. Ask about your Hubitat devices, rooms, rules, or hub status.</div></div>
    <div class="inputrow">
      <input id="query" placeholder="Ask your Hubitat…" autocomplete="off">
      <button id="ask">Ask</button>
    </div>
    <div class="inputrow">
      <button id="speak" class="speak">🎤 Speak</button>
      <button id="clear">Clear conversation</button>
    </div>
  </section>

  <section class="panel">
    <div class="quick">
      <button data-q="What's happening at home?">🏠 What's happening?</button>
      <button data-q="Which lights are on?">💡 Lights on</button>
      <button data-q="Which batteries are low?">🪫 Low batteries</button>
      <button data-q="Check the hub health status">🧠 Hub health</button>
      <button data-q="List my Hubitat rooms">🚪 Rooms</button>
      <button data-q="What is the weather?">🌦️ Weather</button>
      <button data-q="List active automation rules">⚙️ Rules</button>
      <button data-q="Find devices that may need attention">⚠️ Attention</button>
    </div>
  </section>
  <div class="footer">Powered by Ollama and kingpanther13's Hubitat MCP Rule Server. HomeBrain-style web interface; MCP is the device-control source.</div>
</main>
<script>
const TITLE=""" + title_json + r"""; const VERSION=""" + version_json + r""";
document.getElementById('title').textContent=TITLE; document.getElementById('version').textContent='v'+VERSION;
const chat=document.getElementById('chat'), input=document.getElementById('query'), ask=document.getElementById('ask');
let history=JSON.parse(sessionStorage.getItem('hmcp_history')||'[]');
function save(){sessionStorage.setItem('hmcp_history',JSON.stringify(history.slice(-12)))}
function bubble(role,text,meta=''){const el=document.createElement('div');el.className='bubble '+role;el.textContent=text;chat.appendChild(el);if(meta){const m=document.createElement('div');m.className='bubble meta';m.textContent=meta;chat.appendChild(m)}chat.scrollTop=chat.scrollHeight}
async function status(){try{const r=await fetch('/api/status');const s=await r.json();setPill('mcp',s.mcp?.online, s.mcp?.online?`MCP online · ${s.mcp.tools||0} tools`:`MCP offline · ${s.mcp?.error||'unavailable'}`);setPill('ollama',s.ollama?.online,s.ollama?.online?`Ollama online · ${s.ollama.model}`:`Ollama offline · ${s.ollama?.error||'unavailable'}`);setPill('overall',s.mcp?.online,s.mcp?.online?'Hubitat MCP ready':'Hubitat MCP unavailable');document.getElementById('tools').textContent=s.mcp?.tools??'—';document.getElementById('model').textContent=s.ollama?.model||'—';document.getElementById('fallback').textContent=s.fallback_enabled?'Enabled':'Disabled'}catch(e){setPill('overall',false,'Status error: '+e.message)}}
function setPill(id,ok,text){const e=document.getElementById(id);e.textContent=text;e.className='pill '+(ok?'online':'offline')}
async function submit(q){q=(q||input.value).trim();if(!q)return;input.value='';const priorHistory=history.slice(-10);bubble('user',q);history.push({role:'user',content:q});save();ask.disabled=true;const started=performance.now();const timer=setInterval(()=>{ask.textContent=`Working… ${Math.floor((performance.now()-started)/1000)}s`},1000);ask.textContent='Working…';try{const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q,history:priorHistory})});const a=await r.json();const text=a.message||a.detail||'No response';const seconds=Number.isFinite(a.elapsed_ms)?` · ${(a.elapsed_ms/1000).toFixed(1)}s`:'';bubble('assistant',text,`Route: ${a.route||'unknown'}${a.model?' · '+a.model:''}${seconds}`);history.push({role:'assistant',content:text});save();document.getElementById('lastRoute').textContent=a.route||'—';document.getElementById('route').textContent='Route: '+(a.route||'unknown');if(window.speechSynthesis&&text.length<900){const u=new SpeechSynthesisUtterance(text.replace(/[-•]\s/g,''));u.rate=1;window.speechSynthesis.cancel();window.speechSynthesis.speak(u)}}catch(e){bubble('assistant','Request failed: '+e.message)}finally{clearInterval(timer);ask.disabled=false;ask.textContent='Ask';status()}}
ask.onclick=()=>submit();input.addEventListener('keydown',e=>{if(e.key==='Enter')submit()});document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>submit(b.dataset.q));document.getElementById('clear').onclick=()=>{history=[];save();chat.innerHTML='<div class="bubble assistant">Conversation cleared.</div>'};
document.getElementById('speak').onclick=()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){bubble('assistant','Speech recognition is not supported by this browser.');return}const r=new SR();r.lang='en-GB';r.interimResults=false;r.onresult=e=>{const q=e.results[0][0].transcript;input.value=q;submit(q)};r.onerror=e=>bubble('assistant','Speech recognition error: '+e.error);r.start()};
status();setInterval(status,30000);
</script>
</body>
</html>"""
