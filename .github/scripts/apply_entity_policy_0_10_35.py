from pathlib import Path
import re

APP = Path("hubitat-mcp-ai/rootfs/app")

def rewrite(path: Path, transform) -> None:
    before = path.read_text(encoding="utf-8")
    after = transform(before)
    if after == before:
        raise SystemExit(f"no change made in {path}")
    path.write_text(after, encoding="utf-8")

(APP / "entity_request_policy.py").write_text('''from __future__ import annotations
import re
from dataclasses import asdict, dataclass
from typing import Any
from entity_resolution import infer_ordinal, normalise_text

_BROAD_PATTERNS = (
    r"(?:show|list|find|search|display|get) (?:all )?(?:my |the )?devices(?: in .+)?",
    r"(?:what|which) devices (?:are|do|have|need|in|on|off).+",
    r"devices in (?:the )?.+",
)
_PREFIX = re.compile(r"^(?:please )?(?:(?:turn|switch|set|dim|open|close|lock|unlock|find|locate|show|read|check|get)\\s+|what(?:'s| is)\\s+)(?:the )?", re.I)
_TRAILING = re.compile(r"\\s+(?:on|off|state|status|level|power|temperature|humidity)(?:\\s+now)?$", re.I)
_ROOM = re.compile(r"\\b(?:in|from)\\s+(?:the )?([a-z0-9 -]+?)(?:\\s+room)?$", re.I)

@dataclass(frozen=True)
class EntityRequest:
    query: str
    target_phrase: str
    room: str | None = None
    device_type: str | None = None
    ordinal: int | None = None
    broad_inventory: bool = False
    targeted: bool = False
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def _device_type(value: str) -> str | None:
    q = normalise_text(value)
    aliases = {
        "light": ("light", "lamp", "bulb", "dimmer"),
        "fan": ("fan", "ventilation"),
        "switch": ("switch", "socket", "plug", "outlet"),
        "thermostat": ("thermostat", "trv", "radiator"),
        "contact": ("contact", "door", "window"),
        "motion": ("motion", "presence", "occupancy"),
        "lock": ("lock",),
    }
    for canonical, terms in aliases.items():
        if any(re.search(rf"\\b{re.escape(term)}\\b", q) for term in terms):
            return canonical
    return None

def parse_entity_request(query: str) -> EntityRequest:
    q = normalise_text(query).strip(" .!?")
    broad = any(re.fullmatch(pattern, q) for pattern in _BROAD_PATTERNS)
    room_match = _ROOM.search(q)
    room = normalise_text(room_match.group(1)) if room_match else None
    target = _TRAILING.sub("", _PREFIX.sub("", q))
    target = re.sub(r"\\b(?:to|at)\\s+\\d+(?:\\s*%)?$", "", target).strip()
    if room_match and room_match.start() > 0:
        target = target[:room_match.start()].strip()
    target = re.sub(r"^(?:a|an|the)\\s+", "", target).strip()
    useful = bool(target and target not in {"device", "devices", "all devices"})
    return EntityRequest(q, target, room, _device_type(target or q), infer_ordinal(target or q), broad, useful and not broad)

def is_targeted_device_request(query: str) -> bool:
    return parse_entity_request(query).targeted

__all__ = ["EntityRequest", "is_targeted_device_request", "parse_entity_request"]
''', encoding="utf-8")

orchestrator = APP / "mcp_agent_orchestrator.py"
rewrite(orchestrator, lambda text: text.replace("from device_health_fast_route import is_attention_query, is_device_health_query\n", "from device_health_fast_route import is_attention_query, is_device_health_query\nfrom entity_request_policy import parse_entity_request\n", 1))
old = '''    agent = getattr(application, "ollama", None)
    targeted_check = getattr(agent, "_targeted_device_lookup", None)
    if callable(targeted_check) and not targeted_check(query):
        return answer
    broad_check = getattr(agent, "_is_broad_device_inventory_request", None)
    if callable(broad_check) and bool(broad_check(query)):
        return answer

    targeted = getattr(agent, "_answer_from_targeted_device_search", None)
'''
new = '''    agent = getattr(application, "ollama", None)
    entity_request = parse_entity_request(query)
    if entity_request.broad_inventory or not entity_request.targeted:
        return answer

    targeted = getattr(agent, "_answer_from_targeted_device_search", None)
'''
rewrite(orchestrator, lambda text: text.replace(old, new, 1))
rewrite(orchestrator, lambda text: text.replace('    result["tool_policy_corrected"] = True\n', '    result["tool_policy_corrected"] = True\n    result["entity_resolution_request"] = entity_request.as_dict()\n', 1))

rewrite(Path("hubitat-mcp-ai/config.yaml"), lambda text: re.sub(r'(?m)^version: ["\'][^"\']+["\']$', 'version: "0.10.35"', text, count=1))
rewrite(APP / "entrypoint.py", lambda text: re.sub(r'PREVIOUS_RELEASE_VERSION = "[^"]+"\s+RELEASE_VERSION = "[^"]+"', 'PREVIOUS_RELEASE_VERSION = "0.10.34"\nRELEASE_VERSION = "0.10.35"', text, count=1))
rewrite(APP / "device_intelligence_webui.py", lambda text: re.sub(r'PWA_RELEASE_VERSION = "[^"]+"', 'PWA_RELEASE_VERSION = "0.10.35"', text, count=1).replace('hubitat-mcp-ai-shell-v0.10.34', 'hubitat-mcp-ai-shell-v0.10.35'))

Path("tests/test_entity_request_policy.py").write_text('''from __future__ import annotations
import sys
from pathlib import Path
APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
from entity_request_policy import is_targeted_device_request, parse_entity_request

def test_targeted_fan_switch():
    r = parse_entity_request("Find Fan Switch")
    assert r.targeted and r.target_phrase == "fan switch" and r.device_type == "fan"

def test_numbered_living_room_light():
    r = parse_entity_request("Check the second living room light")
    assert r.targeted and r.ordinal == 2 and r.device_type == "light"

def test_sensor_lookup_is_targeted():
    r = parse_entity_request("Find FP2 Bedroom 3 Lux")
    assert r.targeted and r.target_phrase == "fp2 bedroom 3 lux"

def test_room_inventory_is_broad_not_targeted():
    r = parse_entity_request("Show devices in the living room")
    assert r.broad_inventory and not r.targeted

def test_generic_inventory_is_not_targeted():
    assert not is_targeted_device_request("List all devices")
''', encoding="utf-8")
Path("hubitat-mcp-ai/CHANGELOG-0.10.35.md").write_text("# Hubitat MCP AI 0.10.35\n\n- Centralises targeted-device request classification in the entity-resolution layer.\n- Removes duplicate Ollama-specific targeted and broad-inventory checks.\n- Adds structured entity-request diagnostics and regression coverage.\n", encoding="utf-8")
