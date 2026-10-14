from __future__ import annotations

import json
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
    extract_tool_message_device_identities,
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


def test_tool_message_identities_extract_history_result_without_inventory():
    messages = [{
        "role": "tool",
        "tool_name": "homebrain_device_history",
        "content": json.dumps({
            "result": {
                "success": True,
                "deviceId": "7827",
                "label": "Big lamp",
                "events": [{"name": "switch", "value": "off"}],
            }
        }),
    }]

    assert extract_tool_message_device_identities(messages) == [
        {"id": "7827", "label": "Big lamp"}
    ]


def test_tool_message_identities_extract_nested_resolver_target_and_dedupe():
    messages = [
        {
            "role": "tool",
            "content": json.dumps({
                "result": {
                    "deviceId": "77",
                    "label": "Front Door",
                    "target": {"id": "77", "label": "Front Door"},
                }
            }),
        },
        {
            "role": "tool",
            "content": json.dumps({"result": {"id": "77", "label": "Front Door"}}),
        },
    ]

    assert extract_tool_message_device_identities(messages) == [
        {"id": "77", "label": "Front Door"}
    ]


def test_tool_message_identities_ignore_naked_ids_generic_names_and_bad_json():
    messages = [
        {"role": "assistant", "content": '{"deviceId":"42","label":"Kitchen Light"}'},
        {"role": "tool", "content": "not-json"},
        {"role": "tool", "content": json.dumps({"result": {"deviceId": "42"}})},
        {"role": "tool", "content": json.dumps({"result": {"id": "9", "name": "switch"}})},
    ]

    assert extract_tool_message_device_identities(messages) == []


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


def test_event_produced_by_app_is_not_inferred_to_be_device():
    """Live regression: Bedroom 3 Mesh has refresh commands from an app.

    The final device grounding guard must not demand a device-state lookup
    for Device Health Monitor (app 4072) merely because the history lists
    it in producedBy with both id and label.
    """
    tool_messages = [{"role": "tool", "content": json.dumps({
        "result": {
            "deviceId": "7103", "label": "Bedroom 3 Mesh",
            "observedEvents": [
                {
                    "name": "command-refresh",
                    "producedBy": {
                        "id": "4072", "label": "Device Health Monitor",
                        "type": "app",
                    },
                },
                {
                    "name": "mqttStatus", "value": "connected",
                    "producedBy": {
                        "id": "7103", "label": "Bedroom 3 Mesh",
                        "type": "device",
                    },
                },
            ],
        }
    })}]
    devices = extract_tool_message_device_identities(tool_messages)
    assert devices == [{"id": "7103", "label": "Bedroom 3 Mesh"}]
    assert find_named_device_mismatch(
        "The Device Health Monitor app requested refresh for Bedroom 3 Mesh.",
        devices, {"7103"},
    ) is None


def test_non_device_producer_types_are_ignored_but_real_other_device_is_checked():
    tool_messages = [{"role": "tool", "content": json.dumps({
        "results": [
            {"id": "111", "label": "Another Rule", "type": "app"},
            {"id": "222", "label": "A Bridge", "type": "device"},
            {"id": "333", "label": "A Service", "entityType": "integration"},
            {"id": "444", "label": "An App Instance", "appId": "444"},
        ],
    })}]
    devices = extract_tool_message_device_identities(tool_messages)
    assert devices == [{"id": "222", "label": "A Bridge"}]
    assert find_named_device_mismatch(
        "A Bridge is offline.", devices, {"7103"},
    ) == "A Bridge"


def test_untyped_targeted_device_resolver_identity_is_preserved():
    messages = [{"role": "tool", "content": json.dumps({
        "target": {"id": "7103", "label": "Bedroom 3 Mesh"},
    })}]
    assert extract_tool_message_device_identities(messages) == [
        {"id": "7103", "label": "Bedroom 3 Mesh"}
    ]


def test_investigative_why_is_not_misclassified_as_hubitat_write():
    from mcp_agent_orchestrator import _explicit_mutation_request

    assert _explicit_mutation_request(
        "Investigate thoroughly why did Livingroom Light 1 turn on?"
    ) is False
    assert _explicit_mutation_request(
        "Diagnose why Bedroom 3 Mesh did not turn on."
    ) is False
    assert _explicit_mutation_request(
        "Turn on Livingroom Light 1."
    ) is True
    assert _explicit_mutation_request(
        "Investigate this issue and turn on Livingroom Light 1."
    ) is True
