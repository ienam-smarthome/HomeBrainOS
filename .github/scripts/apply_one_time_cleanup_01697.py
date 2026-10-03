from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:180]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"pattern not unique in {path}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1))


# Rule authoring: one-time rules are cleaned up nightly; do not append a
# self-pause action that the live hub did not reliably execute.
replace_once(
    "hubitat-mcp-ai/rootfs/app/rule_authoring_service.py",
    '''            actions = (\n                (create_action, self._self_pause_action())\n                if not intent.recurring\n                else (create_action,)\n            )\n''',
    '''            # One-time rules are deliberately left with only their dated\n            # trigger and device action. The nightly HomeBrain cleanup removes\n            # expired generated rules after the safety grace period; self-pause\n            # proved unreliable on the live hub and is no longer required.\n            actions = (create_action,)\n''',
)

# App wiring/config defaults.
replace_once(
    "hubitat-mcp-ai/rootfs/app/app.py",
    'from mcp_client import HubitatMCPClient\n',
    'from mcp_client import HubitatMCPClient\nfrom one_time_rule_cleanup import OneTimeRuleCleanupScheduler, OneTimeRuleCleanupService\n',
)
replace_once(
    "hubitat-mcp-ai/rootfs/app/app.py",
    '        "morning_health_check_time": "07:00",\n',
    '        "morning_health_check_time": "07:00",\n        "one_time_rule_cleanup_enabled": True,\n        "one_time_rule_cleanup_time": "01:00",\n        "one_time_rule_cleanup_grace_minutes": 10,\n',
)
replace_once(
    "hubitat-mcp-ai/rootfs/app/app.py",
    '''health_scheduler = MorningHealthScheduler(\n    health_audit,\n    enabled=_bool(OPTIONS.get("morning_health_check_enabled"), True),\n    daily_time=str(OPTIONS.get("morning_health_check_time") or "07:00"),\n    local_now=_health_scheduler_now,\n    notifier=pushover_notifier,\n)\n\nagent = UnifiedMCPAgent(\n''',
    '''health_scheduler = MorningHealthScheduler(\n    health_audit,\n    enabled=_bool(OPTIONS.get("morning_health_check_enabled"), True),\n    daily_time=str(OPTIONS.get("morning_health_check_time") or "07:00"),\n    local_now=_health_scheduler_now,\n    notifier=pushover_notifier,\n)\none_time_rule_cleanup = OneTimeRuleCleanupService(\n    mcp,\n    local_now=_health_scheduler_now,\n    grace_minutes=int(OPTIONS.get("one_time_rule_cleanup_grace_minutes") or 10),\n)\none_time_rule_cleanup_scheduler = OneTimeRuleCleanupScheduler(\n    one_time_rule_cleanup,\n    enabled=_bool(OPTIONS.get("one_time_rule_cleanup_enabled"), True),\n    daily_time=str(OPTIONS.get("one_time_rule_cleanup_time") or "01:00"),\n    local_now=_health_scheduler_now,\n)\n\nagent = UnifiedMCPAgent(\n''',
)
replace_once(
    "hubitat-mcp-ai/rootfs/app/app.py",
    '''async def lifespan(_: FastAPI):\n    health_scheduler.start()\n    try:\n        yield\n    finally:\n        await health_scheduler.close()\n''',
    '''async def lifespan(_: FastAPI):\n    health_scheduler.start()\n    one_time_rule_cleanup_scheduler.start()\n    try:\n        yield\n    finally:\n        await one_time_rule_cleanup_scheduler.close()\n        await health_scheduler.close()\n''',
)

# Add-on manifest/release metadata.
replace_once("hubitat-mcp-ai/config.yaml", 'version: "0.16.96"', 'version: "0.16.97"')
replace_once(
    "hubitat-mcp-ai/config.yaml",
    '  morning_health_check_time: "07:00"\n',
    '  morning_health_check_time: "07:00"\n  one_time_rule_cleanup_enabled: true\n  one_time_rule_cleanup_time: "01:00"\n  one_time_rule_cleanup_grace_minutes: 10\n',
)
replace_once(
    "hubitat-mcp-ai/config.yaml",
    '  morning_health_check_time: str\n',
    '  morning_health_check_time: str\n  one_time_rule_cleanup_enabled: bool\n  one_time_rule_cleanup_time: str\n  one_time_rule_cleanup_grace_minutes: int\n',
)
replace_once("README.md", '| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.96 |', '| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.16.97 |')
replace_once("hubitat-mcp-ai/README.md", 'Current add-on version: **0.16.96**.', 'Current add-on version: **0.16.97**.')
replace_once(
    "hubitat-mcp-ai/README.md",
    '## Architecture\n\n0.16.96 makes',
    '''## Architecture\n\n0.16.97 gives HomeBrain-generated one-time Rule Machine schedules a bounded lifecycle. A dedicated background scheduler runs at 01:00 Hubitat local time by default and soft-deletes only expired rules whose names exactly match the HomeBrain `(One-time YYYY-MM-DD HH:MM)` convention, after a 10-minute safety grace period. Deletes use `hub_delete_native_app` with `force=false` and `confirm=true`; a failed list read deletes nothing and an individual failure does not stop later candidates. Newly created one-time rules no longer append the unreliable self-pause action.\n\n0.16.96 makes''',
)
replace_once(
    "hubitat-mcp-ai/CHANGELOG-INDEX.md",
    '## Current release\n\n- [0.16.96](CHANGELOG-0.16.96.md)\n\n## Recent performance releases\n',
    '## Current release\n\n- [0.16.97](CHANGELOG-0.16.97.md)\n\n## Recent performance releases\n\n- [0.16.96](CHANGELOG-0.16.96.md)\n',
)
replace_once(
    "docs/RUNTIME-MODULE-MAP.md",
    '| `natural_datetime.py` | Formats authoritative ISO event timestamps for natural-language answers. |\n',
    '| `natural_datetime.py` | Formats authoritative ISO event timestamps for natural-language answers. |\n| `one_time_rule_cleanup.py` | Soft-deletes expired HomeBrain-generated one-time Rule Machine rules on a guarded Hubitat-local nightly schedule. |\n',
)

# Focused existing regression: one-time authoring now emits the create action only.
replace_once(
    "hubitat-mcp-ai/tests/test_relative_schedule_service.py",
    '    assert len(decision.actions) == 2\n',
    '    assert len(decision.actions) == 1\n',
)
replace_once(
    "hubitat-mcp-ai/tests/test_relative_schedule_service.py",
    '''    pause = decision.actions[1]["args"]["addAction"]\n    assert pause["capability"] == "pauseRule"\n\n''',
    '',
)
