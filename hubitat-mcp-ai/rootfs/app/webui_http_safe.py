from __future__ import annotations

from typing import Any


_OLD_RESPONSE = (
    "if(response.status===409)return;const answer=await response.json();"
    "showAnswer(answer);pendingUser=null;history.push({role:'assistant',content:answer.message||''});save()"
)
_NEW_RESPONSE = (
    "if(response.status===409)return;const raw=await response.text();let answer=null;"
    "try{answer=raw?JSON.parse(raw):null}catch(parseError){answer=null}"
    "if(!answer||typeof answer!=='object'){const preview=String(raw||'').trim();"
    "answer={success:false,route:'server-error',message:`HomeBrain returned HTTP ${response.status}${response.statusText?' '+response.statusText:''}. ${preview||'The response body was empty.'}`,technical:`HTTP ${response.status}${response.statusText?' '+response.statusText:''}\nContent-Type: ${response.headers.get('content-type')||'unknown'}\n\n${preview||'<empty response>'}`};}"
    "else if(!response.ok&&answer.success!==false){answer.success=false;answer.route=answer.route||'server-error';answer.message=answer.message||answer.detail||`HomeBrain returned HTTP ${response.status}.`;answer.technical=answer.technical||raw;}"
    "showAnswer(answer);pendingUser=null;history.push({role:'assistant',content:answer.message||''});save()"
)


def patch_http_errors(page: str) -> str:
    """Parse ask responses as text first so plain HTTP failures remain visible."""

    if "HomeBrain returned HTTP ${response.status}" in page:
        return page
    return page.replace(_OLD_RESPONSE, _NEW_RESPONSE, 1)


def install_http_safe_webui(webui_module: Any) -> None:
    if getattr(webui_module, "_homebrain_http_safe", False):
        return
    original_patch = webui_module.patch_page

    def patched_page(page: str) -> str:
        return patch_http_errors(original_patch(page))

    webui_module.patch_page = patched_page
    webui_module._homebrain_http_safe = True


__all__ = ["install_http_safe_webui", "patch_http_errors"]
