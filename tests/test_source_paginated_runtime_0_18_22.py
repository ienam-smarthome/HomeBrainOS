"""v0.18.22: complete paginated Groovy source != verified device runtime."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from source_method_projection import SourceChunkCollector
from source_analysis_completion import source_runtime_evidence_status
from shared_investigation_completion import apply_shared_investigation_completion

QUESTION = (
    "Trace the full Groovy source implementation of Bedroom 3 Mesh "
    "(device 7103, driver code 3686). Show connect(), deviceHealthCheck(), "
    "mqttStatus, lastSeen, dataAgeSeconds and power verification. "
    "Distinguish confirmed code from runtime observations and identify "
    "the strongest supported explanation for the offline state. Read-only."
)


def sample_source():
    # The actual requested method lives beyond the first 4,000 chars.
    return (
        '// Driver source\n'
        + ('// configuration, preferences and harmless comments\n' * 420)
        + 'def initialize() { runIn(300, "deviceHealthCheck") }\n'
        + 'def connect() {\n'
        + '  interfaces.mqtt.connect("tcp://broker", "hubitat_device")\n'
        + '  sendEvent(name: "mqttStatus", value: "connected")\n'
        + '}\n'
        + 'def deviceHealthCheck() {\n'
        + '  checkDataHealth()\n'
        + '  sendEvent(name: "healthStatus", value: "offline")\n'
        + '}\n'
        + 'def markSeen() {\n'
        + '  sendEvent(name: "lastSeen", value: now())\n'
        + '  sendEvent(name: "dataAgeSeconds", value: 0)\n'
        + '}\n'
        + 'def verifyPower() { log.warn("Power ON not confirmed") }\n'
    )


def page(text, offset, width=4000, ident="3686"):
    excerpt = text[offset:offset + width]
    return {
        "success": True, "driverId": ident, "offset": offset,
        "totalLength": len(text), "source": excerpt,
        "nextOffset": offset + len(excerpt),
    }


def args(ident="3686"):
    return {"tool": "hub_get_source",
            "args": {"id": ident, "type": "driver"}}


def run_pages(text, offsets):
    collector = SourceChunkCollector(QUESTION)
    results = [collector.observe(page(text, offset), args()) for offset in offsets]
    return collector, results


def test_six_page_source_yields_one_complete_method_evidence_packet():
    text = sample_source()
    assert len(text) > 4000
    offsets = list(range(0, len(text), 4000))
    assert len(offsets) >= 6
    collector, results = run_pages(text, offsets)
    assert all(x is None for x in results[:-1])
    packet = results[-1]
    assert packet is not None
    assert "def connect()" in packet
    assert "def deviceHealthCheck()" in packet
    assert "def markSeen()" in packet
    assert "def verifyPower()" in packet
    assert "line numbers" in packet
    assert "runtime proof" in packet
    assert collector.observe(page(text, 0), args()) is None


def test_reordered_but_complete_pages_reconstruct_verbatim():
    text = sample_source()
    offsets = list(range(0, len(text), 4000))
    collector, results = run_pages(text, offsets[::-1])
    assert sum(bool(x) for x in results) == 1
    assert "def markSeen()" in next(x for x in results if x)


def test_gap_wrong_driver_conflicting_total_or_overlap_never_certifies():
    text = sample_source()
    for mutation in ("gap", "id", "total", "overlap", "bad_unicode"):
        collector = SourceChunkCollector(QUESTION)
        first = page(text, 0)
        assert collector.observe(first, args()) is None
        second = page(text, 4000)
        if mutation == "gap":
            second = page(text, 4050)
        elif mutation == "id":
            second["driverId"] = "9977"
        elif mutation == "total":
            second["totalLength"] += 4
        elif mutation == "overlap":
            second = page(text, 3999)
        elif mutation == "bad_unicode":
            second["source"] += "\ufffd"
        assert collector.observe(second, args()) is None
        # Missing, invalid or overlapping prefix must not yield proof.
        assert collector.observe(page(text, len(text) - 11), args()) is None


def test_same_page_can_reappear_without_double_counting():
    text = sample_source()
    collector = SourceChunkCollector(QUESTION)
    first = page(text, 0)
    assert collector.observe(first, args()) is None
    assert collector.observe(first, args()) is None
    packet = None
    for offset in range(4000, len(text), 4000):
        packet = collector.observe(page(text, offset), args())
    assert packet is not None


def receipt(operation, *, mode=None, target="7103", source=False):
    args_ = {"deviceId": target}
    if mode:
        args_["mode"] = mode
    if source:
        args_ = {"id": "3686", "type": "driver"}
    return {
        "tool": "hub_read_apps_code" if source else "hub_read_devices",
        "sub_tool": operation,
        "success": True, "mutates": False, "effect": "read",
        "arguments": {"tool":operation,"args":args_},
        "details": ({"sourceRetrieved":True, "sourceCodeId":"3686",
                     "offset":0, "chunkLength":20531,
                     "totalLength":20531} if source else {}),
    }


def completed_source():
    return receipt("hub_get_source", source=True)


def outcome(receipts):
    return SimpleNamespace(
        message="Confirmed source method behaviour; physical state not verified.",
        route="unified-mcp-agent", request_class="live-read",
        evidence=receipts,
        metrics={"outcome":"success", "counters":{}},
        investigation_coverage=None,
    )


def test_source_only_runtime_request_is_unresolved():
    resolved = apply_shared_investigation_completion(
        outcome([completed_source()]), QUESTION,
    )
    meta = resolved.investigation_coverage
    assert meta["fullImplementationVerified"] is True
    assert meta["runtimeEvidence"]["required"] is True
    assert meta["runtimeEvidence"]["satisfied"] is False
    assert set(meta["runtimeEvidence"]["missing"]) == {
        "device_state", "device_history", "device_logs",
    }
    assert meta["objectiveSatisfied"] is False
    assert meta["questionResolved"] is False
    assert resolved.metrics["outcome"] == "unresolved"
    assert "Runtime correlation incomplete" in resolved.message


def test_same_device_scoped_evidence_is_required_for_runtime_completion():
    rows = [completed_source(),
            receipt("hub_get_device", mode="summary"),
            receipt("hub_list_device_events"),
            receipt("hub_get_logs")]
    complete = source_runtime_evidence_status(QUESTION, rows)
    assert complete["required"] and complete["satisfied"]
    result = apply_shared_investigation_completion(outcome(rows), QUESTION)
    assert result.investigation_coverage["objectiveSatisfied"] is True
    # Source from one device, event from another must not count.
    rows[2] = receipt("hub_list_device_events", target="9172")
    partial = source_runtime_evidence_status(QUESTION, rows)
    assert not partial["satisfied"]
    assert "device_history" in partial["missing"]


def test_code_only_question_does_not_require_scoped_device_logs():
    prompt = "Trace full Groovy source for implementation of mqttStatus and lastSeen."
    answer = apply_shared_investigation_completion(
        outcome([completed_source()]), prompt,
    )
    assert answer.investigation_coverage["objectiveSatisfied"] is True
    assert answer.investigation_coverage["runtimeEvidence"]["required"] is False
