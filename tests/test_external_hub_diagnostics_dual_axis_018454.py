"""Graph presentation regression: preserved source times and two independent scales."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from webui import render_page  # noqa: E402


def _js(page):
    begin = page.index("function diagNiceChartScale(")
    end = page.index("async function loadIncidentTimeline(){", begin)
    helpers = page.index("const diagUnit=")
    helpers_end = page.index("function drawDiagRebootMarkers(", helpers)
    return page[begin:end] + "\n" + page[helpers:helpers_end]


def test_chart_controls_and_evidence_contract_visible():
    page = render_page("HomeBrain", "0.18.454")
    for word in (
        'id="diagTimelineLayout"', 'value="combined" selected', 'value="split"',
        "diagChartYGridRight(", "diagTimelineMemoryGuide", "diagTimelineCpuGuide",
        "timelineData)drawIncidentTimeline(timelineData)", "diagChartHorizontal",
        'viewBox="0 0 860 320"', "diag_segment!==previousSegment",
        "No interpolation across missing intervals",
        "External observations are not proof of a reboot cause",
    ):
        assert word in page, word


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_combined_memory_cpu_dual_axis_cursor_and_local_split_toggle():
    page = render_page("HomeBrain", "0.18.454")
    script = _js(page)
    harness = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),elements=new Map();
function makeNode(tag='div'){
 return {tag,attrs:{},children:[],textContent:'',value:'',listeners:{},
  setAttribute(k,v){this.attrs[k]=String(v)},
  append(...items){this.children.push(...items)},
  replaceChildren(){this.children=[]},
  addEventListener(k,fn){this.listeners[k]=fn},
  getBoundingClientRect(){return {left:0,width:860}},
  focus(){}
 };
}
const document={
 getElementById(id){if(!elements.has(id))elements.set(id,makeNode());return elements.get(id)},
 createElementNS(_ns,tag){return makeNode(tag)},
 createElement(tag){return makeNode(tag)},
 createTextNode(text){let n=makeNode('textnode');n.textContent=text;return n}
};
document.getElementById('diagTimelineLayout').value='combined';
const ctx=vm.createContext({document});
vm.runInContext(__SCRIPT__,ctx);
ctx.fixture={
 range_start:'2026-11-07T10:00:00+00:00',
 range_end:'2026-11-07T10:20:00+00:00',probe_seconds:30,
 metrics:{
  free_os_mb:{observed_metric_points:2,downsampled:false,samples:[
   {recorded_at:'2026-11-07T10:02:00+00:00',reachable:1,free_os_mb:920,diag_segment:0},
   {recorded_at:'2026-11-07T10:12:00+00:00',reachable:1,free_os_mb:740,diag_segment:1}
  ]},
  native_load_pct:{observed_metric_points:2,downsampled:false,samples:[
   {recorded_at:'2026-11-07T10:02:00+00:00',reachable:1,native_load_pct:20,native_sample_label:'07-11 10:00'},
   {recorded_at:'2026-11-07T10:12:00+00:00',reachable:1,native_load_pct:75,native_sample_label:'07-11 10:10'}
  ]}
 },reboots:[{occurred_at:'2026-11-07T10:10:00+00:00',firmware:'2.5.3.117'}],incidents:[]
};
vm.runInContext('drawIncidentTimeline(fixture)',ctx);
const chart=document.getElementById('diagTimelineChart');
assert(chart.children.filter(x=>x.tag==='text' && Number(x.attrs.x)===833).length>=5,
       'Independent right-side CPU axis missing');
const paths=chart.children.filter(x=>x.tag==='path');
assert.equal(paths.length,2,'Two independently observed series required');
assert(paths[0].attrs.d.includes(' M'),'Observed missing interval must break memory line');
assert(chart.children.some(x=>x.attrs.stroke==='#f59e0b'),'Actual startup marker missing');
vm.runInContext("timelineSelectAt(Date.parse('2026-11-07T10:02:00+00:00'))",ctx);
for(const name of ['diagTimelineMemoryGuide','diagTimelineCpuGuide']){
 const guide=chart.children.find(x=>x.attrs.id===name);
 assert(guide, name+' missing');
 assert.equal(guide.attrs.visibility,'visible');
}
const readout=document.getElementById('diagTimelineReadout').textContent;
assert(readout.includes('920 MB')&&readout.includes('20 %'),readout);
assert(readout.includes('native label')&&readout.includes('external probe'),readout);
document.getElementById('diagTimelineLayout').value='split';
document.getElementById('diagTimelineLayout').listeners.change();
assert(!chart.children.some(x=>x.tag==='text'&&Number(x.attrs.x)===833),
       'Split should not have a right-side overlay axis');
assert(chart.children.some(x=>x.tag==='text'&&x.textContent.includes('independent scale')),
       'Split display lost its original panel scale labels');
assert.equal(chart.children.filter(x=>x.tag==='path').length,2);
"""
    result = subprocess.run(
        ["node", "-"], input=harness.replace("__SCRIPT__", json.dumps(script)),
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_full_page_inline_javascript_syntax():
    page = render_page("HomeBrain", "0.18.454")
    js = page[page.rfind("<script>")+8:page.rfind("</script>")]
    result = subprocess.run(
        ["node", "--check", "-"], input=js, text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
