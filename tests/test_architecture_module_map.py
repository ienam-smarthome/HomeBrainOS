from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
MODULE_DOCS = (
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "ARCHITECTURE-MODULE-MAP-UPDATE.md",
)
MODULE_ROW = re.compile(r"^\| `([^`]+\.py)` \|", re.MULTILINE)


def _runtime_modules() -> set[str]:
    return {
        path.name
        for path in APP_DIR.glob("*.py")
        if path.name != "__init__.py"
    }


def _documented_modules() -> set[str]:
    documented: set[str] = set()
    for path in MODULE_DOCS:
        documented.update(MODULE_ROW.findall(path.read_text(encoding="utf-8")))
    return documented


def test_runtime_modules_match_documented_module_maps() -> None:
    runtime = _runtime_modules()
    documented = _documented_modules()

    missing = sorted(runtime - documented)
    stale = sorted(documented - runtime)

    assert not missing, (
        "Live runtime modules missing from the architecture module maps: "
        + ", ".join(missing)
    )
    assert not stale, (
        "Architecture module-map entries no longer present in rootfs/app: "
        + ", ".join(stale)
    )
