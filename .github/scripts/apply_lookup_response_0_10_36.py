from pathlib import Path
import re

APP = Path("hubitat-mcp-ai/rootfs/app")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


orchestrator = APP / "mcp_agent_orchestrator.py"
helper_marker = "async def _apply_device_tool_policy(\n"
helpers = r'''_LOOKUP_PREFIX_RE = re.compile(
    r"^(?:find|locate|search for|look for|where is|where's)\b",
    re.IGNORECASE,
)


def _is_explicit_device_lookup(query: str) -> bool:
    """Return true for identity/location lookups, not state or value questions."""

    return bool(_LOOKUP_PREFIX_RE.match(_normalise(query)))


def _iter_device_records(value: Any):
    """Yield device-shaped dictionaries from nested targeted-search evidence."""

    if isinstance(value, dict):
        if value.get("id") not in (None, "") and (value.get("label") or value.get("name")):
            if any(key in value for key in ("room", "roomName", "currentStates", "capabilities", "disabled")):
                yield value
        for child in value.values():
            yield from _iter_device_records(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_device_records(child)


def _lookup_record_score(device: dict[str, Any], target_phrase: str) -> tuple[int, int]:
    label = _normalise(str(device.get("label") or device.get("name") or ""))
    target = _normalise(target_phrase)
    compact_label = re.sub(r"[^a-z0-9]", "", label)
    compact_target = re.sub(r"[^a-z0-9]", "", target)
    exact = int(bool(compact_target) and compact_label == compact_target)
    overlap = len(set(target.split()) & set(label.split()))
    return exact, overlap


def _best_lookup_device(payload: Any, target_phrase: str) -> dict[str, Any] | None:
    records = list(_iter_device_records(payload))
    if not records:
        return None
    return max(records, key=lambda item: _lookup_record_score(item, target_phrase))


def _format_lookup_device(device: dict[str, Any]) -> str:
    label = str(device.get("label") or device.get("name") or "Device")
    room = device.get("room") or device.get("roomName") or device.get("room_name")
    device_type = device.get("name") or device.get("category") or device.get("deviceType")
    disabled = bool(device.get("disabled"))
    parts = [f"Found {label}"]
    if room:
        parts[0] += f" in {room}"
    if device_type and _normalise(str(device_type)) != _normalise(label):
        parts.append(f"Device type: {device_type}")
    parts.append("Status: disabled" if disabled else "Status: available")
    return ". ".join(parts) + "."


async def _apply_device_lookup_response_policy(
    application: Any,
    query: str,
    history: list[dict[str, str]],
    answer: dict[str, Any],
) -> dict[str, Any]:
    """Make explicit find/locate requests terminal and evidence-shaped.

    A lookup asks where/what a device is. It must not be reinterpreted as a request
    for the device's current sensor value merely because the label contains words
    such as lux, temperature or power.
    """

    if not _is_explicit_device_lookup(query):
        return answer
    entity_request = parse_entity_request(query)
    if entity_request.broad_inventory or not entity_request.targeted:
        return answer
    executed = _executed_tool_names(answer)
    if not ({"homebrain_search_devices", "hub_list_devices"} & executed):
        return answer

    agent = getattr(application, "ollama", None)
    targeted = getattr(agent, "_answer_from_targeted_device_search", None)
    if not callable(targeted):
        return answer

    corrected = await targeted(
        query,
        history,
        RuntimeError("Explicit lookup requires deterministic targeted-device evidence"),
    )
    result = dict(corrected)
    device = _best_lookup_device({"targeted": corrected, "planner": answer}, entity_request.target_phrase)
    if device is not None:
        result["message"] = _format_lookup_device(device)
        result["lookup_device"] = {
            "id": str(device.get("id") or ""),
            "label": str(device.get("label") or device.get("name") or ""),
            "room": device.get("room") or device.get("roomName") or device.get("room_name"),
            "device_type": device.get("name") or device.get("category") or device.get("deviceType"),
            "disabled": bool(device.get("disabled")),
        }
    result["lookup_response_policy_corrected"] = True
    result["entity_resolution_request"] = entity_request.as_dict()
    result["original_message"] = str(answer.get("message") or "")
    result["original_executed_tools"] = sorted(executed)
    return result


'''
replace_once(orchestrator, helper_marker, helpers + helper_marker)

flow_marker = '''            result = await _apply_automation_recommendation_policy(
                application,
                query,
                result,
            )
'''
flow_replacement = '''            result = await _apply_device_lookup_response_policy(
                application,
                query,
                history,
                result,
            )
            result = await _apply_automation_recommendation_policy(
                application,
                query,
                result,
            )
'''
replace_once(orchestrator, flow_marker, flow_replacement)
replace_once(
    orchestrator,
    '    "_apply_device_tool_policy",\n',
    '    "_apply_device_tool_policy",\n    "_apply_device_lookup_response_policy",\n    "_is_explicit_device_lookup",\n',
)

config = Path("hubitat-mcp-ai/config.yaml")
text = config.read_text(encoding="utf-8")
text = re.sub(r'(?m)^version: ["\'][^"\']+["\']$', 'version: "0.10.36"', text, count=1)
config.write_text(text, encoding="utf-8")

entrypoint = APP / "entrypoint.py"
text = entrypoint.read_text(encoding="utf-8")
text = re.sub(
    r'PREVIOUS_RELEASE_VERSION = "[^"]+"\s+RELEASE_VERSION = "[^"]+"',
    'PREVIOUS_RELEASE_VERSION = "0.10.35"\nRELEASE_VERSION = "0.10.36"',
    text,
    count=1,
)
entrypoint.write_text(text, encoding="utf-8")

webui = APP / "device_intelligence_webui.py"
text = webui.read_text(encoding="utf-8")
text = re.sub(r'PWA_RELEASE_VERSION = "[^"]+"', 'PWA_RELEASE_VERSION = "0.10.36"', text, count=1)
text = re.sub(r'hubitat-mcp-ai-shell-v[0-9.]+', 'hubitat-mcp-ai-shell-v0.10.36', text)
webui.write_text(text, encoding="utf-8")

Path("tests").mkdir(parents=True, exist_ok=True)
Path("tests/test_explicit_device_lookup_response.py").write_text(r'''from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import (
    _apply_device_lookup_response_policy,
    _is_explicit_device_lookup,
)


class FakeAgent:
    async def _answer_from_targeted_device_search(self, query, history, error):
        return {
            "success": True,
            "route": "mcp-fast",
            "message": "The sensor is not reporting a lux value.",
            "mcp_response": {
                "devices": [
                    {
                        "id": "999",
                        "name": "Illuminance Sensor",
                        "label": "FP2 Bedroom 3 Lux",
                        "room": "Bedroom 3",
                        "disabled": False,
                        "currentStates": {},
                    }
                ]
            },
        }


def test_lookup_intent_does_not_include_value_question():
    assert _is_explicit_device_lookup("Find FP2 Bedroom 3 Lux")
    assert _is_explicit_device_lookup("Locate the front door sensor")
    assert not _is_explicit_device_lookup("What is the lux reading from FP2 Bedroom 3 Lux?")


@pytest.mark.asyncio
async def test_find_sensor_returns_identity_room_type_and_availability():
    application = SimpleNamespace(ollama=FakeAgent())
    planner_answer = {
        "message": "It is not currently reporting a lux value.",
        "tools_used": [{"name": "homebrain_search_devices", "success": True}],
    }
    result = await _apply_device_lookup_response_policy(
        application,
        "Find FP2 Bedroom 3 Lux",
        [],
        planner_answer,
    )
    assert result["message"] == (
        "Found FP2 Bedroom 3 Lux in Bedroom 3. "
        "Device type: Illuminance Sensor. Status: available."
    )
    assert result["lookup_response_policy_corrected"] is True
    assert result["lookup_device"]["id"] == "999"
    assert "not reporting" not in result["message"].lower()


@pytest.mark.asyncio
async def test_value_question_is_left_for_value_reading_route():
    application = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "message": "Reading response",
        "tools_used": [{"name": "homebrain_search_devices", "success": True}],
    }
    result = await _apply_device_lookup_response_policy(
        application,
        "What is the lux reading from FP2 Bedroom 3 Lux?",
        [],
        answer,
    )
    assert result is answer
''', encoding="utf-8")

Path("hubitat-mcp-ai/CHANGELOG-0.10.36.md").write_text(
    "# Hubitat MCP AI 0.10.36\n\n"
    "- Makes explicit `find`, `locate`, and `search for` requests deterministic.\n"
    "- Reports matched device identity, room, type, and availability.\n"
    "- Prevents sensor names such as `Lux` from being misread as value requests.\n",
    encoding="utf-8",
)
