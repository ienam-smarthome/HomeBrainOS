"""Ground model claims about one specific device against this turn's evidence.

grounding_policy.py / live_evidence_authority.py only check that *some* live
tool call succeeded this turn, never that it actually backs the specific
device the final answer names -- a model that reads Device A's live state
could still answer a question about Device B and pass that check untouched.
This module adds one further, narrow check on top of it: when the final
answer names a specific device (matched against the known inventory label)
and this turn's successful evidence receipts carry a *different* device's
id, the claim is not grounded for that device.

This deliberately does not attempt full claim-to-evidence verification
(extracting every factual statement in the answer and matching each one to
specific evidence) -- that is a much larger, higher-risk scope with no
existing test harness. It only catches the clearest failure mode: an answer
confidently naming one device while this turn's device-scoped evidence is
about a different device entirely. It is intentionally silent (does nothing)
when:
  - the answer does not name any known device by label, or
  - this turn collected no device-scoped evidence at all (in that case the
    existing has-any-live-evidence check in grounding_policy.py is the
    relevant guard, not this one), or
  - the named device's id *is* among this turn's evidence.

Known limitation: label matching is a plain case-insensitive whole-word
search over the final answer text, not an understanding of which clauses
are factual claims. An answer that merely *mentions* another device for
comparison ("unlike the Front Door, the Back Door is now locked") can still
trigger a retry if evidence was only collected for the Back Door. This is an
accepted tradeoff for a narrow, deterministic, low-risk check -- the retry
instruction asks the model to fetch evidence for the named device, which is
harmless even when the mention was incidental.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


DEVICE_CLAIM_RETRY_INSTRUCTION = (
    'HOST DEVICE-EVIDENCE MISMATCH: Your answer names "{label}", but no '
    "successful tool result this turn was scoped to that device -- the "
    'live evidence you gathered is about a different device. Call the '
    'appropriate read tool for "{label}" specifically, then answer only '
    "from that result."
)
DEVICE_CLAIM_REFUSAL = (
    'I could not verify the claim about "{label}" against evidence actually '
    "collected for that device this turn, so I will not provide an "
    "unverified answer."
)

_DEVICE_ID_KEYS = ("deviceId", "device_id", "id")
_MIN_LABEL_LENGTH = 3


class DeviceClaimAction(str, Enum):
    """Outcome when the final answer names a device by label."""

    ACCEPT = "accept"
    RETRY = "retry"
    REFUSE = "refuse"


@dataclass(frozen=True, slots=True)
class DeviceClaimDecision:
    """One deterministic device-claim-grounding decision."""

    action: DeviceClaimAction
    message: str | None = None
    mismatched_label: str | None = None


def _normalize_id(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    return text or None


def extract_receipt_device_ids(receipts: list[dict[str, Any]]) -> set[str]:
    """Collect every device id referenced by a successful receipt's
    arguments this turn.

    Searches nested dicts because gateway-style calls wrap the real
    arguments inside {"tool": ..., "args": {"deviceId": ...}}; a bare
    top-level id would miss those entirely.
    """

    ids: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _DEVICE_ID_KEYS:
                    normalized = _normalize_id(value)
                    if normalized:
                        ids.add(normalized)
                _walk(value)
        elif isinstance(node, list):
            for item in node[:20]:
                _walk(item)

    for receipt in receipts:
        if not receipt.get("success"):
            continue
        _walk(receipt.get("arguments"))
    return ids


def find_named_device_mismatch(
    answer: str,
    devices: list[dict[str, Any]],
    receipt_device_ids: set[str],
) -> str | None:
    """Return the first device label the answer names whose id was never
    referenced by this turn's successful evidence, or None if there is no
    such mismatch.

    Deliberately conservative: only ever fires when this turn actually
    collected device-scoped evidence (`receipt_device_ids` non-empty) -- a
    turn with no device-scoped evidence at all is left to the existing
    has-any-live-evidence grounding check instead of this one.
    """

    text = str(answer or "")
    if not text.strip() or not receipt_device_ids:
        return None

    candidates: list[tuple[str, str]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        label = str(device.get("label") or "").strip()
        device_id = _normalize_id(device.get("id"))
        if not label or not device_id or len(label) < _MIN_LABEL_LENGTH:
            continue
        candidates.append((label, device_id))

    # Live-observed false positive: when one device's label is a prefix of
    # another's (e.g. "Front Door" vs. "Front Door Sensor"), a correct,
    # fully-evidenced answer about the longer-labeled device still matched
    # the shorter label as a valid word-bounded substring (a space isn't a
    # word character), flagging a device the answer never actually named.
    # Matching longest labels first, and treating a shorter label's match
    # as already accounted for once it falls entirely inside a longer
    # label's match span, avoids double-counting the same mention under
    # two different device labels.
    candidates.sort(key=lambda item: len(item[0]), reverse=True)

    claimed_spans: list[tuple[int, int]] = []
    mismatch: str | None = None
    for label, device_id in candidates:
        pattern = rf"(?<![\w-]){re.escape(label)}(?![\w-])"
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        start, end = match.span()
        if any(
            claimed_start <= start and end <= claimed_end
            for claimed_start, claimed_end in claimed_spans
        ):
            continue
        claimed_spans.append((start, end))
        if device_id in receipt_device_ids:
            continue
        if mismatch is None:
            mismatch = label
    return mismatch


class DeviceClaimGroundingPolicy:
    """Allow one retry before refusing an unresolved device-evidence mismatch."""

    def __init__(self) -> None:
        self._retry_used = False

    def decide(self, mismatched_label: str | None) -> DeviceClaimDecision:
        """Accept when there is no mismatch, retry once, then refuse."""

        if mismatched_label is None:
            return DeviceClaimDecision(DeviceClaimAction.ACCEPT)
        if not self._retry_used:
            self._retry_used = True
            return DeviceClaimDecision(
                DeviceClaimAction.RETRY,
                DEVICE_CLAIM_RETRY_INSTRUCTION.format(label=mismatched_label),
                mismatched_label=mismatched_label,
            )
        return DeviceClaimDecision(
            DeviceClaimAction.REFUSE,
            DEVICE_CLAIM_REFUSAL.format(label=mismatched_label),
            mismatched_label=mismatched_label,
        )


__all__ = [
    "DEVICE_CLAIM_REFUSAL",
    "DEVICE_CLAIM_RETRY_INSTRUCTION",
    "DeviceClaimAction",
    "DeviceClaimDecision",
    "DeviceClaimGroundingPolicy",
    "extract_receipt_device_ids",
    "find_named_device_mismatch",
]
