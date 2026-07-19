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
.copy-manual{margin-top:10px;padding:10px;border:1px solid #7c5c16;border-radius:10px;background:#221b0f;color:#fde68a}
.copy-manual-label{font-size:12px;line-height:1.4;margin-bottom:7px}
.copy-manual textarea{display:block;width:100%;min-height:180px;margin:0 0 8px;padding:9px;border:1px solid #6b7280;border-radius:8px;background:#fff;color:#111;font:12px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap}
.copy-manual .small-button{margin:0}
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
function homebrainLegacyCopy(text){
  const area=document.createElement('textarea');
  area.value=text;
  area.setAttribute('readonly','');
  area.setAttribute('aria-hidden','true');
  area.style.position='fixed';
  area.style.left='0';
  area.style.top='0';
  area.style.width='2px';
  area.style.height='2px';
  area.style.padding='0';
  area.style.border='0';
  area.style.opacity='0.01';
  area.style.pointerEvents='none';
  area.style.fontSize='16px';
  document.body.appendChild(area);
  area.focus({preventScroll:true});
  area.select();
  area.setSelectionRange(0,area.value.length);
  let copied=false;
  try{copied=Boolean(document.execCommand&&document.execCommand('copy'))}catch(error){copied=false}
  area.remove();
  return copied;
}
function homebrainCopyFeedback(button,copied,label){
  const original=button.dataset.copyLabel||button.textContent||'Copy';
  button.dataset.copyLabel=original;
  button.disabled=false;
  button.textContent=label||(copied?'Copied':'Select text');
  button.classList.toggle('copy-success',copied);
  button.classList.toggle('copy-error',!copied);
  window.setTimeout(()=>{
    button.textContent=button.dataset.copyLabel||'Copy';
    button.classList.remove('copy-success','copy-error');
  },1800);
}
function homebrainShowManualCopy(text,button){
  const host=button.closest('.answer-shell')||document.getElementById('outputCard')||document.body;
  host.querySelector('.copy-manual')?.remove();
  const panel=document.createElement('div');
  panel.className='copy-manual';
  const label=document.createElement('div');
  label.className='copy-manual-label';
  label.textContent='Automatic copy is blocked by this browser. The full result is selected below—use Copy from the browser menu.';
  const area=document.createElement('textarea');
  area.value=text;
  area.setAttribute('readonly','');
  const close=document.createElement('button');
  close.type='button';
  close.className='small-button';
  close.textContent='Close';
  close.onclick=()=>panel.remove();
  panel.append(label,area,close);
  host.appendChild(panel);
  area.focus({preventScroll:false});
  area.select();
  area.setSelectionRange(0,area.value.length);
  homebrainCopyFeedback(button,false,'Text selected');
}
function homebrainCopyResult(answer,button){
  const text=homebrainCopyPayload(answer);
  button.disabled=true;
  // Run the legacy path synchronously while the browser still considers this a
  // direct user tap. This is required on plain HTTP and some HA ingress clients.
  if(homebrainLegacyCopy(text)){
    homebrainCopyFeedback(button,true,'Copied');
    return;
  }
  if(window.isSecureContext&&navigator.clipboard&&typeof navigator.clipboard.writeText==='function'){
    navigator.clipboard.writeText(text).then(
      ()=>homebrainCopyFeedback(button,true,'Copied'),
      ()=>homebrainShowManualCopy(text,button)
    );
    return;
  }
  homebrainShowManualCopy(text,button);
}
"""


def patch_clipboard(page: str) -> str:
    """Make the result Copy button work in HA ingress and direct HTTP browsers."""

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
