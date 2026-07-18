from __future__ import annotations

from typing import Any

from fastapi.responses import HTMLResponse


DEVICE_HANDLER_MARKER = "document.getElementById('refreshMcp').onclick=async()=>{"
CLIENT_MARKER = "const input=document.getElementById('query'),ask=document.getElementById('ask'),output=document.getElementById('outputCard'),working=document.getElementById('working');"
CLIENT_REPLACEMENT = r"""let clientId=sessionStorage.getItem('hmcp_client_id');if(!clientId){clientId=(globalThis.crypto?.randomUUID?.()||('hmcp-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)));sessionStorage.setItem('hmcp_client_id',clientId)};const input=document.getElementById('query'),ask=document.getElementById('ask'),output=document.getElementById('outputCard'),working=document.getElementById('working');"""
ASK_PAYLOAD_MARKER = "headers:{'Content-Type':'application/json'},body:JSON.stringify({query,history:prior})"
ASK_PAYLOAD_REPLACEMENT = "headers:{'Content-Type':'application/json','X-HMCP-Client':clientId},body:JSON.stringify({query,history:prior,session_id:clientId})"

DEVICE_HANDLER = r"""document.getElementById('deviceCatalogue').onclick=async()=>{working.classList.add('show');try{const response=await fetch('/api/device-catalogue?force=true');const data=await response.json();const groups=Object.entries(data.groups||{}).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));const items=groups.map(([name,count])=>({icon:'📂',title:name.replaceAll('-',' '),value:String(count),subtitle:'Selected devices identified in this group'}));for(const name of (data.without_room||[]).slice(0,10))items.push({icon:'🏷️',title:name,value:'No room',subtitle:'Assign a Hubitat room for clearer natural answers',tone:'warning'});for(const [alias,names] of Object.entries(data.ambiguous_aliases||{}).slice(0,10))items.push({icon:'⚠️',title:alias,value:names.length+' matches',subtitle:names.join(', '),tone:'warning'});showAnswer({success:true,route:'system',message:`Indexed ${data.selected_count||0} selected Hubitat devices.`,display:{title:'Device intelligence catalogue',subtitle:`Refreshed ${Number(data.last_refresh_age_seconds||0).toFixed(1)}s ago · ${data.rooms?.length||0} rooms`,metrics:[{label:'Selected devices',value:data.selected_count||0,icon:'📱'},{label:'Device groups',value:groups.length,icon:'📂'},{label:'Without room',value:(data.without_room||[]).length,icon:'🏷️'},{label:'Ambiguous aliases',value:Object.keys(data.ambiguous_aliases||{}).length,icon:'⚠️'}],items,note:'The dashboard, device status and device-type questions now share this cached live-state index. A successful control command invalidates it before the next read.'},technical:JSON.stringify(data,null,2)});}catch(error){showAnswer({success:false,route:'error',message:'Could not load the device catalogue: '+error.message})}finally{working.classList.remove('show')}};document.getElementById('clearConversation').onclick=async()=>{working.classList.add('show');try{const response=await fetch('/api/conversation-context/clear',{method:'POST',headers:{'Content-Type':'application/json','X-HMCP-Client':clientId},body:JSON.stringify({session_id:clientId})});const data=await response.json();history=[];save();input.value='';window.speechSynthesis?.cancel();showAnswer({success:true,route:'system',message:'Conversation context cleared.',display:{title:'Conversation cleared',subtitle:'Follow-up references will start fresh',metrics:[{label:'Context',value:'Cleared',icon:'🧹'}],note:'Device states and the shared MCP cache were not cleared.'},technical:JSON.stringify(data,null,2)});}catch(error){showAnswer({success:false,route:'error',message:'Could not clear conversation context: '+error.message})}finally{working.classList.remove('show')}};document.getElementById('refreshMcp').onclick=async()=>{"""


def patch_page(page: str) -> str:
    page = page.replace(
        '<button class="secondary" id="mcpToolCatalogue">MCP tool catalogue</button>',
        '<button class="secondary" id="mcpToolCatalogue">MCP tool catalogue</button>'
        '<button class="secondary" id="deviceCatalogue">Device catalogue</button>'
        '<button class="secondary" id="clearConversation">Clear conversation</button>',
    )
    page = page.replace(CLIENT_MARKER, CLIENT_REPLACEMENT)
    page = page.replace(ASK_PAYLOAD_MARKER, ASK_PAYLOAD_REPLACEMENT)
    page = page.replace(DEVICE_HANDLER_MARKER, DEVICE_HANDLER)
    return page


def install_device_intelligence_webui(application: Any) -> None:
    api = application.app
    api.router.routes[:] = [
        route
        for route in api.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in (getattr(route, "methods", set()) or set())
        )
    ]

    @api.get("/", response_class=HTMLResponse)
    async def indexed_home() -> HTMLResponse:
        page = application.render_page(
            str(application.OPTIONS.get("web_title") or "Hubitat MCP AI"),
            application.VERSION,
        )
        return HTMLResponse(patch_page(page))


__all__ = ["install_device_intelligence_webui", "patch_page"]
