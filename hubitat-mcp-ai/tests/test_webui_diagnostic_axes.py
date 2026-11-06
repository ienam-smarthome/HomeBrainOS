"""Regression checks for the real, read-only diagnostic SVG axis helpers."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from webui import render_page  # noqa: E402


def _axes_source() -> str:
    page = render_page("HomeBrain", "test")
    start = page.index("function diagNiceChartScale(")
    end = page.index("const timelinePlot=", start)
    return page[start:end]


def test_both_diagnostic_charts_use_dense_axes_and_source_boundaries():
    page = render_page("HomeBrain", "test")
    assert "diagChartTimeGrid(svg,svg,first,last,timelinePlot.left,timelinePlot.right," in page
    assert "diagChartYGrid(svg,timelinePlot.left,timelinePlot.right," in page
    assert "diagChartYGrid(group,diagPlot.left,diagPlot.right," in page
    assert "diagChartTimeGrid(svg,group,first,last,diagPlot.left,diagPlot.right," in page
    assert "diagNiceChartScale(memoryLow,memoryHigh,8)" in page
    assert "diagNiceChartScale(0,cpuHigh,8)" in page
    assert "diagNiceChartScale(Math.max(0,rawMin-padding),rawMax+padding,10)" in page
    assert "t-prev>(kind==='native'?900000:" in page
    assert "diag_segment!==previousSegment" in page
    assert "These observations do not establish a cause." in page


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_axis_helpers_generate_dense_grid_and_fit_phone_without_fake_samples():
    # Execute the exact helper definitions shipped in the add-on (no reimplementation).
    source = _axes_source()
    script = source + """
function diagChartSvgNode(tag, attributes, textValue) {
  return {tag, attributes, textValue};
}
function diagMetricValue(value) {return String(value);}
function renderGrid(width, first, last) {
  const nodes=[];
  const svg={getBoundingClientRect:()=>({width})};
  const layer={append:(node)=>nodes.push(node)};
  diagChartTimeGrid(svg,layer,first,last,75,825,30,292,319);
  return nodes;
}
const first=Date.parse('2026-11-06T13:00:00Z');
const last=Date.parse('2026-11-06T19:00:00Z');
const desktop=renderGrid(900,first,last);
const phone=renderGrid(320,first,last);
const multi=renderGrid(900,first,first+3*86400000);
const memory=diagNiceChartScale(640,985,8);
const cpu=diagNiceChartScale(0,56.6,8);
const y=[];
diagChartYGrid({append:n=>y.push(n)},75,825,30,142,memory,'free_os_mb','#93c5fd');
process.stdout.write(JSON.stringify({
  desktopLines:desktop.filter(n=>n.tag==='line').length,
  desktopLabels:desktop.filter(n=>n.tag==='text').map(n=>n.textValue),
  phoneLines:phone.filter(n=>n.tag==='line').length,
  multiLabels:multi.filter(n=>n.tag==='text').map(n=>n.textValue),
  memory,
  cpu,
  yLines:y.filter(n=>n.tag==='line').length,
  yLabels:y.filter(n=>n.tag==='text').length,
}));
"""
    done = subprocess.run(["node", "-e", script], capture_output=True,
                          text=True, check=True, timeout=10)
    results = json.loads(done.stdout)
    assert results["desktopLines"] >= 10
    assert 3 <= results["phoneLines"] < results["desktopLines"]
    assert all(":" in label for label in results["desktopLabels"])
    assert all("Nov" in label for label in results["multiLabels"])
    assert results["memory"]["min"] <= 640
    assert results["memory"]["max"] >= 985
    assert results["cpu"]["min"] == 0
    assert results["cpu"]["max"] >= 56.6
    assert results["yLines"] >= 7
    assert results["yLabels"] == results["yLines"]
