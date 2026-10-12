"""Verify that structured OFF analysis actually appears in final answers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))
from off_hypothesis_synthesis_guard import guard_off_hypothesis_summary


def graph():
    return {"offHypotheses": {
        "status": "producer-unresolved",
        "sensorTimerComparisons": [
            {"sensor": "Example FP300", "elapsedBeforeOffMs": 69.0,
             "configuredDelayMs": 5000.0, "assessment": "too-soon-for-new-timer"},
            {"sensor": "Example Soft Sensor", "elapsedBeforeOffMs": -949.0,
             "configuredDelayMs": 5000.0, "assessment": "edge-after-off"},
        ],
    }}


def test_timer_feasibility_is_rendered_when_synthesis_skips_it():
    result, changed = guard_off_hypothesis_summary(
        "The OFF cause remains unresolved. No matching command was recorded.", graph()
    )
    assert changed
    assert "69 ms before OFF" in result
    assert "5 seconds" in result
    assert "could not have expired" in result
    assert "earlier pending timer" in result


def test_do_not_duplicate_existing_timing_analysis():
    draft = "The FP300 edge is too soon for a newly started timer."
    assert guard_off_hypothesis_summary(draft, graph()) == (draft, False)


def test_no_hypothesis_no_rewrite():
    draft = "The light switched off."
    assert guard_off_hypothesis_summary(draft, {}) == (draft, False)


def test_unsupported_absence_inference_is_bounded():
    draft = ("This indicates the command did not originate from a "
             "Hubitat-managed device or app that logs standard commands.")
    result, changed = guard_off_hypothesis_summary(draft, graph())
    assert changed
    assert "cannot exclude unrecorded" in result
    assert "did not originate" not in result


def test_repeated_uncertainty_line_is_removed():
    phrase = ("The OFF transition occurred near sensor inactivity, but the "
              "sensor/timer trigger is unverified and the OFF command producer is unidentified.")
    draft = "* " + phrase + "\n* Other fact.\n* " + phrase + "\n"
    result, changed = guard_off_hypothesis_summary(draft, graph())
    assert changed
    assert result.count(phrase) == 1
