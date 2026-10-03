from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui import render_page


def test_cleanup_status_and_manual_controls_are_visible() -> None:
    page = render_page("HomeBrain", "0.16.100")
    assert "One-time rule cleanup" in page
    assert 'id="cleanupNextRun"' in page
    assert 'id="cleanupLastRun"' in page
    assert 'id="cleanupDeleted"' in page
    assert 'id="runOneTimeCleanup"' in page
    assert "api/one-time-rule-cleanup" in page
    assert "api/one-time-rule-cleanup/run" in page
