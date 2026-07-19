from __future__ import annotations

from typing import Any

import webui


HEALTH_SUMMARY = """<div class="card grid dashboard-grid" id="summaryCard">
<button class="summary-tile" data-q="Which lights are on?"><div class="big" id="dashLights">—</div><div>Lights on</div><div class="mini">Tap for live details</div></button>
<button class="summary-tile" data-q="Which motion sensors are active?"><div class="big" id="dashMotion">—</div><div>Motion active</div><div class="mini">Live Hubitat states</div></button>
<button class="summary-tile" id="healthSummary" data-q="Are any devices offline or stale?"><div class="big" id="dashHealth">—</div><div>Offline / stale</div><div class="mini" id="dashHealthDetail">Live healthStatus</div></button>
<button class="summary-tile" id="batterySummary" data-q="Which batteries are low?"><div class="big" id="dashBatteries">—</div><div>Low batteries</div><div class="mini">At or below 20%</div></button>
<div class="summary-meta"><span>AI <strong id="model">—</strong></span><span>Last route <strong id="lastRoute">—</strong></span><span>Last response <strong id="lastTime">—</strong></span><span>Dashboard <strong id="dashAge">Loading…</strong></span><span>State cache <strong id="dashCache">—</strong></span></div>
</div>"""


HEALTH_STATUS_FUNCTION = """function setDash(id,value){const node=document.getElementById(id);if(node)node.textContent=value===null||value===undefined?'—':String(value)}async function status(){const results=await Promise.allSettled([fetch('/api/status'),fetch('/api/dashboard'),fetch('/api/mcp-cache')]);if(results[0].status==='fulfilled'){try{const data=await results[0].value.json();const runtime=data.ollama||{};setPill('mcpStatus',data.mcp?.online,data.mcp?.online?`Hubitat MCP · ${data.mcp.tools||0} tools`:`Hubitat MCP offline · ${data.mcp?.error||'unavailable'}`);let aiState=false,aiText='Ollama offline · '+(runtime.error||'unavailable');if(runtime.online){if(runtime.model_loaded){aiState=true;aiText=`AI ready · ${runtime.model}`;}else if(runtime.model_present){aiState=null;aiText=`AI available · ${runtime.model} loads on demand`;}else{aiText=`AI model missing · ${runtime.model||'not configured'}`;}}setPill('ollamaStatus',aiState,aiText);document.getElementById('model').textContent=runtime.routine_model||runtime.model||'—'}catch(error){setPill('mcpStatus',false,'Status error · '+error.message)}}else setPill('mcpStatus',false,'Status request failed');if(results[1].status==='fulfilled'){try{const dash=await results[1].value.json();setDash('dashLights',dash.lights_on);setDash('dashMotion',dash.motion_active);setDash('dashHealth',dash.health_issues);setDash('dashBatteries',dash.low_batteries);const health=document.getElementById('healthSummary');health?.classList.toggle('warning',Number(dash.health_issues)>0);const healthDetail=document.getElementById('dashHealthDetail');if(healthDetail){healthDetail.textContent=dash.health_success===false?'Health scan unavailable':`${dash.offline_devices||0} offline · ${dash.stale_telemetry||0} stale`;}const battery=document.getElementById('batterySummary');battery?.classList.toggle('warning',Number(dash.low_batteries)>0);const age=document.getElementById('dashAge');if(age)age.textContent=dash.success?'Live':'Unavailable'}catch(error){const age=document.getElementById('dashAge');if(age)age.textContent='Unavailable'}}if(results[2].status==='fulfilled'){try{const cache=(await results[2].value.json()).cache||{};const node=document.getElementById('dashCache');if(node)node.textContent=`${cache.entries||0} entries · ${cache.hits||0} hits`;}catch(error){const node=document.getElementById('dashCache');if(node)node.textContent='Unavailable'}}}"""


def install_dashboard_health_tile(module: Any = webui) -> None:
    """Replace the visible switch count with actionable device-health metrics."""

    module.NEW_SUMMARY = HEALTH_SUMMARY
    module.NEW_STATUS_FUNCTION = HEALTH_STATUS_FUNCTION


__all__ = [
    "HEALTH_STATUS_FUNCTION",
    "HEALTH_SUMMARY",
    "install_dashboard_health_tile",
]
