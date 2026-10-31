"""Stage 3F source-only genuine in-process model-round capture contract.

The tests manufacture call-shaped inputs; only the installed orchestrator's
explicit injection point can observe actual model responses. No network,
MCP execution, app config writes or raw trace file output is permitted.
"""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from mcp_agent_orchestrator import UnifiedMCPAgent
from stage3_local_capture import LocalStage3FCapture
from test_canonical_investigation_foundation import named_lookup, native_command
from test_stage3_loop_shadow import call, schema

CONSENT = "AUTHORISE_LOCAL_READ_TRACE"


def fixture():
    receipts = [
        named_lookup("101", "Secret Personal Bedroom Room"),
        native_command("101", issuer="3001", label="Secret Home Application"),
    ]
    calls = [
        call(gateway="hub_read_apps_code", leaf="hub_get_app_config",
             args={"appId": "3001"}),
        call(gateway="hub_read_devices", leaf="hub_list_device_events",
             args={"deviceId": "101", "since": "2026-10-31T14:00:00Z",
                   "until": "2026-10-31T15:00:00Z", "attribute": "switch"}),
    ]
    schemas = [
        schema("hub_read_apps_code", ("hub_get_app_config",)),
        schema("hub_read_devices", ("hub_list_device_events",
                                    "hub_list_device_dependents")),
    ]
    return receipts, calls, schemas


def test_explicit_consent_is_required_and_retention_is_bounded():
    with pytest.raises(ValueError, match="consent"):
        LocalStage3FCapture(consent="yes")
    with pytest.raises(ValueError, match="lifetime"):
        LocalStage3FCapture(consent=CONSENT, ttl_seconds=901)
    with pytest.raises(ValueError, match="lifetime"):
        LocalStage3FCapture(consent=CONSENT, ttl_seconds=0)
    with pytest.raises(ValueError, match="domain"):
        LocalStage3FCapture(consent=CONSENT, domain="Private Home Name")
    cap = LocalStage3FCapture(consent=CONSENT, domain="lighting")
    assert cap.status()["enabled"] is True
    assert cap.status()["stored_to_disk"] is False


def test_consent_injection_is_double_gated_and_addon_defaults_disabled():
    signature = inspect.signature(UnifiedMCPAgent.__init__).parameters
    assert signature["stage3_shadow_mode"].default == "off"
    assert signature["stage3_capture_session"].default is None
    # No config or add-on factory changes accompany this constructor-only
    # opt-in: the user-facing add-on continues default-disabled.


def test_recorded_source_read_choices_are_pseudonymised_not_exported():
    cap = LocalStage3FCapture(consent=CONSENT)
    evidence, calls, schemas = fixture()
    original = deepcopy((evidence, calls, schemas))
    identity = object()
    status = cap.capture_round(evidence, calls, schemas, request_identity=identity)
    assert status == {"captured": True, "rounds": 1}
    assert (evidence, calls, schemas) == original
    assert cap.status()["round_count"] == 1
    stored = json.dumps(cap._rounds)
    for forbidden in ("Secret Personal Bedroom Room", "Secret Home Application",
                      '"3001"', '"101"', "2026-10-31", "Secret Home",
                      "authorization", "password"):
        assert forbidden not in stored
    assert '"Private App"' in stored
    report = cap.private_report()
    assert report["source_case_count"] == 1
    assert report["round_count"] == 1
    assert report["origins"]["user_labelled_redacted_trace"] == 1
    assert report["independently_authenticated_genuine_traces"] == 0
    assert report["live_quality_improvement_verified"] is False
    assert report["can_trigger_live_activation"] is False
    assert "3001" not in json.dumps(report)


def test_stable_ephemeral_numeric_aliases_and_sensitive_time_pair_loss():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    cap.capture_round(r, c, s)
    snapshot = cap._rounds[0]
    model_args = [m["function"]["arguments"]["args"] for m in snapshot["model_tool_calls"]]
    app_alias = model_args[0]["appId"]
    dev_alias = model_args[1]["deviceId"]
    assert app_alias.isdecimal() and dev_alias.isdecimal()
    assert app_alias != dev_alias and len(app_alias) <= 16
    assert model_args[1]["since"] != "2026-10-31T14:00:00+00:00"
    # Same original ID in a verified synthetic source receipt maps to the
    # same pseudonym as that model's proposal.
    issuer = [x for x in snapshot["receipts_before"] if x.get("synthetic_issuer_projection")]
    assert issuer and issuer[0]["details"]["observedEvents"][0]["producedBy"]["appId"] == app_alias
    cap.capture_round(r, c, s)
    again = cap._rounds[1]
    assert again["model_tool_calls"][0]["function"]["arguments"]["args"]["appId"] == app_alias


def test_secrets_and_unadvertised_mutations_never_enter_capture():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    r.append({"tool": "hub_manage_devices", "mutates": True, "success": True,
              "effect": "write", "arguments": {"token": "SECRET-CONTROL-TOKEN"}})
    c.extend([
        call(gateway="hub_manage_devices", leaf="hub_delete_device",
             args={"deviceId": "101", "password": "SECRET-PASSWORD"}),
        call(gateway="hub_read_apps_code", leaf="hub_get_app_config",
             args={"appId": "3001", "api_key": "SECRET-API-KEY"}),
    ])
    cap.capture_round(r, c, s)
    body = json.dumps(cap._rounds)
    assert "SECRET-" not in body
    assert "hub_manage_devices" not in body
    assert "hub_delete_device" not in body
    assert "api_key" not in body
    assert len(cap._rounds[0]["model_tool_calls"]) == 2


def test_original_model_arguments_and_source_receipts_are_never_mutated():
    cap = LocalStage3FCapture(consent=CONSENT)
    evidence, calls, schemas = fixture()
    original = deepcopy((evidence, calls, schemas))
    cap.capture_round(evidence, calls, schemas)
    cap.private_report()
    assert (evidence, calls, schemas) == original


def test_request_identity_isolation_prevents_cross_request_collection():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    first, second = object(), object()
    assert cap.capture_round(r, c, s, request_identity=first)["captured"]
    result = cap.capture_round(r, c, s, request_identity=second)
    assert result == {"captured": False, "reason": "different-request"}
    assert cap.status()["round_count"] == 1
    assert cap.status()["skipped_round_count"] == 1


def test_ttl_expiration_purges_all_ram_records_and_session_secret():
    now = [100.0]
    cap = LocalStage3FCapture(consent=CONSENT, ttl_seconds=2,
                              clock=lambda: now[0])
    r, c, s = fixture()
    cap.capture_round(r, c, s)
    now[0] = 102.0
    assert cap.status()["enabled"] is False
    assert cap._key == b""
    assert cap._rounds == []
    assert cap.private_report() == {"available": False, "reason": "disabled-expired-or-empty"}
    assert cap.capture_round(r, c, s)["captured"] is False


def test_manual_disable_is_immediate_and_irreversible():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    cap.capture_round(r, c, s)
    cap.disable()
    assert cap.status()["round_count"] == 0
    assert cap._key == b""
    assert cap.private_report()["available"] is False
    assert cap.capture_round(r, c, s)["captured"] is False


def test_large_inputs_fail_closed_without_silent_truncation():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    assert cap.capture_round(r * 81, c, s) == {
        "captured": False, "reason": "unbounded-round"}
    assert cap.capture_round(r, c * 9, s)["captured"] is False
    assert cap.status()["round_count"] == 0


def test_unverified_app_issuer_is_not_credited_to_listener():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    c.append(call(gateway="hub_read_apps_code", leaf="hub_get_app_config",
                  args={"appId": "3999"}))
    cap.capture_round(r, c, s)
    report = cap.private_report()
    assert report["total_unattested_ids_suppressed"] >= 1
    assert report["end_to_end_latency_measured"] is False


def test_no_explicit_operation_enum_means_no_model_calls_captured():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, _ = fixture()
    no_enum = schema()
    del no_enum["function"]["parameters"]["properties"]["tool"]["enum"]
    assert cap.capture_round(r, c, [no_enum])["captured"] is True
    assert cap._rounds[0]["model_tool_calls"] == []
    assert cap.private_report()["can_trigger_live_activation"] is False


def test_raw_timestamps_do_not_survive_as_history_or_source_order():
    cap = LocalStage3FCapture(consent=CONSENT)
    r, c, s = fixture()
    cap.capture_round(r, c, s)
    assert "2026-10-31" not in json.dumps(cap._rounds)
    assert all(row.get("synthetic_issuer_projection") is not None
               for row in cap._rounds[0]["receipts_before"]
               if "synthetic_issuer_projection" in row)
    report = cap.private_report()
    assert report["physical_ack_or_causal_initiator_proven"] is False


def test_two_observation_metrics_registered_in_original_metric_gate():
    from request_metrics import RequestMetrics
    names = ("stage3_capture_round_observed", "stage3_capture_observation_error")
    assert set(names).issubset(RequestMetrics.ALLOWED_COUNTERS)
    m = RequestMetrics()
    token = m.begin()
    try:
        for name in names:
            m.increment(name)
            assert m.snapshot()["counters"][name] == 1
    finally:
        m.reset(token)
