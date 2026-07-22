from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"replacement marker not found in {path}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")

app = "hubitat-mcp-ai/rootfs/app"
replace(
    f"{app}/control_focus_octopus_energy.py",
    'r"how much (?:power|electricity) (?:are we|is the house|is my home) using(?: right)? now",',
    'r"how much (?:power|electricity) (?:are we|is the house|is my home) using(?: (?:right )?now)?",',
)
replace(
    f"{app}/control_focus_octopus_energy.py",
    'r"what(?:\'s| is) (?:our|the(?: whole house)?|my|current|whole house) (?:power|electricity) (?:usage|use|consumption)(?: right)? now",',
    'r"what(?:\'s| is) (?:our|the(?: whole house)?|my|current|whole house) (?:power|electricity) (?:usage|use|consumption)(?: (?:right )?now)?",',
)
replace("hubitat-mcp-ai/config.yaml", 'version: "0.10.33"', 'version: "0.10.34"')
replace(f"{app}/entrypoint.py", 'PREVIOUS_RELEASE_VERSION = "0.10.32"\nRELEASE_VERSION = "0.10.33"', 'PREVIOUS_RELEASE_VERSION = "0.10.33"\nRELEASE_VERSION = "0.10.34"')
replace(f"{app}/device_intelligence_webui.py", 'PWA_RELEASE_VERSION = "0.10.33"', 'PWA_RELEASE_VERSION = "0.10.34"')
replace(f"{app}/device_intelligence_webui.py", "hubitat-mcp-ai-shell-v0.10.33", "hubitat-mcp-ai-shell-v0.10.34")

Path("hubitat-mcp-ai/tests/test_whole_house_power_optional_now.py").write_text(
'''from __future__ import annotations
import sys
from pathlib import Path
APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period


def test_whole_house_power_without_now_is_terminal():
    query = "What is the whole house power consumption?"
    assert is_whole_house_power_query(query)
    assert is_octopus_energy_query(query)
    assert requested_octopus_period(query) == "power"


def test_whole_house_power_with_now_remains_terminal():
    assert is_whole_house_power_query("What is the whole house power consumption now?")


def test_hyphenated_whole_house_without_now_is_terminal():
    assert is_whole_house_power_query("What is the whole-house power consumption?")


def test_device_specific_power_is_not_captured():
    assert not is_whole_house_power_query("What is the freezer power consumption?")
''', encoding="utf-8")

Path("hubitat-mcp-ai/CHANGELOG_0.10.34.md").write_text(
"# Hubitat MCP AI 0.10.34\n\n- Makes `now` optional in whole-house live-power questions.\n- Keeps spaced and hyphenated natural wording on the deterministic Octopus route.\n- Prevents device-specific power questions from being captured.\n", encoding="utf-8")

# Triggered by a user-authored commit so GitHub Actions can publish the generated release commit.
