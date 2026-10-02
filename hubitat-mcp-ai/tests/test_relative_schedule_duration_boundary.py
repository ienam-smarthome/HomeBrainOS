from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from rule_authoring_service import RuleAuthoringService


TARGET = "Block Media-Google-TV-Streamer"


def test_for_duration_is_not_a_relative_start_schedule() -> None:
    service = RuleAuthoringService(
        None,
        lambda *args, **kwargs: None,
        now=lambda: datetime(2026, 10, 2, 22, 25, 12),
    )  # type: ignore[arg-type]

    assert service.matches_request(f"turn on {TARGET} for 1 minute") is False
