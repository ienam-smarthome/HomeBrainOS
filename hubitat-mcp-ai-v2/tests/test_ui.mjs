import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
const html=readFileSync(new URL('../rootfs/app/ui.html',import.meta.url),'utf8');
const script=html.split('<script>')[1].split('</script>')[0].replace(/loadStatus\(\);\s*$/, '');
const version=html.match(/const UI_VERSION="([^"]+)"/)[1];
function harness(){
 const elements=new Map(),timers=new Map(),timeouts=new Map();let clock=1000,seq=0,focused=false,fallback='',copied='',askCalls=0,clearCalls=0,askBodies=[];
 const element=(tag='div')=>({tagName:tag.toUpperCase(),children:[],_text:'',get textContent(){return this._text+this.children.map(c=>c.textContent).join('');},set textContent(v){this._text=String(v);this.children=[];},appendChild(c){this.children.push(c);return c;},append(...nodes){nodes.forEach(n=>this.appendChild(n));},replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);},setAttribute(k,v){this[k]=v;},getBoundingClientRect(){return {width:860,height:360,left:0};},value:'',disabled:false,hidden:false,style:{},classList:(()=>{const classes=new Set();return{add(...names){names.forEach(n=>classes.add(n));},remove(...names){names.forEach(n=>classes.delete(n));},toggle(name,on){if(on===undefined? !classes.has(name):on){classes.add(name);return true;}classes.delete(name);return false;},contains(name){return classes.has(name);}}})(),addEventListener(){},focus(){focused=true;},click(){state.downloadName=this.download;}});
 const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 const state={status:{version,configured:true,model:'gemma4:31b-cloud'},result:{answer:'Original **answer**',elapsed_ms:2000,rounds:2,tool_calls:[{result:{source:'unchanged'}}]},httpError:null,copyWorks:true,askBodies};
 const document={getElementById:el,activeElement:element(),body:{appendChild(){}},createTextNode(text){const e=element('#text');e.textContent=text;return e;},createElementNS(_ns,tag){return element(tag);},createElement(tag){const e=element(tag);e.select=()=>{fallback=e.value;};e.setSelectionRange=()=>{};e.remove=()=>{};return e;},execCommand(){return state.copyWorks;}};
 const navigator={clipboard:{writeText:async text=>{copied=text;}}};
 const context=vm.createContext({document,navigator,window:{addEventListener(){}},crypto:webcrypto,Blob,URL:class extends URL{static createObjectURL(blob){state.downloadBlob=blob;return "blob:test";}static revokeObjectURL(){}},setTimeout(fn){const id=++seq;timeouts.set(id,fn);return id;},clearTimeout(id){timeouts.delete(id);},Date,console,performance:{now:()=>clock},setInterval(fn){timers.set(++seq,fn);return seq;},clearInterval(id){timers.delete(id);},fetch:async(url,init)=>{
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
 return{state,el,timers,timeouts,navigator,run:code=>vm.runInContext(code,context),flushTimeouts(){const scheduled=[...timeouts.values()];timeouts.clear();for(const fn of scheduled)fn();},get copied(){return copied;},get fallback(){return fallback;},get focused(){return focused;},get askCalls(){return askCalls;},get clearCalls(){return clearCalls;}};
}
const h=harness();h.el('question').value='Read only question';
await h.run('submitAsk()');
assert.equal(h.el('responseTime').textContent,'Response time: 2.5 s');
assert.equal(h.timers.size,0);assert.equal(h.el('send').disabled,false);
assert.match(html,/id="copyStatus"[^>]*role="status"[^>]*aria-live="polite"/);
await h.run("copyResult('answer')");assert.equal(h.copied,h.state.result.answer);
assert.equal(h.el('copyAnswer').textContent,'✓ Copied!');
assert.equal(h.el('copyAnswer').classList.contains('copy-feedback-ok'),true);
assert.match(h.el('copyStatus').textContent,/Answer copied to clipboard/);
assert.equal(h.timeouts.size,1);
h.flushTimeouts();
assert.equal(h.el('copyAnswer').textContent,'Copy answer');
assert.equal(h.el('copyAnswer').classList.contains('copy-feedback-ok'),false);
assert.equal(h.el('copyStatus').textContent,'');
await h.run("copyResult('technical')");
assert.equal(h.el('copyTechnical').textContent,'✓ Copied!');
assert.equal(h.el('copyTechnical').classList.contains('copy-feedback-ok'),true);
h.flushTimeouts();
assert.equal(h.el('copyTechnical').textContent,'Copy technical details');
const detail=JSON.parse(h.copied);
assert.deepEqual(detail.response,h.state.result);assert.equal(detail.model,'gemma4:31b-cloud');
assert.equal(detail.question,'Read only question');assert.ok(detail.request_id);
assert.equal(detail.client_elapsed_ms,2500);assert.equal(detail.server_elapsed_ms,2000);assert.equal(detail.ui_version,version);
h.navigator.clipboard.writeText=async()=>{throw Error('insecure context');};
await h.run("copyResult('answer')");assert.equal(h.fallback,h.state.result.answer);assert.equal(h.focused,true);
h.navigator.clipboard=undefined;await h.run("copyResult('technical')");assert.deepEqual(JSON.parse(h.fallback).response,h.state.result);
h.state.copyWorks=false;await h.run("copyResult('answer')");
assert.equal(h.el('copyAnswer').textContent,'Copy failed');
assert.equal(h.el('copyAnswer').classList.contains('copy-feedback-fail'),true);
assert.equal(h.el('copyStatus').classList.contains('copy-status-error'),true);
assert.match(h.el('copyStatus').textContent,/Copy unavailable/);
h.flushTimeouts();assert.equal(h.el('copyAnswer').textContent,'Copy answer');
h.state.result={answer:'Model failed',error:'model',elapsed_ms:20,tool_calls:[{result:'retained'}]};
await h.run('submitAsk()');assert.equal(h.run('technicalDetails.response.error'),'model');
assert.equal(h.el('copyStatus').textContent,'');
assert.equal(h.el('copyAnswer').textContent,'Copy answer');
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
// An old asynchronous clipboard completion cannot override newer request UI.
const race=harness();race.el('question').value='Private input';await race.run('submitAsk()');
let clipboardComplete;
race.navigator.clipboard.writeText=()=>new Promise(resolve=>{clipboardComplete=resolve;});
const oldCopy=race.run("copyResult('answer')");
assert.equal(race.el('copyAnswer').textContent,'Copy answer');
race.run('clearResult()');
clipboardComplete();await oldCopy;
assert.equal(race.el('copyAnswer').textContent,'Copy answer');
assert.equal(race.el('copyStatus').textContent,'');
assert.equal(race.timeouts.size,0);
console.log('UI behavior checks passed: visible clipboard confirmation, expiry, failed-copy feedback, stale-copy safety, exact copies, receipt preservation, clipboard fallback, timing, failures, stale state and duplicate submission.');

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
assert(html.includes('id="benchmarkTab"'));
assert(html.includes('id="autonomousTab"'));
assert(html.includes('id="reasoningTab"'));
assert(html.includes('id="reasoningSelect"'));
assert(html.includes('id="reasoningModelConsent"'));
assert(html.includes('id="reasoningCloudConsent"'));
assert(html.includes('id="reasoningRun"'));
assert(html.includes('id="reasoningAnswerA"'));
assert(html.includes('id="reasoningAnswerB"'));
assert(html.includes('id="reasoningScoresA"'));
assert(html.includes('id="reasoningScoresB"'));
assert(html.includes('id="reasoningReportPreview"'));
assert.match(html,/api\/reasoning-ab\//);
assert.match(html,/condition.mapping.remains.hidden|assignments.remain.hidden/);

assert(html.includes('id="autolabSelect"'));
assert(html.includes('id="autolabRun"'));
assert(html.includes('id="autolabModelConsent"'));
assert(html.includes('id="autolabCloudConsent"'));
assert(html.includes('id="autolabCoverage"'));
assert(html.includes('id="autolabScores"'));
assert(html.includes('id="autolabReportPreview"'));
assert.match(html,/api\/autonomous\//);
assert.match(html,/synthetic test only/i);

assert(html.includes('id="benchZip"'));
assert(html.includes('id="benchPrivateConsent"'));
assert(html.includes('id="benchCloudConsent"'));
assert(html.includes('id="benchPilot1"'));
assert(html.includes('id="benchPilot2"'));
assert(html.includes('id="benchSource"'));
assert(html.includes('id="benchScoresA"'));
assert(html.includes('id="benchScoresB"'));
assert(html.includes('id="benchDelete"'));
assert.match(html,/score both versions|Score A and B/i);
assert.match(html,/api\/benchmark\//);
assert.match(html,/X-Homebrain-Request/);

assert(html.includes('id="incidentTimeline"'));
assert(html.includes('id="timelineLayout"'));
assert(html.includes('id="timelinePair"'));
assert(html.includes('2 aligned panels · taller'));
assert(html.includes('External memory + CPU'));
assert(html.includes('Native memory + CPU'));
assert(html.includes('External + native memory'));
assert(html.includes('id="timelineCoverage"'));
assert(html.includes('Separate · 3 aligned panels'));
assert(html.includes('Memory overlaid · CPU separate'));
assert(html.includes('Overlay all · dual axes'));

assert(html.includes('id="plotExtent"'));
assert(html.includes('id="timelineSource"'));
assert(html.includes('id="timelinePopout"'));
assert(html.includes('id="detailPopout"'));
assert(html.includes('id="timelineReturn"'));
assert(html.includes('id="detailReturn"'));
assert.match(html,/graph-popout-timeline/);
assert.match(html,/graph-popout-detail/);
assert(html.includes('id="timelineInspect"'));
assert(html.includes('id="timelineAsk"'));
assert(html.includes('id="detailReadout"'));
assert(html.includes('id="resetTimelineZoom"'));
assert(html.includes('id="resetDetailZoom"'));
assert(html.includes('id="timelineZoomInfo"'));
assert(html.includes('id="detailZoomInfo"'));
assert(html.includes('<option value="native_load_pct">Native 5m load equivalent (%)</option>'));
assert(html.includes('<option value="native_load5">Native 5m load (raw, unscaled)</option>'));
assert.equal(rich.run("diagValue(15, 'native_load_pct')"),"15%");
assert.equal(rich.run("diagValue(0.6, 'native_load5')"),"0.6 load");
assert.equal(rich.run("diagValue(125.5, 'native_load_pct')"),"125.5%");
assert(html.includes('id="detailPrimaryLegend"'));
assert(html.includes('id="detailCpuLegend"'));
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
  native_free_os_mb:{samples:[
   {recorded_at:'2026-11-08T12:03:00Z',collected_at:'2026-11-08T12:06:00Z',
    reachable:1,native_free_os_mb:1272.8,native_sample_label:'11-08 12:03:00',
    timestamp_basis:'native_label_hub_timezone',diag_segment:0}
  ],observed_metric_points:1,timestamp_basis:'native_label_hub_timezone'},
  native_load_pct:{samples:[
   {recorded_at:'2026-11-08T12:00:00Z',reachable:1,native_load_pct:20,native_sample_label:'source-1',diag_segment:0},
   {recorded_at:'2026-11-08T12:05:00Z',reachable:1,native_load_pct:23,native_sample_label:'source-2',diag_segment:0}
  ],observed_metric_points:2}
 },reboots:[{occurred_at:'2026-11-08T12:10:00Z',firmware:'2.5.3.119'}],incidents:[]
};
timeline.run('timelineData='+JSON.stringify(sourceFixture));
timeline.run('drawIncidentTimeline()');
assert(timeline.el('incidentTimeline').children.some(n=>n.tagName==='PATH'));
assert(timeline.el('timelineCoverage').textContent.includes('Native OS memory'));
assert(timeline.el('timelineCoverage').textContent.includes('Native CPU load'));
assert(timeline.el('timelineCoverage').textContent.includes('unknown, not 0%'));
const yFrom=(kind,value)=>timeline.run('timelineShown.yFor('+JSON.stringify(kind)+','+value+')');
assert(yFrom('memory',830)<yFrom('nativeMemory',1272.8));
assert(yFrom('nativeMemory',1272.8)<yFrom('cpu',20));
const unsolicitedDots=timeline.el('incidentTimeline').children.filter(n=>
 n.tagName==='CIRCLE'&&!n.id&&n['data-role']!=='isolated-source-sample');
assert.equal(unsolicitedDots.length,0,
 'No permanent circles at all extrema or every native reading');
assert.equal(timeline.el('incidentTimeline').children.filter(n=>
 n['data-role']==='isolated-source-sample').length,1,
 'A genuine single native memory reading remains visibly marked');

assert(timeline.el('timelineMeta').textContent.includes('2 distinct native 5m CPU readings'));
assert(timeline.el('timelineMeta').textContent.includes('1 native 5m memory readings'));
assert(timeline.el('timelineEvents').textContent.includes('Highest native 5m OS memory'));
timeline.run("selectTimelineTime(Date.parse('2026-11-08T12:03:00Z'))");
assert(timeline.el('timelineReadout').textContent.includes('Native 5m OS memory'));
assert(timeline.el('timelineReadout').textContent.includes('1,272.8 MB'));
assert(timeline.el('timelineReadout').textContent.includes('native_label_hub_timezone'));

timeline.run('inspectTimelineSelection()');
assert(timeline.el('timelineEvidence').textContent.includes('native_memory_reading'));
assert(timeline.el('timelineEvidence').textContent.includes('11-08 12:03:00'));
timeline.run("selectTimelineTime(Date.parse('2026-11-08T12:35:00Z'))");
assert(timeline.el('timelineReadout').textContent.includes('no reading within 3 minutes'));


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
timeline.el('timelineLayout').value='combined';
timeline.run('drawIncidentTimeline()');
assert(timeline.el('incidentTimeline').textContent.includes('shared scale'));
assert(timeline.el('incidentTimeline').textContent.includes('not utilisation'));
timeline.el('timelineLayout').value='overlay';
timeline.run('drawIncidentTimeline()');
assert(timeline.el('incidentTimeline').textContent.includes('CPU load equivalent · % (right)'));
timeline.el('timelineLayout').value='split';
timeline.run('drawIncidentTimeline()');
// Two tall aligned graphs show only the selected pair, not overlaid traces.
// The height and panel bands are larger than the default 3-panel layout.
const chartPaths=()=>timeline.el('incidentTimeline').children
 .filter(node=>node.tagName==='PATH').map(node=>node.stroke);
const chartHeight=()=>Number(timeline.el('incidentTimeline').viewBox.split(' ').at(-1));
const panelHeight=kind=>timeline.run('timelineShown.panels['+
 JSON.stringify(kind)+'].bottom - timelineShown.panels['+JSON.stringify(kind)+'].top');
const threePanelHeight=panelHeight('memory');
assert.equal(timeline.el('timelinePairRow').hidden,true);
timeline.el('timelineLayout').value='tall';
timeline.el('timelinePair').value='external-cpu';
timeline.run('drawIncidentTimeline()');
assert.equal(timeline.el('timelinePairRow').hidden,false);
assert(chartHeight()>=720);
assert(panelHeight('memory')>threePanelHeight*2);
assert(panelHeight('cpu')>threePanelHeight*2);
assert(timeline.run('timelineShown.panels.memory.bottom')<
       timeline.run('timelineShown.panels.cpu.top'));
assert(chartPaths().includes('#70b9ff')&&chartPaths().includes('#6ee7b7'));
assert(!chartPaths().includes('#c4a1ff'));
timeline.el('timelinePair').value='native-cpu';
timeline.run('drawIncidentTimeline()');
assert(chartPaths().includes('#c4a1ff')&&chartPaths().includes('#6ee7b7'));
assert(!chartPaths().includes('#70b9ff'));
timeline.run("selectTimelineTime(Date.parse('2026-11-08T12:00:00Z'))");
assert.equal(timeline.el('timelineDotmemory').visibility,'hidden');
assert.equal(timeline.el('timelineDotcpu').visibility,'visible');
timeline.el('timelinePair').value='external-native';
timeline.run('drawIncidentTimeline()');
assert(chartPaths().includes('#70b9ff')&&chartPaths().includes('#c4a1ff'));
assert(!chartPaths().includes('#6ee7b7'));
assert(timeline.run('timelineShown.panels.memory.bottom')<
       timeline.run('timelineShown.panels.nativeMemory.top'));
assert.equal(timeline.el('timelineDotcpu').visibility,'hidden');
timeline.run("window.location={origin:'http://127.0.0.1:8789',pathname:'/ingress/homebrain',search:''}");
let tallUrl=timeline.run("graphPageUrl('timeline').href");
assert(tallUrl.includes('layout=tall'));
assert(tallUrl.includes('pair=external-native'));
timeline.el('timelineLayout').value='split';
timeline.run('drawIncidentTimeline()');
assert.equal(timeline.el('timelinePairRow').hidden,true);
// Overnight date+time labels must have enough actual logical SVG space,
// rather than being counted from CSS pixels and placed into an 860-unit plot.
timeline.run("timelineData.range_start='2026-11-07T06:00:00Z'; drawIncidentTimeline()");
const axisLabels=timeline.el('incidentTimeline').children.filter(
  n=>n.tagName==='TEXT'&&n['data-axis']==='time');
assert(axisLabels.length>=3&&axisLabels.length<=6);
assert(axisLabels.some(n=>n.textContent.includes('Nov')));
const xValues=axisLabels.map(n=>Number(n.x));
assert(xValues.every((x,i)=>i===0||x-xValues[i-1]>=145));
timeline.run("window.location={origin:'http://127.0.0.1:8789',pathname:'/ingress/homebrain',search:''}");
timeline.el('range').value='6';timeline.el('timelineLayout').value='split';
timeline.el('metric').value='native_load_pct';
const popoutURL=timeline.run("graphPageUrl('timeline').href");
assert(popoutURL.includes('/ingress/homebrain?graph_view=timeline'));
assert(popoutURL.includes('range=6'));
assert(popoutURL.includes('layout=split'));
assert(popoutURL.includes('metric=native_load_pct'));
assert(!popoutURL.includes('source-1'));
assert(!popoutURL.includes('PRIVATE'));
// Source-isolated selection. A substantial drag creates a bounded time window,
// not a fresh tool request or a modification to the original source rows.
const fullSpan=timeline.run('timelineWindow(timelineData).end - timelineWindow(timelineData).start');
const startDrag=timeline.run("startChartBrush('timeline',{clientX:200,pointerId:7,button:0})");
assert.equal(startDrag,true);
timeline.run("moveChartBrush('timeline',{clientX:500,pointerId:7})");
assert(Math.abs(timeline.run('zoomBrush.to')-500)<.001);
assert.equal(timeline.run("endChartBrush('timeline',{clientX:500,pointerId:7})"),true);
assert.equal(timeline.run('diagnosticZoom!==null'),true);
assert(timeline.run('diagnosticZoom.end-diagnosticZoom.start')<fullSpan);
assert.equal(timeline.el('resetTimelineZoom').disabled,false);
assert.equal(timeline.el('resetDetailZoom').disabled,false);
assert.match(timeline.el('timelineZoomInfo').textContent,/Zoomed to/);
const zoomURL=timeline.run("graphPageUrl('timeline').href");
assert(zoomURL.includes('zoom_start=')&&zoomURL.includes('zoom_end='));
assert(!zoomURL.includes('source-1'));
const firstSpan=timeline.run('diagnosticZoom.end-diagnosticZoom.start');
assert.equal(timeline.run("setDiagnosticZoom(diagnosticZoom.start+1000,diagnosticZoom.end-1000)"),true);
assert(timeline.run('diagnosticZoom.end-diagnosticZoom.start')<firstSpan);
timeline.run('resetDiagnosticZoom()');
assert.equal(timeline.run('diagnosticZoom'),null);
assert.equal(timeline.el('resetTimelineZoom').disabled,true);
assert.equal(timeline.el('resetDetailZoom').disabled,true);
assert(!timeline.run("graphPageUrl('detail').href").includes('zoom_start'));
// A click or a tiny accidental movement remains an inspection, not a zoom.
timeline.run("startChartBrush('timeline',{clientX:250,pointerId:9,button:0})");
timeline.run("endChartBrush('timeline',{clientX:254,pointerId:9})");
assert.equal(timeline.run('diagnosticZoom'),null);
assert.equal(timeline.run('timelineSelection!==null'),true);
assert.equal(timeline.askCalls,0);

// Downsampled extrema may be minutes apart even when every underlying 30s
// external probe succeeded. Real segment changes must still break the trace.
const gapTest=harness();
const gapAt=(time,segment)=>({recorded_at:'2026-11-08T'+time+'Z',
 ...(segment===undefined?{}:{diag_segment:segment})});
const gapCall=(a,b,native=false,downsampled=false)=>
 gapTest.run('diagnosticTraceGap('+JSON.stringify(a)+','+JSON.stringify(b)+','+
  native+',30,'+downsampled+')');
assert.equal(gapCall(null,gapAt('12:00:00',0),false,true),false);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:05:00',0),false,true),false);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:05:00',0),false,false),true);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:00:30',1),false,true),true);
assert.equal(gapCall(gapAt('12:00:00'),gapAt('12:05:00'),false,true),true);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:05:00'),false,true),true);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:01:00',0)),false);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:20:00',0),true,true),false);
assert.equal(gapCall(gapAt('12:00:00',0),gapAt('12:20:00',0),true,false),true);
const reducedFixture={
 range_start:'2026-11-08T11:50:00Z',range_end:'2026-11-08T12:20:00Z',
 metrics:{free_os_mb:{downsampled:true,observed_metric_points:3409,
  samples:[
   {recorded_at:'2026-11-08T12:00:00Z',reachable:1,free_os_mb:830,diag_segment:0},
   {recorded_at:'2026-11-08T12:05:00Z',reachable:1,free_os_mb:850,diag_segment:0},
   {recorded_at:'2026-11-08T12:10:00Z',reachable:1,free_os_mb:810,diag_segment:1},
   {recorded_at:'2026-11-08T12:15:00Z',reachable:1,free_os_mb:825,diag_segment:1}
  ]}},reboots:[],incidents:[]
};
const reducedSvg=harness();
reducedSvg.el('range').value='6';
reducedSvg.el('plotExtent').value='full';
reducedSvg.el('timelineLayout').value='split';
reducedSvg.run('timelineData='+JSON.stringify(reducedFixture)+';drawIncidentTimeline()');
const memoryPath=()=>reducedSvg.el('incidentTimeline').children.find(
 node=>node.tagName==='PATH'&&node.stroke==='#70b9ff').d;
assert.equal(memoryPath().match(/[ML]/g).join(''),'MLML');
reducedSvg.run('timelineData.metrics.free_os_mb.downsampled=false;drawIncidentTimeline()');
assert.equal(memoryPath().match(/[ML]/g).join(''),'MMMM');
// The canvas detail graph consumes the same gap contract as the SVG timeline.
const reducedCanvas=harness(),canvasOps=[];
const fakeContext={
 scale(){},fillRect(){},fillText(){},setLineDash(){},beginPath(){},
 moveTo(){if(this.strokeStyle==='#70b9ff'&&this.lineWidth===2.1)canvasOps.push('M');},
 lineTo(){if(this.strokeStyle==='#70b9ff'&&this.lineWidth===2.1)canvasOps.push('L');},
 stroke(){},save(){},rect(){},clip(){},restore(){},arc(){},fill(){}
};
reducedCanvas.el('graph').getContext=()=>fakeContext;
reducedCanvas.el('plotExtent').value='full';
reducedCanvas.el('metric').value='free_os_mb';
const reducedDetail={start:Date.parse(reducedFixture.range_start),
 end:Date.parse(reducedFixture.range_end),a:reducedFixture.metrics.free_os_mb.samples,
 b:[],ak:'free_os_mb',bk:null,probe_seconds:30,
 aDownsampled:true,bDownsampled:false,reboots:[],incidents:[]};
reducedCanvas.run('timelineData='+JSON.stringify(reducedFixture)+
 ';visual='+JSON.stringify(reducedDetail)+';draw()');
assert.equal(canvasOps.join(''),'MLML');
canvasOps.length=0;
reducedCanvas.run('visual.aDownsampled=false;draw()');
assert.equal(canvasOps.join(''),'MMMM');
console.log('Downsampled chart tests passed: recorded continuity, real gaps, raw fallback, SVG and canvas.');

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
