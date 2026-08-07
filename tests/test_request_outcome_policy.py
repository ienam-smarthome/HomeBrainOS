from request_outcome_policy import classify_completed_request


def test_success_without_failure_counters() -> None:
    assert classify_completed_request({}) == "success"
    assert classify_completed_request(None) == "success"


def test_each_coverage_counter_maps_to_expected_outcome() -> None:
    cases = {
        "grounding_refusals": "refused",
        "mutation_verification_failures": "failed",
        "device_control_failures": "failed",
        "request_cancellations": "cancelled",
        "confirmation_expired": "unresolved",
        "device_resolution_ambiguous": "unresolved",
        "device_resolution_missing": "unresolved",
    }

    for counter, expected in cases.items():
        assert classify_completed_request({counter: 1}) == expected


def test_device_control_failure_is_not_masked_as_success() -> None:
    """Regression test for a live-observed bug: a routine light/switch
    dispatch failure ("Failed: Livingroom Light 2 and Livingroom Light
    1.") touched no fixed counter at all, so this classifier fell through
    to its "success" default and the WebUI showed a green Success badge
    next to a message that said the command failed."""

    assert classify_completed_request({"device_control_failures": 1}) == "failed"


def test_outcome_precedence_is_stable_when_multiple_counters_exist() -> None:
    assert classify_completed_request({
        "grounding_refusals": 1,
        "mutation_verification_failures": 1,
        "request_cancellations": 1,
    }) == "refused"

    assert classify_completed_request({
        "mutation_verification_failures": 1,
        "request_cancellations": 1,
        "device_resolution_missing": 1,
    }) == "failed"

    assert classify_completed_request({
        "request_cancellations": 1,
        "confirmation_expired": 1,
    }) == "cancelled"


def test_non_outcome_metrics_do_not_change_classification() -> None:
    assert classify_completed_request({
        "model_rounds": 2,
        "tool_calls": 3,
        "tool_discovery_calls": 1,
        "mcp_retries": 2,
        "evidence_retries": 1,
        "confirmation_queued": 1,
    }) == "success"


def test_zero_and_negative_values_do_not_change_classification() -> None:
    assert classify_completed_request({
        "grounding_refusals": 0,
        "mutation_verification_failures": -1,
        "request_cancellations": 0,
        "device_resolution_missing": 0,
    }) == "success"
