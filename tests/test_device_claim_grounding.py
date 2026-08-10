from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_claim_grounding import (  # noqa: E402
    DEVICE_CLAIM_REFUSAL,
    DEVICE_CLAIM_RETRY_INSTRUCTION,
    DeviceClaimAction,
    DeviceClaimGroundingPolicy,
    extract_receipt_device_ids,
    find_named_device_mismatch,
)


_DEVICES = [
    {"id": "42", "label": "Kitchen Light"},
    {"id": "77", "label": "Front Door"},
]


def test_extract_receipt_device_ids_reads_nested_gateway_arguments():
    receipts = [
        {
            "success": True,
            "arguments": {
                "tool": "hub_get_device_attribute",
                "args": {"deviceId": "42", "attribute": "switch"},
            },
        },
        {
            "success": True,
            "arguments": {"tool": "hub_manage_devices", "args": {"id": "77"}},
        },
    ]

    assert extract_receipt_device_ids(receipts) == {"42", "77"}


def test_extract_receipt_device_ids_ignores_failed_receipts():
    receipts = [
        {
            "success": False,
            "arguments": {"tool": "x", "args": {"deviceId": "42"}},
        },
    ]

    assert extract_receipt_device_ids(receipts) == set()


def test_extract_receipt_device_ids_ignores_non_scalar_id_values():
    receipts = [
        {
            "success": True,
            "arguments": {"deviceId": {"nested": "not a real id"}},
        },
    ]

    assert extract_receipt_device_ids(receipts) == set()


def test_named_device_mismatch_is_found_when_evidence_covers_a_different_device():
    mismatch = find_named_device_mismatch(
        "The Front Door is currently locked.", _DEVICES, {"42"}
    )

    assert mismatch == "Front Door"


def test_no_mismatch_when_the_named_device_matches_the_evidence():
    mismatch = find_named_device_mismatch(
        "The Kitchen Light is on.", _DEVICES, {"42"}
    )

    assert mismatch is None


def test_no_mismatch_when_no_known_device_is_named():
    mismatch = find_named_device_mismatch(
        "Nothing relevant was found.", _DEVICES, {"42"}
    )

    assert mismatch is None


def test_no_mismatch_when_this_turn_collected_no_device_scoped_evidence():
    """A turn with zero device-scoped evidence is left to the existing
    has-any-live-evidence grounding check instead of this one."""

    mismatch = find_named_device_mismatch("The Front Door is locked.", _DEVICES, set())

    assert mismatch is None


def test_short_labels_are_never_matched_to_avoid_false_positives():
    devices = [{"id": "1", "label": "TV"}]

    mismatch = find_named_device_mismatch(
        "The TV in the living room is on.", devices, {"42"}
    )

    assert mismatch is None


def test_prefix_label_collision_does_not_produce_a_false_mismatch():
    """Live-observed false positive: a correct, fully-evidenced answer
    about "Front Door Sensor" was flagged as naming a mismatched device
    because "Front Door" (a *different* real device, id "1") matched as a
    valid word-bounded substring of the longer label -- even though the
    answer never actually named that shorter-labeled device at all.
    """

    devices = [
        {"id": "1", "label": "Front Door"},
        {"id": "2", "label": "Front Door Sensor"},
    ]

    mismatch = find_named_device_mismatch(
        "The Front Door Sensor shows the door is closed.", devices, {"2"}
    )

    assert mismatch is None


def test_prefix_label_collision_still_catches_a_genuine_mismatch():
    """The longest-match-first fix must not blind the check to a real,
    separately-mentioned mismatch just because a longer-labeled sibling
    device also exists."""

    devices = [
        {"id": "1", "label": "Front Door"},
        {"id": "2", "label": "Front Door Sensor"},
    ]

    mismatch = find_named_device_mismatch(
        "The Front Door is locked.", devices, {"2"}
    )

    assert mismatch == "Front Door"


def test_prefix_label_collision_still_catches_a_different_unrelated_device():
    devices = [
        {"id": "1", "label": "Front Door Sensor"},
        {"id": "3", "label": "Kitchen Light"},
    ]

    mismatch = find_named_device_mismatch(
        "The Front Door Sensor shows closed but the Kitchen Light is on.",
        devices,
        {"1"},
    )

    assert mismatch == "Kitchen Light"


def test_policy_accepts_when_there_is_no_mismatch():
    policy = DeviceClaimGroundingPolicy()

    decision = policy.decide(None)

    assert decision.action is DeviceClaimAction.ACCEPT
    assert decision.message is None


def test_policy_retries_once_then_refuses_the_same_mismatch():
    policy = DeviceClaimGroundingPolicy()

    first = policy.decide("Front Door")
    assert first.action is DeviceClaimAction.RETRY
    assert first.message == DEVICE_CLAIM_RETRY_INSTRUCTION.format(label="Front Door")

    second = policy.decide("Front Door")
    assert second.action is DeviceClaimAction.REFUSE
    assert second.message == DEVICE_CLAIM_REFUSAL.format(label="Front Door")


def test_policy_refuses_even_when_a_different_device_mismatches_on_the_retry():
    """The policy's retry budget is one *decision cycle*, not one per label
    -- a model that keeps naming the wrong device after the retry
    instruction must not get unlimited additional attempts."""

    policy = DeviceClaimGroundingPolicy()

    assert policy.decide("Front Door").action is DeviceClaimAction.RETRY

    second = policy.decide("Back Door")
    assert second.action is DeviceClaimAction.REFUSE
    assert second.message == DEVICE_CLAIM_REFUSAL.format(label="Back Door")
