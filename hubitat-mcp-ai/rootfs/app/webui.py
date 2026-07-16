from __future__ import annotations

from webui_homebrain import render_homebrain_page


HOME_BRAIN_MOBILE_PATCH = r"""
.connection-tile{display:none}
#summaryCard .big{font-size:24px;line-height:1.05}
#summaryCard .metric>div:last-child{font-size:13px;line-height:1.2}
.model-value{font-size:20px!important;overflow-wrap:normal;word-break:normal;letter-spacing:-.02em}
#summaryCard .metric{min-height:78px}
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

NEW_OLLAMA_STATUS = """const inference=data.ollama_inference||{};const inferenceState=inference.state||'unknown';let ollamaPillState=false;let ollamaPillText='Ollama offline · '+(data.ollama?.error||'unavailable');if(data.ollama?.online){if(inference.ready===true){ollamaPillState=true;ollamaPillText=`Ollama ready · ${data.ollama.model}`;}else if(inference.ready===false){ollamaPillState=null;ollamaPillText=`Ollama server online · inference ${inferenceState==='timeout'?'timed out':'failed'}`;}else if(inferenceState==='retry-due'){ollamaPillState=null;ollamaPillText=`Ollama server online · rechecking inference`;}else{ollamaPillState=null;ollamaPillText=`Ollama server online · inference not checked`;}}setPill('ollamaStatus',ollamaPillState,ollamaPillText);"""


OLD_SUBMIT_START = """query=(query||input.value).trim();if(!query)return;input.value='';"""
NEW_SUBMIT_START = """query=(query||input.value).trim();if(!query)return;input.value=query;localStorage.setItem('hmcp_last_query',query);"""


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
    page = page.replace(OLD_SUBMIT_START, NEW_SUBMIT_START)
    page = page.replace(
        "document.getElementById('readAnswers').checked=readAnswers;",
        "document.getElementById('readAnswers').checked=readAnswers;"
        "input.value=localStorage.getItem('hmcp_last_query')||'';",
    )
    page = page.replace("setInterval(status,30000);", "setInterval(status,10000);")
    return page.replace("</style>", HOME_BRAIN_MOBILE_PATCH + "</style>", 1)
