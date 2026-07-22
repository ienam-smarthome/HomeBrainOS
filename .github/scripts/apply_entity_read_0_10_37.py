from pathlib import Path
import re

APP = Path('hubitat-mcp-ai/rootfs/app')


def rewrite(path: Path, transform):
    before = path.read_text(encoding='utf-8')
    after = transform(before)
    if after == before:
        raise RuntimeError(f'No change applied to {path}')
    path.write_text(after, encoding='utf-8')


orchestrator = APP / 'mcp_agent_orchestrator.py'
text = orchestrator.read_text(encoding='utf-8')

helper_marker = '_LOOKUP_PREFIX_RE = re.compile('
helpers = r'''_DEVICE_ATTRIBUTE_REQUESTS = (
    (re.compile(r"\b(?:lux|illuminance)\b", re.IGNORECASE), "illuminance", "lux"),
)


def _requested_device_attribute(query: str) -> tuple[str, str] | None:
    q = _normalise(query)
    if not any(term in q for term in ("reading", "value", "current", "what is", "what's", "how bright")):
        return None
    for pattern, attribute, unit in _DEVICE_ATTRIBUTE_REQUESTS:
        if pattern.search(q):
            return attribute, unit
    return None


def _attribute_target_phrase(query: str) -> str:
    q = str(query or "").strip().strip(" .!?")
    match = re.search(r"\b(?:from|of)\s+(.+)$", q, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return parse_entity_request(query).target_phrase


def _tool_data(result: Any) -> Any:
    return getattr(result, "data", result)


def _extract_attribute_value(value: Any, attribute: str) -> Any:
    if isinstance(value, dict):
        states = value.get("currentStates") or value.get("current_states") or value.get("attributes")
        if isinstance(states, dict) and states.get(attribute) not in (None, ""):
            return states.get(attribute)
        if value.get(attribute) not in (None, ""):
            return value.get(attribute)
        for child in value.values():
            found = _extract_attribute_value(child, attribute)
            if found not in (None, ""):
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _extract_attribute_value(child, attribute)
            if found not in (None, ""):
                return found
    return None


async def _load_authoritative_inventory(application: Any) -> tuple[Any, list[dict[str, Any]]]:
    result = await application.mcp.call_tool("hub_list_devices", {})
    return result, list(_iter_device_records(_tool_data(result)))


async def _read_authoritative_device(application: Any, device_id: str) -> Any:
    desired = {
        "ids": [device_id],
        "deviceIds": [device_id],
        "device_ids": [device_id],
        "id": device_id,
        "deviceId": device_id,
    }
    supported = getattr(application.mcp, "supported_arguments", None)
    arguments = await supported("hub_read_devices", desired) if callable(supported) else {"ids": [device_id]}
    if not arguments:
        arguments = {"ids": [device_id]}
    return await application.mcp.call_tool("hub_read_devices", arguments)


async def _answer_terminal_entity_read(application: Any, query: str) -> dict[str, Any] | None:
    explicit_lookup = _is_explicit_device_lookup(query)
    attribute_request = _requested_device_attribute(query)
    if not explicit_lookup and attribute_request is None:
        return None

    inventory_result, devices = await _load_authoritative_inventory(application)
    target_phrase = parse_entity_request(query).target_phrase if explicit_lookup else _attribute_target_phrase(query)
    device = _best_lookup_device(devices, target_phrase)
    tools_used = [{"name": "hub_list_devices", "success": not bool(getattr(inventory_result, "is_error", False))}]
    if device is None:
        return {
            "success": False,
            "route": "mcp-fast",
            "intent": "device-lookup" if explicit_lookup else "device-attribute-read",
            "message": f'I could not find a device matching "{target_phrase}".',
            "tools_used": tools_used,
            "entity_resolution_request": parse_entity_request(query).as_dict(),
            "answered_by": "deterministic entity resolver",
        }

    if explicit_lookup:
        return {
            "success": True,
            "route": "mcp-fast",
            "intent": "device-lookup",
            "message": _format_lookup_device(device),
            "lookup_device": {
                "id": str(device.get("id") or ""),
                "label": str(device.get("label") or device.get("name") or ""),
                "room": device.get("room") or device.get("roomName") or device.get("room_name"),
                "device_type": device.get("name") or device.get("category") or device.get("deviceType"),
                "disabled": bool(device.get("disabled")),
            },
            "tools_used": tools_used,
            "entity_resolution_request": parse_entity_request(query).as_dict(),
            "answered_by": "deterministic entity resolver",
        }

    attribute, unit = attribute_request
    read_result = await _read_authoritative_device(application, str(device.get("id") or ""))
    tools_used.append({"name": "hub_read_devices", "success": not bool(getattr(read_result, "is_error", False))})
    value = _extract_attribute_value(_tool_data(read_result), attribute)
    label = str(device.get("label") or device.get("name") or "Device")
    if value in (None, ""):
        message = f"{label} is available, but Hubitat did not expose a current {attribute} value."
        success = False
    else:
        message = f"{label} is {value} {unit}."
        success = True
    return {
        "success": success,
        "route": "mcp-fast",
        "intent": "device-attribute-read",
        "message": message,
        "device_id": str(device.get("id") or ""),
        "device_label": label,
        "attribute": attribute,
        "value": value,
        "unit": unit,
        "tools_used": tools_used,
        "entity_resolution_request": parse_entity_request(query).as_dict(),
        "answered_by": "deterministic entity reader",
    }


'''
if '_answer_terminal_entity_read' not in text:
    if helper_marker not in text:
        raise RuntimeError('lookup helper marker not found')
    text = text.replace(helper_marker, helpers + helper_marker, 1)

ask_marker = '''        try:\n            planner = getattr(application.ollama, "answer_with_planner", None)\n'''
ask_replacement = '''        try:\n            terminal_entity = await _answer_terminal_entity_read(application, query)\n            if terminal_entity is not None:\n                terminal_entity.setdefault("success", True)\n                terminal_entity["agent_orchestrator"] = "deterministic-entity-read"\n                terminal_entity["legacy_fallback_used"] = False\n                terminal_entity["conversation_history_used"] = False\n                terminal_entity.setdefault("version", application.VERSION)\n                return terminal_entity\n            planner = getattr(application.ollama, "answer_with_planner", None)\n'''
if 'terminal_entity = await _answer_terminal_entity_read' not in text:
    if ask_marker not in text:
        raise RuntimeError('ask insertion marker not found')
    text = text.replace(ask_marker, ask_replacement, 1)

if '"_answer_terminal_entity_read"' not in text:
    text = text.replace('    "_apply_device_tool_policy",\n', '    "_answer_terminal_entity_read",\n    "_apply_device_tool_policy",\n', 1)

orchestrator.write_text(text, encoding='utf-8')

rewrite(Path('hubitat-mcp-ai/config.yaml'), lambda s: re.sub(r'(?m)^version: ["\'][^"\']+["\']$', 'version: "0.10.37"', s, count=1))
rewrite(APP / 'entrypoint.py', lambda s: re.sub(r'PREVIOUS_RELEASE_VERSION = "[^"]+"\s+RELEASE_VERSION = "[^"]+"', 'PREVIOUS_RELEASE_VERSION = "0.10.36"\nRELEASE_VERSION = "0.10.37"', s, count=1))
rewrite(APP / 'device_intelligence_webui.py', lambda s: re.sub(r'PWA_RELEASE_VERSION = "[^"]+"', 'PWA_RELEASE_VERSION = "0.10.37"', s, count=1))

Path('tests/test_deterministic_entity_read.py').write_text(r'''from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import _answer_terminal_entity_read


class Result:
    def __init__(self, data):
        self.data = data
        self.is_error = False


class MCP:
    async def supported_arguments(self, name, desired):
        return {"ids": desired["ids"]}

    async def call_tool(self, name, arguments):
        if name == "hub_list_devices":
            return Result({"devices": [{
                "id": "123",
                "name": "Illuminance Sensor",
                "label": "FP2 Bedroom 3 Lux",
                "room": "Bedroom 3",
                "disabled": False,
                "currentStates": {},
            }]})
        assert name == "hub_read_devices"
        assert arguments == {"ids": ["123"]}
        return Result({"devices": [{
            "id": "123",
            "label": "FP2 Bedroom 3 Lux",
            "currentStates": {"illuminance": 212},
        }]})


def app():
    return SimpleNamespace(mcp=MCP(), VERSION="0.10.37")


def test_find_is_terminal_identity_lookup():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "Find FP2 Bedroom 3 Lux"))
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-lookup"
    assert "Found FP2 Bedroom 3 Lux in Bedroom 3" in answer["message"]
    assert "lux value" not in answer["message"].lower()


def test_lux_question_reads_authoritative_attribute():
    answer = asyncio.run(_answer_terminal_entity_read(app(), "What is the lux reading from FP2 Bedroom 3 Lux?"))
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "device-attribute-read"
    assert answer["value"] == 212
    assert answer["message"] == "FP2 Bedroom 3 Lux is 212 lux."
    assert [item["name"] for item in answer["tools_used"]] == ["hub_list_devices", "hub_read_devices"]
''', encoding='utf-8')

Path('hubitat-mcp-ai/CHANGELOG-0.10.37.md').write_text('''# Hubitat MCP AI 0.10.37

- Makes explicit device lookup requests terminal and deterministic.
- Resolves exact device IDs before reading sensor attributes.
- Uses `hub_read_devices` for live values such as illuminance instead of relying on projected inventory.
- Prevents Gemma from replacing authoritative values with missing-value guesses.
''', encoding='utf-8')
