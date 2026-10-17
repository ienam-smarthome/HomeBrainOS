"""v0.18.21: inspect actual later-file Groovy methods, not first-2k tool previews."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from source_method_projection import source_method_packet, _requested_symbols


PROMPT = (
    "Independently investigate actual Groovy driver source. Trace "
    "`mqttStatus`, `lastSeen`, `dataAgeSeconds`, `deviceHealth`, "
    "watchdog reconnection and command acknowledgements, and correlate "
    "source implementation with logs and events. Read-only."
)
ARGS = {"tool": "hub_get_source",
        "args": {"id": "3686", "type": "driver"}}


def driver_source():
    header = 'metadata { definition(name: "Tasmota MQTT") {} }\n'
    # Keep the relevant method definitions outside the compact tool
    # evidence packet's first 2,200 characters.
    padding = ("// harmless introductory configuration boilerplate\n" * 90)
    code = (
        'def initialize() { runIn(300, "deviceHealthCheck") }\n'
        'def connect() { sendEvent(name: "mqttStatus", value: "connected") }\n'
        'def deviceHealthCheck() {\n'
        '  log.warn("Watchdog fired after 309s without data")\n'
        '  connect()\n'
        '}\n'
        'def parse(String response) {\n'
        '  sendEvent(name: "lastSeen", value: now())\n'
        '  sendEvent(name: "dataAgeSeconds", value: 0)\n'
        '  sendEvent(name: "deviceHealth", value: "online")\n'
        '}\n'
        'def verifyPower() {\n'
        '  log.warn("Power ON not confirmed after 3 retries")\n'
        '}\n'
    )
    return header + padding + code


def full_data(source=None):
    raw = source or driver_source()
    return {"success": True, "driverId": "3686", "offset": 0,
            "totalLength": len(raw), "hasMore": False, "source": raw}


def test_extracts_late_method_bodies_from_complete_one_piece_driver():
    source = driver_source()
    assert source.index("def parse(") > 2200
    packet = source_method_packet(full_data(), ARGS, PROMPT)
    assert packet is not None
    assert "HOST SOURCE-DERIVED METHOD EVIDENCE" in packet
    assert "def deviceHealthCheck()" in packet
    assert 'sendEvent(name: "mqttStatus"' in packet
    assert 'sendEvent(name: "lastSeen"' in packet
    assert 'sendEvent(name: "dataAgeSeconds"' in packet
    assert "full candidate method body shown" in packet
    assert "line numbers" in packet
    assert "runtime proof" in packet
    assert len(packet) <= 14000


def test_lexical_selection_is_generic_not_named_device_canned_answer():
    source = (
        "def inspectCustomSensor() {\n"
        '  sendEvent(name: "packetSequence", value: 17)\n'
        "}\n"
    )
    symbols = _requested_symbols("Trace `packetSequence` in Groovy", source)
    assert "packetSequence" in symbols
    packet = source_method_packet(full_data(source), ARGS, "Trace Groovy `packetSequence`")
    assert packet is not None
    assert "def inspectCustomSensor()" in packet


def test_never_extracts_from_incomplete_or_inconsistent_source():
    base = full_data()
    for changes in (
        {"success": False},
        {"totalLength": base["totalLength"] + 1},
        {"offset": 1000},
        {"driverId": "7777"},
        {"source": ""},
        {"totalLength": -1},
    ):
        assert source_method_packet({**base, **changes}, ARGS, PROMPT) is None
    assert source_method_packet(base, {"tool":"hub_get_source",
        "args":{"id":"3686","type":"app"}}, PROMPT) is None
    assert source_method_packet(base, {"tool":"hub_get_source",
        "args":{"id":"3687","type":"driver"}}, PROMPT) is None


def test_nested_tool_output_and_utf16_surrogates_behave_conservatively():
    data = full_data(driver_source() + "// 🎶 test\n")
    import json
    nested = {"result": data}
    packet = source_method_packet(nested, ARGS, PROMPT)
    assert packet is not None
    # Hubitat reports Java UTF-16 code units, not Python code points.
    data["totalLength"] = len(data["source"]) + 1
    assert source_method_packet(nested, ARGS, PROMPT) is not None
    data["totalLength"] += 10
    assert source_method_packet(nested, ARGS, PROMPT) is None


def test_redacts_secrets_in_source_bound_for_model():
    source = driver_source() + "def setMqttSettings() {\n mqttPassword = 'redactme'\n}\n"
    packet = source_method_packet(
        full_data(source), ARGS,
        PROMPT + " Trace `mqttPassword`.",
    )
    assert packet is not None
    assert "redactme" not in packet
    assert "[REDACTED]" in packet


def test_does_not_invent_method_body_or_transport_verification():
    packet = source_method_packet(full_data(), ARGS, PROMPT)
    assert packet is not None
    assert "no extra device operations were performed" in packet
    assert "not a full call graph" in packet
    assert "runtime proof" in packet
    assert "physical Tasmota endpoint offline" not in packet
