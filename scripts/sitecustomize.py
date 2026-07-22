"""One-shot release patch for room inventory canonicalisation."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

BRANCH = "agent/fix-room-inventory-0.10.29"


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
        "hubitat-mcp-ai/rootfs/app/fast_fallback_room_inventory.py",
        '    def _room_key(value: Any) -> str:\n        return re.sub(r"[^a-z0-9]+", " ", _normalise(value)).strip()\n',
        '    def _room_key(value: Any) -> str:\n        """Canonical room key tolerant of spaces, punctuation and spoken numbering."""\n        return re.sub(r"[^a-z0-9]+", "", _normalise(value))\n',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/entrypoint.py",
        'PREVIOUS_RELEASE_VERSION = "0.10.27"\nRELEASE_VERSION = "0.10.28"',
        'PREVIOUS_RELEASE_VERSION = "0.10.28"\nRELEASE_VERSION = "0.10.29"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        'PWA_RELEASE_VERSION = "0.10.28"',
        'PWA_RELEASE_VERSION = "0.10.29"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        "hubitat-mcp-ai-shell-v0.10.28",
        "hubitat-mcp-ai-shell-v0.10.29",
    )
    replace(
        "hubitat-mcp-ai/config.yaml",
        'version: "0.10.28"',
        'version: "0.10.29"',
    )

    Path("hubitat-mcp-ai/CHANGELOG-0.10.29.md").write_text(
        "# Hubitat MCP AI 0.10.29\n\n"
        "## Natural room inventory matching\n\n"
        "- Fixes `Show devices in the living room` falling through to single-device lookup.\n"
        "- Treats `Livingroom`, `living room`, and `living-room` as the same exact Hubitat room.\n"
        "- Treats `Bedroom1` and `bedroom 1` as the same room while preserving authoritative room membership.\n"
        "- Adds regression coverage for room candidate extraction and canonical room keys.\n",
        encoding="utf-8",
    )
    Path("tests/test_room_inventory_aliases.py").write_text(
        "from __future__ import annotations\n\n"
        "import importlib.util\n"
        "from pathlib import Path\n\n\n"
        "def load_module():\n"
        "    path = Path('hubitat-mcp-ai/rootfs/app/fast_fallback_room_inventory.py')\n"
        "    spec = importlib.util.spec_from_file_location('room_inventory_test_module', path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    assert spec and spec.loader\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n\n\n"
        "def test_room_candidate_extracts_living_room() -> None:\n"
        "    module = load_module()\n"
        "    assert module.FastFallbackRouter._room_candidate('Show devices in the living room') == 'living room'\n\n\n"
        "def test_room_keys_ignore_spacing_and_punctuation() -> None:\n"
        "    module = load_module()\n"
        "    key = module.FastFallbackRouter._room_key\n"
        "    assert key('Livingroom') == key('living room') == key('living-room')\n"
        "    assert key('Bedroom1') == key('bedroom 1') == key('Bedroom-1')\n",
        encoding="utf-8",
    )

    Path(__file__).unlink(missing_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-m", "Fix natural room inventory matching")
    run("git", "push", "origin", f"HEAD:{BRANCH}")


main()
