from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from agent_prompt_policy import build_system_prompt


def test_performance_prompt_separates_measurement_observation_and_hypothesis():
    prompt = build_system_prompt(
        "Device manifest omitted or unavailable.",
        now=datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    )

    assert "HUB PERFORMANCE / OPTIMISATION" in prompt
    assert "MEASURED findings" in prompt
    assert "Logs and event streams are OBSERVATIONS" in prompt
    assert "label the explanation as a HYPOTHESIS" in prompt
    assert "30 minutes must not be used as causal proof" in prompt


def test_performance_prompt_requires_component_local_investigation():
    prompt = build_system_prompt(
        "Device manifest omitted or unavailable.",
        now=datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    )

    assert "inspect the same app/driver" in prompt
    assert "inspect that same component's schedules" in prompt
    assert "discover and call the relevant scheduled-job diagnostic" in prompt
    assert "secondary observations" in prompt


def test_room_status_prompt_preserves_provenance_and_freshness_boundaries():
    prompt = build_system_prompt(
        "Device manifest omitted or unavailable.",
        now=datetime(2026, 10, 9, 22, 55, tzinfo=timezone.utc),
    )

    assert "ROOM STATUS EVIDENCE" in prompt
    assert "unattributed range" in prompt
    assert "Never invent a timestamp" in prompt
    assert "do not call that fresh detection" in prompt
    assert "root cause separate" in prompt
    assert "missing numeric ID" in prompt
    assert "EXPLICIT HEALTH PRECEDENCE" in prompt
    assert "offline; last reported inactive" in prompt
    assert "Device Health/Warning section" in prompt
