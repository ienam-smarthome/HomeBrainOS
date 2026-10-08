from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from health_audit_service import _log_findings  # noqa: E402
from frozen_core import health_audit_service_core as core  # noqa: E402


def test_info_event_with_failed_word_is_not_promoted_to_an_error() -> None:
    washing = {
        "level": "INFO",
        "message": (
            "app|4157|Washing machine finished notification|"
            "Not triggered: Power level of Washing Machine(6) reported < 5.0 "
            "but Washing Machine failed to stay that way for: 0:00:180"
        ),
    }
    assert core._log_level(washing) == "info"
    section, issues = _log_findings([washing])
    assert section["error_group_count"] == 0
    assert section["warning_group_count"] == 0
    assert issues == []


def test_explicit_warn_error_and_no_level_fallback_are_preserved() -> None:
    rows = [
        {"level": "DEBUG", "message": "An exception did not happen"},
        {"level": "TRACE", "message": "failure retrying"},
        {"level": "WARN", "message": "Timeout while reading"},
        {"level": "ERROR", "message": "Operation failed"},
        {"message": "Operation failed without explicit level"},
    ]
    assert [core._log_level(r) for r in rows] == [
        "info", "info", "warning", "error", "error"
    ]
    section, _ = _log_findings(rows)
    assert section["error_group_count"] == 2
    assert section["warning_group_count"] == 1


def test_mcp_structured_error_is_decoded_before_500_character_cutoff() -> None:
    entry = {
        "appId": "4151",
        "generation": "1234567890",
        "extraMetadata": "x" * 600,
        "entry": {
            "level": "error",
            "component": "server",
            "message": (
                "Validation error in hub_list_devices: attributeNames applies only "
                "to format='context' (got format 'summary'); it would be ignored."
            ),
        },
    }
    raw = "app|4151|MCP Rule Server|[MCP1] " + json.dumps(entry)
    section, issues = _log_findings([{"level": "ERROR", "message": raw}])
    assert section["error_group_count"] == 1
    group = section["error_groups"][0]
    assert group["summary"].startswith("Validation error in hub_list_devices")
    assert "attributeNames applies only" in group["message"]
    assert "extraMetadata" not in group["message"]
    assert "attributeNames applies only" in issues[0]["detail"]


def test_mcp_structured_log_without_json_keeps_prior_fallback() -> None:
    summary = core._log_summary(
        "app|4151|MCP Rule Server|ordinary warning", "ordinary"
    )
    assert "ordinary warning" in summary
    assert core._structured_mcp_entry(
        "app|4151|MCP Rule Server|not JSON {this is not JSON}"
    ) is None
