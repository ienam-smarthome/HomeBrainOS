from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_entrypoint_uses_only_the_central_named_entity_resolver_layer():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "install_named_entity_resolution_adapters" in source
    assert "install_named_rule_match_guard" not in source
    assert "named_rule_match_guard =" not in source


def test_disable_guard_is_installed_before_central_entity_resolution():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    disable_position = source.index("named_rule_disable_guard = install_named_rule_disable_guard")
    resolver_position = source.index("named_entity_resolver = install_named_entity_resolution_adapters")

    assert disable_position < resolver_position
