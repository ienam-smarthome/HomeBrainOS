"""One-shot CI patcher for the 0.10.28 runtime UI version release."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

BRANCH = "agent/fix-runtime-ui-version-0.10.28"


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

    # Pull-request workflows check out a synthetic merge ref. Move back to the
    # actual feature branch before creating the release commit.
    if head_ref == BRANCH:
        run("git", "fetch", "origin", BRANCH)
        run("git", "checkout", "-B", BRANCH, f"origin/{BRANCH}")

    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        'PWA_RELEASE_VERSION = "0.10.23"',
        'PWA_RELEASE_VERSION = "0.10.28"',
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        "SERVICE_WORKER = r\"\"\"const CACHE='hubitat-mcp-ai-shell-v1';",
        "SERVICE_WORKER = r\"\"\"const CACHE='hubitat-mcp-ai-shell-v0.10.28';",
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        "    application.VERSION = PWA_RELEASE_VERSION\n    api.version = PWA_RELEASE_VERSION\n",
        "    # The entrypoint owns the authoritative release version. The Web UI\n"
        "    # must display it, never replace it with a separately maintained value.\n"
        "    release_version = str(getattr(application, 'VERSION', PWA_RELEASE_VERSION))\n"
        "    api.version = release_version\n",
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py",
        "            PWA_RELEASE_VERSION,\n",
        "            release_version,\n",
    )
    replace(
        "hubitat-mcp-ai/rootfs/app/entrypoint.py",
        'PREVIOUS_RELEASE_VERSION = "0.10.26"\nRELEASE_VERSION = "0.10.27"',
        'PREVIOUS_RELEASE_VERSION = "0.10.27"\nRELEASE_VERSION = "0.10.28"',
    )
    replace(
        "hubitat-mcp-ai/config.yaml",
        'version: "0.10.27"',
        'version: "0.10.28"',
    )

    Path("hubitat-mcp-ai/CHANGELOG-0.10.28.md").write_text(
        "# Hubitat MCP AI 0.10.28\n\n"
        "## Runtime and Web UI version alignment\n\n"
        "- Fixes the Web UI header incorrectly showing v0.10.23 after newer add-on updates.\n"
        "- Stops the PWA installer from overwriting the authoritative runtime release version.\n"
        "- Makes the rendered header use the entrypoint release version.\n"
        "- Refreshes the service-worker cache namespace so older cached HTML is discarded.\n"
        "- Keeps the Home Assistant manifest, FastAPI runtime, status API and Web UI aligned.\n",
        encoding="utf-8",
    )

    Path("tests/test_webui_release_version.py").write_text(
        "from __future__ import annotations\n\n"
        "import ast\n"
        "from pathlib import Path\n\n\n"
        "def assignment(path: str, name: str) -> str:\n"
        "    tree = ast.parse(Path(path).read_text(encoding='utf-8'))\n"
        "    for node in tree.body:\n"
        "        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):\n"
        "            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):\n"
        "                return node.value.value\n"
        "    raise AssertionError(f'{name} not found')\n\n\n"
        "def test_webui_does_not_overwrite_application_release_version() -> None:\n"
        "    source = Path('hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py').read_text(encoding='utf-8')\n"
        "    assert 'application.VERSION = PWA_RELEASE_VERSION' not in source\n"
        "    assert \"release_version = str(getattr(application, 'VERSION', PWA_RELEASE_VERSION))\" in source\n"
        "    assert 'release_version,' in source\n\n\n"
        "def test_release_sources_are_aligned() -> None:\n"
        "    entrypoint = assignment('hubitat-mcp-ai/rootfs/app/entrypoint.py', 'RELEASE_VERSION')\n"
        "    pwa = assignment('hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py', 'PWA_RELEASE_VERSION')\n"
        "    config = Path('hubitat-mcp-ai/config.yaml').read_text(encoding='utf-8')\n"
        "    assert entrypoint == '0.10.28'\n"
        "    assert pwa == entrypoint\n"
        "    assert 'version: \\\"0.10.28\\\"' in config\n",
        encoding="utf-8",
    )

    Path("scripts/sitecustomize.py").unlink(missing_ok=True)
    Path("scripts/ast.py").unlink(missing_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-m", "Fix runtime Web UI version alignment")
    run("git", "push", "origin", f"HEAD:{BRANCH}")


main()
