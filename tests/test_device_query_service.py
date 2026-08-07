import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from device_target_resolver import resolve_device_candidate  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


class QueryMCP:
    def __init__(self, devices):
        self.devices = devices

    async def call_tool(self, name, arguments):
        return MCPToolResult(
            name, arguments, {}, "ok", {"devices": self.devices}
        )

    async def get_cached_devices(self):
        return self.devices


def device(label, room, capabilities, **attributes):
    return {
        "id": label,
        "label": label,
        "room": room,
        "capabilities": capabilities,
        "attributes": attributes,
    }


@pytest.mark.asyncio
async def test_query_devices_finds_hottest_room():
    service = DeviceQueryService(
        QueryMCP([
            device("Bedroom Meter", "Bedroom", ["TemperatureMeasurement"], temperature=27.5),
            device("Hallway Meter", "Hallway", ["TemperatureMeasurement"], temperature=30),
            device("Fridge Meter", "Appliances", ["TemperatureMeasurement"], temperature=-1),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.query_devices({
        "attribute": "temperature",
        "operation": "maximum",
        "group_by": "room",
    })

    assert result.data["winner"]["room"] == "Hallway"
    assert result.data["winner"]["value"] == 30
    assert result.data["winner"]["unit"] == "°C"


@pytest.mark.asyncio
async def test_query_devices_finds_highest_humidity():
    service = DeviceQueryService(
        QueryMCP([
            device("Living Meter", "Living Room", ["RelativeHumidityMeasurement"], humidity=48),
            device("Bathroom Meter", "Bathroom", ["RelativeHumidityMeasurement"], humidity="71%"),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.query_devices({
        "attribute": "humidity",
        "operation": "maximum",
        "group_by": "room",
    })

    assert result.data["winner"]["room"] == "Bathroom"
    assert result.data["winner"]["value"] == 71


@pytest.mark.asyncio
async def test_targeted_resolver_handles_spaces_hyphens_and_label_prefixes():
    class TargetedMCP:
        def __init__(self):
            self.calls = []
            self.devices = [{
                "id": "6916",
                "label": "Block Tab-S9-FE",
                "capabilities": ["Switch"],
                "commands": ["blockInternet", "allowInternet", "addTime"],
            }]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            assert arguments == {"tool": "hub_list_devices", "args": {}}
            return MCPToolResult(
                name, arguments, {}, "ok", {"devices": self.devices}
            )

        async def get_cached_devices(self):
            return self.devices

    mcp = TargetedMCP()
    receipts = []
    service = DeviceQueryService(
        mcp, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.resolve_device({"name": "tab s9"})

    assert result.data["matched"] is True
    assert result.data["deviceId"] == "6916"
    assert result.data["label"] == "Block Tab-S9-FE"
    assert result.data["target"]["commands"] == [
        "blockInternet", "allowInternet", "addTime"
    ]
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert len(receipts) == 1
    assert receipts[0][1]["evidence_kind"] == "authoritative_state_snapshot"


@pytest.mark.asyncio
async def test_room_climate_query_excludes_hub_and_appliance_telemetry():
    service = DeviceQueryService(
        QueryMCP([
            device("Hub Info (C8 Pro)", "Bridge", ["TemperatureMeasurement"], temperature=50.2),
            device(
                "Fridge Meter",
                "Appliances",
                ["TemperatureMeasurement", "RelativeHumidityMeasurement"],
                temperature=2.0,
                humidity=87,
            ),
            device(
                "Bedroom Meter",
                "Bedroom 1",
                ["TemperatureMeasurement", "RelativeHumidityMeasurement"],
                temperature=28.9,
                humidity=43,
            ),
        ]),
        lambda *args, **kwargs: None,
    )

    temperature = await service.query_devices({
        "attribute": "temperature",
        "operation": "maximum",
        "group_by": "room",
    })
    humidity = await service.query_devices({
        "attribute": "humidity",
        "operation": "maximum",
        "group_by": "room",
    })

    assert temperature.data["winner"]["label"] == "Bedroom Meter"
    assert humidity.data["winner"]["label"] == "Bedroom Meter"


@pytest.mark.asyncio
async def test_weather_snapshot_selects_weather_device_and_all_attributes():
    service = DeviceQueryService(
        QueryMCP([
            device(
                "Livingroom Meter",
                "Living Room",
                ["TemperatureMeasurement"],
                temperature=28.8,
            ),
            device(
                "Weather Open-Meteo",
                "Climate",
                ["TemperatureMeasurement", "RelativeHumidityMeasurement"],
                temperature=24.9,
                humidity=50,
                weather="partly cloudy",
            ),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.weather_snapshot({})

    assert result.data["count"] == 1
    assert result.data["primary"]["label"] == "Weather Open-Meteo"
    assert result.data["primary"]["attributes"] == {
        "temperature": 24.9,
        "humidity": 50,
        "weather": "partly cloudy",
    }


@pytest.mark.asyncio
async def test_query_devices_ranks_only_sockets_by_power():
    service = DeviceQueryService(
        QueryMCP([
            device("TV socket", "Sockets", ["Switch", "PowerMeter"], power=82),
            device("Desk plug", "Office", ["Outlet", "PowerMeter"], power=40),
            device("Whole Home Meter", "Energy", ["PowerMeter"], power=900),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.query_devices({
        "attribute": "power",
        "operation": "maximum",
        "device_kind": "socket",
    })

    assert result.data["winner"]["label"] == "TV socket"
    assert result.data["count"] == 2


def test_target_resolution_accepts_spaced_room_name_and_omitted_kind():
    result = resolve_device_candidate(
        "living room two",
        [
            {"id": "1", "label": "Livingroom Light 1"},
            {"id": "2", "label": "Livingroom Light 2"},
            {"id": "3", "label": "Bedroom 2 Light"},
        ],
    )

    assert result.target["id"] == "2"
    assert result.reason == "exact semantic name with device-kind token omitted"


def test_target_resolution_uses_room_metadata_for_spoken_device_name():
    result = resolve_device_candidate(
        "bedroom three big lamp",
        [
            {"id": "1", "label": "Bedroom 3 Light", "roomName": "Bedroom 3"},
            {"id": "2", "label": "Big lamp", "roomName": "Bedroom 3"},
            {"id": "3", "label": "My Floor Lamp", "roomName": "Bedroom 1"},
        ],
    )

    assert result.target["id"] == "2"
    assert result.matched_name == "Big lamp"
    assert result.reason == "exact semantic room and device name"


@pytest.mark.asyncio
async def test_home_snapshot_tracked_presence_includes_away_people_too():
    """Regression test for a real live failure: "is Tahmid home" answered
    "I don't see anyone named Tahmid" even though he's a real, live Life360
    member -- just not currently present. The `presence` field only ever
    lists people who ARE home, so a specific-person question about someone
    away had zero evidence to work with. `tracked_presence` must list every
    presence-capable device regardless of status, so an away person is
    still identifiable with home=False rather than looking non-existent.
    """

    service = DeviceQueryService(
        QueryMCP([
            device(
                "Enamul Khan", "Life360", ["PresenceSensor", "Battery"],
                presence="present",
            ),
            device(
                "Tahmid Khan", "Life360", ["PresenceSensor", "Battery"],
                presence="not present",
            ),
        ]),
        lambda *_a, **_k: None,
    )

    result = await service.home_snapshot({})

    present_labels = {item["label"] for item in result.data["presence"]}
    assert present_labels == {"Enamul Khan"}

    tracked = {item["label"]: item for item in result.data["tracked_presence"]}
    assert tracked["Enamul Khan"]["home"] is True
    assert tracked["Tahmid Khan"]["home"] is False
    assert tracked["Tahmid Khan"]["presence"] == "not present"


def test_attribute_value_generic_fallback_is_opt_in_only():
    """Regression test for a real live failure: "show current power" on
    "Octopus Meter Current Power" answered "does not report a current
    power value" even though the reading ("231 W") is right there under
    valueStr -- this device has no attribute literally named power/
    activePower/powerMeter, only value/valueStr. The fallback must be
    opt-in (never applied to the cross-device ranking path in
    query_devices, which could wrongly sweep in an unrelated device's own
    differently-meaning generic value attribute).
    """

    octopus_meter = device(
        "Octopus Meter Current Power", "Octopus Energy", ["Refresh", "HealthCheck"],
        value=231.0, valueStr="231 W", unit="none",
    )

    without_fallback = DeviceQueryService._attribute_value(octopus_meter, "power")
    assert without_fallback == (None, None)

    with_fallback = DeviceQueryService._attribute_value(
        octopus_meter, "power", allow_generic_value_fallback=True
    )
    assert with_fallback == ("valueStr", "231 W")


def test_attribute_value_named_alias_still_wins_over_generic_fallback():
    plug = device(
        "Freezer (MQTT)", "Appliances", ["Switch"], power=74, valueStr="ignored",
    )

    result = DeviceQueryService._attribute_value(
        plug, "power", allow_generic_value_fallback=True
    )
    assert result == ("power", 74)


class _TargetedMCP:
    """Minimal MCP fake returning a fixed device list, mirroring the
    TargetedMCP used inline in the earlier resolve_device test above."""

    def __init__(self, devices):
        self.devices = devices

    async def call_tool(self, name, arguments):
        return MCPToolResult(name, arguments, {}, "ok", {"devices": self.devices})

    async def get_cached_devices(self):
        return self.devices


@pytest.mark.asyncio
async def test_resolve_device_light_query_excludes_non_light_same_room():
    """Regression test for a live-observed bug: "hallway light" scored a
    thermostat valve (no switch/light capability, just a shared room name)
    as an equally valid disambiguation candidate alongside the two real
    hallway lights, because resolve_device_candidate has no capability
    awareness and was fed the complete, unfiltered inventory."""

    devices = [
        device("Hallway Light 1", "Hallway", ["Switch", "SwitchLevel"], switch="on"),
        device("Hallway Light 2", "Hallway", ["Switch", "SwitchLevel"], switch="off"),
        device("Hallway TRV", "Hallway", ["ThermostatHeatingSetpoint"], temperature=27.2),
    ]
    service = DeviceQueryService(_TargetedMCP(devices), lambda *args, **kwargs: None)

    result = await service.resolve_device({"name": "hallway light"})

    assert result.data["matched"] is False
    assert "Hallway TRV" not in result.data["alternatives"]
    assert set(result.data["alternatives"]) <= {"Hallway Light 1", "Hallway Light 2"}


@pytest.mark.asyncio
async def test_resolve_device_bare_attribute_with_multiple_reporters_is_unresolved():
    """Regression test for a live-observed bug: a bare "temperature" query
    silently resolved to one specific sensor by name-string similarity
    alone, even though several other devices in the same house
    independently report a temperature reading with a materially
    different value at the same moment. That is a confident-wrong-answer
    risk and should be surfaced as a disambiguation, not a silent pick."""

    devices = [
        device(
            "Livingroom temp & humidity", "Living Room",
            ["TemperatureMeasurement"], temperature=27.8,
        ),
        device(
            "Bedroom 1 Meter", "Bedroom 1",
            ["TemperatureMeasurement"], temperature=27.1,
        ),
        device(
            "Fridge Meter", "Appliances",
            ["TemperatureMeasurement"], temperature=6.2,
        ),
    ]
    service = DeviceQueryService(_TargetedMCP(devices), lambda *args, **kwargs: None)

    result = await service.resolve_device({"name": "temperature"})

    assert result.data["matched"] is False
    assert result.data["deviceId"] is None
    assert len(result.data["alternatives"]) >= 2


@pytest.mark.asyncio
async def test_resolve_device_exact_label_match_bypasses_bare_attribute_guard():
    """A device whose real label literally *is* the attribute word (e.g.
    a driver labelled "Temperature") must still resolve deterministically
    -- the new bare-attribute disambiguation only applies to non-exact,
    ranked-similarity matches, never to an exact normalized-name hit."""

    devices = [
        device("Temperature", "Climate", ["TemperatureMeasurement"], temperature=21.0),
        device("Hallway Meter", "Hallway", ["TemperatureMeasurement"], temperature=27.2),
    ]
    service = DeviceQueryService(_TargetedMCP(devices), lambda *args, **kwargs: None)

    result = await service.resolve_device({"name": "temperature"})

    assert result.data["matched"] is True
    assert result.data["label"] == "Temperature"
