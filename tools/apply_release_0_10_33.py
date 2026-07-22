from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"replacement marker missing in {path}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


replace(
    "hubitat-mcp-ai/rootfs/app/control_focus_octopus_energy.py",
    r'(?:our|the|my|current|whole house) (?:power|electricity)',
    r'(?:our|the(?: whole house)?|my|current|whole house) (?:power|electricity)',
)
replace("hubitat-mcp-ai/config.yaml", 'version: "0.10.32"', 'version: "0.10.33"')
replace(
    "hubitat-mcp-ai/rootfs/app/entrypoint.py",
    'PREVIOUS_RELEASE_VERSION = "0.10.31"\nRELEASE_VERSION = "0.10.32"',
    'PREVIOUS_RELEASE_VERSION = "0.10.32"\nRELEASE_VERSION = "0.10.33"',
)
replace(
    "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
    'PWA_RELEASE_VERSION = "0.10.32"',
    'PWA_RELEASE_VERSION = "0.10.33"',
)
replace(
    "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
    "hubitat-mcp-ai-shell-v0.10.32",
    "hubitat-mcp-ai-shell-v0.10.33",
)

Path("hubitat-mcp-ai/CHANGELOG-0.10.33.md").write_text(
    "# Hubitat MCP AI 0.10.33\n\n"
    "- Recognises the natural phrase `the whole-house power consumption`.\n"
    "- Keeps the classified fast route terminal instead of falling through to Gemma.\n"
    "- Adds regression coverage for both hyphenated and spaced wording.\n",
    encoding="utf-8",
)

Path("tests/test_whole_house_power_article.py").write_text(
    "from __future__ import annotations\n"
    "import sys\n"
    "from pathlib import Path\n"
    "APP = Path('hubitat-mcp-ai/rootfs/app').resolve()\n"
    "if str(APP) not in sys.path: sys.path.insert(0, str(APP))\n"
    "from control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period\n\n"
    "def test_the_hyphenated_whole_house_power_query_is_terminal():\n"
    "    query = 'What is the whole-house power consumption?'\n"
    "    assert is_whole_house_power_query(query)\n"
    "    assert is_octopus_energy_query(query)\n"
    "    assert requested_octopus_period(query) == 'power'\n\n"
    "def test_the_spaced_whole_house_power_query_is_terminal():\n"
    "    assert is_whole_house_power_query('What is the whole house power consumption?')\n",
    encoding="utf-8",
)
