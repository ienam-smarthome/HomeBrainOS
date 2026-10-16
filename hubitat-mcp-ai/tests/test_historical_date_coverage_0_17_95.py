"""An off-time command must not vanish from all-evidence date summaries."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from api_response_builder import _guard_exclusive_history_date_claim


def test_cross_date_command_never_disappears():
    message = ("Because no focal event was found at 08:16, the evidence gathered "
               "in this turn exclusively covers activity from **16 October 2026**.")
    evidence = [
        {"success": True, "details": {"commandEvents": [
            {"date": "2026-10-12T07:25:37+0100", "name": "command-on"}]}},
        {"success": True, "details": {"events": [
            {"date": "2026-10-16T18:00:00+0100", "name": "switch"}]}},
    ]
    out = _guard_exclusive_history_date_claim(message, evidence)
    assert "exclusively covers" not in out
    assert "12 October 2026" in out
    assert "16 October 2026" in out
    assert "no focal event was found at 08:16" in out


def test_no_rewrite_for_only_one_observed_date():
    msg = "The evidence gathered in this turn exclusively covers activity from **16 October 2026**."
    evidence = [{"success": True, "details": {"events": [
        {"date": "2026-10-16T18:00:00+0100"}]}}]
    assert _guard_exclusive_history_date_claim(msg, evidence) == msg
