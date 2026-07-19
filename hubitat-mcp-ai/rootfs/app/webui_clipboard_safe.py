from __future__ import annotations

import re
from typing import Any


_COPY_HANDLER = (
    "const actions=el('div','answer-actions'),copy=el('button','small-button','Copy');"
    "copy.onclick=()=>navigator.clipboard?.writeText(answer.message||'');"
    "actions.appendChild(copy);"
)
_COPY_REPLACEMENT = (
    "const actions=el('div','answer-actions'),copy=el('button','small-button','Copy');"
    "copy.onclick=()=>homebrainCopyResult(answer,copy);"
    "actions.appendChild(copy);"
)

_COPY_CSS = r"""
.small-button.copy-success{background:#166534;box-shadow:inset 0 0 0 1px rgba(134,239,172,.45)}
.small-button.copy-error{background:#991b1b;box-shadow:inset 0 0 0 1px rgba(254,202,202,.35)}
"""

_COPY_HELPERS = r"""
function homebrainCopyPayload(answer){
  const parts=[];
  const title=String(answer?.display?.title||'').trim();
  const message=String(answer?.message||answer?.detail||'').trim();
  let technical='';
  if(answer?.technical!==undefined&&answer?.technical!==null){
    try{technical=typeof answer.technical==='string'?answer.technical:JSON.stringify(answer.technical,null,2)}catch(error){technical=String(answer.technical)}
    technical=String(technical||'').trim();
  }
  if(title)parts.push(title);
  if(message&&message!==title)parts.push(message);
  if(technical)parts.push('Technical details\n'+technical);
  return parts.join('\n\n')||'No response';
}
async function homebrainWriteClipboard(text){
  try{
    if(navigator.clipboard&&typeof navigator.clipboard.writeText==='function'){
      await navigator.clipboard.writeText(text);
      return true;
    }
  }catch(error){}
  const area=document.createElement('textarea');
  area.value=text;
  area.setAttribute('readonly','');
  area.setAttribute('aria-hidden','true');
  area.style.position='fixed';
  area.style.left='-9999px';
  area.style.top='0';
  area.style.opacity='0';
  area.style.pointerEvents='none';
  area.style.fontSize='16px';
  document.body.appendChild(area);
  area.focus();
  area.select();
  area.setSelectionRange(0,area.value.length);
  let copied=false;
  try{copied=Boolean(document.execCommand&&document.execCommand('copy'))}catch(error){copied=false}
  area.remove();
  return copied;
}
async function homebrainCopyResult(answer,button){
  const original=button.textContent||'Copy';
  button.disabled=true;
  const copied=await homebrainWriteClipboard(homebrainCopyPayload(answer));
  button.disabled=false;
  button.textContent=copied?'Copied':'Copy failed';
  button.classList.toggle('copy-success',copied);
  button.classList.toggle('copy-error',!copied);
  window.setTimeout(()=>{
    button.textContent=original;
    button.classList.remove('copy-success','copy-error');
  },1600);
}
"""


def patch_clipboard(page: str) -> str:
    """Make the result Copy button work inside HA ingress and mobile browsers."""

    if "homebrainCopyResult" in page:
        return page

    if _COPY_HANDLER in page:
        page = page.replace(_COPY_HANDLER, _COPY_REPLACEMENT, 1)
    else:
        page = re.sub(
            r"copy\.onclick=\(\)=>navigator\.clipboard\?\.writeText\(answer\.message\|\|''\);",
            "copy.onclick=()=>homebrainCopyResult(answer,copy);",
            page,
            count=1,
        )

    page = page.replace("</style>", _COPY_CSS + "</style>", 1)
    page = page.replace("</script>", _COPY_HELPERS + "</script>", 1)
    return page


def install_clipboard_safe_webui(webui_module: Any) -> None:
    """Wrap the final HomeBrain page patch exactly once."""

    if getattr(webui_module, "_homebrain_clipboard_safe", False):
        return
    original_patch = webui_module.patch_page

    def patched_page(page: str) -> str:
        return patch_clipboard(original_patch(page))

    webui_module.patch_page = patched_page
    webui_module._homebrain_clipboard_safe = True


__all__ = ["install_clipboard_safe_webui", "patch_clipboard"]
