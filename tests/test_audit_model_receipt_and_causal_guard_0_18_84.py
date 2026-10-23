"""Regression replay for the 0.18.83 optional AI audit and provider receipt.

No real Hubitat devices, Ollama calls or paid providers used.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit_ai_advisory_guard import calibrate_audit_ai_advisory
from request_metrics import RequestMetrics, active_request_identity, record_active_provider_model


REPORT = """
### Offline-device evidence (identity-grounded)
- Bedroom 3 Mesh (ID 7103): state=offline, source=healthStatus.
### Automation configuration and dependency investigation
- App actions and execution unverified.
- Action direction and execution unverified.
### Scheduled jobs
- 0 rows have explicit, source-recognised owner fields.
- Scheduler-key attribution unverified.
### Performance leaders (not automatic faults)
- 20 top-ranked rows returned. Performance data is a top-ranked sample.
"""
LIVE_AI_REPLY = """### Executive Audit Summary

#### 1. Confirmed Device Outages (Errors)
* **Observed Evidence:** Bedroom 3 Mesh (7103) and Tuya Remote (3483) are reported offline via healthStatus.
* **Practical Impact:** Any automations relying on these devices as triggers or targets will fail to execute.

#### 2. Scheduler and App State Mismatch (Performance Risk)
* **Observed Evidence:** Scheduler keys are present for OwnTracks (app 3892) and Livingroom Nest Mini (app 3951), although disabled.
* **Practical Impact:** The hub may be wasting resources executing "ghost" scheduled jobs for automations that are inactive.

#### 3. High Resource Consumption Outliers (Performance Risk)
* **Observed Evidence:** Tasmota Discovery Listener shows pctBusy=24.3%.
* **Practical Impact:** High pctBusy values increase the risk of hub sluggishness or the triggering of LimitExceededException during peak activity.
"""


def test_live_output_no_longer_claims_unverified_failures_or_ghost_jobs():
    message, reasons = calibrate_audit_ai_advisory(LIVE_AI_REPLY, REPORT)
    assert set(reasons) == {
        "offline_effect_unverified", "scheduler_ownership_unverified",
        "pctbusy_risk_unverified",
    }
    assert "Confirmed Device Outages" not in message
    assert "will fail to execute" not in message
    assert "executing \"ghost\" scheduled jobs" not in message
    assert "increase the risk of hub sluggishness" not in message
    assert "no wasted work was verified" in message
    assert "did not establish its" in message
    assert "does not establish hub-wide CPU contention" in message
    assert "state=offline" in message
    assert "24.3%" in message


def test_no_mutation_of_report_without_source_caveats():
    fixed, flags = calibrate_audit_ai_advisory(LIVE_AI_REPLY, "No source evidence was obtained.")
    assert fixed == LIVE_AI_REPLY
    assert flags == ()


def test_verified_request_local_model_record_without_agent_observation():
    async def model_response():
        assert active_request_identity() is not None
        record_active_provider_model("gemma4:31b", "ollama-cloud")
        return {"content": "Read-only answer"}

    async def run():
        metrics = RequestMetrics()
        assert active_request_identity() is None
        token = metrics.begin()
        try:
            reply = await asyncio.wait_for(model_response(), timeout=1)
            assert reply["content"] == "Read-only answer"
            receipt = active_request_identity().model_round_details
            assert receipt == [{"model": "gemma4:31b", "provider": "ollama-cloud"}]
        finally:
            metrics.reset(token)
        assert active_request_identity() is None
    asyncio.run(run())


def test_failed_optional_model_round_does_not_invent_participant():
    async def never_finishes():
        raise RuntimeError("fake provider failed")

    async def run():
        metrics = RequestMetrics()
        token = metrics.begin()
        try:
            try:
                await asyncio.wait_for(never_finishes(), timeout=1)
            except RuntimeError:
                pass
            assert active_request_identity().model_round_details == []
        finally:
            metrics.reset(token)
        assert active_request_identity() is None
    asyncio.run(run())
