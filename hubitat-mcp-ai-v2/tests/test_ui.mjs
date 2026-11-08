import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
const html=readFileSync(new URL('../rootfs/app/ui.html',import.meta.url),'utf8');
const script=html.split('<script>')[1].split('</script>')[0].replace(/loadStatus\(\);\s*$/, '');
const version=html.match(/const UI_VERSION="([^"]+)"/)[1];
function harness(){
 const elements=new Map(),timers=new Map();let clock=1000,seq=0,focused=false,fallback='',copied='',askCalls=0,clearCalls=0,askBodies=[];
 const element=(tag='div')=>({tagName:tag.toUpperCase(),children:[],_text:'',get textContent(){return this._text+this.children.map(c=>c.textContent).join('');},set textContent(v){this._text=String(v);this.children=[];},appendChild(c){this.children.push(c);return c;},append(...nodes){nodes.forEach(n=>this.appendChild(n));},replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);},setAttribute(k,v){this[k]=v;},getBoundingClientRect(){return {width:860,height:360,left:0};},value:'',disabled:false,hidden:false,style:{},classList:{remove(){},toggle(){},contains(){return false;}},addEventListener(){},focus(){focused=true;},click(){state.downloadName=this.download;}});
 const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 const state={status:{version,configured:true,model:'gemma4:31b-cloud'},result:{answer:'Original **answer**',elapsed_ms:2000,rounds:2,tool_calls:[{result:{source:'unchanged'}}]},httpError:null,copyWorks:true,askBodies};
 const document={getElementById:el,activeElement:element(),body:{appendChild(){}},createTextNode(text){const e=element('#text');e.textContent=text;return e;},createElementNS(_ns,tag){return element(tag);},createElement(tag){const e=element(tag);e.select=()=>{fallback=e.value;};e.setSelectionRange=()=>{};e.remove=()=>{};return e;},execCommand(){return state.copyWorks;}};
 const navigator={clipboard:{writeText:async text=>{copied=text;}}};
 const context=vm.createContext({document,navigator,window:{addEventListener(){}},crypto:webcrypto,Blob,URL:class extends URL{static createObjectURL(blob){state.downloadBlob=blob;return "blob:test";}static revokeObjectURL(){}},setTimeout:fn=>fn(),Date,console,performance:{now:()=>clock},setInterval(fn){timers.set(++seq,fn);return seq;},clearInterval(id){timers.delete(id);},fetch:async(url,init)=>{
 if(url==='api/status')return{ok:true,json:async()=>state.status};
 if(url==='api/conversation/clear'){clearCalls++;assert.equal(init.headers['X-Homebrain-Request'],'1');assert.equal(typeof JSON.parse(init.body).conversation_id,'string');return{ok:true,json:async()=>({cleared:true})};}
 assert.equal(url,'api/ask');askCalls++;askBodies.push(JSON.parse(init.body));assert.equal(init.headers['X-Homebrain-Request'],'1');
 assert.equal(el('copyAnswer').disabled,true);assert.equal(el('copyTechnical').disabled,true);
 for(const fn of [...timers.values()]){if(fn.toString().includes('Waiting:')){clock+=1250;fn();assert.match(el('responseTime').textContent,/Waiting: 1.3 s/);}}
 if(state.pending)await state.pending;
 clock+=1250;
 return{ok:!state.httpError,status:503,json:async()=>state.httpError?{detail:state.httpError}:state.result};
 }});
 vm.runInContext(script,context);
 return{state,el,timers,navigator,run:code=>vm.runInContext(code,context),get copied(){return copied;},get fallback(){return fallback;},get focused(){return focused;},get askCalls(){return askCalls;},get clearCalls(){return clearCalls;}};
}
const h=harness();h.el('question').value='Read only question';
await h.run('submitAsk()');
assert.equal(h.el('responseTime').textContent,'Response time: 2.5 s');
assert.equal(h.timers.size,0);assert.equal(h.el('send').disabled,false);
await h.run("copyResult('answer')");assert.equal(h.copied,h.state.result.answer);
await h.run("copyResult('technical')");
const detail=JSON.parse(h.copied);
assert.deepEqual(detail.response,h.state.result);assert.equal(detail.model,'gemma4:31b-cloud');
assert.equal(detail.question,'Read only question');assert.ok(detail.request_id);
assert.equal(detail.client_elapsed_ms,2500);assert.equal(detail.server_elapsed_ms,2000);assert.equal(detail.ui_version,version);
h.navigator.clipboard.writeText=async()=>{throw Error('insecure context');};
await h.run("copyResult('answer')");assert.equal(h.fallback,h.state.result.answer);assert.equal(h.focused,true);
h.navigator.clipboard=undefined;await h.run("copyResult('technical')");assert.deepEqual(JSON.parse(h.fallback).response,h.state.result);
h.state.copyWorks=false;await h.run("copyResult('answer')");assert.match(h.el('copyStatus').textContent,/Copy unavailable/);
h.state.result={answer:'Model failed',error:'model',elapsed_ms:20,tool_calls:[{result:'retained'}]};
await h.run('submitAsk()');assert.equal(h.run('technicalDetails.response.error'),'model');
h.state.httpError='Service unavailable';await h.run('submitAsk()');
assert.equal(h.el('answer').textContent,'Request failed: Service unavailable');
assert.equal(h.run('technicalDetails.error.type'),'transport');assert.equal(h.run('technicalDetails.response'),null);assert.equal(h.timers.size,0);
h.state.status.version='old';const count=h.askCalls;await h.run('submitAsk()');
assert.equal(h.askCalls,count);assert.equal(h.el('responseTime').textContent,'Response time: not sent');
assert.equal(h.run('technicalDetails.model'),null);assert.equal(h.run('technicalDetails.request_id'),null);
const d=harness();d.el('question').value='One request';let release;
d.state.pending=new Promise(resolve=>{release=resolve;});
const first=d.run('submitAsk()');await new Promise(resolve=>setImmediate(resolve));
await d.run('submitAsk()');assert.equal(d.askCalls,1);release();await first;
assert.equal(d.timers.size,0);
console.log('UI behavior checks passed: exact copies, receipt preservation, clipboard fallback, timing, failures, stale state and duplicate submission.');

const rich=harness();
const rendered=rich.run('renderAnswer("# Devices\\n\\n| Device | State |\\n| --- | --- |\\n| **Lamp** | \x60off\x60 |\\n\\n- Item\\n\\n<script>alert(1)</script>\\n\\n\x60\x60\x60\\n<img src=x onerror=alert(1)>\\n\x60\x60\x60")');
const all=node=>[node,...node.children.flatMap(all)];
assert(all(rendered).some(n=>n.tagName==='TABLE'));
assert(all(rendered).some(n=>n.tagName==='STRONG'&&n.textContent==='Lamp'));
assert(all(rendered).some(n=>n.tagName==='CODE'&&n.textContent==='off'));
assert(!all(rendered).some(n=>['SCRIPT','IMG'].includes(n.tagName)));
assert(rendered.textContent.includes('<script>alert(1)</script>'));
assert(rendered.textContent.includes('<img src=x onerror=alert(1)>'));
rich.el('question').value='First question';await rich.run('submitAsk()');
rich.el('question').value='Second question';await rich.run('submitAsk()');
assert.equal(rich.state.askBodies[0].conversation_id,rich.state.askBodies[1].conversation_id);
assert.equal(rich.el('conversationHistory').hidden,false);
assert(rich.el('turns').textContent.includes('First question'));
assert(!rich.el('turns').textContent.includes('Second question'));
assert.equal(rich.el('rawAnswer').textContent,rich.state.result.answer);
await rich.run('downloadTechnical()');
assert.equal(JSON.parse(await rich.state.downloadBlob.text()).question,'Second question');
assert(rich.state.downloadName.endsWith('.json'));
const previousId=rich.state.askBodies.at(-1).conversation_id;
rich.run('newConversation()');assert.equal(rich.clearCalls,1);
assert.equal(rich.run('messages.length'),0);
assert.equal(rich.run('turns.length'),0);
assert.equal(rich.el('copyAnswer').disabled,true);
assert.equal(rich.el('downloadTechnical').disabled,true);
assert.equal(rich.el('conversationHistory').hidden,true);
rich.el('question').value='After reset';await rich.run('submitAsk()');
assert.notEqual(rich.state.askBodies.at(-1).conversation_id,previousId);
assert.equal(rich.state.askBodies.at(-1).history.length,0);
rich.el('send').disabled=true;rich.el('question').value='Keep draft';rich.run('newConversation()');assert.equal(rich.el('question').value,'Keep draft');
rich.run("draw=()=>{}; fetch=async url=>({ok:true,json:async()=>url.includes('/status')?{status:'disabled',last:{}}:{range_start:'2026-11-07T00:00:00Z',range_end:'2026-11-08T00:00:00Z',metrics:{}}});");
rich.el('range').value='24';rich.el('metric').value='combined';await rich.run('refreshDiagnostics()');
assert.equal(rich.el('recorderNotice').hidden,false);assert.match(rich.el('recorderNotice').textContent,/External recorder is disabled/);
assert(html.includes('id="diagnosticsTab"'));
assert(html.includes('id="incidentTimeline"'));
assert(html.includes('id="timelineLayout"'));
assert(html.includes('id="plotExtent"'));
assert(html.includes('id="timelineSource"'));
assert(html.includes('id="timelineInspect"'));
assert(html.includes('id="timelineAsk"'));
assert(html.includes('id="detailReadout"'));
assert.match(rich.el('timelineMeta').textContent,/No.*observations|0 external OS-memory observations/);
const timeline=harness();
timeline.el('range').value='6';
timeline.el('plotExtent').value='fit';
timeline.el('timelineLayout').value='split';
const sourceFixture={
 range_start:'2026-11-08T06:00:00Z',range_end:'2026-11-08T12:40:00Z',
 metrics:{
  free_os_mb:{samples:[
   {recorded_at:'2026-11-08T12:00:00Z',reachable:1,free_os_mb:830,diag_segment:0},
   {recorded_at:'2026-11-08T12:00:30Z',reachable:1,free_os_mb:835,diag_segment:0}
  ],observed_metric_points:2},
  native_load_pct:{samples:[
   {recorded_at:'2026-11-08T12:00:00Z',reachable:1,native_load_pct:20,native_sample_label:'source-1',diag_segment:0},
   {recorded_at:'2026-11-08T12:05:00Z',reachable:1,native_load_pct:23,native_sample_label:'source-2',diag_segment:0}
  ],observed_metric_points:2}
 },reboots:[{occurred_at:'2026-11-08T12:10:00Z',firmware:'2.5.3.119'}],incidents:[]
};
timeline.run('timelineData='+JSON.stringify(sourceFixture));
timeline.run('drawIncidentTimeline()');
assert(timeline.el('incidentTimeline').children.some(n=>n.tagName==='PATH'));
assert(timeline.el('timelineMeta').textContent.includes('2 distinct native 5m CPU readings'));
assert(timeline.el('timelineMeta').textContent.includes('Time axis fitted'));
assert(timeline.el('timelineEvents').textContent.includes('Confirmed startup'));
assert.equal(timeline.el('timelineInspect').disabled,false);
timeline.run('inspectTimelineSelection()');
assert(timeline.el('timelineEvidence').textContent.includes('saved_external_recorder_only'));
timeline.run('prepareTimelineQuestion()');
assert(timeline.el('question').value.includes('do not change anything.'));
assert.equal(timeline.askCalls,0);
timeline.el('plotExtent').value='full';
timeline.run('redrawDiagnostics=()=>drawIncidentTimeline();redrawDiagnostics()');
assert(!timeline.el('timelineMeta').textContent.includes('Time axis fitted'));

console.log('Usability checks passed: safe Markdown/tables, original text, session reset/history, JSON download, diagnostics empty state and tab target.');

// UI math is display-only; raw answer and receipts remain byte-identical.
const mathSource="| Device | State | Setpoint | Note |\n| --- | --- | --- | --- |\n| **Bedroom 1 TRV** | Unknown | $21.0^\\circ\\text{C}$ | Command only |\n| **Bedroom 3 TRV** | **Heating** $\\rightarrow$ **Idle** | $22.0 \\rightarrow 21.0^\\circ\\text{C}$ | $\\sim$09:30:15 |\n\nText notation: \\(20.5^\\circ\\text{C}\\), $x^{2}$, $CO_{2}$, $\\geq 70\\%$, $\\approx 2$.\nUnknown: $\\frac{1}{2}$.\nLiteral code: `$21.0^\\circ\\text{C}$`.\nCurrency: $5 to $10 is not math.\nKeep raw markup literal: <svg onload=alert(1)>.";
const mathRendered=rich.run('renderAnswer('+JSON.stringify(mathSource)+')');
assert(all(mathRendered).some(n=>n.tagName==='TABLE'));
assert(mathRendered.textContent.includes("21.0°C"));
assert(mathRendered.textContent.includes("Heating → Idle"));
assert(mathRendered.textContent.includes("22.0 → 21.0°C"));
assert(mathRendered.textContent.includes("≈09:30:15"));
assert(mathRendered.textContent.includes("20.5°C"));
assert(mathRendered.textContent.includes("x²"));
assert(mathRendered.textContent.includes("CO₂"));
assert(mathRendered.textContent.includes("≥ 70%"));
assert(mathRendered.textContent.includes("≈ 2"));
assert(mathRendered.textContent.includes("<svg onload=alert(1)>"));
assert(mathRendered.textContent.includes("Currency: $5 to $10 is not math."));
assert(mathRendered.textContent.includes("$\\frac{1}{2}$"));
const mathCode=all(mathRendered).find(n=>n.tagName==='CODE'&&n.textContent.includes('21.0'));
assert.equal(mathCode.textContent,"$21.0^\\circ\\text{C}$");
assert(!all(mathRendered).some(n=>n.tagName==='SVG'));
const mathUi=harness();
mathUi.state.result={answer:mathSource,elapsed_ms:123,rounds:2,tool_calls:[]};
mathUi.el('question').value='Compare setpoints';
await mathUi.run('submitAsk()');
assert(mathUi.el('answer').textContent.includes('22.0 → 21.0°C'));
assert.equal(mathUi.el('rawAnswer').textContent,mathSource);
await mathUi.run("copyResult('answer')");
assert.equal(mathUi.copied,mathSource);
await mathUi.run("copyResult('technical')");
assert.equal(JSON.parse(mathUi.copied).response.answer,mathSource);
console.log('Inline math display tests passed: source fidelity, Unicode, code literals, unsupported TeX and text-only XSS.');
