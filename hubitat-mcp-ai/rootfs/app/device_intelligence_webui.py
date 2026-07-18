from __future__ import annotations

import re
from typing import Any

from fastapi.responses import HTMLResponse


DEVICE_HANDLER_MARKER = "document.getElementById('refreshMcp').onclick=async()=>{"
ASK_PAYLOAD_MARKER = "JSON.stringify({query,history:prior})"
ASK_PAYLOAD_REPLACEMENT = "JSON.stringify({query,history:prior,session_id:clientId})"
SUMMARY_MARKER = "if(answer.display.subtitle)output.appendChild(el('div','result-subtitle',answer.display.subtitle));const metrics=metricGrid(answer.display.metrics);"
SUMMARY_REPLACEMENT = "if(answer.display.subtitle)output.appendChild(el('div','result-subtitle',answer.display.subtitle));if(answer.display.summary)output.appendChild(el('div','result-summary',answer.display.summary));const metrics=metricGrid(answer.display.metrics);"

SNAPSHOT_CSS = r"""
.result-summary{font-size:14px;line-height:1.5;margin:8px 0 12px;padding:10px 12px;background:#111;border-left:3px solid rgba(34,197,94,.8);border-radius:7px;white-space:pre-wrap;overflow-wrap:anywhere}
.result-section{grid-column:1/-1;color:#d7d7db;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;margin:7px 2px 0;padding-top:5px;border-top:1px solid #29292d}
.result-section:first-child{border-top:0;margin-top:0;padding-top:0}
"""

GROUPED_ITEM_LIST = r"""function itemList(items){if(!Array.isArray(items)||!items.length)return null;const list=el('div','result-list');let lastGroup='';items.forEach(item=>{const group=String(item.group||'');if(group&&group!==lastGroup){list.appendChild(el('div','result-section',group));lastGroup=group}const row=el('div','result-item '+(item.tone||''));row.appendChild(el('div','',item.icon||'•'));const main=el('div','result-main');main.appendChild(el('div','result-name',item.title||''));if(item.subtitle)main.appendChild(el('div','result-sub',item.subtitle));row.appendChild(main);if(item.value!==undefined&&item.value!==null&&item.value!=='')row.appendChild(el('div','result-side',String(item.value)));list.appendChild(row)});return list}function showAnswer(answer){"""

DEVICE_HANDLER = r"""document.getElementById('deviceCatalogue').onclick=async()=>{working.classList.add('show');try{const response=await fetch('/api/device-catalogue?force=true');const data=await response.json();const groups=Object.entries(data.groups||{}).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));const items=groups.map(([name,count])=>({icon:'📂',title:name.replaceAll('-',' '),value:String(count),subtitle:'Selected devices identified in this group'}));for(const name of (data.without_room||[]).slice(0,10))items.push({icon:'🏷️',title:name,value:'No room',subtitle:'Assign a Hubitat room for clearer natural answers',tone:'warning'});for(const [alias,names] of Object.entries(data.ambiguous_aliases||{}).slice(0,10))items.push({icon:'⚠️',title:alias,value:names.length+' matches',subtitle:names.join(', '),tone:'warning'});showAnswer({success:true,route:'system',message:`Indexed ${data.selected_count||0} selected Hubitat devices.`,display:{title:'Device intelligence catalogue',subtitle:`Refreshed ${Number(data.last_refresh_age_seconds||0).toFixed(1)}s ago · ${data.rooms?.length||0} rooms`,metrics:[{label:'Selected devices',value:data.selected_count||0,icon:'📱'},{label:'Device groups',value:groups.length,icon:'📂'},{label:'Without room',value:(data.without_room||[]).length,icon:'🏷️'},{label:'Ambiguous aliases',value:Object.keys(data.ambiguous_aliases||{}).length,icon:'⚠️'}],items,note:'The dashboard, device status and device-type questions now share this cached live-state index. A successful control command invalidates it before the next read.'},technical:JSON.stringify(data,null,2)});}catch(error){showAnswer({success:false,route:'error',message:'Could not load the device catalogue: '+error.message})}finally{working.classList.remove('show')}};document.getElementById('clearConversation').onclick=async()=>{working.classList.add('show');try{const response=await fetch('/api/conversation-context/clear',{method:'POST',headers:{'Content-Type':'application/json','X-HMCP-Client':clientId},body:JSON.stringify({session_id:clientId})});const data=await response.json();history=[];save();input.value='';localStorage.removeItem('hmcp_last_query');window.speechSynthesis?.cancel();showAnswer({success:true,route:'system',message:'Conversation context cleared.',display:{title:'Conversation cleared',subtitle:'Follow-up references will start fresh',metrics:[{label:'Context',value:'Cleared',icon:'🧹'}],note:'Device states and the shared MCP cache were not cleared.'},technical:JSON.stringify(data,null,2)});}catch(error){showAnswer({success:false,route:'error',message:'Could not clear conversation context: '+error.message})}finally{working.classList.remove('show')}};document.getElementById('refreshMcp').onclick=async()=>{"""


def patch_page(page: str) -> str:
    page = page.replace(
        '<button class="secondary" id="mcpToolCatalogue">MCP tool catalogue</button>',
        '<button class="secondary" id="mcpToolCatalogue">MCP tool catalogue</button>'
        '<button class="secondary" id="deviceCatalogue">Device catalogue</button>'
        '<button class="secondary" id="clearConversation">Clear conversation</button>',
    )
    # webui.py already creates a stable clientId and sends it in X-HMCP-Client.
    # Add the same ID to the validated JSON body without declaring it twice.
    page = page.replace(ASK_PAYLOAD_MARKER, ASK_PAYLOAD_REPLACEMENT)
    page = page.replace(DEVICE_HANDLER_MARKER, DEVICE_HANDLER)
    page = page.replace("</style>", SNAPSHOT_CSS + "</style>", 1)
    page = re.sub(
        r"function itemList\(items\)\{.*?\}function showAnswer\(answer\)\{",
        GROUPED_ITEM_LIST,
        page,
        count=1,
        flags=re.S,
    )
    page = page.replace(SUMMARY_MARKER, SUMMARY_REPLACEMENT, 1)
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
