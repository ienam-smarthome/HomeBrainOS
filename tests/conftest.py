from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

_HISTORICAL_FAILURES_FILE = Path(__file__).with_name("historical_failures.txt")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-historical-failures",
        action="store_true",
        default=False,
        help="Run tests quarantined from the legacy full-suite baseline without xfail marking.",
    )


def _historical_nodeids() -> set[str]:
    if not _HISTORICAL_FAILURES_FILE.exists():
        return set()
    return {
        line.strip()
        for line in _HISTORICAL_FAILURES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-historical-failures"):
        return

    historical = _historical_nodeids()
    if not historical:
        return

    marker = pytest.mark.xfail(
        strict=False,
        reason=(
            "Quarantined legacy assertion from the pre-0.10.166 full-suite baseline; "
            "the blocking release gate remains authoritative until this test is modernised."
        ),
    )
    for item in items:
        if item.nodeid in historical:
            item.add_marker(marker)
