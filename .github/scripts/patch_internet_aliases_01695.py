from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"pattern not unique in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


path = "hubitat-mcp-ai/rootfs/app/rule_authoring_service.py"
replace_once(path, "import logging\nimport re\n", "import json\nimport logging\nimport re\n")
replace_once(
    path,
    "from device_target_resolver import resolve_device_candidate\n",
    "from device_target_resolver import normalized_name, resolve_device_candidate\n",
)
replace_once(
    path,
    "        *,\n        now: Callable[[], datetime] = datetime.now,\n    ) -> None:\n        self.mcp = mcp_client\n        self._record_evidence = record_evidence\n        self._now = now\n",
    "        *,\n        now: Callable[[], datetime] = datetime.now,\n        internet_control_aliases: Any | None = None,\n    ) -> None:\n        self.mcp = mcp_client\n        self._record_evidence = record_evidence\n        self._now = now\n        self.internet_control_aliases = self._parse_internet_control_aliases(\n            internet_control_aliases\n        )\n\n    @staticmethod\n    def _parse_internet_control_aliases(value: Any | None) -> dict[str, str]:\n        if value in {None, \"\"}:\n            return {}\n        if isinstance(value, str):\n            try:\n                value = json.loads(value)\n            except Exception:\n                return {}\n        if not isinstance(value, dict):\n            return {}\n        aliases: dict[str, str] = {}\n        for alias, label in value.items():\n            alias_text = str(alias or \"\").strip()\n            label_text = str(label or \"\").strip()\n            if alias_text and label_text:\n                aliases[normalized_name(alias_text)] = label_text\n        return aliases\n\n    def _configured_internet_target(\n        self, requested: str, identities: list[dict[str, Any]]\n    ) -> dict[str, Any] | None:\n        requested_key = normalized_name(requested)\n        configured_label = self.internet_control_aliases.get(requested_key)\n        if configured_label is None:\n            for label in self.internet_control_aliases.values():\n                if normalized_name(label) == requested_key:\n                    configured_label = label\n                    break\n        if not configured_label:\n            return None\n        wanted = normalized_name(configured_label)\n        matches = []\n        for item in identities:\n            if not isinstance(item, dict):\n                continue\n            names = (\n                item.get(\"label\"),\n                item.get(\"name\"),\n                item.get(\"displayName\"),\n                item.get(\"deviceLabel\"),\n            )\n            if any(normalized_name(name) == wanted for name in names if name):\n                matches.append(dict(item))\n        return matches[0] if len(matches) == 1 else None\n",
)
old = '''            internet_candidates = [
                item
                for item in identities
                if isinstance(item, dict)
                and str(room_name(item) or "").casefold() == "internet"
            ]
            scoped = resolve_device_candidate(intent.target, internet_candidates)
            self._record_evidence(
                "homebrain_device_inventory",
                {"group": "Internet"},
                success=scoped.target is not None,
                elapsed_ms=round((time.monotonic() - identity_started) * 1000),
                summary=(
                    f"{len(internet_candidates)} Internet-group candidates; "
                    f"target={'resolved' if scoped.target is not None else 'unresolved'}"
                ),
                supports_live_claim=True,
                evidence_kind="deterministic_internet_target_scope",
            )
            if scoped.target is None:
                if scoped.alternatives:
                    return RuleAuthoringDecision(
                        True,
                        "I could not uniquely match that request to an Internet-control "
                        "device. Possible matches: "
                        + ", ".join(scoped.alternatives[:3])
                        + ". Nothing was queued.",
                    )
                return RuleAuthoringDecision(
                    True,
                    f"I could not match **{intent.target}** to a device in the "
                    "authoritative **Internet** group. Nothing was queued.",
                )

            selected_label = str(
                scoped.target.get("label")
                or scoped.target.get("name")
                or intent.target
            ).strip()
'''
new = '''            internet_candidates = [
                item
                for item in identities
                if isinstance(item, dict)
                and str(room_name(item) or "").casefold() == "internet"
            ]
            configured_target = self._configured_internet_target(
                intent.target,
                [item for item in identities if isinstance(item, dict)],
            )
            if configured_target is not None:
                scoped_target = configured_target
                scoped_alternatives: tuple[str, ...] = ()
                scope_source = "configured alias"
            else:
                scoped = resolve_device_candidate(intent.target, internet_candidates)
                scoped_target = scoped.target
                scoped_alternatives = scoped.alternatives
                scope_source = "Internet room"
            self._record_evidence(
                "homebrain_device_inventory",
                {"group": "Internet"},
                success=scoped_target is not None,
                elapsed_ms=round((time.monotonic() - identity_started) * 1000),
                summary=(
                    f"{len(internet_candidates)} Internet-group candidates; "
                    f"configured_aliases={len(self.internet_control_aliases)}; "
                    f"source={scope_source}; "
                    f"target={'resolved' if scoped_target is not None else 'unresolved'}"
                ),
                supports_live_claim=True,
                evidence_kind="deterministic_internet_target_scope",
            )
            if scoped_target is None:
                if scoped_alternatives:
                    return RuleAuthoringDecision(
                        True,
                        "I could not uniquely match that request to an Internet-control "
                        "device. Possible matches: "
                        + ", ".join(scoped_alternatives[:3])
                        + ". Nothing was queued.",
                    )
                return RuleAuthoringDecision(
                    True,
                    f"I could not match **{intent.target}** to a device in the "
                    "authoritative **Internet** group or configured Internet aliases. "
                    "Nothing was queued.",
                )

            selected_label = str(
                scoped_target.get("label")
                or scoped_target.get("name")
                or intent.target
            ).strip()
'''
replace_once(path, old, new)

path = "hubitat-mcp-ai/rootfs/app/mcp_agent_orchestrator.py"
replace_once(
    path,
    "        known_automations: Any | None = None,\n        max_tool_result_chars: int = 24000,\n",
    "        known_automations: Any | None = None,\n        internet_control_aliases: Any | None = None,\n        max_tool_result_chars: int = 24000,\n",
)
replace_once(
    path,
    "        self.rule_authoring = RuleAuthoringService(\n            self.mcp,\n            self.evidence.record,\n        )\n",
    "        self.rule_authoring = RuleAuthoringService(\n            self.mcp,\n            self.evidence.record,\n            internet_control_aliases=internet_control_aliases,\n        )\n",
)

path = "hubitat-mcp-ai/rootfs/app/app.py"
replace_once(
    path,
    '        "semantic_default_temperature_step": 1.0,\n',
    '        "semantic_default_temperature_step": 1.0,\n        "internet_control_aliases_json": "{}",\n',
)
replace_once(
    path,
    '    known_automations=OPTIONS.get("causal_known_automations_json"),\n',
    '    known_automations=OPTIONS.get("causal_known_automations_json"),\n    internet_control_aliases=OPTIONS.get("internet_control_aliases_json"),\n',
)

Path("hubitat-mcp-ai/tests/test_internet_control_aliases.py").write_text(r'''from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService


def result(name: str, arguments: dict[str, Any], data: Any) -> MCPToolResult:
    return MCPToolResult(name=name, arguments=arguments, raw={}, text="", data=data, is_error=False)


ADB = {
    "id": "7000",
    "label": "Google TV Streamer (ADB)",
    "roomName": "Living Room",
    "commands": ["on", "off"],
    "capabilities": ["Switch"],
}
CONTROL = {
    "id": "6923",
    "label": "Block Media-Google-TV-Streamer",
    "commands": ["on", "off"],
    "capabilities": ["Switch"],
}


class FakeMCP:
    async def get_cached_devices(self):
        return [dict(ADB), dict(CONTROL)]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if name == "hub_read_devices":
            label = str(arguments.get("args", {}).get("labelFilter") or "")
            devices = [dict(CONTROL)] if label == CONTROL["label"] else []
            return result(name, arguments, {"success": True, "devices": devices})
        if name == "hub_read_rules":
            return result(name, arguments, {"success": True, "rules": []})
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_explicit_alias_extends_internet_scope_without_room_membership() -> None:
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *_args, **_kwargs: None,
        now=lambda: datetime(2026, 10, 3, 8, 0, 0),
        internet_control_aliases='{"Google TV":"Block Media-Google-TV-Streamer"}',
    )
    decision = await service.propose(
        "block Google TV after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert decision.handled is True
    assert decision.message is None
    assert decision.target["id"] == "6923"
    assert decision.actions[0]["args"]["addAction"]["deviceIds"] == ["6923"]
    assert decision.actions[0]["args"]["addAction"]["command"] == "off"


@pytest.mark.asyncio
async def test_missing_alias_does_not_guess_from_block_prefix() -> None:
    service = RuleAuthoringService(
        FakeMCP(),
        lambda *_args, **_kwargs: None,
        now=lambda: datetime(2026, 10, 3, 8, 0, 0),
    )
    decision = await service.propose(
        "block Google TV after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )
    assert decision.handled is True
    assert decision.actions == ()
    assert "configured Internet aliases" in str(decision.message)
''')

path = "hubitat-mcp-ai/config.yaml"
replace_once(path, 'version: "0.16.94"\n', 'version: "0.16.95"\n')
replace_once(
    path,
    '  semantic_default_temperature_step: 1.0\n',
    '  semantic_default_temperature_step: 1.0\n  internet_control_aliases_json: "{}"\n',
)
replace_once(
    path,
    '  semantic_default_temperature_step: float\n',
    '  semantic_default_temperature_step: float\n  internet_control_aliases_json: str\n',
)

path = "README.md"
replace_once(path, "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.94 |", "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.95 |")

path = "hubitat-mcp-ai/README.md"
replace_once(path, "Current add-on version: **0.16.94**.", "Current add-on version: **0.16.95**.")
replace_once(
    path,
    "## Architecture\n\n",
    "## Architecture\n\n0.16.95 adds an explicit, empty-by-default `internet_control_aliases_json` map for Internet control surfaces that intentionally are not assigned to the Hubitat `Internet` room. A configured alias such as `{'Google TV':'Block Media-Google-TV-Streamer'}` is treated as an exact deterministic identity binding only for scheduled Internet access; HomeBrain still verifies the selected device exposes the real `on`/`off` Switch command before proposing Rule Machine JSON. No global `Block ...` prefix heuristic is introduced, ordinary TV power control is unchanged, and room-based Internet controls remain the default authoritative path.\n\n",
)
replace_once(
    path,
    "semantic_default_temperature_step: 1.0\n",
    "semantic_default_temperature_step: 1.0\ninternet_control_aliases_json: '{\"Google TV\":\"Block Media-Google-TV-Streamer\"}'\n",
)

path = "hubitat-mcp-ai/CHANGELOG-INDEX.md"
replace_once(
    path,
    "## Current release\n\n- [0.16.94](CHANGELOG-0.16.94.md)\n\n## Recent performance releases\n",
    "## Current release\n\n- [0.16.95](CHANGELOG-0.16.95.md)\n\n## Recent performance releases\n\n- [0.16.94](CHANGELOG-0.16.94.md)\n",
)

Path("hubitat-mcp-ai/CHANGELOG-0.16.95.md").write_text('''# Hubitat MCP AI 0.16.95

## Explicit Internet-control aliases

- Adds `internet_control_aliases_json`, an empty-by-default JSON object mapping user phrases to exact Hubitat control-surface labels.
- Configured aliases may extend scheduled Internet control beyond devices assigned to the `Internet` room without introducing a global name-prefix heuristic.
- Alias matching is exact after HomeBrain name normalization; the configured target label must identify exactly one current Hubitat device.
- The selected target is still re-read and verified for the real Switch `off`/`on` command before any Rule Machine write is proposed.
- Existing Internet-room semantics remain unchanged: `off` means blocked and `on` means allowed.
- Ordinary device power scheduling remains outside this alias map.

Example:

```yaml
internet_control_aliases_json: '{"Google TV":"Block Media-Google-TV-Streamer"}'
```
''')
