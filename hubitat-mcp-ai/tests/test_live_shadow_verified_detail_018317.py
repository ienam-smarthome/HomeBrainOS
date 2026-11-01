"""Stage 8.2: verified detailed source read, scoped privacy projection, safe blocks."""
import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_preflight import build_verified_detail_shadow  # noqa: E402
from webui import render_page  # noqa: E402


def manifest():
    return [
        {"id": "7103", "label": "Do not return sensitive device name",
         "attributes": [
             {"name": "healthStatus", "currentValue": "offline"},
             {"name": "mqttStatus", "currentValue": "connected"},
             {"name": "switch", "currentValue": "off"},
             {"name": "power", "currentValue": 8},
             {"name": "lastError", "currentValue": "access_token=SECRET"},
             {"name": "lastMessage", "currentValue": "private log"},
             {"name": "ip", "currentValue": "192.168.1.50"},
         ]},
        {"id": "7900", "attributes": {"switch": "on",
                 "lastError": "OTHER_PRIVATE_SECRET"}},
    ]


def provenance():
    return {"source": "fresh_projected_gateway", "projection": "full",
            "complete": True, "devices": 2, "pages": 1}


def project(devices=None, info=None, id="7103"):
    return build_verified_detail_shadow(
        id, manifest() if devices is None else devices,
        provenance() if info is None else info,
        observed_at_utc="2026-11-01T12:02:00+00:00",
    )


def test_fresh_verified_manifest_exposes_only_one_target_and_reports_not_proof():
    data = project()
    assert data["status"] == "verified_identity_with_reported_states"
    assert data["verified_inventory_coverage"] is True
    assert data["reported_states"] == {
        "healthStatus": "offline", "mqttStatus": "connected",
        "power": 8, "switch": "off",
    }
    assert data["ready_for_historical_investigation"] is False
    assert data["historical_causation_verified"] is False
    assert data["device_origin_packet_verified"] is False
    assert data["publisher_approval"] is False
    assert data["device_commands"] == 0
    assert data["cloud_requests"] == 0
    result = str(data)
    for forbidden in ("sensitive device name", "192.168.1.50",
                      "SECRET", "OTHER_PRIVATE", "private log", "7900"):
        assert forbidden not in result


@pytest.mark.parametrize("override", [
    {"complete": False}, {"source": "full_detailed_fallback"},
    {"source": "cached"}, {"projection": "identity_only"},
    {"complete": None}, {},
])
def test_no_stale_or_unverified_inventory_promoted_to_evidence(override):
    p = provenance()
    p.update(override)
    if not override:
        p = {}
    item = project(info=p)
    assert item["status"] == "blocked_unverified_detailed_inventory"
    assert item["reported_states"] == {}
    assert not item["verified_inventory_coverage"]


def test_conflicting_duplicate_ids_and_count_mismatch_are_blocked():
    d = manifest()
    d.append(dict(d[0]))
    assert project(devices=d)["status"] == "blocked_ambiguous_detailed_inventory"
    assert project(info={**provenance(), "devices": 4})[
        "status"] == "blocked_detailed_count_conflict"
    assert project(devices=[{"id": None}])[
        "status"] == "blocked_ambiguous_detailed_inventory"


def test_typed_and_map_states_are_both_bounded_and_conflicts_omitted():
    d = manifest()
    d[0]["currentStates"] = {"switch": "on", "sensorStatus": "offline",
                             "lastError": "PRIVATE"}
    data = project(devices=d)
    assert "switch" not in data["reported_states"]
    assert data["reported_states"]["sensorStatus"] == "offline"
    assert "lastError" not in data["reported_states"]


def test_injected_driver_strings_are_never_echoed():
    d = manifest()
    d[0]["attributes"][0]["currentValue"] = "<script>alert(1)</script>"
    d[0]["attributes"][1]["currentValue"] = "connected\nprivate"
    data = project(devices=d)
    assert "healthStatus" not in data["reported_states"]
    assert "mqttStatus" not in data["reported_states"]
    assert "script" not in str(data)
    assert "private" not in str(data)


def test_unknown_target_and_missing_states_are_not_turned_into_offline():
    assert project(id="9999")["status"] == "target_not_in_verified_detailed_inventory"
    d = manifest()
    d[0]["attributes"] = [{"name": "lastError", "value": "secret"}]
    assert project(devices=d)["status"] == "verified_identity_no_allowlisted_state"


def test_ui_new_explicit_consent_button_and_no_cloud_model():
    html = render_page("HomeBrainOS", "0.18.317")
    for item in (
        "runLiveShadowDetail", "liveShadowDetailedReport",
        "api/live-shadow/verified-detail", "may require multiple Hubitat reads",
        "confirm_read_only:true", "liveShadowConsent').checked=false",
        "Detailed inventory coverage verified",
    ):
        assert item in html


def test_endpoint_opt_in_and_no_ai_or_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    calls = []

    async def fake_audit(*, identity_only=False):
        assert identity_only is False
        calls.append("verified_detailed_read_only")
        return manifest(), provenance()

    monkeypatch.setattr(module.mcp, "get_audit_devices", fake_audit)
    monkeypatch.setattr(module.mcp, "endpoint_url", "http://example.invalid/mcp")

    async def forbid_cloud(*args, **kwargs):
        raise AssertionError("Cloud must not run")
    monkeypatch.setattr(module.agent.transport, "_chat_post", forbid_cloud)

    body = {"device_id": "7103", "confirm_read_only": True}
    headers = {"x-homebrain-live-readonly": "confirmed",
               "Origin": "http://testserver"}
    with TestClient(module.app) as client:
        assert client.post("/api/live-shadow/verified-detail", json=body).status_code == 403
        assert client.post("/api/live-shadow/verified-detail", json=body,
            headers={**headers, "Origin": "https://attacker.example"}).status_code == 403
        assert client.post("/api/live-shadow/verified-detail", json=body,
            headers={**headers, "sec-fetch-site": "cross-site"}).status_code == 403
        assert client.post("/api/live-shadow/verified-detail",
            json={**body, "confirm_read_only": False},
            headers=headers).status_code == 403
        assert client.post("/api/live-shadow/verified-detail",
            json={**body, "device_id": "abc"},
            headers=headers).status_code == 422
        assert calls == []
        reply = client.post("/api/live-shadow/verified-detail", json=body,
                            headers=headers)
        assert reply.status_code == 200, reply.text
        assert reply.headers["cache-control"] == "no-store"
        assert reply.json()["reported_states"]["healthStatus"] == "offline"
        assert calls == ["verified_detailed_read_only"]


def test_publisher_and_normal_orchestration_untouched():
    for name in ("causal_claim_publication.py", "mcp_agent_orchestrator.py",
                 "tool_executor.py", "final_answer_coordinator.py"):
        content = (APP / name).read_text()
        assert "build_verified_detail_shadow" not in content
        assert "/api/live-shadow/verified-detail" not in content
