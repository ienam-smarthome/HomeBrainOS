from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

agent_path = ROOT / "hubitat-mcp-ai/rootfs/app/homebrain_agent.py"
text = agent_path.read_text(encoding="utf-8")
text = text.replace(
    "from device_query_service import DeviceQueryService\nfrom device_target_resolver import resolve_capable_device_candidate\n",
    "from device_query_service import DeviceQueryService\nfrom device_state_summary import room_name\nfrom device_target_resolver import resolve_device_candidate\n",
)
text = text.replace(
    "from request_metrics import RequestMetrics\n",
    "from request_metrics import RequestMetrics\nfrom rule_authoring_service import RuleAuthoringService\n",
)
pattern = re.compile(
    r"    async def _internet_access_outcome\(\n.*?\n    async def _resolve_pending_confirmation\(",
    re.S,
)
replacement = '''    async def _internet_access_outcome(
        self, target_name: str, command: str, *, session_key: str
    ) -> AgentOutcome:
        """Execute immediate Internet access against authoritative room controls.

        ``blockInternet`` / ``allowInternet`` are semantic intent labels only.
        Hubitat devices assigned to the authoritative ``Internet`` room are
        ordinary Switch controls: ``off`` means Internet blocked and ``on``
        means Internet allowed. Resolve inside that room first, verify the real
        Switch command on the selected device, then execute and verify the
        literal ``switch`` state. Never infer Internet semantics from a
        ``Block ...`` label prefix.
        """

        async def operation() -> str:
            started = time.monotonic()
            identities: list[dict[str, Any]] = []
            identity_source = "identity refresh"
            peek = getattr(self.mcp, "peek_device_identities", None)
            if callable(peek):
                try:
                    identities = [
                        dict(item) for item in (peek() or []) if isinstance(item, dict)
                    ]
                except Exception:
                    identities = []
                if identities:
                    identity_source = "identity cache"
                    self.request_metrics.increment("identity_cache_hit")
            if not identities:
                reader = getattr(self.mcp, "get_cached_devices", None)
                if not callable(reader):
                    reader = getattr(self.mcp, "get_device_identities", None)
                if not callable(reader):
                    return "I could not read the authoritative Internet device group."
                try:
                    identities = [
                        dict(item)
                        for item in (await reader() or [])
                        if isinstance(item, dict)
                    ]
                    self.request_metrics.increment("identity_refresh")
                except Exception as exc:
                    return f"I could not read the device list: {exc}"

            internet_candidates = [
                item
                for item in identities
                if str(room_name(item) or "").casefold() == "internet"
            ]
            scoped_target, scoped_alternatives = RuleAuthoringService._internet_local_target(
                target_name, internet_candidates
            )
            scope_source = "Internet room local-token match"
            if scoped_target is None and not scoped_alternatives:
                scoped = resolve_device_candidate(target_name, internet_candidates)
                scoped_target = scoped.target
                scoped_alternatives = scoped.alternatives
                scope_source = "Internet room fuzzy fallback"
            elif scoped_target is None:
                scope_source = "Internet room local-token ambiguity"

            self.evidence.record(
                "homebrain_device_inventory",
                {"group": "Internet"},
                success=scoped_target is not None,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=(
                    f"{len(internet_candidates)} Internet-group candidates; "
                    f"identity_source={identity_source}; source={scope_source}; "
                    f"target={'resolved' if scoped_target is not None else 'unresolved'}"
                ),
                supports_live_claim=True,
                evidence_kind="deterministic_internet_target_scope",
            )

            if scoped_target is None:
                if scoped_alternatives:
                    alternatives = list(scoped_alternatives)
                    self._choices.set(alternatives)
                    self.request_metrics.increment("device_resolution_ambiguous")
                    return self._choice_message(alternatives)
                return (
                    f'I could not match **{target_name}** to a device in the '
                    "authoritative **Internet** group. Nothing was sent."
                )

            semantic_block = command.casefold() == "blockinternet"
            real_command = "off" if semantic_block else "on"
            expected_switch = real_command
            expected_access = "blocked" if semantic_block else "allowed"
            selected_label = str(
                scoped_target.get("label") or scoped_target.get("name") or target_name
            ).strip()

            # Re-read the selected control surface by authoritative label and
            # verify the real command immediately before the write.
            resolver = DeviceQueryService(self.mcp, self.evidence.record)
            resolved = await resolver.resolve_device(
                {"name": selected_label, "required_command": real_command}
            )
            data = resolved.data if isinstance(resolved.data, dict) else {}
            device = data.get("target") if isinstance(data.get("target"), dict) else None
            if device is None:
                return (
                    f"I matched **{selected_label}** as the Internet control, but it "
                    f"does not currently advertise the required Switch command: {real_command}. "
                    "Nothing was sent."
                )

            device_id = str(device.get("id") or device.get("deviceId") or "")
            label = str(device.get("label") or device.get("name") or selected_label)
            if not device_id:
                return f"The resolved device **{label}** has no stable Hubitat ID."

            call_started = time.monotonic()
            result = await self.mcp.call_tool(
                "hub_manage_devices",
                {
                    "tool": "hub_call_device_command",
                    "args": {
                        "deviceId": device_id,
                        "command": real_command,
                        "waitFor": {
                            "attribute": "switch",
                            "expectedValue": expected_switch,
                            "timeoutMs": 5000,
                        },
                    },
                },
            )
            command_success = self._tool_succeeded(result)
            wait_for = result.data.get("waitFor") if isinstance(result.data, dict) else None
            verified = bool(wait_for.get("converged")) if isinstance(wait_for, dict) else False
            self.evidence.record(
                "hub_manage_devices",
                {
                    "tool": "hub_call_device_command",
                    "args": {"deviceId": device_id, "command": real_command},
                },
                success=command_success and verified,
                elapsed_ms=round((time.monotonic() - call_started) * 1000),
                summary=(
                    f"Internet {expected_access}: {real_command} {label}: "
                    f"{'verified' if verified else 'sent' if command_success else 'failed'}"
                ),
                evidence_kind="device_command_result",
            )
            if command_success and verified:
                self._selected_devices[session_key] = label
                verb_past = "blocked" if semantic_block else "unblocked"
                return f"{label} internet access {verb_past}."
            if command_success:
                return (
                    f"Sent the {real_command} command to {label}, but could not verify "
                    f"Internet access became {expected_access} within 5 seconds."
                )
            verb = "block" if semantic_block else "allow"
            return (
                f"Could not {verb} internet access for {label}: "
                f"{result.text or 'unknown error'}"
            )

        return await self._direct_outcome(operation, request_class="write")

    async def _resolve_pending_confirmation('''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"homebrain_agent replacement count={count}")
agent_path.write_text(text, encoding="utf-8")

# Update the live-shape regression fixture to the authoritative Internet-room
# Switch contract and add the exact M6 Ultra live phrase.
test_path = ROOT / "tests/test_homebrain_agent.py"
t = test_path.read_text(encoding="utf-8")
t = t.replace(
'''# Real device shapes pulled live from the hub this bug was found against:
# two devices both plausibly named "tv" -- a plain power-switch labelled
# exactly "TV", and a separate network-integration device labelled "Block
# Google-TV-Streamer" that is the only one of the two that actually
# advertises blockInternet/allowInternet.''',
'''# Internet controls are ordinary Switch devices in the authoritative
# Internet room. A similarly named ordinary device outside that room must
# never steal block/unblock intent.''')
t = t.replace('''TV_STREAMER_BLOCK_DEVICE = {
    "id": "6923", "label": "Block Google-TV-Streamer", "name": "Cudy Device-192.168.1.108",
    "roomName": "Multimedia",
    "commands": [
        "addTime", "allowInternet", "blockInternet", "off", "on", "refresh",
        "resetUsage", "setDeviceIP", "setDeviceMAC",
    ],
}
''', '''TV_STREAMER_BLOCK_DEVICE = {
    "id": "6923", "label": "Block Google-TV-Streamer", "name": "Cudy Device-192.168.1.108",
    "roomName": "Internet",
    "capabilities": ["Switch"],
    "commands": ["off", "on", "refresh"],
}
M6_BLOCK_DEVICE = {
    "id": "6999", "label": "Block PC-NucBox-M6Ultra", "name": "Cudy Device-M6Ultra",
    "roomName": "Internet",
    "capabilities": ["Switch"],
    "commands": ["off", "on", "refresh"],
}
''')
t = t.replace(
'''    """Fake MCP exposing exactly the two real device shapes above, plus
    hub_call_device_command handling for block/allowInternet.
    """

    def __init__(self, *, converged: bool = True) -> None:
        self.devices = [TV_SWITCH_DEVICE, TV_STREAMER_BLOCK_DEVICE]
''',
'''    """Fake MCP exposing an ordinary TV plus authoritative Internet switches."""

    def __init__(self, *, converged: bool = True) -> None:
        self.devices = [TV_SWITCH_DEVICE, TV_STREAMER_BLOCK_DEVICE, M6_BLOCK_DEVICE]
''')
t = t.replace(
'''    async def get_cached_devices(self) -> list[dict[str, object]]:
        return list(self.devices)

    async def call_tool(self, gateway: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_call_device_command":
''',
'''    def peek_device_identities(self) -> list[dict[str, object]]:
        return list(self.devices)

    async def get_cached_devices(self) -> list[dict[str, object]]:
        return list(self.devices)

    async def call_tool(self, gateway: str, arguments: dict[str, object]) -> MCPToolResult:
        self.calls.append((gateway, arguments))
        if gateway == "hub_read_devices" and arguments.get("tool") == "hub_list_devices":
            args = arguments.get("args") or {}
            label_filter = str(args.get("labelFilter") or "").casefold()
            devices = [
                item for item in self.devices
                if not label_filter
                or label_filter in str(item.get("label") or "").casefold()
                or label_filter in str(item.get("name") or "").casefold()
            ]
            return MCPToolResult(gateway, arguments, {}, "ok", {"success": True, "devices": devices})
        if arguments.get("tool") == "hub_call_device_command":
''')
t = t.replace(
'''    This must now resolve to the device that actually advertises
    blockInternet (id 6923, not the switch at 4221), dispatch the real
    command, and never touch the model at all.''',
'''    This must resolve inside the authoritative Internet room (id 6923,
    not the ordinary TV switch at 4221), dispatch real Switch off, and
    never touch the model at all.''')
t = t.replace('''    assert dispatch_calls[0]["args"]["command"] == "blockInternet"
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "blocked"
''', '''    assert dispatch_calls[0]["args"]["command"] == "off"
    assert dispatch_calls[0]["args"]["waitFor"]["attribute"] == "switch"
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "off"
''')
t = t.replace('''    assert dispatch_calls[0]["args"]["command"] == "allowInternet"
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "allowed"
''', '''    assert dispatch_calls[0]["args"]["command"] == "on"
    assert dispatch_calls[0]["args"]["waitFor"]["attribute"] == "switch"
    assert dispatch_calls[0]["args"]["waitFor"]["expectedValue"] == "on"
''')
anchor = '''@pytest.mark.asyncio
async def test_unconverged_block_reports_uncertainty_not_silent_success() -> None:
'''
extra = '''@pytest.mark.asyncio
async def test_live_unblock_m6_ultra_pc_uses_internet_room_switch_on() -> None:
    mcp = InternetAccessMCP(converged=True)
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result(
        "unblock M6 ultra PC", session_id="unblock-m6-live-regression"
    )

    assert outcome.message == "Block PC-NucBox-M6Ultra internet access unblocked."
    dispatch_calls = [
        args for _, args in mcp.calls if args.get("tool") == "hub_call_device_command"
    ]
    assert len(dispatch_calls) == 1
    assert dispatch_calls[0]["args"]["deviceId"] == "6999"
    assert dispatch_calls[0]["args"]["command"] == "on"
    assert dispatch_calls[0]["args"]["waitFor"] == {
        "attribute": "switch", "expectedValue": "on", "timeoutMs": 5000
    }


'''
if extra not in t:
    t = t.replace(anchor, extra + anchor)
t = t.replace('''    assert "could not find a device that supports blocking internet access" in outcome.message
''', '''    assert "authoritative **Internet** group" in outcome.message
''')
test_path.write_text(t, encoding="utf-8")

# Release metadata/docs.
config = ROOT / "hubitat-mcp-ai/config.yaml"
c = config.read_text(encoding="utf-8").replace('version: "0.16.98"', 'version: "0.16.99"', 1)
config.write_text(c, encoding="utf-8")

root_readme = ROOT / "README.md"
r = root_readme.read_text(encoding="utf-8").replace("| 0.16.98 | Maintained |", "| 0.16.99 | Maintained |", 1)
root_readme.write_text(r, encoding="utf-8")

readme = ROOT / "hubitat-mcp-ai/README.md"
r = readme.read_text(encoding="utf-8")
r = r.replace("Current add-on version: **0.16.98**.", "Current add-on version: **0.16.99**.", 1)
marker = "## Architecture\n\n"
entry = (
    "0.16.99 aligns immediate Internet block/unblock with the authoritative Internet-room Switch semantics already used by scheduled control. Semantic `blockInternet`/`allowInternet` intent is now compiled to real `off`/`on`, target resolution stays inside the Hubitat `Internet` room, natural names such as `M6 Ultra PC` use the same conservative room-local token matching, and verification waits for literal `switch=off/on`. The model and synthetic Internet commands are no longer involved in this immediate path.\n\n"
)
if entry not in r:
    r = r.replace(marker, marker + entry, 1)
readme.write_text(r, encoding="utf-8")

index = ROOT / "hubitat-mcp-ai/CHANGELOG-INDEX.md"
i = index.read_text(encoding="utf-8")
i = i.replace("- [0.16.98](CHANGELOG-0.16.98.md)", "- [0.16.99](CHANGELOG-0.16.99.md)", 1)
i = i.replace("## Recent performance releases\n\n", "## Recent performance releases\n\n- [0.16.98](CHANGELOG-0.16.98.md)\n\n", 1)
index.write_text(i, encoding="utf-8")

changelog = ROOT / "hubitat-mcp-ai/CHANGELOG-0.16.99.md"
changelog.write_text('''# Hubitat MCP AI 0.16.99

## Immediate Internet block/unblock semantics

- Immediate `block` / `unblock` / `allow internet` requests now use the same authoritative Hubitat `Internet` room contract as scheduled Internet control.
- Semantic `blockInternet` is compiled to real Switch `off`; semantic `allowInternet` is compiled to real Switch `on`.
- The selected device is re-read by authoritative label and must advertise the real `off`/`on` command immediately before the write.
- Verification waits for the literal `switch` attribute to converge to `off`/`on`; it no longer depends on a synthetic `internetAccess` attribute.
- Natural room-local identity matching covers the live `unblock M6 ultra PC` -> `Block PC-NucBox-M6Ultra` case without changing the global device resolver.
- Ambiguous or missing Internet-room targets fail closed; ordinary similarly named devices outside the Internet room cannot win.
- Fresh structural identity cache is reused first, preserving the low-latency path introduced in 0.16.98.

## Regression coverage

- Immediate TV block sends `off`, not `blockInternet`.
- Immediate TV allow sends `on`, not `allowInternet`.
- Exact live phrase `unblock M6 ultra PC` resolves the Internet-room M6 control and sends verified `on`.
- Scheduled requests remain handed to RuleAuthoringService unchanged.
''', encoding="utf-8")

# Remove the one-shot patch files from the resulting release commit.
for rel in [".github/scripts/apply_0_16_99.py", ".github/workflows/apply_0_16_99.yml"]:
    p = ROOT / rel
    if p.exists():
        p.unlink()
