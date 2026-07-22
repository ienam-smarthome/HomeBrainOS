from __future__ import annotations

from typing import Any

from control_agent_intent import is_control_candidate


_DEVICE_MUTATION_TOOLS = {
    "hub_call_device_command",
    "hub_manage_devices",
}


def enforce_device_mutation_result(query: str, answer: dict[str, Any]) -> dict[str, Any]:
    """Never let successful reads hide failed device-control mutations."""

    if not is_control_candidate(query):
        return answer
    mutations = [
        item
        for item in answer.get("tools_used") or []
        if isinstance(item, dict) and str(item.get("name") or "") in _DEVICE_MUTATION_TOOLS
    ]
    if not mutations:
        # Safe clarifications, policy blocks and unresolved responses explicitly
        # report failure and must retain their useful explanation. Missing/true
        # success with no mutation evidence fails closed.
        if answer.get("success") is False:
            return answer
        result = dict(answer)
        result["original_message"] = str(answer.get("message") or "")
        result["mutation_policy_corrected"] = True
        result["success"] = False
        result["submitted"] = False
        result["verified"] = None
        result["outcome"] = "failed"
        result["intent"] = "device-control-not-executed"
        result["message"] = (
            "No device command was executed. HomeBrain only read device information, "
            "so no device state change can be claimed."
        )
        return result

    succeeded = [item for item in mutations if item.get("success") is True]
    failed = [item for item in mutations if item.get("success") is not True]
    if not failed:
        return answer

    result = dict(answer)
    result["original_message"] = str(answer.get("message") or "")
    result["mutation_policy_corrected"] = True
    result["success"] = False
    if not succeeded:
        result["intent"] = "device-control-failed"
        result["message"] = "No device command was completed. The requested devices were not changed."
    else:
        result["intent"] = "device-control-partial"
        result["message"] = (
            f"Only {len(succeeded)} of {len(mutations)} device-control operations completed; "
            f"{len(failed)} failed."
        )
    return result


__all__ = ["enforce_device_mutation_result"]
