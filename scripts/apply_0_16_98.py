from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))


rule = ROOT / "hubitat-mcp-ai/rootfs/app/rule_authoring_service.py"

anchor = '''        return matches[0] if len(matches) == 1 else None\n\n    @staticmethod\n    def _clock(value: str) -> str | None:\n'''
insert = '''        return matches[0] if len(matches) == 1 else None\n\n    @staticmethod\n    def _internet_identity_tokens(value: Any) -> set[str]:\n        \"\"\"Return order-independent identity tokens for Internet controls only.\n\n        This intentionally does not change the global device resolver. Internet\n        control labels commonly contain control/presentation prefixes and compact\n        model names (for example ``Block PC-NucBox-M6Ultra``), while users naturally\n        say the same identity as ``M6 Ultra PC``. Split camel/digit boundaries,\n        ignore only non-identifying Internet-control words, and let extra candidate\n        tokens remain harmless.\n        \"\"\"\n\n        text = str(value or \"\").strip()\n        if not text:\n            return set()\n        text = re.sub(r\"(?<=[a-z0-9])(?=[A-Z])\", \" \", text)\n        text = re.sub(r\"(?<=\\d)(?=[A-Za-z])\", \" \", text)\n        text = re.sub(r\"[^A-Za-z0-9]+\", \" \", text).casefold()\n        ignored = {\"block\", \"internet\", \"access\", \"control\", \"the\", \"a\", \"an\"}\n        return {token for token in text.split() if token not in ignored}\n\n    @classmethod\n    def _internet_local_target(\n        cls, requested: str, identities: list[dict[str, Any]]\n    ) -> tuple[dict[str, Any] | None, tuple[str, ...]]:\n        \"\"\"Resolve a unique token-subset match inside the Internet room.\n\n        The match is intentionally scope-local and conservative: every identifying\n        token supplied by the user must be present in one candidate name after the\n        bounded normalization above. If more than one Internet control satisfies\n        that condition, surface the ambiguity rather than guessing.\n        \"\"\"\n\n        wanted = cls._internet_identity_tokens(requested)\n        if not wanted:\n            return None, ()\n        matches: list[tuple[str, dict[str, Any]]] = []\n        for item in identities:\n            if not isinstance(item, dict):\n                continue\n            names = [\n                str(item.get(field) or \"\").strip()\n                for field in (\"label\", \"name\", \"displayName\", \"deviceLabel\")\n            ]\n            names = [name for name in names if name]\n            matched_name = next(\n                (\n                    name\n                    for name in names\n                    if wanted.issubset(cls._internet_identity_tokens(name))\n                ),\n                None,\n            )\n            if matched_name is not None:\n                matches.append((matched_name, dict(item)))\n        if len(matches) == 1:\n            return matches[0][1], ()\n        if len(matches) > 1:\n            alternatives: list[str] = []\n            for name, _item in matches:\n                if name not in alternatives:\n                    alternatives.append(name)\n            return None, tuple(alternatives[:3])\n        return None, ()\n\n    @staticmethod\n    def _clock(value: str) -> str | None:\n'''
replace_once(rule, anchor, insert)

old_identity = '''                # get_cached_devices() is the long-established enriched identity\n                # interface used by the control/query paths and by older MCP\n                # clients/test doubles. Prefer it here; fall back to the newer\n                # get_device_identities() helper when only that interface exists.\n                identity_reader = getattr(self.mcp, \"get_cached_devices\", None)\n                if not callable(identity_reader):\n                    identity_reader = getattr(self.mcp, \"get_device_identities\", None)\n                if not callable(identity_reader):\n                    raise AttributeError(\"No device identity reader is available\")\n                identities = list(await identity_reader() or [])\n'''
new_identity = '''                # Identity metadata remains authoritative for longer than live\n                # state. Reuse a fresh complete structural snapshot first instead\n                # of forcing the 12-second device-manifest cache to refresh. This\n                # keeps scheduled Internet resolution fast after any recent\n                # inventory/live-context read while still falling back to one\n                # bounded refresh when no fresh identity snapshot exists.\n                identities: list[dict[str, Any]] = []\n                identity_source = \"identity refresh\"\n                identity_peek = getattr(self.mcp, \"peek_device_identities\", None)\n                if callable(identity_peek):\n                    try:\n                        identities = list(identity_peek() or [])\n                    except Exception:\n                        identities = []\n                    if identities:\n                        identity_source = \"identity cache\"\n                if not identities:\n                    identity_reader = getattr(self.mcp, \"get_cached_devices\", None)\n                    if not callable(identity_reader):\n                        identity_reader = getattr(self.mcp, \"get_device_identities\", None)\n                    if not callable(identity_reader):\n                        raise AttributeError(\"No device identity reader is available\")\n                    identities = list(await identity_reader() or [])\n                    identity_source = \"identity refresh\"\n'''
replace_once(rule, old_identity, new_identity)

old_match = '''            if configured_target is not None:\n                scoped_target = configured_target\n                scoped_alternatives: tuple[str, ...] = ()\n                scope_source = \"configured alias\"\n            else:\n                scoped = resolve_device_candidate(intent.target, internet_candidates)\n                scoped_target = scoped.target\n                scoped_alternatives = scoped.alternatives\n                scope_source = \"Internet room\"\n'''
new_match = '''            if configured_target is not None:\n                scoped_target = configured_target\n                scoped_alternatives: tuple[str, ...] = ()\n                scope_source = \"configured alias\"\n            else:\n                local_target, local_alternatives = self._internet_local_target(\n                    intent.target, internet_candidates\n                )\n                if local_target is not None:\n                    scoped_target = local_target\n                    scoped_alternatives = ()\n                    scope_source = \"Internet room local-token match\"\n                elif local_alternatives:\n                    scoped_target = None\n                    scoped_alternatives = local_alternatives\n                    scope_source = \"Internet room local-token ambiguity\"\n                else:\n                    scoped = resolve_device_candidate(intent.target, internet_candidates)\n                    scoped_target = scoped.target\n                    scoped_alternatives = scoped.alternatives\n                    scope_source = \"Internet room fuzzy fallback\"\n'''
replace_once(rule, old_match, new_match)

old_summary = '''                    f\"{len(internet_candidates)} Internet-group candidates; \"\n                    f\"configured_aliases={len(self.internet_control_aliases)}; \"\n                    f\"source={scope_source}; \"\n'''
new_summary = '''                    f\"{len(internet_candidates)} Internet-group candidates; \"\n                    f\"configured_aliases={len(self.internet_control_aliases)}; \"\n                    f\"identity_source={identity_source}; \"\n                    f\"source={scope_source}; \"\n'''
replace_once(rule, old_summary, new_summary)

# Regression coverage mirrors the live Internet inventory and proves that a warm
# structural identity cache is enough; the slower manifest refresh must not run.
test_path = ROOT / "hubitat-mcp-ai/tests/test_relative_schedule_service.py"
test_text = test_path.read_text()
append = r'''

class WarmInternetIdentityMCP:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.device_reads: list[str] = []

    def peek_device_identities(self) -> list[dict[str, Any]]:
        return [
            {"id": "8101", "label": "Block Camera-G100-42EA", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8102", "label": "Block Camera-G100-7B37", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8103", "label": "Block Enamul-s-Tab-S9-FE", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8104", "label": "Block Google-Nest-Hub", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8105", "label": "Block Media-Google-Nest-Mini", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "6923", "label": "Block Media-Google-TV-Streamer", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8107", "label": "Block PC-NucBox-M6Ultra", "room": "Internet", "capabilities": ["Switch"]},
            {"id": "8108", "label": "Block Tab-S9-FE", "room": "Internet", "capabilities": ["Switch"]},
        ]

    async def get_cached_devices(self) -> list[dict[str, Any]]:
        self.refresh_calls += 1
        raise AssertionError("fresh identity cache should avoid manifest refresh")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if name == "hub_get_info":
            return result(name, arguments, {"timezone": "Europe/London"})
        if name == "hub_read_devices":
            label_filter = str((arguments.get("args") or {}).get("labelFilter") or "")
            self.device_reads.append(label_filter)
            if label_filter != "Block PC-NucBox-M6Ultra":
                raise AssertionError(f"unexpected target lookup: {label_filter!r}")
            return result(
                name,
                arguments,
                {
                    "success": True,
                    "devices": [
                        {
                            "id": "8107",
                            "label": "Block PC-NucBox-M6Ultra",
                            "name": "Block PC-NucBox-M6Ultra",
                            "room": "Internet",
                            "capabilities": ["Switch"],
                            "commands": ["on", "off"],
                        }
                    ],
                },
            )
        if name == "hub_read_rules":
            return result(name, arguments, {"success": True, "rules": []})
        raise AssertionError(f"Unexpected tool: {name} {arguments}")


@pytest.mark.asyncio
async def test_relative_block_m6_ultra_pc_matches_compact_reordered_internet_label_from_identity_cache() -> None:
    evidence: list[tuple[Any, ...]] = []
    mcp = WarmInternetIdentityMCP()
    service = RuleAuthoringService(
        mcp,
        lambda *args, **kwargs: evidence.append((args, kwargs)),
        now=lambda: datetime(2026, 10, 3, 10, 0, 0),
    )

    decision = await service.propose(
        "block M6 Ultra PC after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.message is None
    assert decision.target is not None
    assert decision.target["id"] == "8107"
    assert mcp.refresh_calls == 0
    assert mcp.device_reads == ["Block PC-NucBox-M6Ultra"]
    assert decision.actions[0]["args"]["addAction"] == {
        "capability": "runCommand",
        "deviceIds": ["8107"],
        "capabilityFilter": "Switch",
        "command": "off",
    }
    inventory_receipts = [
        item for item in evidence
        if item[0] and item[0][0] == "homebrain_device_inventory"
    ]
    assert inventory_receipts
    assert "identity_source=identity cache" in inventory_receipts[0][1]["summary"]
    assert "source=Internet room local-token match" in inventory_receipts[0][1]["summary"]


@pytest.mark.asyncio
async def test_internet_local_token_match_keeps_two_tab_controls_ambiguous() -> None:
    mcp = WarmInternetIdentityMCP()
    service = RuleAuthoringService(
        mcp,
        lambda *args, **kwargs: None,
        now=lambda: datetime(2026, 10, 3, 10, 0, 0),
    )

    decision = await service.propose(
        "block Tab S9 FE after 1 minute",
        available_gateways={RULE_MACHINE_GATEWAY},
    )

    assert decision.handled is True
    assert decision.actions == ()
    assert decision.message is not None
    assert "Possible matches" in decision.message
    assert "Block Enamul-s-Tab-S9-FE" in decision.message
    assert "Block Tab-S9-FE" in decision.message
    assert mcp.refresh_calls == 0
    assert mcp.device_reads == []
'''
if "test_relative_block_m6_ultra_pc_matches_compact_reordered_internet_label_from_identity_cache" in test_text:
    raise SystemExit("0.16.98 regression tests already present")
test_path.write_text(test_text.rstrip() + append + "\n")

# Release metadata.
replace_once(ROOT / "hubitat-mcp-ai/config.yaml", 'version: "0.16.97"', 'version: "0.16.98"')
replace_once(ROOT / "README.md", '| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.97 |', '| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.98 |')

addon_readme = ROOT / "hubitat-mcp-ai/README.md"
replace_once(addon_readme, 'Current add-on version: **0.16.97**.', 'Current add-on version: **0.16.98**.')
replace_once(
    addon_readme,
    '## Architecture\n\n0.16.97',
    '## Architecture\n\n0.16.98 keeps scheduled Internet target resolution authoritative to the Hubitat `Internet` room while making that room-local identity match tolerant of natural token order and compact model labels. For example, `M6 Ultra PC` deterministically matches `Block PC-NucBox-M6Ultra` only when that is the unique Internet-group token-subset match; ambiguous controls still fail closed. The path now reuses the longer-lived complete identity cache before refreshing the detailed device manifest, avoiding unnecessary slow refreshes when structural identity is already fresh. Global device matching, Internet `on`/`off` semantics, scheduler grammar, and one-time cleanup are unchanged.\n\n0.16.97',
)

index = ROOT / "hubitat-mcp-ai/CHANGELOG-INDEX.md"
replace_once(
    index,
    '## Current release\n\n- [0.16.97](CHANGELOG-0.16.97.md)\n\n## Recent performance releases\n\n- [0.16.96]',
    '## Current release\n\n- [0.16.98](CHANGELOG-0.16.98.md)\n\n## Recent performance releases\n\n- [0.16.97](CHANGELOG-0.16.97.md)\n\n- [0.16.96]',
)

changelog = ROOT / "hubitat-mcp-ai/CHANGELOG-0.16.98.md"
if changelog.exists():
    raise SystemExit("CHANGELOG-0.16.98.md already exists")
changelog.write_text('''# Hubitat MCP AI 0.16.98\n\n## Internet-group local identity matching\n\n- Scheduled Internet access remains strictly scoped to the authoritative Hubitat `Internet` room/group or an explicit configured Internet alias.\n- Adds a conservative room-local token-subset matcher before the existing fuzzy fallback. It tolerates natural token reordering and compact/camel model labels such as `M6 Ultra PC` versus `Block PC-NucBox-M6Ultra`.\n- Every identifying token supplied by the user must occur in the candidate identity after bounded normalization; extra candidate tokens are allowed.\n- Multiple matching Internet controls remain ambiguous and are surfaced for clarification rather than guessed.\n- The global device resolver is unchanged.\n\n## Identity-cache latency\n\n- Scheduled Internet resolution now reuses `peek_device_identities()` when a complete identity snapshot is still within the identity TTL.\n- It falls back to one bounded manifest/identity refresh only when no fresh structural identity cache exists.\n- This avoids expiring the short live-device cache forcing a multi-second manifest refresh when structural room/name/capability identity is already fresh.\n- The selected control surface is still re-read by authoritative label and its real `on`/`off` Switch command is verified before a Rule Machine proposal is queued.\n\n## Regression coverage\n\n- `M6 Ultra PC` uniquely resolves to `Block PC-NucBox-M6Ultra` inside the Internet room.\n- A warm identity cache prevents a manifest refresh on that path.\n- `Tab S9 FE` remains ambiguous when both `Block Enamul-s-Tab-S9-FE` and `Block Tab-S9-FE` satisfy the same scoped token identity.\n''')
