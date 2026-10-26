"""Duration and incomplete-investigation UI contract for opt-in V2."""
from __future__ import annotations

from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from investigation_v2.test_webui import render_v2_test_page


def test_duration_format_has_minutes_total_seconds_and_original_milliseconds():
    page = render_v2_test_page()
    assert "function readableDuration(ms)" in page
    assert "Math.floor(ms/60000)" in page
    assert "(ms/1000).toFixed(3)" in page
    assert "(remainingMs/1000).toFixed(3)" in page
    assert "Duration · '+duration.seconds" in page
    assert "duration?.primary??'Unavailable'" in page
    assert "duration_seconds:duration?.seconds??null" in page
    assert "duration_ms:duration?.milliseconds??null" in page
    assert "data.elapsed_ms+' ms'" not in page


def test_duration_and_status_fail_closed_and_keep_scope_separate():
    page=render_v2_test_page()
    assert "typeof ms!=='number'||!Number.isFinite(ms)||ms<0" in page
    assert "Commands retained (retrieved)" in page
    assert "read_budget_reached" in page
    assert "planning_timeout" in page
    assert "no_approved_discriminating_reads" in page
    assert "investigation incomplete" in page
    assert "localStorage" not in page
    assert "sessionStorage" not in page
    assert "innerHTML" not in page
