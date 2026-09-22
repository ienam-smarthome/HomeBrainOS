from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_subject_prefetch import causal_subject_seed  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


def device(
    device_id: str,
    label: str,
    *,
    room: str = "",
) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": ["Switch", "PowerMeter"],
        "attributes": {"switch": "off", "power": 0},
        "commands": ["on", "off"],
    }


def test_exact_named_switch_causal_subject_is_prefetched() -> None:
    seed = causal_subject_seed(
        "Why did Dehumidifier 2 turn on?",
        [
            device("4222", "Dehumidifier 2"),
            device("5313", "Dehumidifier 1"),
        ],
    )

    assert seed is not None
    assert seed.name == "Dehumidifier 2"
    assert seed.attribute == "switch"
    assert seed.confidence == 1.0


def test_minor_device_typo_is_prefetched_when_unique() -> None:
    seed = causal_subject_seed(
        "Why did dehumidifer 2 turn on?",
        [
            device("4222", "Dehumidifier 2"),
            device("5313", "Dehumidifier 1"),
        ],
    )

    assert seed is not None
    assert seed.name == "Dehumidifier 2"
    assert seed.attribute == "switch"
    assert seed.confidence >= 0.90
    assert seed.matched_text == "dehumidifer 2"


def test_numbered_device_mismatch_does_not_prefetch_wrong_target() -> None:
    seed = causal_subject_seed(
        "Why did Dehumidifier 3 turn on?",
        [
            device("4222", "Dehumidifier 2"),
            device("5313", "Dehumidifier 1"),
        ],
    )

    assert seed is None


def test_generic_or_non_transition_causal_question_stays_model_routed() -> None:
    identities = [device("4222", "Dehumidifier 2")]

    assert causal_subject_seed(
        "Why is Dehumidifier 2 using so much power?",
        identities,
    ) is None
    assert causal_subject_seed(
        "Why is the room humid?",
        identities,
    ) is None


def test_non_switch_device_does_not_take_switch_prefetch_path() -> None:
    seed = causal_subject_seed(
        "Why did Front Door turn on?",
        [{
            "id": "10",
            "label": "Front Door",
            "capabilities": ["ContactSensor"],
            "attributes": {"contact": "closed"},
        }],
    )

    assert seed is None


def test_prefetch_metric_is_supported_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_subject_prefetch")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["causal_subject_prefetch"] == 1
    assert {
        "label": "Causal subject prefetches",
        "value": "1",
    } in present_request_metrics(snapshot)
