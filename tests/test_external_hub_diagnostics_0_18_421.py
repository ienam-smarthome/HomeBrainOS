"""External Hub Diagnostics: no real LAN access, no device writes."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
import sys

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from external_hub_diagnostics import (  # noqa: E402
    ExternalHubDiagnostics, parse_live_memory, parse_native_sample,
    validate_hub_url,
)
from webui import render_page  # noqa: E402


def make_recorder(tmp_path):
    instance = ExternalHubDiagnostics(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "diag.sqlite3", probe_seconds=30,
    )
    instance._initialize()
    return instance


def test_local_only_endpoint_guard_and_parsers():
    assert validate_hub_url("http://192.168.1.239") == "http://192.168.1.239"
    for url in (
        "https://192.168.1.239", "http://8.8.8.8",
        "http://example.com", "http://127.0.0.1",
        "http://192.168.1.239/reboot", "http://a:b@192.168.1.239",
        "http://192.168.1.239?token=secret", "http://192.168.1.239:9999",
    ):
        with pytest.raises(ValueError):
            validate_hub_url(url)
    assert parse_live_memory(" 1048576 \n") == 1024.0
    with pytest.raises(ValueError):
        parse_live_memory("invalid")
    sample = parse_native_sample(
        "Date/time,Free OS,5m CPU avg,Total Java,Free Java,Direct Java\n"
        "11-05 18:20:20,905000,1.04,331392,86152,9000\n"
    )
    assert sample["native_sample_label"] == "11-05 18:20:20"
    assert sample["java_allocated_heap_used_pct"] == 74.0
    assert sample["native_load5"] == 1.04


def test_external_probes_persist_and_native_source_does_not_poll_at_30s(tmp_path):
    rec = make_recorder(tmp_path)
    urls = []

    def handler(request):
        urls.append(request.url.path)
        if request.url.path.endswith("freeOSMemoryLast"):
            return httpx.Response(200, text=(
                "Date/time,Free OS,5m CPU avg,Total Java,Free Java,Direct Java\n"
                "11-05 18:20:20,905000,1.04,331392,86152,9000\n"
            ))
        return httpx.Response(200, text="921600")

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False,
        ) as client:
            await rec._poll(client)
            # Same native sample remains cached; never claim a 30s Java source.
            await rec._poll(client)

    asyncio.run(scenario())
    assert urls.count("/hub/advanced/freeOSMemory") == 2
    assert urls.count("/hub/advanced/freeOSMemoryLast") == 1
    reply = rec.history(hours=1)
    assert len(reply["samples"]) >= 1
    last = rec.status()["last"]
    assert last["free_os_mb"] == 900.0
    assert last["native_sample_label"] == "11-05 18:20:20"
    assert last["java_free_mb"] > 80
    assert rec.status()["last_good_at"]
    assert reply["coverage"] == "partial_observations_not_proof_of_cause"


def test_two_failures_open_outage_and_recovery_closes_it(tmp_path):
    rec = make_recorder(tmp_path)
    attempts = 0

    def handler(request):
        nonlocal attempts
        if request.url.path.endswith("freeOSMemoryLast"):
            return httpx.Response(200, text="11-05 18:20:20,905000,1.04,331392,86152")
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("failed", request=request)
        return httpx.Response(200, text="921600")

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False,
        ) as client:
            await rec._poll(client)
            assert rec.status()["status"] == "degraded"
            await rec._poll(client)
            assert rec.status()["status"] == "offline"
            await rec._poll(client)

    asyncio.run(scenario())
    assert rec.status()["status"] == "online"
    rows = rec.history(hours=1)
    assert len(rows["incidents"]) == 1
    assert rows["incidents"][0]["recovered_at"] is not None
    assert "hub-unreachable" == rows["incidents"][0]["kind"]
    with sqlite3.connect(str(rec.path)) as db:
        assert db.execute("SELECT COUNT(*) FROM samples WHERE reachable=0").fetchone()[0] == 2


def test_default_disabled_and_ui_contract(tmp_path):
    instance = ExternalHubDiagnostics(
        enabled=False, hub_url="", path=tmp_path / "missing.sqlite3",
    )
    assert instance.status()["status"] == "disabled"
    assert instance.history()["samples"] == []
    page = render_page("HomeBrain", "0.18.421")
    for marker in (
        'id="hubDiagnosticsCard"', 'id="diagOS"', 'id="diagJava"',
        'id="diagHeap"', 'id="diagLatency"', 'id="diagChart"',
        'id="diagIncidents"', 'id="diagDetails"',
        "api/hub-diagnostics/status", "api/hub-diagnostics/history",
    ):
        assert marker in page
