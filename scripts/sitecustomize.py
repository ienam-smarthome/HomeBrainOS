"""One-shot release patch for hyphenated whole-house power queries."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

BRANCH = "agent/fix-hyphenated-power-route-0.10.32"


def replace(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def run(*args: str) -> None:
    subprocess.run(list(args), check=True)


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    ref_name = os.environ.get("GITHUB_REF_NAME", "")
    head_ref = os.environ.get("GITHUB_HEAD_REF", "")
    if BRANCH not in {ref_name, head_ref}:
        return
    if head_ref == BRANCH:
        run("git", "fetch", "origin", BRANCH)
        run("git", "checkout", "-B", BRANCH, f"origin/{BRANCH}")

    replace(
        "hubitat-mcp-ai/rootfs/app/control_focus_octopus_energy.py",
        '    return re.sub(r"\\s+", " ", _normalise(value)).strip(" .!?")\n',
        '    return re.sub(r"\\s+", " ", _normalise(value).replace("-", " ")).strip(" .!?")\n',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/entrypoint.py",
        'PREVIOUS_RELEASE_VERSION = "0.10.30"\nRELEASE_VERSION = "0.10.31"',
        'PREVIOUS_RELEASE_VERSION = "0.10.31"\nRELEASE_VERSION = "0.10.32"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        'PWA_RELEASE_VERSION = "0.10.31"',
        'PWA_RELEASE_VERSION = "0.10.32"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        "hubitat-mcp-ai-shell-v0.10.31",
        "hubitat-mcp-ai-shell-v0.10.32",
    )
    replace(
        "hubitat-mcp-ai/config.yaml",
        'version: "0.10.31"',
        'version: "0.10.32"',
    )

    Path("hubitat-mcp-ai/CHANGELOG-0.10.32.md").write_text(
        "# Hubitat MCP AI 0.10.32\n\n"
        "- Treats `whole-house` and `whole house` identically in live-power questions.\n"
        "- Keeps generic whole-house power reads on the deterministic Octopus terminal route.\n"
        "- Prevents a fast-route classification from falling through to the unified AI agent.\n",
        encoding="utf-8",
    )
    Path("tests/test_hyphenated_whole_house_power.py").write_text(
        "from __future__ import annotations\n"
        "import sys\n"
        "from pathlib import Path\n"
        "APP = Path('hubitat-mcp-ai/rootfs/app').resolve()\n"
        "if str(APP) not in sys.path: sys.path.insert(0, str(APP))\n"
        "from control_focus_octopus_energy import is_octopus_energy_query, is_whole_house_power_query, requested_octopus_period\n\n"
        "def test_hyphenated_whole_house_power_routes_terminally():\n"
        "    query = 'What is the whole-house power consumption?'\n"
        "    assert is_whole_house_power_query(query)\n"
        "    assert is_octopus_energy_query(query)\n"
        "    assert requested_octopus_period(query) == 'power'\n\n"
        "def test_spaced_whole_house_remains_supported():\n"
        "    assert is_whole_house_power_query('What is the whole house power consumption?')\n",
        encoding="utf-8",
    )

    Path(__file__).unlink(missing_ok=True)
    Path(__file__).with_name("ast.py").unlink(missing_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-m", "Fix hyphenated whole-house power routing")
    run("git", "push", "origin", f"HEAD:{BRANCH}")


main()
