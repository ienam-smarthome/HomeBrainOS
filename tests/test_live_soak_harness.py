from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_live_soak.py"
spec = importlib.util.spec_from_file_location("run_live_soak", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_live_read_requires_evidence() -> None:
    case = module.SoakCase(
        "read",
        "Which lights are on?",
        "session",
        require_evidence=True,
    )

    assert module.validate_case(
        case,
        {"success": True, "message": "Two lights are on.", "evidence": []},
    ) == ["authoritative evidence is missing"]


def test_confirmation_case_requires_pending_action() -> None:
    case = module.SoakCase(
        "confirmation",
        "Disable Test Rule",
        "session",
        expect_confirmation=True,
    )

    assert module.validate_case(
        case,
        {
            "success": True,
            "message": "Please confirm.",
            "confirmation_required": False,
        },
    ) == ["confirmation_required did not match expected True"]


def test_valid_response_passes() -> None:
    case = module.SoakCase(
        "logs",
        "Show logs",
        "session",
        require_evidence=True,
    )

    assert module.validate_case(
        case,
        {
            "success": True,
            "message": "No recent errors were returned.",
            "evidence": [{"tool": "hub_read_diagnostics", "success": True}],
        },
    ) == []


def test_empty_message_is_rejected() -> None:
    case = module.SoakCase("empty", "Hello", "session")

    assert module.validate_case(case, {"success": True, "message": "  "}) == [
        "response message is empty"
    ]
