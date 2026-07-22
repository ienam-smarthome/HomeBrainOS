from pathlib import Path
import re


def rewrite(path: str, transform) -> None:
    p = Path(path)
    before = p.read_text(encoding="utf-8")
    after = transform(before)
    p.write_text(after, encoding="utf-8")


app = "hubitat-mcp-ai/rootfs/app"


def patch_power(text: str) -> str:
    return text.replace('(?: right)? now', '(?: (?:right )?now)?')


def patch_webui(text: str) -> str:
    text = re.sub(r'PWA_RELEASE_VERSION = "[^"]+"', 'PWA_RELEASE_VERSION = "0.10.34"', text, count=1)
    return re.sub(r'hubitat-mcp-ai-shell-v[0-9.]+', 'hubitat-mcp-ai-shell-v0.10.34', text, count=1)


rewrite(f"{app}/control_focus_octopus_energy.py", patch_power)
rewrite("hubitat-mcp-ai/config.yaml", lambda text: re.sub(r'(?m)^version: ["\'][^"\']+["\']$', 'version: "0.10.34"', text, count=1))
rewrite(f"{app}/entrypoint.py", lambda text: re.sub(r'PREVIOUS_RELEASE_VERSION = "[^"]+"\s+RELEASE_VERSION = "[^"]+"', 'PREVIOUS_RELEASE_VERSION = "0.10.33"\nRELEASE_VERSION = "0.10.34"', text, count=1))
rewrite(f"{app}/device_intelligence_webui.py", patch_webui)

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

# Concise-log retry.
