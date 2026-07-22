"""One-shot release patch for room inventory parser correction."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

BRANCH = "agent/fix-room-parser-0.10.30"


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

    path = "hubitat-mcp-ai/rootfs/app/fast_fallback_room_inventory.py"
    replace(
        path,
        '        r"(?:listed\\s+)?(?:in|under|inside|from|assigned\\s+to)\\s+(?:the\\s+)?(.+?)(?:\\s+room)?[?.!]*$",',
        '        r"(?:listed\\s+)?(?:in|under|inside|from|assigned\\s+to)\\s+(?:the\\s+)?(.+?)[?.!]*$",',
    )
    replace(
        path,
        '        r"(?:in|under|inside|from|assigned\\s+to)\\s+(?:the\\s+)?(.+?)(?:\\s+room)?[?.!]*$",',
        '        r"(?:in|under|inside|from|assigned\\s+to)\\s+(?:the\\s+)?(.+?)[?.!]*$",',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/entrypoint.py",
        'PREVIOUS_RELEASE_VERSION = "0.10.28"\nRELEASE_VERSION = "0.10.29"',
        'PREVIOUS_RELEASE_VERSION = "0.10.29"\nRELEASE_VERSION = "0.10.30"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        'PWA_RELEASE_VERSION = "0.10.29"',
        'PWA_RELEASE_VERSION = "0.10.30"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        "hubitat-mcp-ai-shell-v0.10.29",
        "hubitat-mcp-ai-shell-v0.10.30",
    )
    replace(
        "hubitat-mcp-ai/config.yaml",
        'version: "0.10.29"',
        'version: "0.10.30"',
    )

    Path("hubitat-mcp-ai/CHANGELOG-0.10.30.md").write_text(
        "# Hubitat MCP AI 0.10.30\n\n"
        "## Room inventory parser correction\n\n"
        "- Fixes `Show devices in the living room` extracting only `living`.\n"
        "- Preserves `living room` as the requested room name before canonical matching.\n"
        "- Keeps explicit forms such as `Show the Livingroom room devices` working.\n"
        "- Adds regression coverage for both show/list and which/what room inventory phrasing.\n",
        encoding="utf-8",
    )
    Path("tests/test_room_inventory_parser.py").write_text(
        "from __future__ import annotations\n\n"
        "import importlib.util\n"
        "import sys\n"
        "from pathlib import Path\n\n\n"
        "APP = Path('hubitat-mcp-ai/rootfs/app').resolve()\n"
        "if str(APP) not in sys.path:\n"
        "    sys.path.insert(0, str(APP))\n\n\n"
        "def load_module():\n"
        "    path = APP / 'fast_fallback_room_inventory.py'\n"
        "    spec = importlib.util.spec_from_file_location('room_inventory_parser_test_module', path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    assert spec and spec.loader\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n\n\n"
        "def test_show_devices_preserves_room_suffix_as_part_of_name() -> None:\n"
        "    router = load_module().FastFallbackRouter\n"
        "    assert router._room_candidate('Show devices in the living room') == 'living room'\n"
        "    assert router._room_key('living room') == router._room_key('Livingroom')\n\n\n"
        "def test_which_devices_preserves_room_suffix_as_part_of_name() -> None:\n"
        "    router = load_module().FastFallbackRouter\n"
        "    assert router._room_candidate('Which devices are in the living room?') == 'living room'\n\n\n"
        "def test_explicit_room_suffix_form_still_extracts_room_name() -> None:\n"
        "    router = load_module().FastFallbackRouter\n"
        "    assert router._room_candidate('Show the Livingroom room devices') == 'Livingroom'\n",
        encoding="utf-8",
    )

    Path(__file__).unlink(missing_ok=True)
    Path("scripts/ast.py").unlink(missing_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-m", "Fix room inventory parser")
    run("git", "push", "origin", f"HEAD:{BRANCH}")


main()
