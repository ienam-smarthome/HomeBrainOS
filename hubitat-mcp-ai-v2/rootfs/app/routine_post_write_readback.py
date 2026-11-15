"""One bounded, separate native READ after a verified routine write receipt.

This is an optional V2 interactive action outcome observation, not a retry,
a physical sensor, or evidence that the command CAUSED a state transition.
Never call a writer, poll, use an AI round, or treat an embedded write snapshot
as independent readback. The Agent calls this ONLY after acceptance of one
original model-selected routine native write.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from mcp import MCPError, redact
from routine_action_fastpath import _normal, _original, _source_state


def _receipt(args: dict, response: dict | None,
             elapsed_ms: int, error: str = "") -> dict:
    row: dict[str, Any] = {
        "name": "hub_get_device",
        "arguments": args,
        "success": bool(isinstance(response, dict)
                        and response.get("isError") is not True),
        "elapsed_ms": elapsed_ms,
        "result_kind": "tool_result",
        "read_only": True,
        "operation_executed": response is not None,
        "client_routine_post_write_readback": True,
    }
    if response is not None:
        text = json.dumps(redact(response), ensure_ascii=False, default=str)
        row["response"] = text
        row["response_characters"] = len(text)
    if error:
        row["error"] = str(redact(error))[:220]
    return row


async def inspect_routine_post_write_state(
    mcp: Any, candidate: dict, *,
    max_seconds: float = 1.35,
) -> tuple[dict, dict | None]:
    """Perform exactly one READ of the model-selected native device.

    Caller guarantees that a matching ORIGINAL write receipt was accepted
    before invoking this helper. Reported state is not physical proof and
    timestamps in the state payload are not the client's monotonic time.
    """
    no_read = {
        "status": "not_attempted", "reported_switch": None,
        "elapsed_ms": 0, "read_only": True,
        "physical_state_verified": False,
    }
    if (not isinstance(candidate, dict)
            or type(candidate.get("device_id")) is not str
            or not candidate["device_id"]
            or candidate.get("command") not in ("on", "off")
            or not isinstance(candidate.get("label"), str)
            or not candidate["label"]
            or not 0.05 <= max_seconds <= 3.0):
        return no_read, None
    args = {"deviceId": candidate["device_id"]}
    start = time.monotonic()
    try:
        original = await asyncio.wait_for(
            mcp.call("hub_get_device", args), timeout=max_seconds
        )
        record = _receipt(
            args, original, round((time.monotonic()-start)*1000)
        )
    except (MCPError, ValueError, asyncio.TimeoutError) as exc:
        record = _receipt(
            args, None, round((time.monotonic()-start)*1000), str(exc)
        )
        return {
            **no_read, "status": "read_unavailable",
            "elapsed_ms": record["elapsed_ms"],
        }, record
    document = _original(record)
    if document is None:
        return {
            **no_read, "status": "read_unavailable",
            "elapsed_ms": record["elapsed_ms"],
        }, record
    # This is a NEW read, not a copy of the previous write snapshot.
    # No comparison to server wall timestamps is used to claim causality.
    if (str(document.get("id", "")).strip() != candidate["device_id"]
            or not isinstance(document.get("label"), str)
            or _normal(document["label"]) != _normal(candidate["label"])):
        return {
            **no_read, "status": "identity_mismatch",
            "elapsed_ms": record["elapsed_ms"],
        }, record
    observed = _source_state(document)
    if observed is None:
        status = "state_unavailable"
    elif observed == candidate["command"]:
        status = "matched"
    else:
        status = "not_matched"
    return {
        "status": status,
        "reported_switch": observed,
        "elapsed_ms": record["elapsed_ms"],
        "read_only": True,
        "physical_state_verified": False,
        "source": "separate original native hub_get_device after accepted write",
    }, record


def routine_readback_answer(accepted_answer: str, candidate: dict,
                            observation: dict) -> str:
    """Concise evidence-calibrated result; no causality/physical certainty."""
    if not isinstance(observation, dict):
        return accepted_answer
    status = observation.get("status")
    if status not in ("matched", "not_matched", "identity_mismatch",
                      "state_unavailable", "read_unavailable"):
        return accepted_answer
    safe_label = re.sub(r"([\\\x60*_{}\[\]()#+!|>])", r"\\\1",
                        candidate["label"])
    intended = candidate["command"].upper()
    if status == "matched":
        return (f"**{safe_label}: {intended} command accepted.** "
                f"A separate Hubitat read afterward reported switch {intended}. "
                "Physical operation was not independently verified.")
    if status == "not_matched":
        observed = str(observation["reported_switch"]).upper()
        return (f"**{safe_label}: {intended} command accepted.** "
                f"A separate Hubitat read afterward still reported "
                f"switch {observed}; the requested state was not confirmed.")
    if status == "identity_mismatch":
        return (f"**{safe_label}: {intended} command accepted.** "
                "A later native read identified a different device; "
                "the requested state remains unverified.")
    return (f"**{safe_label}: {intended} command accepted.** "
            "The separate Hubitat state read was unavailable or inconclusive; "
            "the requested state remains unverified.")
