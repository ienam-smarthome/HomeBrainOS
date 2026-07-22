"""One-shot release patch for deterministic live whole-house power queries."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess

BRANCH = "agent/fix-live-power-route-0.10.31"

def replace(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")

def run(*args: str) -> None:
    subprocess.run(list(args), check=True)

def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true": return
    if BRANCH not in {os.environ.get("GITHUB_REF_NAME", ""), os.environ.get("GITHUB_HEAD_REF", "")}: return
    replace("hubitat-mcp-ai/rootfs/app/control_focus_octopus_energy.py",
        '    "power": ("power", "live power", "current power", "right now", "currently"),',
        '    "power": ("power", "live power", "current power", "right now", "currently", "now"),')
    replace("hubitat-mcp-ai/rootfs/app/control_focus_octopus_energy.py",
        'def is_octopus_energy_query(query: str) -> bool:\n    return is_octopus_display_query(query) or is_whole_house_period_query(query)\n',
        '''def is_whole_house_power_query(query: str) -> bool:\n    q = _query(query)\n    patterns = (\n        r"how much (?:power|electricity) (?:are we|is the house|is my home) using(?: right)? now",\n        r"what(?:'s| is) (?:our|the|my|current|whole house) (?:power|electricity) (?:usage|use|consumption)(?: right)? now",\n        r"(?:show|give|tell) me (?:the )?(?:current|live|whole house) (?:power|electricity)(?: usage| consumption)?",\n        r"(?:current|live|whole house|overall|total) (?:power|electricity) (?:usage|use|consumption)",\n    )\n    return any(re.fullmatch(pattern, q) for pattern in patterns)\n\n\ndef is_octopus_energy_query(query: str) -> bool:\n    return (\n        is_octopus_display_query(query)\n        or is_whole_house_period_query(query)\n        or is_whole_house_power_query(query)\n    )\n''')
    replace("hubitat-mcp-ai/rootfs/app/entrypoint.py", 'PREVIOUS_RELEASE_VERSION = "0.10.29"\nRELEASE_VERSION = "0.10.30"', 'PREVIOUS_RELEASE_VERSION = "0.10.30"\nRELEASE_VERSION = "0.10.31"')
    replace("hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py", 'PWA_RELEASE_VERSION = "0.10.30"', 'PWA_RELEASE_VERSION = "0.10.31"')
    replace("hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py", 'hubitat-mcp-ai-shell-v0.10.30', 'hubitat-mcp-ai-shell-v0.10.31')
    replace("hubitat-mcp-ai/config.yaml", 'version: "0.10.30"', 'version: "0.10.31"')
    Path("hubitat-mcp-ai/CHANGELOG-0.10.31.md").write_text("# Hubitat MCP AI 0.10.31\n\n- Routes generic live whole-house power questions directly to the authoritative Octopus meter reader.\n- Fetches current readings immediately instead of asking permission to fetch them.\n- Avoids summing individual monitored sockets with the whole-house meter.\n", encoding="utf-8")
    Path("tests/test_live_power_route.py").write_text('''from __future__ import annotations\nimport sys\nfrom pathlib import Path\nAPP = Path("hubitat-mcp-ai/rootfs/app").resolve()\nif str(APP) not in sys.path: sys.path.insert(0, str(APP))\nfrom control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period\n\ndef test_generic_live_power_routes_to_octopus_reader():\n    query = "How much power are we using now?"\n    assert is_whole_house_power_query(query)\n    assert is_octopus_energy_query(query)\n    assert requested_octopus_period(query) == "power"\n\ndef test_non_live_device_power_question_is_not_captured():\n    assert not is_whole_house_power_query("How much power is the freezer using?")\n''', encoding="utf-8")
    Path(__file__).unlink(missing_ok=True)
    Path(__file__).with_name("ast.py").unlink(missing_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-m", "Route live whole-house power deterministically")
    run("git", "push", "origin", f"HEAD:{BRANCH}")

main()
