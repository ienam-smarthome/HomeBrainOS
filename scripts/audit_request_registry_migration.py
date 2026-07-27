from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
ENTRYPOINT = APP_DIR / "entrypoint.py"
ENTRYPOINT_CORE = APP_DIR / "entrypoint_core.py"

EXPECTED_REGISTRIES = (
    "hub-health-display-registry",
    "semantic-home-registry",
    "summary-thermostat-registry",
    "read-execution-registry",
)

LEGACY_RUNTIME_INSTALLERS = (
    "install_home_summary_consistency_guard",
    "install_semantic_home_query_router",
    "install_semantic_home_summary_agent",
    "install_thermostat_summary_guard",
    "install_climate_metric_extrema_route",
    "install_named_rule_status_route",
    "install_execution_contract_bridge",
)


class _CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if isinstance(function, ast.Name):
            self.calls.append(function.id)
        elif isinstance(function, ast.Attribute):
            self.calls.append(function.attr)
        self.generic_visit(node)


def _runtime_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    visitor = _CallVisitor()
    visitor.visit(tree)
    return visitor.calls


def audit() -> dict[str, Any]:
    entrypoint_source = ENTRYPOINT.read_text(encoding="utf-8-sig")
    entrypoint_calls = _runtime_calls(ENTRYPOINT)
    core_calls = _runtime_calls(ENTRYPOINT_CORE)

    registry_positions = {
        name: entrypoint_source.find(f'"{name}"') for name in EXPECTED_REGISTRIES
    }
    missing_registries = [
        name for name, position in registry_positions.items() if position < 0
    ]
    ordered_positions = [registry_positions[name] for name in EXPECTED_REGISTRIES]
    registry_order_valid = not missing_registries and ordered_positions == sorted(
        ordered_positions
    )

    runtime_legacy_calls = sorted(
        set(LEGACY_RUNTIME_INSTALLERS).intersection(entrypoint_calls + core_calls)
    )
    direct_runtime_bridge = (
        "runtime_request_registry = install_runtime_route_bridge(_core.application)"
        in entrypoint_source
    )
    finalized_before_bridge = (
        entrypoint_source.find("auxiliary_request_layers.finalize()")
        < entrypoint_source.find("install_runtime_route_bridge(_core.application)")
    )
    capture_count = entrypoint_source.count("auxiliary_request_layers.capture(")
    registry_install_count = entrypoint_source.count("registry.install,")

    passed = all(
        (
            registry_order_valid,
            not runtime_legacy_calls,
            direct_runtime_bridge,
            finalized_before_bridge,
            capture_count == 5,
            registry_install_count == 4,
        )
    )

    return {
        "passed": passed,
        "expected_registries": list(EXPECTED_REGISTRIES),
        "registry_positions": registry_positions,
        "registry_order_valid": registry_order_valid,
        "runtime_legacy_installer_calls": runtime_legacy_calls,
        "capture_count": capture_count,
        "registry_install_count": registry_install_count,
        "direct_runtime_bridge": direct_runtime_bridge,
        "finalized_before_runtime_bridge": finalized_before_bridge,
        "conclusion": (
            "Thread 1 step 3 complete: maintained answer guards and terminal routes "
            "are registry-composed without legacy runtime reinstallation."
            if passed
            else "Thread 1 step 3 remains open; inspect failed audit fields."
        ),
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
