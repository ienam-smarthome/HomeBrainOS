"""Standalone opt-in V2 test panel. No token is embedded or persisted."""
from __future__ import annotations


def render_v2_test_page() -> str:
    return r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeBrain Investigation V2 Test</title>
<style>
:root{color-scheme:dark}body{font:15px system-ui,Arial;background:#101013;color:#f2f2f5;margin:0}
main{max-width:860px;margin:24px auto;padding:0 14px}
section{background:#202024;padding:18px;border-radius:12px;margin-bottom:14px}
label{display:block;margin:12px 0 5px;font-weight:600}
textarea,input{width:100%;box-sizing:border-box;background:#111115;color:#fff;border:1px solid #555;border-radius:7px;padding:10px;font:inherit}
textarea{min-height:76px}button{padding:12px 17px;border:0;border-radius:8px;background:#4f83ea;color:#fff;font-weight:700;cursor:pointer}
button:disabled{opacity:.6}small,p{color:#c5c5d0;line-height:1.5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#111115;padding:14px;border-radius:8px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px}.metric{background:#121217;padding:12px;border-radius:8px}
.metric strong{display:block;font-size:21px;margin-bottom:4px}a{color:#a9c5ff}
</style></head><body><main>
<h1>Investigation V2 · Test</h1>
<p><a href="./">HomeBrain dashboard</a> · Manual read-only experiment. Normal Ask continues using V1.
No device control, rule edits or automatic background comparison.</p>
<section>
<label for="secret">V2 test access token (set in add-on configuration)</label>
<input id="secret" type="password" autocomplete="off" placeholder="Operator test token">
<label for="question">Investigation question</label>
<textarea id="question" placeholder="Why did Livingroom Light 1 stay on overnight?"></textarea>
<label for="ids">Verified Hubitat device ID(s), separated by commas (maximum 4)</label>
<input id="ids" placeholder="7805">
<label for="v1">Existing V1 answer (optional, paste with Ctrl+V)</label>
<textarea id="v1" placeholder="V1 answer for timestamp-presence comparison"></textarea>
<label for="reference">Claude/reference answer (optional, paste with Ctrl+V)</label>
<textarea id="reference" placeholder="External answer for timestamp-presence comparison"></textarea>
<p><small>Free/default configured provider will be used, but model access can incur provider costs.
Exact timestamp scores do not measure reasoning correctness. Source coverage can remain incomplete.</small></p>
<button id="run">Run V2 read-only test</button>
<span id="status" role="status" aria-live="polite"></span>
</section>
<section id="output" hidden>
<h2>V2 answer</h2>
<div><button type="button" id="copyAnswer">Copy answer</button> <button type="button" id="copyReport">Copy full report</button></div>
<pre id="answer"></pre>
<h2>Measured checks</h2><div class="metrics" id="metrics"></div>
<h2>Investigation details</h2><button type="button" id="copyDetails">Copy investigation details</button><pre id="details"></pre>
</section>
</main><script>
const el=id=>document.getElementById(id);
// HTTP ingress uses a non-secure local origin: clipboard.writeText may be
// unavailable. Fall back to an ephemeral selected textarea; never persist
// report contents or the operator's test token.
async function copyTestText(value){
  if(!value)throw new Error('Nothing available to copy. Run V2 first.');
  if(navigator.clipboard?.writeText){
    try{await navigator.clipboard.writeText(value);return true}catch(error){}
  }
  const tmp=document.createElement('textarea');tmp.value=value;
  tmp.setAttribute('readonly','');tmp.style.position='fixed';tmp.style.left='-9999px';
  document.body.append(tmp);tmp.focus();tmp.select();
  let copied=false;
  try{copied=document.execCommand('copy')}finally{tmp.remove()}
  if(!copied)throw new Error('Clipboard blocked. Select the text and press Ctrl+C.');
  return true;
}
async function copyFrom(testId,label){
  try{await copyTestText(el(testId).textContent);el('status').textContent=' Copied '+label+'.'}
  catch(error){el('status').textContent=' '+error.message}
}

// Render FastAPI validation arrays and HA ingress error objects as readable
// text. Never echo request bodies, headers, tokens or arbitrary server HTML.
function formatTestError(response,data){
  const status='HTTP '+response.status;
  const detail=data&&typeof data==='object'
    ?(data.detail??data.message??data.error??null):null;
  const itemText=item=>{
    if(typeof item==='string')return item.slice(0,360);
    if(!item||typeof item!=='object')return '';
    const location=Array.isArray(item.loc)
      ?item.loc.filter(x=>typeof x==='string'||typeof x==='number')
         .map(x=>String(x).slice(0,40)).slice(0,6).join('.'):'';
    const msg=typeof item.msg==='string'?item.msg:
      typeof item.message==='string'?item.message:
      typeof item.error==='string'?item.error:
      typeof item.type==='string'?item.type:'Invalid request';
    return ((location?location+': ':'')+msg).slice(0,360);
  };
  let problem='';
  if(Array.isArray(detail))problem=detail.slice(0,4).map(itemText).filter(Boolean).join('; ');
  else if(typeof detail==='string')problem=detail.slice(0,720);
  else if(detail&&typeof detail==='object')
    problem=itemText(detail);
  if(!problem){
    if(response.status===422)problem='Invalid test request. Check the question and device IDs.';
    else if(response.status===404)problem='V2 API endpoint unavailable. Confirm add-on version and reload the test page.';
    else if(response.status===403)problem='V2 test access rejected. Check the token matches the saved add-on setting.';
    else if(response.status===503)problem='V2 server or Hubitat read temporarily unavailable; check add-on logs.';
    else problem='Request failed or returned an unreadable response.';
  }
  return (status+': '+problem).slice(0,950);
}
function metric(label,value){
  const outer=document.createElement('div'),number=document.createElement('strong'),caption=document.createElement('small');
  outer.className='metric';number.textContent=value===null||value===undefined?'—':String(value);
  caption.textContent=label;outer.append(number,caption);el('metrics').append(outer);
}
el('copyAnswer').onclick=()=>copyFrom('answer','V2 answer');
el('copyDetails').onclick=()=>copyFrom('details','investigation details');
el('copyReport').onclick=async()=>{
  const full='Investigation V2 test\n\n'+el('answer').textContent+
    '\n\nInvestigation details\n'+el('details').textContent;
  try{await copyTestText(full);el('status').textContent=' Copied full report.'}
  catch(error){el('status').textContent=' '+error.message}
};
el('run').onclick=async()=>{
  const button=el('run');button.disabled=true;el('status').textContent=' Running bounded read-only investigation…';
  el('output').hidden=true;el('metrics').replaceChildren();
  try{
    const question=el('question').value.trim();
    const ids=el('ids').value.split(',').map(x=>x.trim()).filter(Boolean);
    if(el('secret').value.length<16)
      throw new Error('Enter the V2 test token from the add-on configuration (at least 16 characters).');
    if(question.length<5)
      throw new Error('Enter an investigation question (at least five characters).');
    if(ids.length<1||ids.length>4||ids.some(x=>!/^\d{1,20}$/.test(x)))
      throw new Error('Enter one to four numeric Hubitat device IDs, separated by commas.');
    const response=await fetch(new URL('api/v2/test',new URL('./',location.href)),{
      method:'POST',headers:{'Content-Type':'application/json','X-HomeBrain-V2-Test-Token':el('secret').value},
      body:JSON.stringify({
        explicit_opt_in:true,question,
        device_ids:ids,
        existing_v1_answer:el('v1').value||null,
        reference_answer:el('reference').value||null
      })
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(formatTestError(response,data));
    if(!data||typeof data!=='object'||!data.answer)
      throw new Error('HTTP '+response.status+': V2 endpoint returned no investigation result.');
    el('answer').textContent=data.answer?.text||'No answer returned';
    const score=data.scorecard?.v2_measured||{};
    metric('Duration',data.elapsed_ms+' ms');metric('MCP reads',data.investigation?.executed_reads);
    metric('Command retention',score.command_records?score.commands_retained+'/'+score.command_records:'No command evidence');
    metric('Invalid citations',score.invalid_citations);
    metric('Validation flags',score.validator_flags?.length??0);
    metric('Historical source complete',score.source_complete_proven===true?'Proven':'Not proven');
    el('details').textContent=JSON.stringify({
      stopped_because:data.investigation?.stopped_because,
      requested_incident_window:data.investigation?.requested_incident_window,
      hypotheses:data.investigation?.hypotheses,
      coverage:data.investigation?.case?.coverage,
      validation_issues:data.answer?.validation_issues,
      atomic_claim_review:data.atomic_claim_review,
      narrative_audit:data.narrative_audit,
      v1_timestamp_check:data.scorecard?.v1_external,
      reference_timestamp_check:data.scorecard?.reference_external,
      causal_accuracy_comparison_completed:false
    },null,2);
    el('output').hidden=false;el('status').textContent=' Test complete — review source coverage and uncertainties.';
  }catch(error){el('status').textContent=' Test failed: '+String(error?.message||'Unknown error')}
  finally{button.disabled=false}
};
</script></body></html>'''
