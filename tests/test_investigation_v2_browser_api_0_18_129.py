from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def app_with_test_mode(monkeypatch, tmp_path, *, enabled=True):
    options = tmp_path / "options.json"
    options.write_text(json.dumps({
        "investigation_v2_testing_enabled": enabled,
        "investigation_v2_test_token": "long-unit-test-secret-0123456789",
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }), encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(options))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def valid_body():
    return {
        "question": "Why did this light remain on all night?",
        "device_ids": ["7805"], "explicit_opt_in": True,
        "existing_v1_answer": None, "reference_answer": None,
    }


def test_v2_endpoint_requires_saved_opt_in_and_never_proceeds_when_off(
        monkeypatch, tmp_path):
    app = app_with_test_mode(monkeypatch, tmp_path, enabled=False)
    with TestClient(app.app) as client:
        page = client.get("/v2-test")
        denied = client.post("/api/v2/test", json=valid_body(),
                             headers={"X-HomeBrain-V2-Test-Token":
                                      "long-unit-test-secret-0123456789"})
    assert page.status_code == 404
    assert denied.status_code == 404


def test_v2_test_route_reports_auth_and_explicit_opt_in_failures(
        monkeypatch, tmp_path):
    app = app_with_test_mode(monkeypatch, tmp_path)
    with TestClient(app.app) as client:
        page = client.get("/v2-test")
        denied = client.post("/api/v2/test", json=valid_body(),
                             headers={"X-HomeBrain-V2-Test-Token": "not-the-token"})
        no_confirmation = valid_body()
        no_confirmation["explicit_opt_in"] = False
        unconfirmed = client.post("/api/v2/test", json=no_confirmation,
                                  headers={"X-HomeBrain-V2-Test-Token":
                                           "long-unit-test-secret-0123456789"})
    assert page.status_code == 200
    assert "formatTestError" in page.text
    assert "response.status" in page.text
    assert "[object Object]" not in page.text
    assert denied.status_code == 403
    assert unconfirmed.status_code == 403


def test_v2_validation_error_is_an_array_of_field_errors_not_string(
        monkeypatch, tmp_path):
    app = app_with_test_mode(monkeypatch, tmp_path)
    with TestClient(app.app) as client:
        malformed = client.post(
            "/api/v2/test", json={"question": "Why?",
                                  "device_ids": ["7805"], "explicit_opt_in": True},
            headers={"X-HomeBrain-V2-Test-Token":
                     "long-unit-test-secret-0123456789"},
        )
    assert malformed.status_code == 422
    detail = malformed.json()["detail"]
    assert isinstance(detail, list)
    assert any("question" in entry["loc"] for entry in detail)


def test_v2_valid_browser_request_reaches_safe_evaluator_and_emits_scorecard(
        monkeypatch, tmp_path):
    module = app_with_test_mode(monkeypatch, tmp_path)
    from investigation_v2.evidence import CaseFile
    from investigation_v2.read_loop import InvestigationResult
    from investigation_v2.evaluate import V2Evaluation
    from investigation_v2.synthesis import GroundedAnswer

    seen = []
    async def fake_devices(*, refresh=False):
        seen.append(("refresh", refresh))
        return [{"id": 7805, "label": "Livingroom Light 1"}]

    async def fake_evaluate(**kwargs):
        seen.append(("evaluate", kwargs))
        case = CaseFile(original_user_request=kwargs["question"])
        return V2Evaluation(
            investigation=InvestigationResult(
                case=case, hypotheses=[], rounds=1, executed_reads=0,
                stopped_because="model_finished",
            ),
            answer=GroundedAnswer(
                text="The evidence does not verify a root cause.",
                displayed_record_ids=(),
                omitted_material_record_ids=(),
                validation_issues=("incomplete_source_coverage",),
            ),
        )

    monkeypatch.setattr(module.mcp, "get_cached_devices", fake_devices)
    monkeypatch.setattr(module, "evaluate_v2_with_model", fake_evaluate)
    headers={"X-HomeBrain-V2-Test-Token": "long-unit-test-secret-0123456789"}
    with TestClient(module.app) as client:
        good = client.post("/api/v2/test", json=valid_body(), headers=headers)
        unknown = client.post("/api/v2/test", json={**valid_body(),
                              "device_ids": ["99999"]}, headers=headers)

    assert good.status_code == 200, good.text
    result = good.json()
    assert result["answer"]["text"].startswith("The evidence")
    assert result["test_mode"] == "explicit_read_only"
    assert result["production_answer_used"] is False
    assert result["scorecard"]["causal_accuracy_comparison_completed"] is False
    assert result["scorecard"]["v1_external"]["provided"] is False
    assert result["scorecard"]["reference_external"]["provided"] is False
    assert result["investigation"]["executed_reads"] == 0
    assert seen[0] == ("refresh", True)
    assert seen[1][0] == "evaluate"
    options = seen[1][1]
    assert options["verified_entity_ids"] == ("7805",)
    assert options["explicitly_authorised"] is True
    assert options["enable_atomic_claim_validation"] is True
    assert options["enable_evidence_narrative"] is True
    assert unknown.status_code == 422
    assert "Device ID not verified" in unknown.json()["detail"]
    assert len([row for row in seen if row[0] == "evaluate"]) == 1


def test_v2_frontend_uses_safe_diagnostic_format_and_does_not_echo_token():
    from investigation_v2.test_webui import render_v2_test_page
    page = render_v2_test_page()
    assert "function formatTestError(response,data)" in page
    assert "Array.isArray(detail)" in page
    assert "item.loc" in page
    assert "HTTP '+response.status" in page
    assert "formatTestError(response,data)" in page
    assert "if(!savedAccess&&token.length<16)" in page
    assert "if(token)headers['X-HomeBrain-V2-Test-Token']=token;" in page
    assert "credentials:'same-origin'" in page
    assert "const ids=el('ids').value.split(',')" in page
    assert "localStorage" not in page
    assert "sessionStorage" not in page
    assert "innerHTML" not in page
    assert "data.detail||" not in page
