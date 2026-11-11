"""Model-led evidence-sufficiency checkpoint for causal first answers.

The checkpoint does NOT inspect data, infer a cause, select a tool, execute a
read, or rewrite an answer. It gives the connected model one final opportunity
to decide whether discriminating evidence is available before it stops.
"""
from __future__ import annotations

import re

_CAUSAL_QUESTION = re.compile(
    r"\bwhy\b|\bwhat\s+(?:caused|triggered|initiated|made|explains)\b"
    r"|\b(?:cause|reason|trigger)\s+(?:of|for|behind)\b"
    r"|\bwho\s+(?:turned|switched|set|changed|started|stopped|issued)\b",
    re.IGNORECASE,
)

SOURCE_REVIEW_PROMPT = """Evidence-sufficiency checkpoint (internal to this answer).
Your previous draft is NOT evidence. Decide independently whether the
successful source receipts actually answer the user's causal question.

Distinguish an observed outcome, the actor reporting it, a recorded command
issuer, and an event-specific trigger or decision. Check actual returned
filters, lookback, result limits, chronology and competing explanations.
A filtered state history without command rows does not rule out unseen
commands. A device/bridge reporter and notified listeners do not prove
external initiation. Chronological compatibility alone does not prove cause.

If a relevant available READ-ONLY MCP source could materially distinguish
the remaining hypotheses, select its exact tool and arguments now. You own
that decision; there is no prescribed source order or required tool call.
If the existing evidence already establishes the answer, or no proportionate
useful read-only source remains, answer now, calibrating unsupported claims.
Do not request unnecessary reads, invent missing evidence, or change any
device, automation, setting, or external record. Follow the original user's
read-only or approval restrictions. Do not mention this internal checkpoint.
"""



def is_read_only_review_tool(name: str) -> bool:
    """Only exposed read-only core tools/gateways and local receipt reads.

    In the Hubitat MCP skill, hub_read_* gateways are read-only and flat
    hub_get_*, hub_list_* and hub_search_* tools are informational. Manage
    gateways can be mixed read/write and are deliberately not exposed during
    this supplemental checkpoint. The original model loop is untouched.
    """
    return name == "homebrain_read_prior_evidence" or (
        isinstance(name, str)
        and name.startswith(("hub_read_", "hub_get_", "hub_list_", "hub_search_"))
    )


def read_only_review_catalog(tools: list[dict]) -> list[dict]:
    """Select only safe tool definitions; never execute or discover a leaf."""
    return [
        item for item in tools if isinstance(item, dict)
        and isinstance(item.get("function"), dict)
        and is_read_only_review_tool(item["function"].get("name"))
    ]


def is_causal_question(question: str) -> bool:
    """Broad intent hint, independent of a specific device or subsystem."""
    return isinstance(question, str) and bool(_CAUSAL_QUESTION.search(question))


def should_review_completion(
    question: str, *, available_tools: bool, already_reviewed: bool,
    remaining_seconds: float,
) -> bool:
    """Only open a model review when there is a chance to investigate safely.

    A short deadline leaves the original model response intact rather than
    risking a second model timeout. No MCP call is made by this helper.
    """
    return (
        not already_reviewed
        and available_tools
        and remaining_seconds > 8
        and is_causal_question(question)
    )
