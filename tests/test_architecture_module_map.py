from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
MODULE_DOC = ROOT / "docs" / "RUNTIME-MODULE-MAP.md"
MODULE_ROW = re.compile(r"^\| `([^`]+\.py)` \|", re.MULTILINE)


def _runtime_modules() -> set[str]:
    return {
        path.name
        for path in APP_DIR.glob("*.py")
        if path.name != "__init__.py"
    }


def _documented_modules() -> set[str]:
    return set(MODULE_ROW.findall(MODULE_DOC.read_text(encoding="utf-8")))


def test_runtime_modules_match_canonical_module_map() -> None:
    runtime = _runtime_modules()
    documented = _documented_modules()

    missing = sorted(runtime - documented)
    stale = sorted(documented - runtime)

    assert not missing, (
        "Live runtime modules missing from docs/RUNTIME-MODULE-MAP.md: "
        + ", ".join(missing)
    )
    assert not stale, (
        "Canonical runtime-module entries no longer present in rootfs/app: "
        + ", ".join(stale)
    )
