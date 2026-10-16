import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from automation_status_service import AutomationStatusService
from api_response_builder import _guard_exclusive_history_date_claim

def test_scoped_app_status():
    assert not AutomationStatusService.matches_request("Show current status of the Livingroom automation (app 4019). Read-only.")
    assert AutomationStatusService.matches_request("Show all active automations")

def test_history_command_outside_recent_window_is_acknowledged():
    message = "The device history and logs only cover events from 16 October 2026."
    evidence = [{"success": True, "details": {"events": [{"name":"command-on", "date":"2026-10-12T07:25:37+0100", "producedBy":{"label":"05. Maker API - HD+"}}]}}]
    out = _guard_exclusive_history_date_claim(message, evidence)
    assert "only cover" not in out
    assert "2026-10-12" in out
    assert "Maker API" in out
    assert "does not establish the cause" in out
