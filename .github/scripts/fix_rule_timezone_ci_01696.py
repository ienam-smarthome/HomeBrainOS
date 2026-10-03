from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:180]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"pattern not unique in {path}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1))


# Recurring schedules already use bare HH:MM Rule Machine triggers and do not
# need a dated local 'now'. Only one-time schedules should pay for hub timezone.
path = "hubitat-mcp-ai/rootfs/app/rule_authoring_service.py"
old = '''        hub_now, _timezone_name, _timezone_source = (
            await self._hub_timezone.now_in_hub_timezone(
                lambda: self._now()
                if self._now().tzinfo is not None
                else self._now().replace(tzinfo=timezone.utc)
            )
        )
        intent = self._intent(prompt, now=hub_now)
        if intent is None:
            return RuleAuthoringDecision(False)
'''
new = '''        if not intent.recurring:
            runtime_now = self._now()
            if runtime_now.tzinfo is None:
                # The Home Assistant add-on container runs UTC in production.
                # Treat a naive injected/runtime clock as UTC before converting
                # it through the authoritative Hubitat location timezone.
                runtime_now = runtime_now.replace(tzinfo=timezone.utc)
            hub_now, _timezone_name, _timezone_source = (
                await self._hub_timezone.now_in_hub_timezone(lambda: runtime_now)
            )
            intent = self._intent(prompt, now=hub_now)
            if intent is None:
                return RuleAuthoringDecision(False)
'''
replace_once(path, old, new)

# Update existing regression expectations to the evidence-safe wording.
path = "tests/test_confirmed_action_coordinator.py"
replace_once(
    path,
    '''        "**Turn on Bedroom 1 Lamp (One-time 2026-08-07)** was paused "
        "immediately after its one-time trigger so it cannot fire again."
''',
    '''        "**Turn on Bedroom 1 Lamp (One-time 2026-08-07)** was configured to "
        "pause itself after its one-time trigger executes, so it cannot fire again."
''',
)
replace_once(
    path,
    '''        "**Turn on Bedroom 1 Lamp (One-time 2026-08-07)** was created but "
        "could not be confirmed paused afterward: Rule 4171 not found."
''',
    '''        "**Turn on Bedroom 1 Lamp (One-time 2026-08-07)** was created but its "
        "self-pause action could not be confirmed: Rule 4171 not found."
''',
)

path = "tests/_entity_first_orchestrator_cases.py"
replace_once(
    path,
    '    assert "was paused immediately after its one-time trigger" in outcome.message\n',
    '    assert "was configured to pause itself after its one-time trigger executes" in outcome.message\n',
)
