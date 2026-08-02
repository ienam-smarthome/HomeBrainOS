from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_live_soak.py"
spec = importlib.util.spec_from_file_location("run_live_soak", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def valid_metrics() -> dict[str, object]:
    return {
        "metrics": {
            "outcome": "success",
            "counters": {"model_rounds": 1},
            "timings_ms": {"provider": 12, "total": 18},
        },
        "metric_rows": [
            {"label": "Model rounds", "value": "1"},
            {"label": "Total", "value": "18 ms"},
        ],
    }


def test_live_read_requires_evidence() -> None:
    case = module.SoakCase(
        "read",
        "Which lights are on?",
        "session",
        require_evidence=True,
        require_metrics=False,
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
        require_metrics=False,
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
    response = {
        "success": True,
        "message": "No recent errors were returned.",
        "evidence": [{"tool": "hub_read_diagnostics", "success": True}],
        **valid_metrics(),
    }

    assert module.validate_case(case, response) == []


def test_empty_message_is_rejected() -> None:
    case = module.SoakCase("empty", "Hello", "session", require_metrics=False)

    assert module.validate_case(case, {"success": True, "message": "  "}) == [
        "response message is empty"
    ]


def test_metrics_object_is_required_by_default() -> None:
    case = module.SoakCase("metrics", "Hello", "session")

    assert module.validate_case(
        case,
        {"success": True, "message": "Hello."},
    ) == ["metrics object is missing"]


def test_metrics_require_nested_schema_and_stable_rows() -> None:
    result = {
        "metrics": {
            "outcome": "unknown",
            "counters": [],
            "timings_ms": None,
        },
        "metric_rows": [{"label": "Total", "value": "", "extra": "bad"}],
    }

    errors = module.validate_metrics(result)

    assert "metrics outcome is invalid: 'unknown'" in errors
    assert "metrics counters object is missing" in errors
    assert "metrics timings_ms object is missing" in errors
    assert "metric_rows[0] does not use the stable label/value schema" in errors
    assert "metric_rows[0] value is empty" in errors


def test_sensitive_metric_keys_are_rejected_recursively() -> None:
    result = {
        **valid_metrics(),
        "metrics": {
            "outcome": "success",
            "counters": {"model_rounds": 1},
            "timings_ms": {"total": 5},
            "debug": {"session_id": "private-session"},
        },
    }

    assert module.validate_metrics(result) == [
        "privacy-sensitive metric key exposed at metrics.debug.session_id"
    ]


def test_allowed_refused_outcome_passes() -> None:
    result = valid_metrics()
    result["metrics"]["outcome"] = "refused"

    assert module.validate_metrics(result) == []
