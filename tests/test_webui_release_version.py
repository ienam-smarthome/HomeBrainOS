from __future__ import annotations

import ast
from pathlib import Path


def assignment(path: str, name: str) -> str:
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise AssertionError(f'{name} not found')


def test_webui_does_not_overwrite_application_release_version() -> None:
    source = Path('hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py').read_text(encoding='utf-8')
    assert 'application.VERSION = PWA_RELEASE_VERSION' not in source
    assert "release_version = str(getattr(application, 'VERSION', PWA_RELEASE_VERSION))" in source
    assert 'release_version,' in source


def test_release_sources_are_aligned() -> None:
    entrypoint = assignment('hubitat-mcp-ai/rootfs/app/entrypoint.py', 'RELEASE_VERSION')
    pwa = assignment('hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py', 'PWA_RELEASE_VERSION')
    config = Path('hubitat-mcp-ai/config.yaml').read_text(encoding='utf-8')
    assert entrypoint == '0.10.28'
    assert pwa == entrypoint
    assert 'version: \"0.10.28\"' in config
