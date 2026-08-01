from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "hubitat-mcp-ai" / "config.yaml"
ROOT_README = ROOT / "README.md"
ADDON_README = ROOT / "hubitat-mcp-ai" / "README.md"
VERSION_PATTERN = re.compile(r"\b\d+\.\d+\.\d+\b")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _config_version() -> str:
    data = yaml.safe_load(_read(CONFIG))
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise SystemExit(f"invalid add-on version in {CONFIG}: {version!r}")
    return version


def _require_version(path: Path, version: str, marker: str) -> None:
    text = _read(path)
    if marker not in text:
        raise SystemExit(f"missing release marker in {path}: {marker!r}")
    versions = set(VERSION_PATTERN.findall(text))
    if version not in versions:
        raise SystemExit(
            f"{path} does not reference configured add-on version {version}; "
            f"found {sorted(versions)}"
        )


def main() -> int:
    version = _config_version()
    _require_version(ROOT_README, version, "Hubitat MCP AI")
    _require_version(ADDON_README, version, "Current add-on version")
    print(f"release metadata consistent: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
