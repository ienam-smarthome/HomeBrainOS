from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_request_layers.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_request_layers",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_request_layer_analyzer_covers_every_raw_assignment_module():
    result = _module().analyze()

    assert result["assignment_site_count"] == 52
    assert result["module_count"] == 39
    assert result["tier_counts"] == {
        "ai-synthesis": 4,
        "answer-guard": 5,
        "deterministic-fast-read": 4,
        "request-observability": 3,
        "safety-critical-write": 26,
        "semantic-evidence": 5,
        "terminal-route": 5,
    }
    assert len(result["assignments"]) == 52
    assert all(item["tier"] for item in result["assignments"])


def test_route_shadow_observer_is_counted_as_request_observability():
    result = _module().analyze()

    observer_assignments = [
        item
        for item in result["assignments"]
        if item["module"] == "route_shadow_observer"
    ]
    assert len(observer_assignments) == 1
    assert observer_assignments[0]["function"] == "install_route_shadow_observer"
    assert observer_assignments[0]["tier"] == "request-observability"


def test_request_layer_analyzer_ignores_non_production_backups():
    result = _module().analyze()

    assert all(not item["module"].endswith("backup") for item in result["assignments"])
