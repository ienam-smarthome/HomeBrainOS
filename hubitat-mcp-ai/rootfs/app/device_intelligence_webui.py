from __future__ import annotations

import json
import re
from typing import Any

from fastapi.responses import HTMLResponse, Response


PWA_RELEASE_VERSION = "0.10.55"
DEVICE_HANDLER_MARKER = "document.getElementById('refreshMcp').onclick=async()=>{"
ASK_PAYLOAD_MARKER = "JSON.stringify({query,history:prior})"
ASK_PAYLOAD_REPLACEMENT = "JSON.stringify({query,history:prior,session_id:clientId})"
SUMMARY_MARKER = "if(answer.display.subtitle)output.appendChild(el('div','result-subtitle',answer.display.subtitle));const metrics=metricGrid(answer.display.metrics);"
SUMMARY_REPLACEMENT = "if(answer.display.subtitle)output.appendChild(el('div','result-subtitle',answer.display.subtitle));if(answer.display.summary)output.appendChild(el('div','result-summary',answer.display.summary));const metrics=metricGrid(answer.display.metrics);"
ROUTE_BADGE_MARKER = "meta.appendChild(el('span','badge',answer.route||'unknown'));"
ROUTE_BADGE_REPLACEMENT = "meta.appendChild(el('span','badge',(typeof routeLabel==='function'?routeLabel(answer.route):String(answer.route||'unknown'))));if(answer.answered_by)meta.appendChild(el('span','badge','Answered by '+String(answer.answered_by)));if(answer.ai_provider)meta.appendChild(el('span','badge',String(answer.ai_provider)));if(answer.ai_attempted)meta.appendChild(el('span','badge',answer.ai_used?'AI used':'AI attempted → fallback'));"
SHOW_ANSWER_MARKER = "function showAnswer(answer){clearOutput();"
SHOW_ANSWER_REPLACEMENT = "function showAnswer(answer){clearOutput();const asked=localStorage.getItem('hmcp_last_query')||'';if(asked)output.appendChild(el('div','result-question','Asked: '+asked));"
WORKING_MARKER = "clearOutput();output.appendChild(el('div','answer-text','Working on: '+query));"
WORKING_REPLACEMENT = "clearOutput();output.appendChild(el('div','result-question','Asked: '+query));output.appendChild(el('div','answer-text','Contacting Hubitat…'));"

PWA_HEAD = r"""
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="pwa-icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="pwa-icon.svg">
<meta name="theme-color" content="#111111">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Hubitat MCP AI">
"""

PWA_SCRIPT = r"""
<script>
(() => {
  const standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  if (standalone) document.documentElement.classList.add('pwa-standalone');
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => navigator.serviceWorker.register('service-worker.js').catch(() => {}));
  }
})();
</script>
"""

PWA_MANIFEST = {
    "id": "./",
    "name": "Hubitat MCP AI",
    "short_name": "Hubitat AI",
    "description": "HomeBrain AI-first Hubitat assistant",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "display_override": ["standalone", "minimal-ui"],
    "orientation": "portrait-primary",
    "background_color": "#111111",
    "theme_color": "#111111",
    "categories": ["utilities", "productivity"],
    "icons": [
        {"src": "pwa-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}
    ],
}

PWA_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="104" fill="#111111"/>
<path d="M72 242 256 88l184 154v198a24 24 0 0 1-24 24H96a24 24 0 0 1-24-24Z" fill="#f2f2f2"/>
<path d="M49 244 256 69l207 175-31 37L256 133 80 281Z" fill="#ef4444"/>
<rect x="205" y="292" width="102" height="172" rx="10" fill="#9ca3af"/>
<rect x="111" y="278" width="66" height="66" rx="9" fill="#38bdf8"/>
<rect x="335" y="278" width="66" height="66" rx="9" fill="#38bdf8"/>
<circle cx="256" cy="226" r="50" fill="#16a34a"/>
<path d="M256 192v68M222 226h68" stroke="#fff" stroke-width="18" stroke-linecap="round"/>
</svg>"""

SERVICE_WORKER = r"""const CACHE='hubitat-mcp-ai-shell-v0.10.36';
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['./','manifest.webmanifest','pwa-icon.svg'])).catch(()=>{}));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))));self.clients.claim();});
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET')return;const url=new URL(request.url);if(url.origin!==self.location.origin||url.pathname.includes('/api/'))return;event.respondWith(fetch(request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));return response;}).catch(()=>caches.match(request).then(hit=>hit||caches.match('./'))));});
"""

OLD_VOICE_HANDLER = r"""function startVoice(){const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition){showAnswer({success:false,route:'browser',message:'Speech recognition is not supported by this browser.'});return}const recognition=new Recognition();recognition.lang='en-GB';recognition.interimResults=false;const fab=document.getElementById('micFab');fab.classList.add('listening');fab.textContent='■';recognition.onresult=event=>{const query=event.results[0][0].transcript;input.value=query;submit(query)};recognition.onerror=event=>showAnswer({success:false,route:'browser',message:'Speech recognition error: '+event.error});recognition.onend=()=>{fab.classList.remove('listening');fab.textContent='🎤'};recognition.start()}document.getElementById('speak').onclick=startVoice;document.getElementById('micFab').onclick=startVoice;"""

NEW_VOICE_HANDLER = r"""let activeRecognition=null,activeVoiceStop=null;function voiceUi(listening,label){const speak=document.getElementById('speak'),fab=document.getElementById('micFab');if(speak){speak.textContent=listening?(label||'Listening… Tap to stop'):'🎤 Speak';speak.classList.toggle('listening',listening)}if(fab){fab.classList.toggle('listening',listening);fab.textContent=listening?'■':'🎤';fab.setAttribute('aria-label',listening?'Stop listening':'Speak')}}function voiceErrorMessage(error,timedOut,stoppedByUser){if(timedOut)return 'Listening timed out. Tap Speak and try again.';if(stoppedByUser)return 'Listening stopped. No question was sent.';const messages={'not-allowed':'Microphone permission is blocked. Allow microphone access for Home Assistant or this site, then try again.','service-not-allowed':'The phone blocked its speech-recognition service. Check microphone and speech-service permissions.','audio-capture':'No working microphone was available to the browser.','network':'The phone speech-recognition service did not respond. Check its internet connection or try Chrome.','no-speech':'No speech was heard. Tap Speak and try again.','language-not-supported':'English (UK) speech recognition is not available on this phone.'};return messages[error]||('Speech recognition error: '+error)}function startVoice(){if(activeVoiceStop){activeVoiceStop();return}const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition){showAnswer({success:false,route:'browser',message:'Speech recognition is not supported by this browser. Use Chrome or Samsung Internet with microphone permission enabled.'});return}const recognition=new Recognition();let transcript='',failure='',finished=false,stoppedByUser=false,timedOut=false,hardTimer=null,silenceTimer=null;activeRecognition=recognition;recognition.lang='en-GB';recognition.continuous=false;recognition.interimResults=true;recognition.maxAlternatives=1;const clearTimers=()=>{if(hardTimer)clearTimeout(hardTimer);if(silenceTimer)clearTimeout(silenceTimer);hardTimer=null;silenceTimer=null};const finish=()=>{if(finished)return;finished=true;clearTimers();activeRecognition=null;activeVoiceStop=null;voiceUi(false);working.classList.remove('show');working.textContent='Contacting Hubitat…';const heard=transcript.trim();if(heard){input.value=heard;submit(heard);return}showAnswer({success:false,route:'browser',message:voiceErrorMessage(failure,timedOut,stoppedByUser)});};activeVoiceStop=()=>{if(finished)return;stoppedByUser=true;try{recognition.stop()}catch(error){finish()}};recognition.onstart=()=>{voiceUi(true,'Listening… Tap to stop');working.textContent='Listening… speak now. It will send after you pause.';working.classList.add('show');clearOutput();output.appendChild(el('div','answer-text','Listening… Speak now. Tap the red microphone or Speak button to stop.'))};recognition.onspeechstart=()=>voiceUi(true,'Listening…');recognition.onresult=event=>{const parts=[];let finalResult=false;for(let index=0;index<event.results.length;index++){const result=event.results[index];const text=result&&result[0]?String(result[0].transcript||'').trim():'';if(text)parts.push(text);if(result?.isFinal)finalResult=true}transcript=parts.join(' ').trim();if(transcript){input.value=transcript;localStorage.setItem('hmcp_last_query',transcript);clearOutput();output.appendChild(el('div','answer-text','Heard: '+transcript+(finalResult?'':' …')))}if(silenceTimer)clearTimeout(silenceTimer);silenceTimer=setTimeout(()=>{try{recognition.stop()}catch(error){finish()}},finalResult?120:1100)};recognition.onspeechend=()=>{if(silenceTimer)clearTimeout(silenceTimer);silenceTimer=setTimeout(()=>{try{recognition.stop()}catch(error){finish()}},180)};recognition.onnomatch=()=>{failure='no-speech'};recognition.onerror=event=>{failure=String(event.error||'unknown');if(failure==='aborted'&&stoppedByUser)failure=''};recognition.onend=finish;hardTimer=setTimeout(()=>{if(finished)return;timedOut=true;try{recognition.abort()}catch(error){}finish()},9000);try{recognition.start()}catch(error){failure=String(error?.message||error||'start-failed');finish()}}document.getElementById('speak').onclick=startVoice;document.getElementById('micFab').onclick=startVoice;"""

SNAPSHOT_CSS = r"""
.result-summary{font-size:14px;line-height:1.5;margin:8px 0 12px;padding:10px 12px;background:#111;border-left:3px solid rgba(34,197,94,.8);border-radius:7px;white-space:pre-wrap;overflow-wrap:anywhere}
.result-question{font-size:13px;line-height:1.4;margin:0 0 10px;padding:8px 10px;background:#111827;border:1px solid #263752;border-radius:8px;color:#dbeafe;white-space:pre-wrap;overflow-wrap:anywhere}
.result-section{grid-column:1/-1;color:#d7d7db;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;margin:7px 2px 0;padding-top:5px;border-top:1px solid #29292d}
.result-section:first-child{border-top:0;margin-top:0;padding-top:0}
#speak.listening{background:#b91c1c}
.pwa-standalone body{padding-top:max(8px,env(safe-area-inset-top));padding-bottom:max(8px,env(safe-area-inset-bottom))}
"""

ROUTE_LABEL_FUNCTION = r"""function routeLabel(route){const key=String(route||'unknown');const labels={'mcp-fast':'Hubitat live','ollama+mcp':'Ollama + Hubitat','ollama+snapshot':'Ollama insight','mcp-snapshot':'Hubitat snapshot','mcp-snapshot-ai-fallback':'Hubitat snapshot (AI fallback)','mcp-snapshot-state-unavailable':'Hubitat state unavailable','ollama+temperature-insight':'Ollama comparison','mcp-temperature-insight-ai-fallback':'Hubitat comparison (AI fallback)','mcp-temperature-insight':'Hubitat comparison','fallback-compact':'Hubitat fallback','fallback':'Hubitat fallback','mcp-confirmation':'Hubitat confirmation','system':'System','browser':'Browser','error':'Error'};return labels[key]||key.split('-').join(' ')}"""

GROUPED_ITEM_LIST = r"""function itemList(items){if(!Array.isArray(items)||!items.length)return null;const list=el('div','result-list');let lastGroup='';items.forEach(item=>{const group=String(item.group||'');if(group&&group!==lastGroup){list.appendChild(el('div','result-section',group));lastGroup=group}const row=el('div','result-item '+(item.tone||''));row.appendChild(el('div','',item.icon||'•'));const main=el('div','result-main');main.appendChild(el('div','result-name',item.title||''));if(item.subtitle)main.appendChild(el('div','result-sub',item.subtitle));row.appendChild(main);if(item.value!==undefined&&item.value!==null&&item.value!=='')row.appendChild(el('div','result-side',String(item.value)));list.appendChild(row)});return list}
function showAnswer(answer){"""

DEVICE_HANDLER = r"""document.getElementById('deviceCatalogue').onclick=async()=>{working.classList.add('show');try{const response=await fetch('/api/device-catalogue?force=true');const data=await response.json();const groups=Object.entries(data.groups||{}).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));const items=groups.map(([name,count])=>({icon:'📂',title:name.replaceAll('-',' '),value:String(count),subtitle:'Selected devices identified in this group'}));for(const name of (data.without_room||[]).slice(0,10))items.push({icon:'🏷️',title:name,value:'No room',subtitle:'Assign a Hubitat room for clearer natural answers',tone:'warning'});for(const [alias,names] of Object.entries(data.ambiguous_aliases||{}).slice(0,10))items.push({icon:'⚠️',title:alias,value:names.length+' matches',subtitle:names.join(', '),tone:'warning'});showAnswer({success:true,route:'system',message:`Indexed ${data.selected_count||0} selected Hubitat devices.`,display:{title:'Device intelligence catalogue',subtitle:`Refreshed ${Number(data.last_refresh_age_seconds||0).toFixed(1)}s ago · ${data.rooms?.length||0} rooms`,metrics:[{label:'Selected devices',value:data.selected_count||0,icon:'📱'},{label:'Device groups',value:groups.length,icon:'📂'},{label:'Without room',value:(data.without_room||[]).length,icon:'🏷️'},{label:'Ambiguous aliases',value:Object.keys(data.ambiguous_aliases||{}).length,icon:'⚠️'}],items,note:'The dashboard, device status and device-type questions now share this cached live-state index. A successful control command invalidates it before the next read.'},technical:JSON.stringify(data,null,2)});}catch(error){showAnswer({success:false,route:'error',message:'Could not load the device catalogue: '+error.message})}finally{working.classList.remove('show')}};document.getElementById('clearConversation').onclick=async()=>{working.classList.add('show');try{const response=await fetch('/api/conversation-context/clear',{method:'POST',headers:{'Content-Type':'application/json','X-HMCP-Client':clientId},body:JSON.stringify({session_id:clientId})});const data=await response.json();history=[];save();input.value='';localStorage.removeItem('hmcp_last_query');window.speechSynthesis?.cancel();showAnswer({success:true,route:'system',message:'Conversation context cleared.',display:{title:'Conversation cleared',subtitle:'Follow-up references will start fresh',metrics:[{label:'Context',value:'Cleared',icon:'🧹'}],note:'Device states and the shared MCP cache were not cleared.'},technical:JSON.stringify(data,null,2)});}catch(error){showAnswer({success:false,route:'error',message:'Could not clear conversation context: '+error.message})}finally{working.classList.remove('show')}};document.getElementById('refreshMcp').onclick=async()=>{"""


def patch_page(page: str) -> str:
    page = page.replace(
        '<button class="secondary" id="mcpToolCatalogue">MCP tool catalogue</button>',
        '<button class="secondary" id="mcpToolCatalogue">MCP tool catalogue</button>'
        '<button class="secondary" id="deviceCatalogue">Device catalogue</button>'
        '<button class="secondary" id="clearConversation">Clear conversation</button>',
    )
    page = page.replace(
        '<button class="secondary" data-q="What\'s happening at home?">🏠 What\'s happening?</button>',
        '<button class="secondary" data-q="What\'s happening at home?">🏠 What\'s happening?</button>'
        '<button class="secondary" data-q="What looks unusual at home right now?">✨ AI home insight</button>'
        '<button class="secondary" data-q="What can Ollama help with?">🤖 AI question guide</button>',
    )
    page = page.replace(
        'placeholder="Ask your Hubitat…"',
        'placeholder="Ask Hubitat, or start with Ask Ollama: …"',
    )
    page = page.replace("</head>", PWA_HEAD + "</head>", 1)
    page = page.replace("</body>", PWA_SCRIPT + "</body>", 1)
    page = page.replace(ASK_PAYLOAD_MARKER, ASK_PAYLOAD_REPLACEMENT)
    page = page.replace(DEVICE_HANDLER_MARKER, DEVICE_HANDLER)
    page = page.replace(OLD_VOICE_HANDLER, NEW_VOICE_HANDLER, 1)
    page = page.replace("</style>", SNAPSHOT_CSS + "</style>", 1)

    page = re.sub(
        r"function itemList\(items\)\{.*?\}\s*function showAnswer\(answer\)\{",
        GROUPED_ITEM_LIST,
        page,
        count=1,
        flags=re.S,
    )
    page = page.replace(
        "function showAnswer(answer){",
        ROUTE_LABEL_FUNCTION + "\nfunction showAnswer(answer){",
        1,
    )
    page = page.replace(SHOW_ANSWER_MARKER, SHOW_ANSWER_REPLACEMENT, 1)
    page = page.replace(WORKING_MARKER, WORKING_REPLACEMENT, 1)
    page = page.replace(SUMMARY_MARKER, SUMMARY_REPLACEMENT, 1)
    page = page.replace(ROUTE_BADGE_MARKER, ROUTE_BADGE_REPLACEMENT, 1)

    page = page.replace("fetch('/api/", "fetch('api/")
    page = page.replace('fetch("/api/', 'fetch("api/')
    return page


def install_device_intelligence_webui(application: Any) -> None:
    api = application.app
    # The entrypoint owns the authoritative release version. The Web UI
    # must display it, never replace it with a separately maintained value.
    release_version = str(getattr(application, 'VERSION', PWA_RELEASE_VERSION))
    api.version = release_version
    api.router.routes[:] = [
        route
        for route in api.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in (getattr(route, "methods", set()) or set())
        )
    ]

    @api.get("/manifest.webmanifest")
    async def pwa_manifest() -> Response:
        return Response(
            json.dumps(PWA_MANIFEST, separators=(",", ":")),
            media_type="application/manifest+json",
            headers={"Cache-Control": "no-cache"},
        )

    @api.get("/pwa-icon.svg")
    async def pwa_icon() -> Response:
        return Response(PWA_ICON, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    @api.get("/service-worker.js")
    async def pwa_service_worker() -> Response:
        return Response(
            SERVICE_WORKER,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "./"},
        )

    @api.get("/", response_class=HTMLResponse)
    async def indexed_home() -> HTMLResponse:
        page = application.render_page(
            str(application.OPTIONS.get("web_title") or "Hubitat MCP AI"),
            release_version,
        )
        return HTMLResponse(patch_page(page), headers={"Cache-Control": "no-cache"})


__all__ = ["install_device_intelligence_webui", "patch_page"]
