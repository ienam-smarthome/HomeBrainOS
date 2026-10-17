"""Provider model metadata and conservative paid selection regressions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from paid_model_routing import choose_paid_model
from request_metrics import RequestMetrics
from api_response_builder import _participating_model


def _q(prompt):
    return [{"role": "user", "content": prompt}]


def test_paid_routing_needs_real_investigation():
    for question in ["Which lights are on?", "Show the livingroom rule", "Show sensor status"]:
        assert choose_paid_model(_q(question), "hybrid") is None
    assert choose_paid_model(_q("Investigate why Bedroom 1 Light came on"), "hybrid") == "deepseek-v4-pro"
    assert choose_paid_model(_q("Analyse the recent history of the livingroom rule"), "hybrid") == "deepseek-v4.1-flash"
    assert choose_paid_model(_q("Summarise rule execution history"), "hybrid") == "deepseek-v4.1-flash"


def test_actual_round_model_overrides_configured_default():
    m = RequestMetrics()
    token = m.begin()
    try:
        m.increment("model_rounds")
        m.record_provider_model("gemma4:31b", "ollama-cloud")
        m.record_provider_model("deepseek-v4-pro:0813", "ollama-cloud")
        snap = m.snapshot()
        assert _participating_model(snap, "gemma4:31b") == "deepseek-v4-pro:0813"
        assert snap["model_round_details"] == [
            {"model": "gemma4:31b", "provider": "ollama-cloud"},
            {"model": "deepseek-v4-pro:0813", "provider": "ollama-cloud"},
        ]
    finally:
        m.reset(token)


def test_no_model_on_tool_only_response():
    assert _participating_model({"counters": {"model_rounds": 0}}, "gemma4:31b") is None
