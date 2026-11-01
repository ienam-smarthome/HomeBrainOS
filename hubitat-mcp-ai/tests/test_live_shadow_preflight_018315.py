"""Stage 8 opt-in live-read preflight. All Hubitat access is mocked in CI."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_preflight import build_live_shadow_preflight  # noqa: E402
from webui import render_page  # noqa: E402


def context(status="offline", *, complete=True, duplicated=False):
    devices = [{
        "id": "7103",
        "name": "Private Device Name - not included in output",
        "room": "A private room",
        "attributes": {
            "healthStatus": status, "mqttStatus": "connected", "switch": "off",
            "power": 8, "lastError": "access_token:private-secret",
            "lastMessage": "Private log contains address and contact",
            "mac": "00:00:00:00:00:00", "ip": "192.168.1.123",
        },
    }, {"id": "312", "attributes": {"switch": "on"}}]
    if duplicated:
        devices.append(dict(devices[0]))
    return {
        "devices": devices, "idsComplete": complete,
        "partial": False, "truncated": False, "totalDevices": len(devices),
    }


def project(data=None, device_id="7103"):
    return build_live_shadow_preflight(
        device_id, context() if data is None else data,
        observed_at_utc="2026-11-01T11:01:00+00:00",
    )


def test_single_device_readiness_and_transport_not_device_proof():
    item = project()
    assert item["schema"] == "homebrain-live-shadow-preflight.v1"
    assert item["ready_for_read_only_investigation"] is True
    assert item["ready_for_causal_attribution"] is False
    assert item["device_control_enabled"] is False
    assert item["cloud_requests"] == 0
    assert item["publisher_approval"] is False
    assert item["persistent_capture"] is False
    assert item["device_reported_states"] == {
        "healthStatus": "offline", "mqttStatus": "connected",
        "power": 8, "switch": "off"}
    assert item["timestamp_provenance"] == "collector_preflight_time_only"
    text = str(item)
    for forbidden in ("private-secret", "Private Device", "192.168.1.123",
                      "00:00:00:00", "A private room", "lastMessage"):
        assert forbidden not in text


@pytest.mark.parametrize("mutation", [
    lambda x: x.update({"idsComplete": False}),
    lambda x: x.update({"partial": True}),
    lambda x: x.update({"truncated": True}),
    lambda x: x.update({"totalDevices": 100}),
])
def test_partial_or_unknown_inventory_must_fail_closed(mutation):
    x = context()
    mutation(x)
    p = project(x)
    assert p["status"] in {"blocked_explicit_partial_context", "blocked_total_mismatch"}
    assert not p["ready_for_read_only_investigation"]
    assert p["device_reported_states"] == {}


@pytest.mark.parametrize("remove", ["idsComplete", "totalDevices"])
def test_missing_completeness_marker_gives_only_provisional_target_report(remove):
    c = context()
    c.pop(remove)
    p = project(c)
    assert p["status"] == "scoped_reports_unverified_inventory"
    assert p["live_context_complete"] is False
    assert p["ready_for_read_only_investigation"] is False
    assert p["ready_for_device_scoped_observation"] is True
    assert p["device_reported_states"]["healthStatus"] == "offline"
    assert p["context_diagnostics"]["identity_marker"] in ("complete", "missing_or_unrecognised")
    assert p["context_diagnostics"]["total_marker"] in ("matching", "missing_or_unrecognised")
    assert p["publisher_approval"] is False


def test_numeric_string_total_supported_only_when_identity_complete():
    c = context()
    c["totalDevices"] = "2"
    p = project(c)
    assert p["status"] == "ready_for_read_only_followup"
    assert p["live_context_complete"] is True
    assert p["context_diagnostics"]["total_marker"] == "matching"


def test_unknown_target_in_provisional_subset_is_not_global_absence():
    c = context()
    c.pop("idsComplete")
    p = project(c, device_id="9999")
    assert p["status"] == "target_not_seen_in_unverified_context"
    assert not p["ready_for_read_only_investigation"]
    assert p["device_reported_states"] == {}


def test_target_not_exposed_when_partial_or_count_conflicts():
    c = context()
    c["truncated"] = True
    p = project(c)
    assert p["status"] == "blocked_explicit_partial_context"
    assert p["device_reported_states"] == {}
    c = context()
    c["totalDevices"] = 9
    p = project(c)
    assert p["status"] == "blocked_total_mismatch"
    assert p["device_reported_states"] == {}


def test_ambiguous_missing_or_unusable_device_projection_blocked():
    assert project(context(duplicated=True))["status"] == "blocked_target_ambiguous"
    assert project(device_id="9999")["status"] == "target_not_found"
    c = context()
    c["devices"][0]["attributes"] = ["offline"]
    assert project(c)["status"] == "blocked_missing_state_projection"
    c["devices"][0]["attributes"] = {"lastError": "do not return me"}
    assert project(c)["status"] == "blocked_no_bounded_reported_states"


@pytest.mark.parametrize("bad", ["", "x", "-1", "7103x", "7"*13, "１２", "12 3"])
def test_invalid_device_identifiers_blocked(bad):
    with pytest.raises(ValueError, match="invalid target"):
        project(device_id=bad)


def test_untrusted_free_text_never_echoed_or_treated_as_state():
    x = context()
    x["devices"][0]["attributes"]["healthStatus"] = "<script>unsafe</script>"
    x["devices"][0]["attributes"]["mqttStatus"] = "connected\nsecret"
    p = project(x)
    assert "healthStatus" not in p["device_reported_states"]
    assert "mqttStatus" not in p["device_reported_states"]


def test_phone_controls_are_explicit_and_do_not_send_cloud_consent():
    html = render_page("HomeBrainOS", "0.18.315")
    for snippet in (
        "Live Shadow · Read-only preflight",
        'id="liveShadowDeviceId"',
        'id="liveShadowConsent"',
        'id="runLiveShadow" disabled',
        "api/live-shadow/preflight",
        "x-homebrain-live-readonly",
        "confirm_read_only:true",
        "liveShadowConsent').checked=false",
        "No Ollama Cloud requests",
    ):
        assert snippet in html


def test_endpoint_requires_consent_same_origin_and_returns_only_projection(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    read_count = 0

    async def fake_read(*, refresh=False):
        nonlocal read_count
        assert refresh is True
        read_count += 1
        return context()

    monkeypatch.setattr(module.mcp, "get_live_context", fake_read)
    monkeypatch.setattr(module.mcp, "endpoint_url", "http://example.invalid/mcp")
    async def fail_if_model_called(*args, **kwargs):
        raise AssertionError("Cloud model must never run in live preflight")
    monkeypatch.setattr(module.agent.transport, "_chat_post", fail_if_model_called)

    body = {"device_id": "7103", "confirm_read_only": True}
    with TestClient(module.app) as client:
        assert client.post("/api/live-shadow/preflight", json=body).status_code == 403
        headers = {"x-homebrain-live-readonly": "confirmed",
                   "Origin": "http://testserver"}
        assert client.post("/api/live-shadow/preflight", json={**body,
            "confirm_read_only": False}, headers=headers).status_code == 403
        assert client.post("/api/live-shadow/preflight", json=body,
            headers={**headers, "Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/live-shadow/preflight", json=body,
            headers={**headers, "sec-fetch-site": "cross-site"}).status_code == 403
        assert client.post("/api/live-shadow/preflight", json={**body,
            "device_id": "injected"}, headers=headers).status_code == 422
        assert read_count == 0
        good = client.post("/api/live-shadow/preflight", json=body, headers=headers)
        assert good.status_code == 200, good.text
        assert good.headers["cache-control"] == "no-store"
        assert good.json()["status"] == "ready_for_read_only_followup"
        assert good.json()["device_reported_states"]["healthStatus"] == "offline"
        assert read_count == 1


def test_production_agent_and_publisher_are_not_instrumented_by_preflight():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "live_shadow_preflight" not in (APP / name).read_text()
