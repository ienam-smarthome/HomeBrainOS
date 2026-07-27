from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_composition import classify_ask_layer  # noqa: E402


def _targets_application_ask(node: ast.AST) -> bool:
    if not isinstance(node, ast.Attribute) or node.attr != "ask":
        return False
    value = node.value
    if isinstance(value, ast.Name):
        return value.id == "application"
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "application"
    )


class AskAssignmentVisitor(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.functions: list[str] = []
        self.items: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(_targets_application_ask(target) for target in node.targets):
            self._record(node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _targets_application_ask(node.target):
            self._record(node)
        self.generic_visit(node)

    def _record(self, node: ast.AST) -> None:
        function = self.functions[-1] if self.functions else "<module>"
        self.items.append(
            {
                "module": self.module,
                "function": function,
                "line": int(getattr(node, "lineno", 0)),
                "tier": classify_ask_layer(self.module, function),
            }
        )


def analyze() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for path in sorted(APP_DIR.glob("*.py")):
        if path.name == "request_composition.py" or path.name.endswith(".backup"):
            continue
        visitor = AskAssignmentVisitor(path.stem)
        visitor.visit(
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        )
        items.extend(visitor.items)

    modules = sorted({item["module"] for item in items})
    tier_counts = Counter(item["tier"] for item in items)
    return {
        "app_dir": str(APP_DIR),
        "assignment_site_count": len(items),
        "module_count": len(modules),
        "modules": modules,
        "tier_counts": dict(sorted(tier_counts.items())),
        "assignments": items,
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
