from __future__ import annotations

from webui import render_page


def test_attribute_choice_button_preserves_original_attribute() -> None:
    page = render_page("HomeBrain", "0.16.34")

    assert "function choicePrompt(question,choice)" in page
    assert "return `What is the ${choice} ${attribute}?`" in page
    assert "option.onclick=()=>submit(choicePrompt(originalQuestion,choice))" in page


def test_direct_control_choice_button_preserves_original_action() -> None:
    page = render_page("HomeBrain", "0.16.34")

    assert "const directAction=original.match(/^\\s*(?:please\\s+)?" in page
    assert "(turn\\s+on|turn\\s+off|toggle)\\b/i)?.[1]" in page
    assert "(?:can|could|would|will)\\s+you" in page
    assert "if(directAction)return `${directAction} ${choice}`" in page


def test_choice_action_detection_is_not_unanchored() -> None:
    page = render_page("HomeBrain", "0.16.34")

    # Regression: "Why did hallway lights turn on?" contains the words
    # "turn on" but is not a control request. The old unanchored matcher
    # rewrote the clarification click to "turn on Hallway Light 1".
    assert "question.match(/\\b(turn\\s+on|turn\\s+off|toggle)\\b/i)" not in page
    assert "original.match(/^\\s*" in page


def test_non_control_choice_preserves_original_question_and_exact_device() -> None:
    page = render_page("HomeBrain", "0.16.34")

    assert "const original=String(question||'').trim()" in page
    assert (
        "return original?`${original}\\nDevice clarification: "
        "use exactly ${choice}.`:choice"
    ) in page
