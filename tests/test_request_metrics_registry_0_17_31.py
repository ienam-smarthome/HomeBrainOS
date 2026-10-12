"""0.17.31 contract: runtime metric names must be declared before deployment.

The 0.17.30 focal app-log branch raised:
    ValueError: Unsupported metric counter: causal_archived_app_log_checks
because its increment was added without updating RequestMetrics.ALLOWED_COUNTERS.
Check *all* literal active-metric names in the installed application source,
not only the newly introduced counter.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_metrics import (  # noqa: E402
    RequestMetrics,
    increment_active_metric,
    add_active_metric_ms,
    observe_active_metric_max,
)


@pytest.mark.parametrize("name", [
    "causal_archived_app_log_checks",
    "causal_broad_inventory_blocked",
])
def test_focal_metrics_can_increment_under_active_request(name: str) -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        increment_active_metric(name)
        increment_active_metric(name)
        assert metrics.snapshot()["counters"][name] == 2
    finally:
        metrics.reset(token)


def test_every_literal_runtime_metric_name_is_registered() -> None:
    """Catch unknown metrics in cold branches without needing a live hub."""

    call_to_allowlist = {
        "increment_active_metric": RequestMetrics.ALLOWED_COUNTERS,
        "observe_active_metric_max": RequestMetrics.ALLOWED_COUNTERS,
        "add_active_metric_ms": RequestMetrics.ALLOWED_TIMINGS,
    }
    missing: list[str] = []
    scanned = 0
    for path in APP_DIR.rglob("*.py"):
        # Do not inspect vendored third-party files as application call sites.
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        scanned += 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if name not in call_to_allowlist or not node.args:
                continue
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            if first.value not in call_to_allowlist[name]:
                missing.append(
                    f"{path.relative_to(APP_DIR)}:{node.lineno}: "
                    f"{name}({first.value!r})"
                )
    assert scanned > 10, "Expected installed runtime source tree"
    assert not missing, "Unregistered runtime metrics:\n" + "\n".join(missing)


def test_metric_contract_still_rejects_arbitrary_names() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        with pytest.raises(ValueError, match="Unsupported metric counter"):
            increment_active_metric("Bedroom 1 Light private event")
        with pytest.raises(ValueError, match="Unsupported metric timing"):
            add_active_metric_ms("Bedroom 1 Light private event", 2)
        # A pre-registered counter can be safely populated via max semantics.
        observe_active_metric_max("causal_archived_app_log_checks", 3)
        assert metrics.snapshot()["counters"]["causal_archived_app_log_checks"] == 3
    finally:
        metrics.reset(token)
