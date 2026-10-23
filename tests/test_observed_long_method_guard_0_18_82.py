"""Live 0.18.81 replay: app 3933 had WARN method durations despite a model denial."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observed_long_method_guard import (
    observed_long_method_warnings,
    guard_observed_long_method_denials,
)
from api_response_builder import build_agent_response


def logs(app_id="3933", name="08. Octopus Energy", *, success=True, level="WARN"):
    return [{
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs", "success": success,
        "arguments": {"tool": "hub_get_logs", "args": {"appId": app_id, "limit": 100, "since": "24h"}},
        "mutates": False,
        "details": {
            "logs": [
                {"date": "2026-10-23 19:58:04.580", "level": level,
                 "message": f"app|{app_id}|{name}|method scheduledLiveHeartbeat of app {name} ran for 478,707ms"},
                {"date": "2026-10-23 19:59:12.156", "level": level,
                 "message": f"app|{app_id}|{name}|method scheduledLiveHeartbeat of app {name} ran for 310,592ms"},
            ]
        }
    }]


def test_long_warns_from_verified_structured_rows():
    items = observed_long_method_warnings(logs())
    assert set(items) == {"3933"}
    assert items["3933"]["durations_ms"] == [478707, 310592]
    assert items["3933"]["methods"] == ("scheduledLiveHeartbeat",)


def test_real_01881_table_and_prose_denials_are_reconciled():
    original = (
        "| App Name | pctBusy | Observed Logged Execution (ms) |\n"
        "| :--- | :--- | :--- |\n"
        "| **08. Octopus Energy** | 5.6% | Not observed in provided logs |\n\n"
        "* **Octopus Energy:** Logs for this app (from 23:00 to 23:10) show "
        "standard backfilling and REST processing; no execution time warnings "
        "were present in the provided sample.\n"
    )
    corrected, changed = guard_observed_long_method_denials(original, logs())
    assert changed
    assert "Not observed in provided logs" not in corrected
    assert "no execution time warnings" not in corrected
    assert "310,592–478,707" in corrected
    assert "App 3933" in corrected
    assert "timezone unverified" in corrected
    assert "shared failure" in corrected


def test_successful_info_only_or_failed_logs_do_not_cause_repairs():
    text = "* **Octopus Energy:** no execution time warnings were present in the sample."
    for evid in (logs(success=False), logs(level="INFO"),
                 [{"sub_tool": "hub_get_logs", "success": True,
                   "summary": "app|3933|08. Octopus Energy|method run ran for 500,000ms"}],
                 []):
        assert guard_observed_long_method_denials(text, evid) == (text, False)


def test_other_apps_negatives_are_not_changed():
    text = "* **Life360:** no execution time warnings were present in the sample."
    assert guard_observed_long_method_denials(text, logs()) == (text, False)


def test_narrow_true_negative_over_specific_duration_is_not_modified():
    text = "* **Octopus Energy:** no execution time warnings above 500,000ms."
    assert guard_observed_long_method_denials(text, logs()) == (text, False)


def test_correct_uncertainty_and_causal_disclaimer_preserved():
    text = "It is not proven that Octopus Energy caused the same failure."
    assert guard_observed_long_method_denials(text, logs()) == (text, False)


def test_final_response_explicitly_identifies_an_automatic_repair():
    outcome = SimpleNamespace(
        message="* **Octopus Energy:** no execution time warnings were present in the sample.",
        route="unified-mcp-agent", request_class="live-read",
        evidence=logs(), metrics={"counters": {"model_rounds": 1}},
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=100, version="0.18.82"
    )
    assert response["evidence_validation"]["observed_long_method_denial_corrected"] is True
    assert "App 3933" in response["message"]
    assert "no execution time warnings" not in response["message"]
    assert all(row.get("mutates") is False for row in response["evidence"])
