"""v0.18.38: compact, secure saved Q&A and evidence-consistent command issuer."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))
from webui import render_page
from historical_command_source_contract import (
    focused_command_observation, calibrate_command_causality,
)

QUESTION = (
    "Investigate Bedroom 3 Mesh OFF event on 12 October 2026 at 01:30 BST, "
    "compare possible command issuers. Read-only."
)
ISSUER = "Power saving: Bedroom 3 Mesh off @night"


def _command_rows():
    return [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7103", "since": "2026-10-12T00:20:00Z",
            "until": "2026-10-12T00:40:00Z",
        }},
        "details": {"observedEvents": [{
            "name": "command-off", "type": "command",
            "date": "2026-10-12T01:30:01.743+0100",
            "description": "Command called: off()",
            "producedBy": {"appId": 3950, "name": ISSUER},
        }]},
    }]


def test_minimal_ui_keeps_single_answer_and_live_commands():
    page = render_page("HomeBrain", "0.18.110")
    assert 'id="answer"' in page
    assert 'id="ask"' in page and 'id="speak"' in page
    assert 'id="resetContext"' in page
    assert 'id="chatTranscript"' not in page
    assert 'id="currentTurn"' not in page
    assert "if(data.confirmation_required===true)" in page
    assert "Copy technical" in page


def test_positive_same_issuer_reconciles_contradictory_model_denial():
    record = focused_command_observation(QUESTION, _command_rows())
    assert record is not None
    assert record["recordedIssuerAppId"] == "3950"
    assert record["recordedIssuerName"] == ISSUER
    model = (
        'I could not verify the claim about "' + ISSUER
        + '" against evidence actually collected for that device this turn, '
        'so I will not provide an unverified answer.\n\n'
        'The trigger is still unknown.'
    )
    fixed, issues = calibrate_command_causality(model, record, None)
    assert "I could not verify the claim" not in fixed
    assert "**Recorded command verified:**" in fixed
    assert "app 3950" in fixed
    assert "trigger and physical outcome remain unverified" in fixed
    assert "The trigger is still unknown." in fixed
    assert "contradictory_recorded_issuer_denial" in issues


def test_wrong_named_issuer_and_missing_command_never_get_upgraded():
    record = focused_command_observation(QUESTION, _command_rows())
    unrelated = (
        'I could not verify the claim about "Other App" against evidence '
        'actually collected for that device this turn, so I will not '
        'provide an unverified answer.'
    )
    fixed, issues = calibrate_command_causality(unrelated, record, None)
    assert unrelated in fixed
    assert "contradictory_recorded_issuer_denial" not in issues
    assert focused_command_observation(QUESTION, _command_rows()[:-1]) is None
    preserved, issues = calibrate_command_causality(unrelated, None, None)
    assert preserved == unrelated
    assert issues == []
