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
    'r"what(?:\'s| is) (?:our|the(?: whole house)?|my|current|whole house) (?:power|electricity) (?:usage|use|consumption)(?: right)? now",',
    'r"what(?:\'s| is) (?:our|the(?: whole house)?|my|current|whole house) (?:power|electricity) (?:usage|use|consumption)(?: (?:right )?now)?",',
)
replace(
    f"{app}/control_focus_octopus_energy.py",
    'r"how much (?:power|electricity) (?:are we|is the house|is my home) using(?: right)? now",',
    'r"how much (?:power|electricity) (?:are we|is the house|is my home) using(?: (?:right )?now)?",',
)
replace("hubitat-mcp-ai/config.yaml", 'version: "0.10.33"', 'version: "0.10.34"')
replace(f"{app}/entrypoint.py", 'PREVIOUS_RELEASE_VERSION = "0.10.32"\nRELEASE_VERSION = "0.10.33"', 'PREVIOUS_RELEASE_VERSION = "0.10.33"\nRELEASE_VERSION = "0.10.34"')
replace(f"{app}/device_intelligence_webui.py", 'PWA_RELEASE_VERSION = "0.10.33"', 'PWA_RELEASE_VERSION = "0.10.34"')
replace(f"{app}/device_intelligence_webui.py", "hubitat-mcp-ai-shell-v0.10.33", "hubitat-mcp-ai-shell-v0.10.34")

Path("hubitat-mcp-ai/tests/test_whole_house_power_optional_now.py").write_text(
    '''from __future__ import annotations\nimport sys\nfrom pathlib import Path\nAPP = Path("hubitat-mcp-ai/rootfs/app").resolve()\nif str(APP) not in sys.path: sys.path.insert(0, str(APP))\nfrom control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period\n\ndef test_whole_house_power_without_now_is_terminal():\n    query = "What is the whole house power consumption?"\n    assert is_whole_house_power_query(query)\n    assert is_octopus_energy_query(query)\n    assert requested_octopus_period(query) == "power"\n\ndef test_whole_house_power_with_now_remains_terminal():\n    assert is_whole_house_power_query("What is the whole house power consumption now?")\n\ndef test_device_specific_power_is_not_captured():\n    assert not is_whole_house_power_query("What is the freezer power consumption?")\n''',
    encoding="utf-8",
)
Path("hubitat-mcp-ai/CHANGELOG_0.10.34.md").write_text(
    "# Hubitat MCP AI 0.10.34\n\n- Makes `now` optional in whole-house live-power questions.\n- Keeps natural whole-house power wording on the deterministic Octopus terminal route.\n- Adds positive and device-specific negative regression coverage.\n",
    encoding="utf-8",
)
