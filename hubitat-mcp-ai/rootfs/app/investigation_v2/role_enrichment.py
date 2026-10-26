"""Optional bounded enrichment after a validated semantic objective.

A role model cannot plan an MCP call, rewrite intent, or insert device IDs.
Every proposed ID/label pair is validated against live source inventory.
Failures reduce confidence; they must not erase a successful base question.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from typing import Any, Awaitable, Callable, Mapping, Sequence

from .measurement_semantics import candidates, validated_model_hints
from .semantic_plan import SemanticPlan

_ROLE_INSTRUCTIONS = (
    "Classify the *measurement coverage* of each candidate when possible. "
    "Return ONLY JSON object {\"measurement_roles\":[{\"id\":\"...\","
    "\"label\":\"...\",\"role\":\"site_total|circuit_subtotal|individual_load|unknown\"}]}."
    " The id and label must match a supplied candidate exactly. "
    "Site totals measure the entire property; circuit totals cover a group "
    "of downstream devices; individual loads cover one load. "
    "Use unknown when ambiguous, and omit candidates you cannot classify. "
    "These are interpretations, not independently verified device metadata. "
    "Never calculate totals, change the semantic objective, or request tools."
)


async def enrich_measurement_roles(
    plan: SemanticPlan,
    devices: Sequence[Mapping[str,Any]],
    chat: Callable[[list[dict[str,Any]],list[dict[str,Any]]],
                   Awaitable[dict[str,Any]]],
    *,
    timeout_seconds: float = 12,
) -> tuple[SemanticPlan, dict[str, Any]]:
    if (plan.mode != "inventory" or plan.attribute not in ("power","energy")
            or plan.aggregation not in ("top","bottom","sum","average")
            or plan.scope == "named"):
        return plan, {"outcome":"not_applicable","candidates":0,
                      "accepted_hints":0}
    catalog=candidates(devices)
    # A bounded catalogue is a performance and evidence limit, not a source
    # completeness claim. Missing roles remain unknown.
    selected=catalog[:40]
    if not selected:
        return plan, {"outcome":"no_meter_candidates","candidates":0,
                      "accepted_hints":0}
    request=json.dumps({
        "task":"measurement coverage only",
        "meter_candidates":selected,
        "interpretation_only":True,
    },ensure_ascii=True)
    try:
        response=await asyncio.wait_for(
            chat([
                {"role":"system","content":_ROLE_INSTRUCTIONS},
                {"role":"user","content":request},
            ], []),
            timeout=max(1.0,min(20.0,float(timeout_seconds))),
        )
        if not isinstance(response,dict) or response.get("tool_calls"):
            raise ValueError("invalid_role_model_response")
        raw=response.get("content")
        if not isinstance(raw,str) or not 0<len(raw)<=9000:
            raise ValueError("invalid_role_model_length")
        stripped=raw.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped=stripped[3:-3].strip()
            if stripped.lower().startswith("json"):
                stripped=stripped[4:].strip()
        parsed=json.loads(stripped)
        if not isinstance(parsed,dict) or set(parsed)!={"measurement_roles"}:
            raise ValueError("invalid_role_schema")
        approved=validated_model_hints(parsed["measurement_roles"],selected)
        return replace(plan,measurement_roles=approved),{
            "outcome":"enriched","candidates":len(selected),
            "candidate_catalogue_truncated":len(catalog)>len(selected),
            "accepted_hints":len(approved),
        }
    except asyncio.CancelledError:
        # An outer cancellation should still cancel the whole request; a
        # local timeout is caught as TimeoutError below.
        raise
    except Exception as exc:
        reason=("timeout" if isinstance(exc,TimeoutError)
                else "provider_error" if not isinstance(exc,(ValueError,TypeError,json.JSONDecodeError))
                else "invalid_role_proposal")
        return plan,{
            "outcome":"unavailable","reason":reason,
            "candidates":len(selected),
            "candidate_catalogue_truncated":len(catalog)>len(selected),
            "accepted_hints":0,
        }


__all__=["enrich_measurement_roles"]
