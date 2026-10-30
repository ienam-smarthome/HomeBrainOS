"""v0.18.165 control handoff remains navigational, never authorises writes."""
from __future__ import annotations
import sys
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.intent_boundary import incompatible_v2_control_request

def test_imperative_remains_refused_while_status_question_remains_read_only():
    assert incompatible_v2_control_request("Turn on Livingroom Light 2.") is True
    assert incompatible_v2_control_request("Is Livingroom Light 2 on?") is False
