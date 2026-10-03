from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:180]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"pattern not unique in {path}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1))


# The duplicate-name regression is about name uniqueness, not the retired
# self-pause follow-up. One-time authoring now emits one create action.
replace_once(
    "tests/test_rule_authoring_service.py",
    '''    assert decision.rule_names == ("Turn on Bedroom 1 Lamp (One-time 2026-08-07 07:00)",)\n    assert len(decision.actions) == 2\n    assert decision.actions[0]["args"]["addTrigger"]["atTime"] == "2026-08-07T07:00:00"\n''',
    '''    assert decision.rule_names == ("Turn on Bedroom 1 Lamp (One-time 2026-08-07 07:00)",)\n    assert len(decision.actions) == 1\n    assert decision.actions[0]["args"]["addTrigger"]["atTime"] == "2026-08-07T07:00:00"\n''',
)

old_test = '''@pytest.mark.asyncio\nasync def test_one_time_proposal_queues_a_self_pause_followup_action():\n    """A one-time rule proposal must queue exactly two actions: the create,\n    and a follow-up edit that pauses the rule via Hubitat's native\n    pauseRule capability -- a safety net in case the "Certain Time (and\n    optional date)" trigger's underlying scheduler job (observed live to\n    carry a "recurring": true label despite the dated trigger) ever does\n    fire again. The follow-up can't know the real appId yet (the rule\n    doesn't exist until the first action runs), so both its edit target and\n    its own pause target use NEW_RULE_ID_TOKEN, resolved later by\n    ConfirmedActionCoordinator.\n    """\n\n    lamp = {\n        "id": "42",\n        "label": "Bedroom 1 Lamp",\n        "commands": ["on", "off"],\n        "capabilities": ["Switch", "Light"],\n    }\n    fixed_now = datetime(2026, 8, 7, 6, 0, 0)\n    service = RuleAuthoringService(RuleMCP([lamp]), recorder, now=lambda: fixed_now)\n\n    decision = await service.propose(\n        "turn on bedroom 1 lamp at 7am",\n        available_gateways={RULE_MACHINE_GATEWAY},\n    )\n\n    assert len(decision.actions) == 2\n    create, pause = decision.actions\n    assert create["args"]["addTrigger"]["atTime"] == "2026-08-07T07:00:00"\n    assert pause["args"]["appId"] == NEW_RULE_ID_TOKEN\n    assert pause["args"]["addAction"] == {\n        "capability": "pauseRule",\n        "action": "pause",\n        "ruleIds": [NEW_RULE_ID_TOKEN],\n    }\n\n\n'''
new_test = '''@pytest.mark.asyncio\nasync def test_one_time_proposal_queues_only_create_for_nightly_cleanup():\n    """One-time authoring creates the dated rule only.\n\n    Expiry is owned by the guarded 01:00 HomeBrain cleanup service, so a\n    proposal must not append a pauseRule edit to the newly-created rule.\n    """\n\n    lamp = {\n        "id": "42",\n        "label": "Bedroom 1 Lamp",\n        "commands": ["on", "off"],\n        "capabilities": ["Switch", "Light"],\n    }\n    fixed_now = datetime(2026, 8, 7, 6, 0, 0)\n    service = RuleAuthoringService(RuleMCP([lamp]), recorder, now=lambda: fixed_now)\n\n    decision = await service.propose(\n        "turn on bedroom 1 lamp at 7am",\n        available_gateways={RULE_MACHINE_GATEWAY},\n    )\n\n    assert len(decision.actions) == 1\n    create = decision.actions[0]\n    assert create["args"]["addTrigger"]["atTime"] == "2026-08-07T07:00:00"\n    assert create["args"]["addAction"]["capability"] == "runCommand"\n    assert create["args"]["addAction"]["command"] == "on"\n    assert create["args"]["addAction"]["capability"] != "pauseRule"\n\n\n'''
replace_once("tests/test_rule_authoring_service.py", old_test, new_test)

# End-to-end prompt -> confirm regression: confirmation now contains only the
# create write. A pause write would be a regression against the new lifecycle.
replace_once(
    "tests/_entity_first_orchestrator_cases.py",
    '''async def test_one_time_rule_end_to_end_creates_then_self_pauses():\n    """Full round trip for a one-time schedule request: propose -> confirm\n    -> the coordinator resolves the create action's real appId and injects\n    it into the queued self-pause follow-up before executing it. Regression\n    coverage for the auto-pause feature at the level the user actually\n    interacts with it (a plain prompt, then "confirm"), not just the\n    coordinator's substitution mechanics in isolation.\n    """\n''',
    '''async def test_one_time_rule_end_to_end_creates_without_self_pause():\n    """Full prompt -> confirm path creates one dated rule and no pause edit.\n\n    Nightly cleanup owns expiry, so confirmation must not enqueue or execute a\n    second Rule Machine write for pauseRule.\n    """\n''',
)
replace_once(
    "tests/_entity_first_orchestrator_cases.py",
    '''            if name == "hub_manage_rule_machine":\n                assert arguments["args"]["confirm"] is True\n                is_pause = (\n                    arguments["args"].get("addAction", {}).get("capability")\n                    == "pauseRule"\n                )\n                if is_pause:\n                    # The real fix under test: the placeholder must already\n                    # be gone by the time this reaches the fake "hub".\n                    assert arguments["args"]["appId"] == "9001"\n                    assert arguments["args"]["addAction"]["ruleIds"] == ["9001"]\n                    return MCPToolResult(\n                        name, arguments, {}, "",\n                        {"success": True, "appId": 9001, "health": {"ok": True}},\n                    )\n                return MCPToolResult(\n                    name, arguments, {}, "",\n                    {"success": True, "appId": 9001, "health": {"ok": True}},\n                )\n''',
    '''            if name == "hub_manage_rule_machine":\n                assert arguments["args"]["confirm"] is True\n                assert (\n                    arguments["args"].get("addAction", {}).get("capability")\n                    != "pauseRule"\n                ), "nightly cleanup owns expiry; self-pause must not be queued"\n                return MCPToolResult(\n                    name, arguments, {}, "",\n                    {"success": True, "appId": 9001, "health": {"ok": True}},\n                )\n''',
)
replace_once(
    "tests/_entity_first_orchestrator_cases.py",
    '''    assert propose_outcome.confirmation_required is True\n    assert propose_outcome.confirmation_count == 2\n\n    outcome = await agent.process_user_request_result("confirm", session_id="one-time-e2e")\n\n    assert "Created **Turn on Livingroom Light 1" in outcome.message\n    assert "appId: 9001" in outcome.message\n    assert "was configured to pause itself after its one-time trigger executes" in outcome.message\n    assert ai.requests == []\n''',
    '''    assert propose_outcome.confirmation_required is True\n    assert propose_outcome.confirmation_count == 1\n\n    outcome = await agent.process_user_request_result("confirm", session_id="one-time-e2e")\n\n    assert "Created **Turn on Livingroom Light 1" in outcome.message\n    assert "appId: 9001" in outcome.message\n    assert "pause itself" not in outcome.message\n    writes = [arguments for name, arguments in mcp.calls if name == "hub_manage_rule_machine"]\n    assert len(writes) == 1\n    assert writes[0]["args"]["addAction"]["capability"] == "runCommand"\n    assert ai.requests == []\n''',
)
