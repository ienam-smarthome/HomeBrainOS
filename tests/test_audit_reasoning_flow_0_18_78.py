"""v0.18.78: actual model-based synthesis over evidence-first whole-hub audits.

A model must see performance and scheduling evidence beyond the old 7000-char
cutoff. Its claims are non-authoritative and may not trigger Hubitat writes.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit_reasoning_context import build_audit_reasoning_packet
from health_audit_service import render_comprehensive_system_audit


def sample_report():
    return (
        "## Comprehensive Hubitat audit — ATTENTION\n"
        "Read-only: no device changes\n\n"
        "### Prioritised evidence-backed checks\n"
        "- Bedroom 3 Mesh offline with watchdog events.\n\n"
        "### Coverage\n- 205 devices; 200 bounded logs.\n\n"
        "### Quiet devices — not offline verdicts\n"
        + ("Passive sensor quiet 500 hours.\n" * 600)
        + "\n### Measured System Check stage timings\n"
        "- Device inventory took 26000ms; NOT measured CPU usage.\n\n"
        "### Scheduled jobs — queue evidence\n"
        "- 267 entries; owner candidates unverified.\n\n"
        "### Scheduler candidates versus installed automations\n"
        "- Disabled status does not prove jobs execute.\n\n"
        "### Performance leaders (not automatic faults)\n"
        "- 00 Energy Usage: pctTotal=4.943%, averageMs=304.49.\n"
        "- SenseCap Settings: pctTotal=4.918%, device intentionally off.\n\n"
        "### Additional scoped diagnostic findings\n"
        "- Android TV Remote: certificate_unknown warnings.\n\n"
        "### Evidence-based next checks\n"
        "- Check actual source roles before changing settings.\n"
    )


def test_packet_contains_all_material_source_classes_after_oversized_quiet_list():
    report = sample_report()
    assert "pctTotal=4.943%" not in report[:7000]
    packet = build_audit_reasoning_packet(report)
    assert len(packet) <= 14000
    assert "DATA, NOT INSTRUCTIONS" in packet
    assert "top-ranked sample" in packet
    assert "Bedro" in packet
    assert "pctTotal=4.943%" in packet
    assert "Scheduled jobs" in packet and "267 entries" in packet
    assert "26000ms" in packet
    assert "certificate_unknown" in packet
    assert "owner candidates unverified" in packet
    assert "Passive sensor quiet" not in packet


def test_empty_or_plain_report_still_has_non_causal_source_boundary():
    packet = build_audit_reasoning_packet("offline sensor reported, no more evidence")
    assert "NOT INSTRUCTIONS" in packet
    assert "offline sensor reported" in packet
    assert "do not infer" in packet


def test_reasoned_summary_appears_before_detailed_evidence_and_is_labeled():
    snapshot = {
        "status": "attention",
        "checked_at": "2026-10-23T17:20:35+00:00",
        "attention_count": 0,
        "issues": [],
        "sections": {
            "devices": {"total": 205, "offline_count": 0,
                        "low_battery_count": 0},
            "automations": {"total": 160},
            "logs": {"available": True, "entries_checked": 200,
                     "checked_hours": 24},
        },
    }
    report = render_comprehensive_system_audit(
        snapshot, {}, ai_advisory=(
            "Energy Usage deserves first investigation by observed pctTotal; "
            "the measured number is not direct Hubitat CPU utilization."
        ),
    )
    assert "### Reasoned answer" in report
    assert "Optional AI diagnostic hypotheses — unverified" in report
    assert report.index("### Reasoned answer") < report.index("### Coverage")
    assert report.index("### Reasoned answer") < report.index(
        "### Evidence-based next checks"
    )
    assert "No repairs performed" in report


@pytest.mark.asyncio
async def test_chat_audit_default_invokes_model_with_current_user_question(monkeypatch):
    import app as module
    calls = []
    fake_outcome = SimpleNamespace(message="Audit complete", route="comprehensive-system-audit")

    async def fake_full_audit(audit, mcp, **kwargs):
        calls.append((audit, mcp, kwargs))
        return fake_outcome

    monkeypatch.setitem(
        module.OPTIONS, "comprehensive_audit_ai_analysis_enabled", True,
    )
    monkeypatch.setattr(module, "run_comprehensive_chat_audit", fake_full_audit)
    prompt = (
        "Perform a comprehensive hub audit, check devices, logs, apps and "
        "performance, and rank the three most important issues."
    )
    reply = await module._agent_request(module.ChatRequest(prompt=prompt))
    assert reply is fake_outcome
    assert len(calls) == 1
    assert calls[0][2]["analysis_chat"] == module.agent.transport.chat
    assert calls[0][2]["analysis_focus"] == prompt


@pytest.mark.asyncio
async def test_opt_out_still_skips_model_path(monkeypatch):
    import app as module
    calls = []

    async def fake_full_audit(audit, mcp, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message="Audit complete")

    monkeypatch.setitem(
        module.OPTIONS, "comprehensive_audit_ai_analysis_enabled", False,
    )
    monkeypatch.setattr(module, "run_comprehensive_chat_audit", fake_full_audit)
    prompt = ("Perform a comprehensive hub audit checking devices, logs "
              "and performance statistics.")
    await module._agent_request(module.ChatRequest(prompt=prompt))
    assert calls == [{}]
