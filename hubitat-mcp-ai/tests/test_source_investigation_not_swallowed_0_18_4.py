"""Source investigations must not be swallowed by current-settings shortcuts."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from targeted_lockout_config import current_lockout_config_app_id, read_current_lockout_config
from scoped_app_status_read import scoped_status_app_id


SOURCE_QUERY = (
    "Inspect the Groovy source code for Livingroom Light 1 automation "
    "(app 4019). Identify where motionOffLockoutMinutes is declared, "
    "how its default value is applied, how the saved setting is read, "
    "and how state.motionLockout stores and calculates expiry timestamps. "
    "Explain whether changing the saved duration updates an already "
    "active countdown. Read-only. Do not change settings."
)


def test_real_source_inspection_question_skips_config_only_fastpath():
    assert current_lockout_config_app_id(SOURCE_QUERY) is None


def test_code_default_and_state_inspection_never_treated_as_simple_config():
    for prompt in (
        "For app 4019, compare defaultValue: 30 with persisted lockout duration and explain the code.",
        "How does state.motionLockout implement duration in app 4019?",
        "Read the implementation of app 4019 lockout configuration and explain its getter fallback.",
        "Review the Groovy code path for app 4019 motion-off lockout settings.",
    ):
        assert current_lockout_config_app_id(prompt) is None, prompt


def test_current_settings_still_take_read_only_fastpath():
    for prompt in (
        "What is the current persisted motion-off lockout duration for app 4019?",
        "Read app 4019 lockout settings right now.",
        "Is app 4019's current lockout duration 300 minutes?",
    ):
        assert current_lockout_config_app_id(prompt) == "4019", prompt


def test_historical_lockout_question_is_not_swallowed():
    assert current_lockout_config_app_id(
        "Investigate app 4019 motion lockout settings at 17:23 on 16 October 2026."
    ) is None


def test_source_question_calls_no_current_settings_gateway():
    class Catalog:
        def available_tool(self, *args):
            raise AssertionError("current-config-only gateway must not be selected")

    async def run():
        output = await read_current_lockout_config(
            object(), SOURCE_QUERY, catalog=Catalog()
        )
        assert output is None
    asyncio.run(run())


def test_status_shortcut_does_not_swallow_compound_source_request():
    assert scoped_status_app_id(
        "Inspect the Groovy source code for app 4019 lockout status and "
        "the state.motionLockout expiry implementation. Read-only."
    ) is None
    assert scoped_status_app_id(
        "What is the current status and lockout of app 4019?"
    ) == 4019
