"""Long proposal/write prompts must pass the API boundary without extra authority.

Regression: a structured native Rule Machine question of 2,202 characters
failed with generic HTTP 422 in v0.18.61, before the agent or write-confirmation
workflow had an opportunity to run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from app import ChatRequest, MAX_CHAT_PROMPT_CHARS, app
from webui import render_page


@pytest.mark.parametrize("field", ["query", "prompt"])
def test_rule_write_prompt_2202_chars_is_accepted(field):
    # Proposals and explicit create instructions have the SAME bounded API
    # text shape; acceptance is not write authorisation or confirmation.
    assert MAX_CHAT_PROMPT_CHARS >= 2202
    request = ChatRequest(**{field: "Native Rule Machine TEST\n" + "x" * 2177},
                          model_tier="free")
    assert len(request.message) == 2202
    assert request.model_tier == "free"
    assert request.session_id
    assert request.message.startswith("Native Rule Machine TEST")


@pytest.mark.parametrize("field", ["query", "prompt"])
def test_upper_bound_is_finite_and_exposes_validation_constraint(field):
    good = ChatRequest(**{field: "x" * MAX_CHAT_PROMPT_CHARS})
    assert len(good.message) == MAX_CHAT_PROMPT_CHARS
    with pytest.raises(ValidationError) as exc:
        ChatRequest(**{field: "x" * (MAX_CHAT_PROMPT_CHARS + 1)})
    errors = exc.value.errors(include_input=False)
    assert any(item["type"] == "string_too_long" and
               item["ctx"]["max_length"] == MAX_CHAT_PROMPT_CHARS
               for item in errors)


def test_post_oversize_rejected_before_any_agent_request():
    # No valid-agent invocation here: this checks only pre-route validation.
    client = TestClient(app)
    response = client.post("/api/ask",
                           json={"query": "x" * (MAX_CHAT_PROMPT_CHARS + 1)})
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors[0]["type"] == "string_too_long"
    assert errors[0]["ctx"]["max_length"] == MAX_CHAT_PROMPT_CHARS


def test_frontend_client_displays_specific_422_instead_of_only_http_status():
    page = render_page("HomeBrain", "0.18.62")
    assert "const MAX_CHAT_PROMPT_CHARS=12000;" in page
    assert "function askApiErrorMessage(response,data,length)" in page
    assert "item.type==='string_too_long'" in page
    assert "Ask" in page
    assert "Shorten the question and retry" in page
    assert "nothing was submitted" in page
    assert "askApiErrorMessage(response,data,text.length)" in page
    assert "api/ask" in page
