from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:160]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"pattern not unique in {path}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1))


# RuleAuthoringService: resolve the authoritative Hubitat timezone before
# materialising any one-time absolute timestamp. The first lightweight intent
# pass is only a grammar gate; the second pass owns the actual timestamp.
path = "hubitat-mcp-ai/rootfs/app/rule_authoring_service.py"
replace_once(path, "from datetime import datetime, timedelta\n", "from datetime import datetime, timedelta, timezone\n")
replace_once(
    path,
    "from device_target_resolver import normalized_name, resolve_device_candidate\nfrom mcp_client import HubitatMCPClient\n",
    "from device_target_resolver import normalized_name, resolve_device_candidate\nfrom hub_timezone import HubTimezoneResolver\nfrom mcp_client import HubitatMCPClient\n",
)
replace_once(
    path,
    "        self._record_evidence = record_evidence\n        self._now = now\n        self.internet_control_aliases = self._parse_internet_control_aliases(\n",
    "        self._record_evidence = record_evidence\n        self._now = now\n        self._hub_timezone = HubTimezoneResolver(mcp_client, record_evidence)\n        self.internet_control_aliases = self._parse_internet_control_aliases(\n",
)
replace_once(
    path,
    "    def _intent(self, prompt: str) -> _ScheduleIntent | None:\n",
    "    def _intent(\n        self, prompt: str, *, now: datetime | None = None\n    ) -> _ScheduleIntent | None:\n",
)
replace_once(path, "            return self._relative_intent(text, relative)\n", "            return self._relative_intent(text, relative, now=now)\n")
replace_once(path, "        return self._single_intent(text, daily=daily)\n", "        return self._single_intent(text, daily=daily, now=now)\n")
replace_once(
    path,
    "    def _relative_intent(\n        self,\n        text: str,\n        relative: re.Match[str],\n    ) -> _ScheduleIntent | None:\n",
    "    def _relative_intent(\n        self,\n        text: str,\n        relative: re.Match[str],\n        *,\n        now: datetime | None = None,\n    ) -> _ScheduleIntent | None:\n",
)
replace_once(
    path,
    "            trigger = self._now().replace(microsecond=0) + timedelta(minutes=minutes)\n",
    "            current = now if now is not None else self._now()\n            trigger = current.replace(microsecond=0) + timedelta(minutes=minutes)\n",
)
replace_once(
    path,
    "    def _single_intent(self, text: str, *, daily: bool) -> _ScheduleIntent | None:\n",
    "    def _single_intent(\n        self, text: str, *, daily: bool, now: datetime | None = None\n    ) -> _ScheduleIntent | None:\n",
)
replace_once(
    path,
    "                    at_time if daily else self._next_occurrence_iso(at_time, self._now())\n",
    "                    at_time\n                    if daily\n                    else self._next_occurrence_iso(\n                        at_time, now if now is not None else self._now()\n                    )\n",
)
replace_once(
    path,
    "        intent = self._intent(prompt)\n        if intent is None:\n            return RuleAuthoringDecision(False)\n        if RULE_MACHINE_GATEWAY not in available_gateways:\n            return RuleAuthoringDecision(False)\n",
    "        # First pass is a no-I/O grammar gate. Only genuine deterministic\n        # scheduling requests pay for authoritative timezone resolution.\n        intent = self._intent(prompt)\n        if intent is None:\n            return RuleAuthoringDecision(False)\n        if RULE_MACHINE_GATEWAY not in available_gateways:\n            return RuleAuthoringDecision(False)\n\n        hub_now, _timezone_name, _timezone_source = (\n            await self._hub_timezone.now_in_hub_timezone(\n                lambda: self._now()\n                if self._now().tzinfo is not None\n                else self._now().replace(tzinfo=timezone.utc)\n            )\n        )\n        intent = self._intent(prompt, now=hub_now)\n        if intent is None:\n            return RuleAuthoringDecision(False)\n",
)

# Correct confirmation wording: adding a pauseRule action configures future
# self-pause; it does not prove that the future trigger has already fired.
path = "hubitat-mcp-ai/rootfs/app/confirmed_action_coordinator.py"
replace_once(
    path,
    '                        f"- **{name}** was paused immediately after its "\n                        "one-time trigger so it cannot fire again."\n',
    '                        f"- **{name}** was configured to pause itself after its "\n                        "one-time trigger executes, so it cannot fire again."\n',
)
replace_once(
    path,
    '                    f"- **{name}** was created but could not be confirmed "\n                    f"paused afterward: {detail}. It may still fire again -- "\n                    "check Rule Machine directly."\n',
    '                    f"- **{name}** was created but its self-pause action "\n                    f"could not be confirmed: {detail}. Check Rule Machine directly."\n',
)

# Regression: a UTC container clock must be converted through the hub timezone
# before the relative one-time timestamp is materialised.
Path("hubitat-mcp-ai/tests/test_rule_authoring_hub_timezone.py").write_text('''from datetime import datetime, timezone\n\nimport pytest\n\nfrom mcp_client import MCPToolResult\nfrom rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService\n\n\nclass FakeMCP:\n    async def call_tool(self, name, arguments):\n        if name == "hub_get_info":\n            return MCPToolResult(\n                name=name,\n                arguments=arguments,\n                raw={},\n                text="",\n                data={"success": True, "timeZone": "Europe/London"},\n            )\n        raise RuntimeError(name)\n\n\n@pytest.mark.asyncio\nasync def test_relative_schedule_uses_hub_timezone_not_utc_container_clock():\n    service = RuleAuthoringService(\n        FakeMCP(),\n        lambda *_args, **_kwargs: None,\n        now=lambda: datetime(2026, 10, 3, 8, 42, 0, tzinfo=timezone.utc),\n    )\n\n    # Avoid exercising device/rule I/O: intercept the second, authoritative\n    # intent pass by replacing the resolver-facing portion after timezone work.\n    hub_now, name, source = await service._hub_timezone.now_in_hub_timezone(service._now)\n    intent = service._intent("block Google TV after 1 min", now=hub_now)\n\n    assert name == "Europe/London"\n    assert source == "hub_get_info"\n    assert hub_now.isoformat().startswith("2026-10-03T09:42:00+01:00")\n    assert intent is not None\n    assert intent.start_time == "2026-10-03T09:43:00"\n\n\ndef test_one_time_clock_uses_supplied_hub_local_now_for_next_occurrence():\n    service = RuleAuthoringService(\n        object(),\n        lambda *_args, **_kwargs: None,\n        now=lambda: datetime(2026, 10, 3, 8, 42, 0, tzinfo=timezone.utc),\n    )\n    local_now = datetime.fromisoformat("2026-10-03T09:42:00+01:00")\n    intent = service._intent("turn on Hallway Light 1 at 10am", now=local_now)\n    assert intent is not None\n    assert intent.start_time == "2026-10-03T10:00:00"\n''')

# Release metadata.
replace_once("hubitat-mcp-ai/config.yaml", 'version: "0.16.95"\n', 'version: "0.16.96"\n')
replace_once("README.md", "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.95 |", "| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.96 |")
replace_once("hubitat-mcp-ai/README.md", "Current add-on version: **0.16.95**.", "Current add-on version: **0.16.96**.")
replace_once(
    "hubitat-mcp-ai/README.md",
    "## Architecture\n\n",
    "## Architecture\n\n0.16.96 makes one-time Rule Machine scheduling use the authoritative Hubitat location timezone before converting relative or bare-clock requests into dated `atTime` values. This fixes UTC-container drift such as a BST request at 09:42 being authored for 08:42. The existing `HubTimezoneResolver` supplies an IANA timezone and therefore follows GMT/BST and other DST transitions without a hard-coded offset. Confirmation wording also now states that HomeBrain configured the future self-pause action rather than claiming the rule had already fired and paused.\n\n",
)
replace_once(
    "hubitat-mcp-ai/CHANGELOG-INDEX.md",
    "## Current release\n\n- [0.16.95](CHANGELOG-0.16.95.md)\n\n## Recent performance releases\n",
    "## Current release\n\n- [0.16.96](CHANGELOG-0.16.96.md)\n\n## Recent performance releases\n\n- [0.16.95](CHANGELOG-0.16.95.md)\n",
)
Path("hubitat-mcp-ai/CHANGELOG-0.16.96.md").write_text('''# Hubitat MCP AI 0.16.96\n\n## Hub-local one-time scheduling\n\n- One-time relative schedules now resolve `now` through the authoritative Hubitat IANA timezone before calculating a dated Rule Machine `atTime`.\n- Bare one-time clock requests use the same hub-local clock when deciding whether the next occurrence is today or tomorrow.\n- The fix reuses `HubTimezoneResolver`, so DST changes such as GMT/BST are handled by timezone data rather than a fixed offset.\n- Non-scheduling requests do not pay for timezone lookup; a lightweight grammar pass remains the no-I/O gate.\n- The timezone value is cached by the existing resolver.\n\n## Accurate confirmation wording\n\n- Successful `pauseRule` authoring is reported as **configured to pause itself after the one-time trigger executes**.\n- HomeBrain no longer claims the future trigger has already fired or that the rule is already paused merely because the self-pause action was successfully added.\n''')
