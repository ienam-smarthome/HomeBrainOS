from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_source_guard import guard_checked_source_absence_claim  # noqa: E402
from performance_semantic_grounding import ground_performance_semantics  # noqa: E402


def _performance_evidence() -> list[dict[str, object]]:
    return [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_metrics", "success": True},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_performance_stats", "success": True},
        {"tool": "hub_manage_logs", "sub_tool": "hub_get_logs", "success": True},
    ]


def test_pure_false_source_absence_still_gets_one_deterministic_correction() -> None:
    draft = (
        "The current-turn evidence does not provide the necessary data to analyze hub performance, "
        "review logs, or recommend improvements. No metrics, performance statistics, or log entries "
        "were returned in the provided results."
    )

    corrected, changed = guard_checked_source_absence_claim(draft, _performance_evidence())

    assert changed is True
    assert corrected.count("Current-turn evidence did include successful") == 1
    assert "hub metrics, performance statistics and logs" in corrected
    assert "No metrics" not in corrected


def test_substantive_performance_answer_drops_false_absence_sentence_instead_of_leaking_repair_text() -> None:
    draft = '''### Log Observations (Last 30 Minutes)
* **Halo3000x socket power:** Reporting `ActivePower` approximately every 10 seconds.
The current-turn evidence does not provide the necessary data to review logs.

### Analysis & Recommendations
* **Halo3000x:** The logs show this device reporting power every 10 seconds.
'''

    corrected, changed = guard_checked_source_absence_claim(draft, _performance_evidence())

    assert changed is True
    assert "Reporting `ActivePower` approximately every 10 seconds." in corrected
    assert "The logs show this device reporting power every 10 seconds." in corrected
    assert "Current-turn evidence did include successful" not in corrected
    assert "does not provide the necessary data" not in corrected


def test_legitimate_negative_log_causality_sentence_is_not_mistaken_for_source_absence() -> None:
    draft = (
        "The logs show Halo3000x power updates every 10 seconds. "
        "This does not establish that the logs themselves caused the measured hub load."
    )

    corrected, changed = guard_checked_source_absence_claim(draft, _performance_evidence())

    assert changed is False
    assert corrected == draft
    assert "Current-turn evidence did include successful" not in corrected


def test_conditional_responsiveness_claim_is_softened_to_investigative_wording() -> None:
    draft = (
        "If the TV is frequently offline or the network is unstable, this latency can impact overall "
        "hub responsiveness."
    )

    corrected = ground_performance_semantics(draft)

    assert "can impact overall hub responsiveness" not in corrected
    assert "possible contributor to responsiveness" in corrected
    assert "does not establish that it affects overall hub responsiveness" in corrected


def test_01660_live_halo_observation_shape_does_not_gain_serializer_repair_prose() -> None:
    draft = '''### Log Observations (Last 30 Minutes)
The logs show a high volume of routine telemetry and polling:
* **Halo3000x socket power:** Reporting `ActivePower` approximately every 10 seconds.

### Analysis & Recommendations
**3. Halo3000x Socket (Log Noise/Chatter)**
* **Observation:** The logs show this device reporting power every 10 seconds. This does not establish that recent logs prove a performance cause.
* **Hypothesis:** The device is configured to report on every small change or at a very tight fixed interval.
'''

    corrected, changed = guard_checked_source_absence_claim(draft, _performance_evidence())

    assert changed is False
    assert "Current-turn evidence did include successful" not in corrected
    assert "The logs show this device reporting power every 10 seconds." in corrected
