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
<p><small>HomeBrain automatically identifies the device from your question using
the live Hubitat inventory. A device ID is not required.</small></p>
<details id="targetOverride"><summary>Advanced: specify a device only if automatic matching fails</summary>
<label for="deviceName">Device name (optional)</label>
<input id="deviceName" placeholder="Livingroom Light 1">
<label for="ids">Device ID override (optional; maximum 4, separated by commas)</label>
<input id="ids" placeholder="e.g. 7805">
</details>
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
<h2>V2 investigation summary</h2>
<p id="resolvedDevices"></p>
<div><button type="button" id="copyAnswer">Copy answer</button> <button type="button" id="copyReport">Copy full report</button></div>
<pre id="answer"></pre>
<h2>Measured checks</h2><div class="metrics" id="metrics"></div>
<details id="technicalReport"><summary>Investigation details and full source-backed answer</summary><button type="button" id="copyDetails">Copy investigation details</button><pre id="details"></pre></details>
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
    if(response.status===422)problem='Could not verify a unique device from the live inventory. Check the question or use Advanced options.';
    else if(response.status===404)problem='V2 API endpoint unavailable. Confirm add-on version and reload the test page.';
    else if(response.status===403)problem='V2 test access rejected. Check the token matches the saved add-on setting.';
    else if(response.status===503)problem='V2 server or Hubitat read temporarily unavailable; check add-on logs.';
    else problem='Request failed or returned an unreadable response.';
  }
  return (status+': '+problem).slice(0,950);
}
// Show elapsed wall-clock time in familiar minutes and seconds, while
// preserving full millisecond precision from the API for debugging.
function readableDuration(ms){
  if(typeof ms!=='number'||!Number.isFinite(ms)||ms<0)return null;
  const wholeMinutes=Math.floor(ms/60000);
  const remainingMs=ms-wholeMinutes*60000;
  const seconds=(ms/1000).toFixed(3);
  const remainder=(remainingMs/1000).toFixed(3);
  return {
    primary:wholeMinutes+' min '+remainder+' sec',
    seconds:seconds+' seconds',
    milliseconds:ms
  };
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
    if(ids.length>4||ids.some(x=>!/^\d{1,20}$/.test(x)))
      throw new Error('The optional override accepts at most four numeric Hubitat device IDs.');
    const response=await fetch(new URL('api/v2/test',new URL('./',location.href)),{
      method:'POST',headers:{'Content-Type':'application/json','X-HomeBrain-V2-Test-Token':el('secret').value},
      body:JSON.stringify({
        explicit_opt_in:true,question,
        device_ids:ids,
        device_name:el('deviceName').value.trim()||null,
        existing_v1_answer:el('v1').value||null,
        reference_answer:el('reference').value||null
      })
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(formatTestError(response,data));
    if(!data||typeof data!=='object'||!data.answer)
      throw new Error('HTTP '+response.status+': V2 endpoint returned no investigation result.');
    el('answer').textContent=data.report?.text||data.answer?.text||'No answer returned';
    const targets=Array.isArray(data.resolved_devices)?data.resolved_devices:[];
    el('resolvedDevices').textContent=targets.length
      ? 'Verified Hubitat device'+(targets.length>1?'s':'')+': '+
        targets.map(t=>(t.label||'Device')+' (#'+t.id+')').join(', ')+
        ' · '+(data.resolution_method==='question'?'identified from question':
             data.resolution_method==='device_name'?'matched friendly name':'verified ID override')
      : '';
    const score=data.scorecard?.v2_measured||{};
    const duration=readableDuration(data.elapsed_ms);
    metric(duration?'Duration · '+duration.seconds:'Duration',
           duration?.primary??'Unavailable');
    metric('MCP reads',data.investigation?.executed_reads);
    metric('Commands retained (retrieved)',score.command_records?score.commands_retained+'/'+score.command_records:'No command evidence');
    metric('Invalid citations',score.invalid_citations);
    metric('Validation flags',score.validator_flags?.length??0);
    metric('Historical source complete',score.source_complete_proven===true?'Proven':'Not proven');
    const fm=data.forensic_metrics||{};
    metric('In-window observations',fm.incident_records);
    metric('Historical page reached start',fm.incident_start_reached_by_returned_page===true?'Yes':'Not verified');
    el('details').textContent=JSON.stringify({
      duration:duration?.primary??null,
      duration_seconds:duration?.seconds??null,
      duration_ms:duration?.milliseconds??null,
      resolved_devices:data.resolved_devices,
      resolution_method:data.resolution_method,
      forensic_metrics:data.forensic_metrics,
      stopped_because:data.investigation?.stopped_because,
      planning_rounds:data.investigation?.rounds,
      reads_executed:data.investigation?.executed_reads,
      read_rejection_reasons:data.investigation?.rejected_proposals,
      planning_diagnostics:data.investigation?.planning_diagnostics,
      history_comparison:data.investigation?.history_comparison,

      current_app_identities:data.investigation?.case?.app_identities,
      full_source_backed_answer:data.answer?.text,
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
    el('output').hidden=false;
    const stop=data.investigation?.stopped_because;
    el('status').textContent=(
      stop==='read_budget_reached'?' Test finished — MCP read budget reached; investigation incomplete.':
      stop==='planning_timeout'?' Test finished — AI planning timed out; investigation incomplete.':
      stop==='planning_unavailable'?' Test finished — AI planning unavailable; investigation incomplete.':
      stop==='no_approved_discriminating_reads'?' Test finished — no further approved read; investigate evidence gaps.':
      ' Test finished — review source coverage and uncertainties.'
    );
  }catch(error){el('status').textContent=' Test failed: '+String(error?.message||'Unknown error')}
  finally{button.disabled=false}
};
</script></body></html>'''
