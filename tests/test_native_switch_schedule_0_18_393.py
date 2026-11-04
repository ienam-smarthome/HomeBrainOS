"""Offline, no-write native dated trigger contract from upstream issue #575."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

import pytest
from native_switch_schedule import create_dated_switch, dated_switch_proposal_error

NAME = "HB one-shot | Block Media Google TV Streamer (One-time 2026-11-10 15:35)"


def test_native_dated_trigger_matches_upstream_575_contract():
    proposal = create_dated_switch(
        name=NAME, parent_id=169, device_id="6923", command="off",
        hub_local_at=datetime(2026, 11, 10, 15, 35, tzinfo=ZoneInfo("Europe/London")),
    )
    assert dated_switch_proposal_error(proposal["args"]) is None
    trigger, action = proposal["args"]["args"]["changes"]
    assert trigger["part"] == "trigger"
    assert trigger["value"]["capability"] == "Certain Time (and optional date)"
    fields = {row["name"]: row for row in trigger["value"]["fields"]}
    assert set(fields) == {"time#", "atTime#", "date#", "atDate#"}
    assert fields["atDate#"] == {
        "name": "atDate#", "type": "date", "value": "2026-11-10"
    }
    assert fields["atTime#"]["value"] == "2026-11-10T15:35:00.000+0000"
    assert action["part"] == "action"


def test_native_switch_contract_rejects_mutation_and_wrong_time():
    proposal = create_dated_switch(
        name=NAME, parent_id=169, device_id="6923", command="off",
        hub_local_at=datetime(2026, 11, 10, 15, 35, tzinfo=ZoneInfo("Europe/London")),
    )
    fields = proposal["args"]["args"]["changes"][0]["value"]["fields"]
    fields[-1]["type"] = "text"
    assert dated_switch_proposal_error(proposal["args"]) is not None
    fields[-1]["type"] = "date"
    fields[-1]["value"] = "2026-11-11"
    assert dated_switch_proposal_error(proposal["args"]) is not None


def test_native_switch_contract_refuses_undated_or_invalid_target():
    with pytest.raises(ValueError):
        create_dated_switch(
            name=NAME, parent_id=169, device_id="6923", command="off",
            hub_local_at=datetime(2026, 11, 10, 15, 35),
        )
    with pytest.raises(ValueError):
        create_dated_switch(
            name=NAME, parent_id=169, device_id="0", command="off",
            hub_local_at=datetime(2026, 11, 10, 15, 35, tzinfo=ZoneInfo("Europe/London")),
        )
    with pytest.raises(ValueError):
        create_dated_switch(
            name=NAME, parent_id=169, device_id="6923", command="off",
            hub_local_at=datetime(2026, 11, 10, 16, 35, tzinfo=ZoneInfo("Europe/London")),
        )
