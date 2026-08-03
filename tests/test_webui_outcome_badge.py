from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui import render_page  # noqa: E402


def test_rendered_webui_consumes_api_outcome_presentation() -> None:
    page = render_page("HomeBrain", "0.10.318")

    assert "const outcome=data.outcome_presentation" in page
    assert "outcomeBadge.textContent=outcome.label" in page
    assert "outcome-${outcome.tone}" in page


def test_rendered_webui_supports_every_fixed_tone() -> None:
    page = render_page("HomeBrain", "0.10.318")

    for tone in ("positive", "warning", "neutral", "critical"):
        assert f".outcome-{tone}" in page
    assert "['positive','warning','neutral','critical'].includes(outcome.tone)" in page


def test_outcome_label_is_inserted_with_text_content_not_html() -> None:
    page = render_page("HomeBrain", "0.10.318")

    assert "outcomeBadge.textContent=outcome.label" in page
    assert "outcomeBadge.innerHTML" not in page


def test_legacy_response_without_outcome_presentation_still_renders() -> None:
    page = render_page("HomeBrain", "0.10.318")

    assert "if(outcome&&" in page
    assert "[data.route,data.model" in page


def test_confirmation_button_remains_structurally_gated() -> None:
    page = render_page("HomeBrain", "0.10.318")

    assert "if(data.confirmation_required===true)" in page
    assert "if(/please confirm/i.test(rawMessage))" not in page
