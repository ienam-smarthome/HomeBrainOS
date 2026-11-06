"""External diagnostics 30-day charts and evidence-based startup markers."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from external_hub_diagnostics import (  # noqa: E402
    ExternalHubDiagnostics, parse_system_start_events, summarize_history_samples,
)
from webui import render_page  # noqa: E402


def _instant(value):
    return value.isoformat(timespec="milliseconds")


def test_system_start_parsing_requires_actual_event_and_explicit_offset():
    now = datetime.now(timezone.utc)
    valid = (now - timedelta(minutes=3)).isoformat(timespec="milliseconds")
    payload = json.dumps([
        {"name": "systemStart", "date": valid, "value": "2.5.3.117"},
        {"name": "systemStart", "date": valid, "value": "2.5.3.117"},
        {"name": "manualReboot", "date": valid, "value": "unverified"},
        {"name": "systemStart", "date": "2026-11-05 20:10:00", "value": "2.5.3.117"},
        {"name": "systemStart", "date": (now + timedelta(hours=1)).isoformat()},
    ])
    found = parse_system_start_events(payload)
    assert len(found) == 1
    assert found[0]["firmware"] == "2.5.3.117"
    assert found[0]["source"] == "hub_events_json_systemStart"
    with pytest.raises(ValueError):
        parse_system_start_events("<html>not JSON</html>")


def test_long_range_preserves_actual_low_memory_extremum_and_gap_boundaries():
    finish = datetime.now(timezone.utc)
    start = finish - timedelta(hours=72)
    rows = []
    for i in range(3600):
        row = {
            "recorded_at": _instant(start + timedelta(seconds=i * 30)),
            "reachable": 1, "free_os_mb": 840.0 + i % 6,
        }
        if i == 1800:
            row["free_os_mb"] = 221.0
        if i == 2400:
            row["reachable"] = 0
            row["free_os_mb"] = None
        rows.append(row)
    result = summarize_history_samples(
        iter(rows), metric="free_os_mb", start=start, finish=finish,
        probe_seconds=30, bucket_count=320,
    )
    assert result["source_sample_count"] == 3600
    assert result["observed_metric_points"] == 3599
    assert result["downsampled"] is True
    assert len(result["samples"]) < 2200
    assert min(p["free_os_mb"] for p in result["samples"]) == 221.0
    # No fabricated point for the failed probe; segments split at true gap.
    assert all(p["free_os_mb"] is not None for p in result["samples"])
    point_before = next(p for p in result["samples"] if p["recorded_at"] ==
                        rows[2399]["recorded_at"])
    point_after = next(p for p in result["samples"] if p["recorded_at"] ==
                       rows[2401]["recorded_at"])
    assert point_after["diag_segment"] > point_before["diag_segment"]


def test_short_range_returns_every_real_sample_without_downsampling():
    finish = datetime.now(timezone.utc)
    start = finish - timedelta(hours=1)
    rows = [
        {"recorded_at": _instant(start + timedelta(minutes=i)),
         "reachable": 1, "free_os_mb": 775.0 + i}
        for i in range(40)
    ]
    result = summarize_history_samples(iter(rows), metric="free_os_mb",
                                       start=start, finish=finish,
                                       probe_seconds=30)
    assert result["downsampled"] is False
    assert len(result["samples"]) == 40


def test_native_readings_dedupe_stale_native_labels_in_long_window():
    finish = datetime.now(timezone.utc)
    start = finish - timedelta(hours=72)
    rows = [
        {"recorded_at": _instant(start + timedelta(seconds=i * 30)),
         "reachable": 1, "native_sample_label": f"source-{i//10:04d}",
         "java_free_mb": 28.5 if i == 1200 else (100 + i % 3)}
        for i in range(3100)
    ]
    result = summarize_history_samples(iter(rows), metric="java_free_mb",
                                       start=start, finish=finish, probe_seconds=30)
    assert result["source_sample_count"] == 3100
    assert result["observed_metric_points"] == 310
    assert min(p["java_free_mb"] for p in result["samples"]) == 28.5
    assert len({p["native_sample_label"] for p in result["samples"]}) == len(result["samples"])


def test_recorder_retains_confirmed_reboot_and_fetches_no_more_than_once_per_5m(tmp_path):
    rec = ExternalHubDiagnostics(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "diag.sqlite3", probe_seconds=30, retention_days=30,
    )
    rec._initialize()
    urls = []
    instant = _instant(datetime.now(timezone.utc) - timedelta(minutes=2))
    def handler(request):
        urls.append(request.url.path)
        if request.url.path.endswith("/freeOSMemoryLast"):
            return httpx.Response(200, text=(
                "Date/time,Free OS,5m CPU avg,Total Java,Free Java,Direct Java\n"
                "11-06 14:05:00,905000,0.76,331392,86152,9000\n"
            ))
        if request.url.path == "/hub/eventsJson":
            return httpx.Response(200, json=[
                {"name": "systemStart", "date": instant, "value": "2.5.3.117"},
            ])
        if request.url.path == "/hub/advanced/freeOSMemory":
            return httpx.Response(200, text="844800")
        raise AssertionError("unexpected Hubitat endpoint: "+request.url.path)
    async def run_probes():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False,
        ) as client:
            await rec._poll(client)
            await rec._poll(client)
    asyncio.run(run_probes())
    assert urls.count("/hub/eventsJson") == 1
    assert urls.count("/hub/advanced/freeOSMemory") == 2
    assert urls.count("/hub/advanced/freeOSMemoryLast") == 1
    result = rec.history(hours=72, metric="free_os_mb")
    assert len(result["reboots"]) == 1
    assert result["reboots"][0]["firmware"] == "2.5.3.117"
    assert result["coverage"] == "partial_observations_not_proof_of_cause"
    assert result["hours"] == 72
    assert rec.history(hours=10000)["hours"] == 720
    with pytest.raises(ValueError):
        rec.history(hours=720, metric="nonexistent_metric")
    with sqlite3.connect(str(rec.path)) as db:
        assert db.execute("SELECT COUNT(*) FROM hub_startups").fetchone()[0] == 1


def test_homebrain_exposes_reboots_and_extended_ranges_without_guessing():
    html = render_page("HomeBrain", "0.18.428")
    for snippet in (
        'value="72">3 days', 'value="168">7 days',
        'value="720">30 days',
        'id="diagReboots"',
        'function drawDiagRebootMarkers',
        "event.occurred_at", "event.firmware",
        "diagHistoryMeta.downsampled",
        "row.diag_segment!==previousSegment",
        "api/hub-diagnostics/history?hours=",
        "No confirmed systemStart events available",
        "startups",
    ):
        # One static marker, not a conditional claim that a reboot happened.
        if snippet == "startups":
            continue
        assert snippet in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_homebrain_inline_scripts_have_valid_syntax():
    html = render_page("HomeBrain", "0.18.428")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html)
    assert scripts
    for script in scripts:
        run = subprocess.run(
            ["node", "--check", "-"], input=script,
            capture_output=True, text=True, timeout=15,
        )
        assert run.returncode == 0, run.stderr
