"""Verify five-minute load-equivalent CPU percent without new polling."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from external_hub_diagnostics import ExternalHubDiagnostics, utc_now  # noqa: E402
from webui import render_page  # noqa: E402


@pytest.mark.parametrize(
    "cores,raw_load,expected",
    [(4, 0.76, 19.0), (4, 1.04, 26.0), (2, 0.76, 38.0),
     (4, 5.2, 130.0), (4, 0.0, 0.0)],
)
def test_derived_load_pct_tracks_configured_core_count_and_is_not_capped(
    tmp_path, cores, raw_load, expected
):
    rec = ExternalHubDiagnostics(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "external.sqlite3",
        cpu_cores=cores,
    )
    rec._initialize()
    sample = {
        "recorded_at": utc_now(), "reachable": 1, "free_os_mb": 834.0,
        "native_sample_label": "11-05 19:40:38", "native_load5": raw_load,
    }
    rec._last = sample
    rec._save(sample, None, False)
    status = rec.status()
    history = rec.history(1)
    assert status["cpu_cores"] == cores
    assert status["last"]["native_load5"] == raw_load
    assert status["last"]["native_load_pct"] == expected
    assert history["cpu_cores"] == cores
    assert history["samples"][-1]["native_load_pct"] == expected
    assert history["samples"][-1]["native_load5"] == raw_load


def test_missing_native_cpu_does_not_become_zero(tmp_path):
    rec = ExternalHubDiagnostics(enabled=False, cpu_cores=4,
                                 path=tmp_path / "missing.sqlite3")
    assert rec.status()["last"]["native_load_pct"] is None
    assert rec.history()["cpu_cores"] == 4


def test_homebrain_card_and_chart_distinguish_percent_from_raw_average():
    page = render_page("HomeBrain", "0.18.423")
    assert 'id="diagCpuPercent"' in page
    assert '<option value="native_load_pct">5-minute CPU load equivalent (%)</option>' in page
    assert '<option value="native_load5">5-minute CPU load average (raw)</option>' in page
    assert "not measured CPU utilisation" in page
    assert "metric==='native_load_pct'" in page
    assert "row.native_load_pct" in page


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_rendered_homebrain_javascript_syntax():
    page = render_page("HomeBrain", "0.18.423")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", page)
    assert scripts
    for script in scripts:
        result = subprocess.run(["node", "--check", "-"], input=script,
                                text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
