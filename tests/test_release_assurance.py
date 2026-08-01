from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "hubitat-mcp-ai"


def test_release_consistency_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_release_consistency.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_addon_config_has_safe_ingress_defaults() -> None:
    config = yaml.safe_load((ADDON / "config.yaml").read_text(encoding="utf-8"))
    assert config["ingress"] is True
    assert config["ports"]["8788/tcp"] is None
    assert config["options"]["require_sensitive_confirmation"] is True


def test_runtime_modules_compile() -> None:
    app_root = ADDON / "rootfs" / "app"
    failures: list[str] = []
    for path in sorted(app_root.glob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except Exception as exc:  # pragma: no cover - assertion reports exact module
            failures.append(f"{path.name}: {exc}")
    assert not failures, "\n".join(failures)


def test_required_runtime_dependencies_are_declared() -> None:
    requirements = (ADDON / "rootfs" / "app" / "requirements.txt").read_text(
        encoding="utf-8"
    )
    declared = {
        re.split(r"[<>=!~;\[]", line.strip(), maxsplit=1)[0].lower()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "fastapi" in declared
    assert "uvicorn" in declared
    assert "httpx" in declared
    assert importlib.util.find_spec("yaml") is not None
