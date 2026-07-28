#!/usr/bin/env python3
"""Report static import reachability for the Hubitat MCP AI application."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ENTRYPOINTS = {"app"}


def parse_imports(path: Path, known: set[str]) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in known:
                    imports.add(top)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in known:
                imports.add(top)
    return imports


def dynamic_import_hints(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        marker
        for marker in ("importlib.import_module", "__import__(", "globals()[", "getattr(sys.modules")
        if marker in text
    ]


def build_report(app_dir: Path) -> dict[str, object]:
    files = {path.stem: path for path in app_dir.glob("*.py")}
    known = set(files)
    forward = {module: parse_imports(path, known) for module, path in files.items()}
    entrypoints = ENTRYPOINTS & known
    live: set[str] = set()
    frontier = set(entrypoints)
    while frontier:
        live |= frontier
        frontier = set().union(*(forward.get(module, set()) for module in frontier)) - live
    hints = {module: dynamic_import_hints(path) for module, path in files.items()}
    return {
        "app_dir": str(app_dir),
        "total_modules": len(known),
        "entrypoints_used": sorted(entrypoints),
        "live_count": len(live),
        "orphan_count": len(known - live),
        "live_modules": sorted(live),
        "orphan_modules": sorted(known - live),
        "dynamic_import_hints": {key: value for key, value in hints.items() if value},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--app-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.app_dir.resolve())
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
