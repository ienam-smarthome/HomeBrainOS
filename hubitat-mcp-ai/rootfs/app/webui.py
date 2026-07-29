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
:root{color-scheme:dark;--bg:#0b0b0c;--card:#1f1f21;--tile:#303033;--text:#fff;--muted:#b9b9bd;--blue:#2f7df6;--green:#166534;--red:#991b1b;--amber:#b45309}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Arial,sans-serif}.wrap{max-width:960px;margin:auto;padding:24px}h1{font-size:36px;margin:8px 0 20px}.card{background:var(--card);border-radius:18px;padding:16px;margin:12px 0}.row,.grid{display:flex;gap:10px;flex-wrap:wrap}.pill{padding:8px 12px;border-radius:999px;background:#3a3a3d;font-size:13px}.pill.ok{background:var(--green)}.pill.error{background:var(--red)}.pill strong{margin-left:4px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.tile{background:var(--tile);border-radius:14px;padding:14px;min-width:0}.big{font-size:22px;font-weight:700;overflow-wrap:anywhere;word-break:break-word}.muted{color:var(--muted);font-size:13px}input,button{width:100%;border:0;border-radius:12px;padding:14px;margin:7px 0;font:inherit}input{background:#fff;color:#111}button{background:var(--blue);color:#fff;cursor:pointer}.secondary{background:#333}.confirm{background:var(--green)}.answer{background:#000;border-radius:12px;padding:14px;min-height:52px;margin-top:8px;white-space:pre-wrap;overflow-wrap:anywhere}.answer-meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.badge{background:#243044;border-radius:999px;padding:4px 8px;font-size:12px}.answer-text{white-space:pre-wrap}.technical{margin-top:12px;color:var(--muted)}.technical summary{cursor:pointer}.technical pre{white-space:pre-wrap;overflow:auto;max-height:260px;background:#111;padding:10px;border-radius:8px}.busy{opacity:.65}
.answer-text p{margin:0 0 10px}.answer-text p:last-child{margin-bottom:0}.answer-text h2,.answer-text h3{margin:14px 0 6px;font-size:18px}.answer-text ul,.answer-text ol{margin:6px 0 10px;padding-left:24px}.answer-text li{margin:3px 0}.mic-fab{position:fixed;right:18px;bottom:18px;z-index:10;width:64px;height:64px;margin:0;border-radius:50%;font-size:27px;background:var(--green);box-shadow:0 10px 30px rgba(0,0,0,.5)}.mic-fab.listening{background:#dc2626}.copy-button{width:auto;display:block;margin:10px 0 0 auto;padding:7px 10px;font-size:12px}.technical-copy{margin-top:7px}.copy-ok{background:var(--green)}.copy-fail{background:var(--red)}
.section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}.section-head h2{font-size:19px;margin:0}.mini-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:8px}.mini-stat{background:var(--tile);border-radius:12px;padding:11px;min-width:0}.mini-value{font-size:17px;font-weight:700;overflow-wrap:anywhere}.room-chip.active{outline:2px solid var(--green)}.reason{color:#86efac}.update-available{color:#fbbf24}.empty{grid-column:1/-1;color:var(--muted)}
@media(max-width:520px){.wrap{padding:12px 12px 88px}h1{font-size:28px}.card{border-radius:12px;padding:11px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.mic-fab{right:14px;bottom:14px;width:68px;height:68px}}
</style>
</head>
<body><main class="wrap">
<h1>🏠 <span id="title"></span> <small id="version"></small></h1>
<section class="card row"><span class="pill" id="mcp">MCP unknown</span><span class="pill"><span class="muted">MCP tools</span><strong id="tools">—</strong></span><span class="pill" id="ollama">Ollama unknown</span><span class="pill"><span class="muted">Model</span><strong id="model">—</strong></span><span class="pill"><span class="muted">Last route</span><strong id="lastRoute">—</strong></span><span class="pill"><span class="muted">Response</span><strong id="lastTime">—</strong></span></section>
<section class="card grid">
<button class="tile secondary" data-q="Which lights are on?"><div class="big" id="dashLights">—</div><div>Lights on</div><div class="muted">Tap for live details</div></button>
<button class="tile secondary" data-q="Which motion sensors are active?"><div class="big" id="dashMotion">—</div><div>Motion active</div><div class="muted">Live Hubitat states</div></button>
<button class="tile secondary" data-q="Which switches are on?"><div class="big" id="dashSwitches">—</div><div>Switches on</div><div class="muted">Excludes lights</div></button>
<button class="tile secondary" data-q="Which batteries are low?"><div class="big" id="dashBatteries">—</div><div>Low batteries</div><div class="muted">At or below 20%</div></button>
</section>
<section class="card">
<div class="section-head"><div><h2>Active rooms</h2><span class="muted">Motion active or a light is on</span></div><strong id="activeRoomCount">—</strong></div>
<div class="mini-grid" id="activeRoomGrid"><span class="empty">Loading live room activity…</span></div>
</section>
<section class="card">
<div class="section-head"><div><h2>Rooms</h2><span class="muted" id="dashRoomDevices">Loading device counts…</span></div><strong id="dashRooms">—</strong></div>
<div class="mini-grid" id="roomGrid"><span class="empty">Loading rooms…</span></div>
</section>
<section class="card">
<div class="section-head"><div><h2>Hub information</h2><span class="muted">Live from the Hub Info device</span></div><strong id="dashHubName">—</strong></div>
<div class="mini-grid" id="hubInfoGrid"><span class="empty">Loading Hub Info…</span></div>
</section>
<section class="card">
<input id="query" placeholder="Ask your Hubitat…" autocomplete="off">
<button id="ask">Ask</button><button class="secondary" id="speak">🎤 Speak</button>
<label class="muted"><input id="readAnswers" type="checkbox" style="width:auto"> Read answers aloud</label>
<div class="answer" id="answer">Ready</div>
</section>
<section class="card grid" id="shortcuts">
<button class="secondary" data-q="What's happening at home?">🏠 What's happening?</button>
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
<button id="micFab" class="mic-fab" aria-label="Speak">🎤</button>
<script>
const TITLE=__TITLE__,VERSION=__VERSION__;
const newSessionId=()=>globalThis.crypto?.randomUUID?.()||`hmcp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
const sessionId=sessionStorage.getItem('hmcp_session_id')||newSessionId();
sessionStorage.setItem('hmcp_session_id',sessionId);
document.getElementById('title').textContent=TITLE;document.getElementById('version').textContent='v'+VERSION;
const query=document.getElementById('query'),ask=document.getElementById('ask'),answer=document.getElementById('answer');
query.value=localStorage.getItem('hmcp_last_query')||'';
const apiPath=path=>`${location.pathname.replace(/\/?$/,'/')}${path}`;
function pill(id,ok,text){const node=document.getElementById(id);node.textContent=text;node.className='pill '+(ok?'ok':'error')}
async function jsonResponse(response){const raw=await response.text();try{return JSON.parse(raw)}catch(error){throw new Error(`HTTP ${response.status}: ${raw||'empty response'}`)}}
let activeSpeech=null;function stopAudio(){if('speechSynthesis'in globalThis)speechSynthesis.cancel();activeSpeech=null;document.querySelectorAll('.audio-button').forEach(button=>button.textContent='🔊 Read answer')}
function speakAnswer(value,button=null){const spoken=speechText(value);if(!spoken||!('speechSynthesis'in globalThis))return;stopAudio();const utterance=new SpeechSynthesisUtterance(spoken);utterance.lang='en-GB';utterance.rate=.95;utterance.pitch=1;const voices=speechSynthesis.getVoices();utterance.voice=voices.find(voice=>voice.lang?.toLowerCase().startsWith('en-gb')&&voice.localService)||voices.find(voice=>voice.lang?.toLowerCase().startsWith('en'))||null;activeSpeech=utterance;if(button)button.textContent='■ Stop audio';utterance.onend=utterance.onerror=()=>{if(activeSpeech===utterance){activeSpeech=null;if(button)button.textContent='🔊 Read answer'}};speechSynthesis.speak(utterance)}
let readAnswers=localStorage.getItem('hmcp_read_answers')==='true';document.getElementById('readAnswers').checked=readAnswers;document.getElementById('readAnswers').onchange=event=>{readAnswers=event.target.checked;localStorage.setItem('hmcp_read_answers',String(readAnswers));if(!readAnswers)stopAudio()};
function legacyCopy(value){const area=document.createElement('textarea');area.value=value;area.setAttribute('readonly','');area.style.position='fixed';area.style.opacity='0';document.body.appendChild(area);area.focus();area.select();area.setSelectionRange(0,area.value.length);let ok=false;try{ok=Boolean(document.execCommand&&document.execCommand('copy'))}catch(error){ok=false}area.remove();return ok}
async function copyText(value,button,label){let ok=legacyCopy(value);if(!ok&&globalThis.isSecureContext&&navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(value);ok=true}catch(error){ok=false}}button.textContent=ok?'Copied':'Copy blocked — select text';button.className=`copy-button ${ok?'copy-ok':'copy-fail'}`;setTimeout(()=>{button.textContent=label;button.className='secondary copy-button'+(label==='Copy technical'?' technical-copy':'')},1800)}
function appendInline(parent,value){String(value).split(/(\*\*[^*]+\*\*)/g).filter(Boolean).forEach(part=>{if(part.startsWith('**')&&part.endsWith('**')){const strong=document.createElement('strong');strong.textContent=part.slice(2,-2);parent.appendChild(strong)}else parent.appendChild(document.createTextNode(part.replace(/`([^`]+)`/g,'$1')))})}
function renderMessage(value){const root=document.createElement('div');root.className='answer-text';let list=null;String(value).replace(/\r/g,'').split('\n').forEach(raw=>{const line=raw.trim();if(!line){list=null;return}const bullet=line.match(/^[-*]\s+(.+)$/);if(bullet){if(!list){list=document.createElement('ul');root.appendChild(list)}const item=document.createElement('li');appendInline(item,bullet[1]);list.appendChild(item);return}list=null;const heading=line.match(/^#{1,3}\s+(.+)$/);const node=document.createElement(heading?'h3':'p');appendInline(node,heading?heading[1]:line);root.appendChild(node)});return root}
function speechText(value){return String(value).replace(/```[\s\S]*?```/g,' ').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/\s*\((?:IDs?|device IDs?)\s*:\s*[^)]+\)/gi,'').replace(/\b(?:IDs?|device IDs?)\s*[:#]\s*[\d,\s]+/gi,'').replace(/([a-z])([A-Z])/g,'$1 $2').replace(/\bRTT\b/gi,'response time').replace(/\bCPU\b/g,'C P U').replace(/&/g,' and ').replace(/\s+\/\s+/g,' or ').replace(/:\s*\n/g,'.\n').replace(/^\s*#{1,6}\s*/gm,'').replace(/^\s*[-*+]\s+/gm,'').replace(/>/g,' over ').replace(/=/g,' ').replace(/(\d+(?:\.\d+)?)h\b/gi,'$1 hours').replace(/[*_`]/g,'').replace(/\n+/g,'. ').replace(/\s+/g,' ').replace(/\s+\./g,'.').replace(/\.{2,}/g,'.').trim()}
function showAnswer(data){answer.replaceChildren();const meta=document.createElement('div');meta.className='answer-meta';[data.route,data.model,data.elapsed_ms===undefined?null:`${(data.elapsed_ms/1000).toFixed(1)}s`].filter(Boolean).forEach(value=>{const badge=document.createElement('span');badge.className='badge';badge.textContent=value;meta.appendChild(badge)});if(meta.children.length)answer.appendChild(meta);const rawMessage=data.message||data.detail||'No response';const text=renderMessage(rawMessage);answer.appendChild(text);if(/please confirm/i.test(rawMessage)){const confirm=document.createElement('button');confirm.className='confirm';confirm.textContent='Confirm action';confirm.onclick=()=>submit('confirm');answer.appendChild(confirm)}const audioButton=document.createElement('button');audioButton.className='secondary copy-button audio-button';audioButton.textContent='🔊 Read answer';audioButton.onclick=()=>{if(activeSpeech)stopAudio();else speakAnswer(rawMessage,audioButton)};answer.appendChild(audioButton);const copy=document.createElement('button');copy.className='secondary copy-button';copy.textContent='Copy answer';copy.onclick=()=>copyText(rawMessage,copy,'Copy answer');answer.appendChild(copy);const details=document.createElement('details');details.className='technical';const summary=document.createElement('summary');summary.textContent='Technical details';const technical=JSON.stringify(data,null,2);const technicalCopy=document.createElement('button');technicalCopy.className='secondary copy-button technical-copy';technicalCopy.textContent='Copy technical';technicalCopy.onclick=event=>{event.preventDefault();copyText(technical,technicalCopy,'Copy technical')};const pre=document.createElement('pre');pre.textContent=technical;details.append(summary,technicalCopy,pre);answer.appendChild(details);document.getElementById('lastRoute').textContent=data.route||'—';document.getElementById('lastTime').textContent=data.elapsed_ms===undefined?'—':`${(data.elapsed_ms/1000).toFixed(1)}s`;if(readAnswers&&speechText(rawMessage).length<1500)speakAnswer(rawMessage,audioButton)}
function miniStat(label,value,className=''){const node=document.createElement('div');node.className='mini-stat '+className;const main=document.createElement('div');main.className='mini-value';main.textContent=value??'—';const caption=document.createElement('div');caption.className='muted';caption.textContent=label;node.append(main,caption);return node}
function renderRooms(dash){const rooms=dash.room_counts||[],active=new Map((dash.active_rooms||[]).map(room=>[room.name,room.reasons||[]]));document.getElementById('dashRooms').textContent=`${dash.rooms??rooms.length} rooms`;document.getElementById('dashRoomDevices').textContent=dash.assigned_devices===undefined?'Device count unavailable':`${dash.assigned_devices} assigned devices · ${dash.unassigned_devices??0} unassigned`;const grid=document.getElementById('roomGrid');grid.replaceChildren();rooms.forEach(room=>{const reasons=active.get(room.name);const node=miniStat(room.name,`${room.devices} device${room.devices===1?'':'s'}`,'room-chip'+(reasons?' active':''));if(reasons){const why=document.createElement('div');why.className='muted reason';why.textContent=reasons.join(' · ');node.appendChild(why)}grid.appendChild(node)});if(!rooms.length){const empty=document.createElement('span');empty.className='empty';empty.textContent='No assigned rooms were returned.';grid.appendChild(empty)}const activeGrid=document.getElementById('activeRoomGrid');activeGrid.replaceChildren();const activeRooms=dash.active_rooms||[];document.getElementById('activeRoomCount').textContent=`${activeRooms.length} active`;activeRooms.forEach(room=>activeGrid.appendChild(miniStat((room.reasons||[]).join(' · '),room.name,'room-chip active')));if(!activeRooms.length){const empty=document.createElement('span');empty.className='empty';empty.textContent='No rooms currently have motion active or a light on.';activeGrid.appendChild(empty)}}
function renderHubInfo(hub){const grid=document.getElementById('hubInfoGrid');grid.replaceChildren();document.getElementById('dashHubName').textContent=hub.name||hub.model||'—';if(!hub.name&&!hub.model){const empty=document.createElement('span');empty.className='empty';empty.textContent='Hub Info device unavailable.';grid.appendChild(empty);return}const updateAvailable=/available/i.test(String(hub.update_status||''));const firmware=hub.firmware_version||'—';const update=hub.update_version&&hub.update_version!==hub.firmware_version?`${hub.update_status||'Update available'} · ${hub.update_version}`:(hub.update_status||'No update reported');[['Installed firmware',firmware,''],['Firmware update',update,updateAvailable?'update-available':''],['CPU load',hub.cpu_percent!==undefined&&hub.cpu_percent!==null?`${hub.cpu_load??'—'} · ${hub.cpu_percent}%`:hub.cpu_load,''],['Free memory',hub.free_memory===undefined||hub.free_memory===null?'—':`${hub.free_memory} MB`,''],['Temperature',hub.temperature===undefined||hub.temperature===null?'—':`${hub.temperature} °C`,''],['Uptime',hub.uptime,''],['Database size',hub.database_size===undefined||hub.database_size===null?'—':`${hub.database_size} MB`,''],['IP address',hub.ip_address,''],['Matter',hub.matter_status,'']].forEach(([label,value,className])=>grid.appendChild(miniStat(label,value,className)))}
async function status(){try{const data=await jsonResponse(await fetch(apiPath('api/status')));pill('mcp',data.mcp?.online,data.mcp?.online?'MCP online':`MCP offline · ${data.mcp?.error||'unavailable'}`);pill('ollama',data.ollama?.configured,data.ollama?.configured?'Ollama ready':'Ollama API key required');document.getElementById('tools').textContent=data.mcp?.tools??'—';document.getElementById('model').textContent=data.ollama?.model||'—'}catch(error){pill('mcp',false,'Status error · '+error.message)}try{const dash=await jsonResponse(await fetch(apiPath('api/dashboard')));document.getElementById('dashLights').textContent=dash.lights_on??'—';document.getElementById('dashMotion').textContent=dash.motion_active??'—';document.getElementById('dashSwitches').textContent=dash.switches_on??'—';document.getElementById('dashBatteries').textContent=dash.low_batteries??'—';renderRooms(dash);renderHubInfo(dash.hub_info||{})}catch(error){console.warn('Dashboard unavailable',error)}}
let activeRequest=null,requestSequence=0;
async function submit(text){text=(text||query.value).trim();if(!text)return;stopAudio();query.value=text;localStorage.setItem('hmcp_last_query',text);if(activeRequest)activeRequest.abort();const controller=new AbortController();activeRequest=controller;const sequence=++requestSequence;answer.classList.add('busy');answer.textContent='Working… Ask another question to replace this request.';try{const data=await jsonResponse(await fetch(apiPath('api/ask'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:text,session_id:sessionId}),signal:controller.signal}));if(sequence===requestSequence)showAnswer(data)}catch(error){if(error.name!=='AbortError'&&sequence===requestSequence)showAnswer({success:false,route:'error',message:'Request failed: '+error.message})}finally{if(sequence===requestSequence){activeRequest=null;answer.classList.remove('busy');status()}}}
ask.onclick=()=>submit();query.onkeydown=event=>{if(event.key==='Enter')submit()};document.querySelectorAll('[data-q]').forEach(button=>button.onclick=()=>submit(button.dataset.q));
document.getElementById('refresh').onclick=async()=>{try{const data=await jsonResponse(await fetch(apiPath('api/refresh'),{method:'POST'}));answer.textContent=`MCP tools refreshed: ${data.tools}.`;status()}catch(error){answer.textContent='Refresh failed: '+error.message}};
let activeRecognition=null;function startVoice(){stopAudio();if(activeRecognition){activeRecognition.stop();return}const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition){answer.textContent='Speech recognition is unavailable in this browser.';return}const recognition=new Recognition();activeRecognition=recognition;recognition.lang='en-GB';const fab=document.getElementById('micFab');fab.classList.add('listening');fab.textContent='■';recognition.onresult=event=>submit(event.results[0][0].transcript);recognition.onerror=event=>{answer.textContent='Speech recognition error: '+event.error};recognition.onend=()=>{activeRecognition=null;fab.classList.remove('listening');fab.textContent='🎤'};recognition.start()}
document.getElementById('speak').onclick=startVoice;document.getElementById('micFab').onclick=startVoice;
status();setInterval(status,30000);
</script></body></html>"""
        .replace("__SAFE_TITLE__", safe_title)
        .replace("__TITLE__", title_json)
        .replace("__VERSION__", version_json)
    )


__all__ = ["render_page"]
