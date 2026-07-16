from __future__ import annotations

from webui_homebrain import render_homebrain_page


HOME_BRAIN_MOBILE_PATCH = r"""
.connection-tile{display:none}
#summaryCard .big{font-size:24px;line-height:1.05}
#summaryCard .metric>div:last-child{font-size:13px;line-height:1.2}
.model-value{font-size:20px!important;overflow-wrap:normal;word-break:normal;letter-spacing:-.02em}
#summaryCard .metric{min-height:78px}
#ask.working-button{background:#1d4ed8}
@media(max-width:820px){
  #summaryCard{grid-template-columns:repeat(2,minmax(0,1fr))}
  .shortcut-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  #summaryCard .big{font-size:20px}
  #summaryCard .metric>div:last-child{font-size:12px}
  .model-value{font-size:18px!important}
}
@media(max-width:380px){
  #summaryCard .big{font-size:18px}
  .model-value{font-size:16px!important}
  #summaryCard .metric{padding:9px;min-height:72px}
}
"""


OLD_OLLAMA_STATUS = """setPill('ollamaStatus',data.ollama?.online,data.ollama?.online?`Ollama online · ${data.ollama.model}`:`Ollama offline · ${data.ollama?.error||'unavailable'}`);"""

NEW_OLLAMA_STATUS = """const runtime=data.ollama||{};const inference=data.ollama_inference||{};let ollamaPillState=false;let ollamaPillText='Ollama offline · '+(runtime.error||'unavailable');if(runtime.online){if(runtime.model_loaded){ollamaPillState=true;ollamaPillText=`Ollama ready · ${runtime.model}`;}else if(runtime.model_present){ollamaPillState=null;ollamaPillText=`Ollama available · ${runtime.model} loads on first question`;}else{ollamaPillState=false;ollamaPillText=`Ollama model missing · ${runtime.model||'not configured'}`;}}setPill('ollamaStatus',ollamaPillState,ollamaPillText);"""


CLIENT_STATE_MARKER = """document.getElementById('readAnswers').checked=readAnswers;"""
CLIENT_STATE_REPLACEMENT = """document.getElementById('readAnswers').checked=readAnswers;input.value=localStorage.getItem('hmcp_last_query')||'';let activeController=null,activeRequestSerial=0,pendingUser=null;let clientId=localStorage.getItem('hmcp_client_id');if(!clientId){clientId=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():'hmcp-'+Date.now()+'-'+Math.random().toString(16).slice(2);localStorage.setItem('hmcp_client_id',clientId);}"""


OLD_SUBMIT_FUNCTION = """async function submit(query){query=(query||input.value).trim();if(!query)return;input.value='';const prior=history.slice(-10);history.push({role:'user',content:query});save();working.classList.add('show');ask.disabled=true;ask.textContent='Working…';clearOutput();output.appendChild(el('div','answer-text','Working on: '+query));try{const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,history:prior})});const answer=await response.json();showAnswer(answer);history.push({role:'assistant',content:answer.message||''});save()}catch(error){showAnswer({success:false,route:'error',message:'Request failed: '+error.message})}finally{working.classList.remove('show');ask.disabled=false;ask.textContent='Ask';status()}}"""

NEW_SUBMIT_FUNCTION = """async function submit(query){query=(query||input.value).trim();if(!query)return;input.value=query;localStorage.setItem('hmcp_last_query',query);if(activeController)activeController.abort();if(window.speechSynthesis)window.speechSynthesis.cancel();if(pendingUser&&history.length&&history[history.length-1]?.role==='user'&&history[history.length-1]?.content===pendingUser)history.pop();const prior=history.slice(-10);history.push({role:'user',content:query});pendingUser=query;save();const controller=new AbortController();activeController=controller;const serial=++activeRequestSerial;working.textContent='Working… submit another question to stop this request.';working.classList.add('show');ask.disabled=false;ask.classList.add('working-button');ask.textContent='Stop & ask';clearOutput();output.appendChild(el('div','answer-text','Working on: '+query));try{const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json','X-HMCP-Client':clientId},body:JSON.stringify({query,history:prior}),signal:controller.signal});if(serial!==activeRequestSerial)return;if(response.status===409)return;const answer=await response.json();showAnswer(answer);pendingUser=null;history.push({role:'assistant',content:answer.message||''});save()}catch(error){if(error.name==='AbortError')return;if(serial===activeRequestSerial)showAnswer({success:false,route:'error',message:'Request failed: '+error.message})}finally{if(serial===activeRequestSerial){activeController=null;working.classList.remove('show');ask.classList.remove('working-button');ask.textContent='Ask';status()}}}"""


def render_page(title: str, version: str) -> str:
    """Render the compact HomeBrain-style interface for Hubitat MCP AI."""
    page = render_homebrain_page(title, version)
    page = page.replace(
        '<div class="metric"><div class="big" id="mcpState">',
        '<div class="metric connection-tile"><div class="big" id="mcpState">',
    )
    page = page.replace(
        '<div class="metric"><div class="big" id="ollamaState">',
        '<div class="metric connection-tile"><div class="big" id="ollamaState">',
    )
    page = page.replace(
        'class="big" id="model"',
        'class="big model-value" id="model"',
    )
    page = page.replace(
        '<button class="secondary" id="refreshMcp">Refresh MCP tools</button>',
        '<button class="secondary" data-q="Ollama diagnostics">Ollama diagnostics</button>'
        '<button class="secondary" id="refreshMcp">Refresh MCP tools</button>',
    )
    page = page.replace(OLD_OLLAMA_STATUS, NEW_OLLAMA_STATUS)
    page = page.replace(CLIENT_STATE_MARKER, CLIENT_STATE_REPLACEMENT)
    page = page.replace(OLD_SUBMIT_FUNCTION, NEW_SUBMIT_FUNCTION)
    page = page.replace("setInterval(status,30000);", "setInterval(status,10000);")
    return page.replace("</style>", HOME_BRAIN_MOBILE_PATCH + "</style>", 1)
