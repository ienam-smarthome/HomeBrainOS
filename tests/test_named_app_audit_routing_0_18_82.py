"""Ensure named app cohorts never become whole-hub audits due to 'device' in an app name."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from health_audit_service import is_comprehensive_system_audit_request
from composite_system_audit_policy import is_cross_domain_hub_audit_request


TARGETED = (
    "Investigate whether Life360 (app 4061), Device Status Report (app 3977), "
    "and Octopus Energy (app 3933) are causing excessive Hubitat load. "
    "Read current application performance data and actual ERROR logs. "
    "For each app, tell me whether a LimitExceededException was explicitly "
    "observed, citing the exact app ID and relevant method where available. "
    "Compare timing and possible relationships between these problems. "
    "Explain which conclusions are proven, which are hypotheses and what "
    "evidence is missing. Do not make changes."
)


def test_01881_targeted_app_prompt_is_not_comprehensive():
    assert not is_comprehensive_system_audit_request(TARGETED)
    assert not is_cross_domain_hub_audit_request(TARGETED)


def test_explicit_whole_hub_audit_precedes_named_apps():
    prompt = (
        "Perform a comprehensive system audit of all devices, automations, "
        "performance stats, scheduled jobs and recent error logs, including "
        "Life360 (app 4061), Octopus (app 3933) and Device Status Report (app 3977)."
    )
    assert is_comprehensive_system_audit_request(prompt)


def test_single_app_or_named_device_is_not_a_whole_hub_audit():
    assert not is_comprehensive_system_audit_request(
        "Investigate logs and performance of device 7182 and app 3977."
    )


def test_broad_audit_without_named_app_instances_still_routes():
    prompt = (
        "Investigate my Hubitat system: health, device problems, app errors, "
        "logs and scheduled jobs across the whole hub."
    )
    assert is_cross_domain_hub_audit_request(prompt)


def test_three_names_with_app_ids_remain_targeted_even_if_device_in_name():
    assert not is_comprehensive_system_audit_request(
        "Investigate logs for App 3933, App 4061, and App 3977; "
        "compare device warnings and app statistics."
    )
