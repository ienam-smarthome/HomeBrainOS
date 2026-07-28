from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_request_registry_migration.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("request_registry_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_final_request_registry_audit_passes():
    result = _load_audit_module().audit()

    assert result["passed"] is True
    assert result["registry_order_valid"] is True
    assert result["runtime_legacy_installer_calls"] == []
    assert result["capture_count"] == 6
    assert result["registry_install_count"] == 5
    assert result["direct_runtime_bridge"] is True
    assert result["finalized_before_runtime_bridge"] is True


def test_audit_declares_registry_migration_complete():
    result = _load_audit_module().audit()

    assert result["conclusion"].startswith("Thread 1 step 3 complete")
    assert result["expected_registries"] == [
        "hub-health-display-registry",
        "semantic-home-registry",
        "summary-thermostat-registry",
        "read-execution-registry",
        "ai-grounding-registry",
    ]
