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
    assert 'id="runHealthAudit"' in response.text
    assert "api/health-audit" in response.text
    assert "Run system check now" in response.text
    assert "health-domain-grid" in response.text
    assert "renderHealthAuditV2" in response.text


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
