#!/usr/bin/env python3
"""Report fan-in and consolidation signals for variant-style module families."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

FAMILIES = {
    "control_agent": ("control_agent",),
    "fast_fallback": ("fast_fallback",),
    "ollama_agent": ("ollama_agent",),
    "automation_rule_workflow": ("automation_rule_workflow",),
    "home_snapshot": ("home_snapshot",),
    "device_intelligence": ("device_intelligence",),
    "semantic": ("semantic_home", "semantic_metric", "semantic_read"),
    "webui": ("webui",),
    "conversation_context": ("conversation_context",),
}

WIRING_LAYER = {
    "entrypoint",
    "entrypoint_core",
    "webui",
    "runtime_route_bridge",
    "route_registry",
    "route_catalogue",
    "request_router",
    "routing",
    "routing_policy",
    "dashboard_api",
    "device_intelligence_api",
    "mcp_agent_orchestrator",
}


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


def build_report(app_dir: Path) -> dict[str, list[dict[str, object]]]:
    files = {path.stem: path for path in app_dir.glob("*.py")}
    known = set(files)
    forward = {module: parse_imports(path, known) for module, path in files.items()}
    reverse: dict[str, set[str]] = {module: set() for module in known}
    for module, dependencies in forward.items():
        for dependency in dependencies:
            reverse[dependency].add(module)

    def family_of(module: str) -> str | None:
        for family, prefixes in FAMILIES.items():
            if any(module == prefix or module.startswith(prefix + "_") for prefix in prefixes):
                return family
        return None

    report: dict[str, list[dict[str, object]]] = {}
    for family in FAMILIES:
        rows: list[dict[str, object]] = []
        for module in sorted(item for item in known if family_of(item) == family):
            importers = sorted(reverse[module])
            wiring = [item for item in importers if item in WIRING_LAYER]
            siblings = [item for item in importers if family_of(item) == family and item != module]
            others = [item for item in importers if item not in wiring and item not in siblings]
            if wiring:
                signal = "LIVE (wired directly)"
            elif siblings and not others:
                signal = "SUSPECT (only used by a same-family sibling)"
            elif importers:
                signal = "LIVE (used elsewhere)"
            else:
                signal = "ORPHAN (imported by nothing)"
            rows.append({"module": module, "fan_in": len(importers), "importers": importers, "signal": signal})
        report[family] = rows
    return report


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
