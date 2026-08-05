from __future__ import annotations

from webui import render_page


def test_attribute_choice_button_preserves_original_attribute() -> None:
    page = render_page("HomeBrain", "0.10.334")

    assert "function choicePrompt(question,choice)" in page
    assert "return `What is the ${choice} ${attribute}?`" in page
    assert "option.onclick=()=>submit(choicePrompt(originalQuestion,choice))" in page


def test_control_choice_button_preserves_original_action() -> None:
    page = render_page("HomeBrain", "0.10.334")

    assert "if(action)return `${action} ${choice}`" in page
