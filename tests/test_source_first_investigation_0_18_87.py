"""Regression tests for a source-code question routed as broad performance."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from groovy_source_investigation import requested_groovy_app_id
from performance_host_plan import is_broad_performance_request
from historical_causal_claim_guard import assess_historical_claims

PROMPT = (
    "Perform a deep READ-ONLY root-cause investigation of Device Status Report "
    "(app 3977) and Device Status Report Display (device 7182). Investigate "
    "the observed LimitExceededException log rows naming setReportData at "
    "line 64. Inspect available app configuration, actual Groovy source, "
    "scheduled callbacks, execution frequency, recent logs and performance "
    "statistics. Explain why the exception appears in device-sourced logs "
    "when the app-scoped log query is empty. Identify root cause evidence, "
    "and recommend safest next steps. Do not modify anything."
)


def test_named_source_question_does_not_take_broad_performance_route():
    assert requested_groovy_app_id(PROMPT) == "3977"
    assert not is_broad_performance_request(PROMPT)
    assert not is_broad_performance_request(
        "Inspect actual Groovy source for app 3977 and recommend "
        "improvements to hub performance. No changes."
    )


def test_generic_performance_question_still_uses_performance_route():
    question = "Analyse hub load and recommend improvements"
    assert requested_groovy_app_id(question) is None
    assert is_broad_performance_request(question)


def test_source_overload_statement_is_not_a_device_command_claim():
    message = "App 3977 caused excessive hub load at setReportData line 64."
    assert assess_historical_claims(message, [], command_only=True)[
        "unverifiedCommandActors"
    ] == []


def test_source_review_still_guards_claimed_command_dispatch():
    message = "App 3977 issued a switch-off command yesterday."
    assert assess_historical_claims(message, [], command_only=True)[
        "unverifiedCommandActors"
    ] == ["3977"]


def test_frontend_network_messages_have_distinct_write_and_read_paths():
    frontend = (ROOT / "webui.py").read_text(encoding="utf-8")
    assert "status_verification:'read-outcome-unknown'" in frontend
    assert "status_verification:'write-outcome-unknown'" in frontend
    assert "No Hubitat write was requested" in frontend
    assert "The result of any requested Hubitat write is UNKNOWN" in frontend
    assert "const strictReadOnly = /\\bread[\\s-]*only\\b/i.test(text)" in frontend
