from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def _load_app(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(
        '{"morning_health_check_enabled": false, "morning_health_check_time": "07:00"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(options))
    monkeypatch.setenv("HEALTH_AUDIT_PATH", str(tmp_path / "health.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_health_audit_dashboard_card_is_present(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)

    with TestClient(module.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="systemHealthCard"' in response.text
    assert 'id="healthAuditStatus"' in response.text
    assert 'class="health-heading"' in response.text
    assert '<strong>System check</strong>' in response.text
    assert "audit.message" not in response.text
    assert 'id="runHealthAudit"' in response.text
    assert "api/health-audit" in response.text
    assert "Run system check now" in response.text
    assert "health-domain-grid" in response.text
    assert "renderHealthAuditV2" in response.text
    assert "healthIssueClass" in response.text
    assert "health-issue-critical" in response.text
    assert "health-issue-warning" in response.text
    assert "toUpperCase()+': '" not in response.text
    assert "}\\nfunction healthIssueClass" not in response.text
    assert "function healthTime" in response.text
    assert "function healthIssueClass" in response.text
    assert "Pushover delivery failed" in response.text
    assert 'id="sendPushoverReport"' in response.text
    assert "api/pushover/report" in response.text


def test_health_audit_status_and_manual_run_endpoints(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)
    result = {
        "status": "attention",
        "message": "System check: Attention — 1 item needs attention.",
        "checked_at": "2026-09-19T07:00:00+00:00",
        "attention_count": 1,
        "new_count": 1,
        "resolved_count": 0,
        "issues": [],
        "sections": {"devices": {"total": 84}},
    }

    monkeypatch.setattr(module.health_audit, "latest", lambda: result)

    async def run(*, reason):
        assert reason == "manual"
        return result

    monkeypatch.setattr(module.health_audit, "run", run)

    with TestClient(module.app) as client:
        status = client.get("/api/health-audit")
        manual = client.post("/api/health-audit/run")

    assert status.status_code == 200
    assert status.json()["latest"]["attention_count"] == 1
    assert status.json()["schedule"]["enabled"] is False

    assert manual.status_code == 200
    assert manual.json()["latest"]["sections"]["devices"]["total"] == 84
    assert manual.json()["schedule"]["time"] == "07:00"


def test_manual_pushover_report_endpoint(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)
    report = {"status": "attention", "attention_count": 2}

    class Notifier:
        enabled = True
        configured = True

        async def send(self, audit):
            assert audit == report
            return {"sent": True, "request": "pushover-request-id"}

    monkeypatch.setattr(module, "pushover_notifier", Notifier())
    monkeypatch.setattr(module.health_audit, "latest", lambda: report)

    with TestClient(module.app) as client:
        response = client.post("/api/pushover/report")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Latest System Check report sent to Pushover.",
        "request": "pushover-request-id",
    }


def test_manual_pushover_report_reports_disabled_configuration(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)

    with TestClient(module.app) as client:
        response = client.post("/api/pushover/report")

    assert response.status_code == 409
    assert response.json()["detail"] == "Pushover notifications are disabled"


def test_manual_pushover_report_requires_existing_audit(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)

    class Notifier:
        enabled = True
        configured = True

    monkeypatch.setattr(module, "pushover_notifier", Notifier())
    monkeypatch.setattr(module.health_audit, "latest", lambda: None)

    with TestClient(module.app) as client:
        response = client.post("/api/pushover/report")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "No System Check report is available. Run system check first."
    )
