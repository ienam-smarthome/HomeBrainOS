from __future__ import annotations

from webui_homebrain import render_homebrain_page


HOME_BRAIN_MOBILE_PATCH = r"""
#status{display:none}
.status-row{align-items:center}
#summaryCard.dashboard-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.summary-tile{width:auto;margin:0;background:var(--tile);color:var(--text);text-align:left;border-radius:14px;padding:14px;min-height:88px;transition:background .15s,box-shadow .15s,transform .15s}
.summary-tile:hover,.summary-tile:focus{background:#3a3a3d;box-shadow:inset 0 0 0 1px rgba(147,197,253,.35);outline:0}
.summary-tile:active{transform:translateY(1px)}
.summary-tile.warning{box-shadow:inset 0 0 0 1px rgba(245,158,11,.55)}
.summary-tile .big{font-size:28px;line-height:1.05;overflow-wrap:normal}
.summary-tile .mini{font-size:12px}
.summary-meta{grid-column:1/-1;display:flex;gap:8px 16px;flex-wrap:wrap;align-items:center;padding:2px 2px 0;color:var(--muted);font-size:12px}
.summary-meta strong{color:var(--text);font-weight:700}
#ask.working-button{background:#1d4ed8}
.result-list{max-height:68vh;overflow:auto;padding-right:2px}
.answer-shell{min-width:0}
.answer-text{max-width:100%}
@media(max-width:820px){
  #summaryCard.dashboard-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .shortcut-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .summary-tile{min-height:78px;padding:11px}
  .summary-tile .big{font-size:23px}
}
@media(max-width:420px){
  .status-row{display:grid;grid-template-columns:1fr;gap:6px}
  .pill{font-size:12px;padding:7px 10px;overflow-wrap:anywhere}
  .summary-tile .big{font-size:21px}
  .summary-meta{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px}
  .result-list{max-height:58vh}
}
"""


OLD_SUMMARY = """<div class="card grid" id="summaryCard">
<div class="metric"><div class="big" id="tools">—</div><div>MCP tools</div></div>
<div class="metric"><div class="big" id="mcpState">—</div><div>MCP connection</div></div>
<div class="metric"><div class="big" id="model">—</div><div>Ollama model</div></div>
<div class="metric"><div class="big" id="ollamaState">—</div><div>Ollama connection</div></div>
<div class="metric"><div class="big" id="lastRoute">—</div><div>Last route</div></div>
<div class="metric"><div class="big" id="lastTime">—</div><div>Response time</div></div>
</div>"""

NEW_SUMMARY = """<div class="card grid dashboard-grid" id="summaryCard">
<button class="summary-tile" data-q="Which lights are on?"><div class="big" id="dashLights">—</div><div>Lights on</div><div class="mini">Tap for live details</div></button>
<button class="summary-tile" data-q="Which motion sensors are active?"><div class="big" id="dashMotion">—</div><div>Motion active</div><div class="mini">Live Hubitat states</div></button>
<button class="summary-tile" data-q="Which switches are on?"><div class="big" id="dashSwitches">—</div><div>Switches on</div><div class="mini">Excludes lights</div></button>
<button class="summary-tile" id="batterySummary" data-q="Which batteries are low?"><div class="big" id="dashBatteries">—</div><div>Low batteries</div><div class="mini">At or below 20%</div></button>
<div class="summary-meta"><span>AI <strong id="model">—</strong></span><span>Last route <strong id="lastRoute">—</strong></span><span>Last response <strong id="lastTime">—</strong></span><span>Dashboard <strong id="dashAge">Loading…</strong></span></div>
</div>"""


OLD_STATUS_FUNCTION = """async function status(){try{const response=await fetch('/api/status');const data=await response.json();setPill('status',data.mcp?.online,data.mcp?.online?'Online · Hubitat MCP ready':'MCP unavailable');setPill('mcpStatus',data.mcp?.online,data.mcp?.online?`MCP online · ${data.mcp.tools||0} tools`:`MCP offline · ${data.mcp?.error||'unavailable'}`);setPill('ollamaStatus',data.ollama?.online,data.ollama?.online?`Ollama online · ${data.ollama.model}`:`Ollama offline · ${data.ollama?.error||'unavailable'}`);document.getElementById('tools').textContent=data.mcp?.tools??'—';document.getElementById('mcpState').textContent=data.mcp?.online?'Online':'Offline';document.getElementById('model').textContent=data.ollama?.model||'—';document.getElementById('ollamaState').textContent=data.ollama?.online?'Online':'Offline'}catch(error){setPill('status',false,'Status error: '+error.message)}}"""

NEW_STATUS_FUNCTION = """function setDash(id,value){const node=document.getElementById(id);if(node)node.textContent=value===null||value===undefined?'—':String(value)}async function status(){const results=await Promise.allSettled([fetch('/api/status'),fetch('/api/dashboard')]);if(results[0].status==='fulfilled'){try{const data=await results[0].value.json();const runtime=data.ollama||{};setPill('mcpStatus',data.mcp?.online,data.mcp?.online?`Hubitat MCP · ${data.mcp.tools||0} tools`:`Hubitat MCP offline · ${data.mcp?.error||'unavailable'}`);let aiState=false,aiText='Ollama offline · '+(runtime.error||'unavailable');if(runtime.online){if(runtime.model_loaded){aiState=true;aiText=`AI ready · ${runtime.model}`;}else if(runtime.model_present){aiState=null;aiText=`AI available · ${runtime.model} loads on demand`;}else{aiText=`AI model missing · ${runtime.model||'not configured'}`;}}setPill('ollamaStatus',aiState,aiText);document.getElementById('model').textContent=runtime.routine_model||runtime.model||'—'}catch(error){setPill('mcpStatus',false,'Status error · '+error.message)}}else setPill('mcpStatus',false,'Status request failed');if(results[1].status==='fulfilled'){try{const dash=await results[1].value.json();setDash('dashLights',dash.lights_on);setDash('dashMotion',dash.motion_active);setDash('dashSwitches',dash.switches_on);setDash('dashBatteries',dash.low_batteries);const battery=document.getElementById('batterySummary');battery?.classList.toggle('warning',Number(dash.low_batteries)>0);const age=document.getElementById('dashAge');if(age)age.textContent=dash.success?'Live':'Unavailable'}catch(error){const age=document.getElementById('dashAge');if(age)age.textContent='Unavailable'}}}"""


CLIENT_STATE_MARKER = """document.getElementById('readAnswers').checked=readAnswers;"""
CLIENT_STATE_REPLACEMENT = """document.getElementById('readAnswers').checked=readAnswers;input.value=localStorage.getItem('hmcp_last_query')||'';let activeController=null,activeRequestSerial=0,pendingUser=null;let clientId=localStorage.getItem('hmcp_client_id');if(!clientId){clientId=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():'hmcp-'+Date.now()+'-'+Math.random().toString(16).slice(2);localStorage.setItem('hmcp_client_id',clientId);}"""


OLD_SUBMIT_FUNCTION = """async function submit(query){query=(query||input.value).trim();if(!query)return;input.value='';const prior=history.slice(-10);history.push({role:'user',content:query});save();working.classList.add('show');ask.disabled=true;ask.textContent='Working…';clearOutput();output.appendChild(el('div','answer-text','Working on: '+query));try{const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,history:prior})});const answer=await response.json();showAnswer(answer);history.push({role:'assistant',content:answer.message||''});save()}catch(error){showAnswer({success:false,route:'error',message:'Request failed: '+error.message})}finally{working.classList.remove('show');ask.disabled=false;ask.textContent='Ask';status()}}"""

NEW_SUBMIT_FUNCTION = """async function submit(query){query=(query||input.value).trim();if(!query)return;input.value=query;localStorage.setItem('hmcp_last_query',query);if(activeController)activeController.abort();if(window.speechSynthesis)window.speechSynthesis.cancel();if(pendingUser&&history.length&&history[history.length-1]?.role==='user'&&history[history.length-1]?.content===pendingUser)history.pop();const prior=history.slice(-10);history.push({role:'user',content:query});pendingUser=query;save();const controller=new AbortController();activeController=controller;const serial=++activeRequestSerial;working.textContent='Working… submit another question to stop this request.';working.classList.add('show');ask.disabled=false;ask.classList.add('working-button');ask.textContent='Stop & ask';clearOutput();output.appendChild(el('div','answer-text','Working on: '+query));try{const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json','X-HMCP-Client':clientId},body:JSON.stringify({query,history:prior}),signal:controller.signal});if(serial!==activeRequestSerial)return;if(response.status===409)return;const answer=await response.json();showAnswer(answer);pendingUser=null;history.push({role:'assistant',content:answer.message||''});save()}catch(error){if(error.name==='AbortError')return;if(serial===activeRequestSerial)showAnswer({success:false,route:'error',message:'Request failed: '+error.message})}finally{if(serial===activeRequestSerial){activeController=null;working.classList.remove('show');ask.classList.remove('working-button');ask.textContent='Ask';status()}}}"""


def render_page(title: str, version: str) -> str:
    """Render a compact HomeBrain-style interface without duplicate status tiles."""
    page = render_homebrain_page(title, version)
    page = page.replace(OLD_SUMMARY, NEW_SUMMARY)
    page = page.replace(OLD_STATUS_FUNCTION, NEW_STATUS_FUNCTION)
    page = page.replace(
        '<button class="secondary" id="refreshMcp">Refresh MCP tools</button>',
        '<button class="secondary" data-q="Ollama diagnostics">Ollama diagnostics</button>'
        '<button class="secondary" id="refreshMcp">Refresh MCP tools</button>',
    )
    page = page.replace(CLIENT_STATE_MARKER, CLIENT_STATE_REPLACEMENT)
    page = page.replace(OLD_SUBMIT_FUNCTION, NEW_SUBMIT_FUNCTION)
    page = page.replace("setInterval(status,30000);", "setInterval(status,15000);")
    return page.replace("</style>", HOME_BRAIN_MOBILE_PATCH + "</style>", 1)
