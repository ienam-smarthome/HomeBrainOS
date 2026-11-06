"""Regression tests for legible source-grounded diagnostic chart values."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from webui import render_page  # noqa: E402


def _chart_script(page: str) -> str:
    # Chart rendering uses shared axis helpers declared above the timeline.
    # Include those real production functions when isolating the lower chart,
    # rather than duplicating them as test stubs.
    axis_start = page.index("function diagNiceChartScale(")
    axis_end = page.index("const timelinePlot=", axis_start)
    start = page.index("const diagUnit=")
    end = page.index("async function loadDiagnosticsStatus(){", start)
    return page[axis_start:axis_end] + page[start:end]


def test_chart_has_y_values_summary_and_accessible_point_inspection():
    html = render_page("HomeBrain", "0.18.422")
    for marker in (
        'id="diagChartStats"', 'id="diagPointReadout"',
        'id="diagChart"', 'tabindex="0"',
        "Minimum:", "Maximum:", "Latest:",
        "diagChartCrosshair", "diagChartMarker", "diagTooltip",
        "pointermove", "pointerdown", "ArrowLeft", "ArrowRight",
        "diagMetricValue(value,metric)",
        "No actual readings for this metric yet",
    ):
        assert marker in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_chart_renders_real_numeric_y_ticks_and_selected_sample_without_browser():
    """Exercise the exact dashboard JS with small DOM stubs; no hub calls."""
    page = render_page("HomeBrain", "0.18.422")
    script = _chart_script(page)
    harness = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const chartScript=__CHART_SCRIPT__;
const els=new Map();
function makeNode(tag='div'){
 return {tag,attrs:{},children:[],textContent:'',value:'',
  selectedOptions:[{textContent:'Live Free OS memory (MB)'}],listeners:{},
  setAttribute(k,v){this.attrs[k]=String(v)},
  append(n){this.children.push(n)},
  replaceChildren(){this.children=[]},
  addEventListener(k,fn){this.listeners[k]=fn},
  getBoundingClientRect(){return {left:0,width:760}}
 };
}
const doc={
 getElementById(id){if(!els.has(id))els.set(id,makeNode());return els.get(id)},
 createElementNS(_ns,tag){return makeNode(tag)}
};
doc.getElementById('diagMetric').value='free_os_mb';
const ctx=vm.createContext({document:doc});
vm.runInContext(chartScript,ctx);
vm.runInContext(
 "diagHistoryRows=["+
 "{recorded_at:'2026-11-05T19:27:00+00:00',reachable:1,free_os_mb:834},"+
 "{recorded_at:'2026-11-05T19:27:30+00:00',reachable:1,free_os_mb:912},"+
 "{recorded_at:'2026-11-05T19:28:00+00:00',reachable:1,free_os_mb:845}"+
 "];drawDiagnosticsChart();",ctx);
const svg=doc.getElementById('diagChart');
const labels=svg.children.filter(x=>x.tag==='g').flatMap(x=>x.children).filter(x=>x.tag==='text').map(x=>x.textContent);
assert(labels.some(x=>/MB/.test(x)),'Y-axis labels with MB missing');
assert(labels.some(x=>/19:27/.test(x)),'24-hour time axis missing');
const stats=doc.getElementById('diagChartStats').textContent;
assert(stats.includes('834 MB')&&stats.includes('912 MB')&&stats.includes('845 MB'),stats);
assert(doc.getElementById('diagPointReadout').textContent.includes('845 MB'));
assert(svg.children.some(x=>x.attrs.id==='diagTooltip'),'Tooltip element missing');
vm.runInContext('diagSelectPoint(0)',ctx);
assert(doc.getElementById('diagPointReadout').textContent.includes('834 MB'));
doc.getElementById('diagChart').listeners.keydown({key:'ArrowRight',preventDefault(){}});
assert(doc.getElementById('diagPointReadout').textContent.includes('912 MB'));
doc.getElementById('diagMetric').value='java_free_mb';
doc.getElementById('diagMetric').selectedOptions=[{textContent:'Native Free Java (MB)'}];
vm.runInContext(
 "diagHistoryRows=["+
 "{recorded_at:'2026-11-05T19:28:00+00:00',java_free_mb:124,native_sample_label:'11-05 19:25:00'},"+
 "{recorded_at:'2026-11-05T19:28:30+00:00',java_free_mb:124,native_sample_label:'11-05 19:25:00'},"+
 "{recorded_at:'2026-11-05T19:33:00+00:00',java_free_mb:90,native_sample_label:'11-05 19:30:00'}"+
 "];drawDiagnosticsChart();",ctx);
assert(doc.getElementById('diagChartCaption').textContent.startsWith('2 observed native source'), 'Duplicate native samples falsely counted');
assert(doc.getElementById('diagPointReadout').textContent.includes('native source'));
"""
    proc = subprocess.run(
        ["node", "-"],
        input=harness.replace("__CHART_SCRIPT__", json.dumps(script)),
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_inline_homebrain_javascript_still_valid():
    if shutil.which("node") is None:
        pytest.skip("Node unavailable")
    html = render_page("HomeBrain", "0.18.422")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html)
    assert scripts
    for script in scripts:
        result = subprocess.run(
            ["node", "--check", "-"], input=script,
            text=True, capture_output=True, timeout=15,
        )
        assert result.returncode == 0, result.stderr
