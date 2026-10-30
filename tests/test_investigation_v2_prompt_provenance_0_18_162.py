"""Architectural regression for compact model input, stored settings and single-day UK clocks."""
from __future__ import annotations
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from investigation_v2.evidence import CaseFile, EvidenceItem
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.planning_evidence import planning_evidence
from investigation_v2.temporal_scope import explicit_incident_window

def event(i, action, stage="state_reported", value=None, producer="7103", minute=None, target="7103"):
    stamp = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=i * 2 if minute is None else minute)
    return EvidenceItem(record_id=f"e{i}", source_request_id="test", tool="hub_read_devices",
        operation="hub_list_device_events", source_category="device_events", target_id=target,
        producer_id=producer, producer_label=None, timestamp_utc=stamp.isoformat(),
        timestamp_original=stamp.isoformat(), stage=stage, action=action, value=value,
        raw_references=(f"test.details.events[{i}]",))

def test_medium_case_coalesces_telemetry_but_preserves_material_records():
    rows = [event(i, "voltage", value=str(240 + i % 3)) for i in range(18)]
    rows.extend([event(30, "command-off", "command_issued", producer="3950", minute=60),
                 event(31, "switch", value="off", minute=60.01),
                 event(32, "healthStatus", value="offline", minute=64),
                 event(33, "stored-setting:onOff.3", "config_stored", value="false",
                       producer=None, target="3950", minute=200)])
    case = CaseFile(original_user_request="Investigate", records=rows)
    before = [r.record_id for r in case.records]
    projected = json.loads(planning_evidence(case, None))
    ids = {row["id"] for row in projected["records"]}
    assert len(ids) < len(before)
    assert {"e30", "e31", "e32", "e33"}.issubset(ids)
    assert sum(x["rows"] for x in projected["coalesced_context"]) > 0
    assert [r.record_id for r in case.records] == before

def test_config_source_identified_by_scoped_controller_app_id():
    row = event(40, "stored-setting:onOffSwitch.3", "config_stored",
                "device IDs: 7103", producer=None, target="3950", minute=70)
    case = CaseFile(original_user_request="Investigate", records=[row])
    report = format_investigation_report(case, [], "planning_timeout")
    assert "Controller app #3950" in report
    assert "Source not identified" not in report
    assert "not verified historical configuration" in report
    case.app_identities["3950"] = "Known Controller"
    assert "Known Controller (app #3950)" in format_investigation_report(case, [], "planning_timeout")
