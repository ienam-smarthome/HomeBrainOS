"""Pre-synthesis evidence/claim plan for a single causal OFF investigation.

Normalizes observations, associations and proof limits *before* model synthesis.
The model still writes the answer. Post-synthesis checks guard source-scope
claims, not device names or a single historical incident.
"""
from __future__ import annotations

import json
import re
from typing import Any

from causal_completion_policy import requested_transition_scope


def build_causal_answer_plan(
    graph: dict[str, Any], original_user: str,
) -> dict[str, Any] | None:
    """Build typed, source-scoped answer obligations; do not infer new actors."""
    if (
        graph.get("scope") != "single-observed-event"
        or requested_transition_scope(original_user) != "off"
    ):
        return None
    off = ((graph.get("transitionEvidence") or {}).get("off") or {})
    if not off.get("observed"):
        return None
    focus = graph.get("focus") or {}
    history = off.get("commandHistory") or {}
    state = off.get("state") or {}
    reporter = state.get("reporter") or {}
    direct = off.get("directCommand")
    hypotheses = graph.get("offHypotheses") or {}
    controller = graph.get("controllerCandidate") or {}
    journal = off.get("archivedSensorEvidence") or {}
    journal_observations = [
        row for row in (journal.get("observations") or [])[:8]
        if isinstance(row, dict)
    ]

    command_observation = {
        "kind": "verified-direct-command" if direct else (
            "bounded-command-history-checked" if history.get("checked")
            else "command-history-unavailable-or-unchecked"
        ),
        "focalDirectCommand": direct,
        "historyChecked": bool(history.get("checked")),
        "returnedCommandEvents": history.get("eventCount"),
        "historyResult": history.get("result"),
        "interpretation": (
            "Only the recorded direct command's producer is established."
            if direct else
            "No command linked to the focal OFF was established. The returned "
            "command-history page may contain older events; a missing match "
            "does not prove that Hubitat issued no command."
        ),
    }
    sensor_evidence = []
    for row in (off.get("sensorCorrelations") or [])[:6]:
        if not isinstance(row, dict):
            continue
        sensor_evidence.append({
            "label": row.get("sensor"),
            "value": row.get("value"),
            "signedDeltaMs": row.get("signedDeltaMs"),
            "relationship": "temporal-correlation-only",
        })

    timer_assessments = []
    for row in (hypotheses.get("sensorTimerComparisons") or []):
        if not isinstance(row, dict):
            continue
        timer_assessments.append({
            "sensor": row.get("sensor"),
            "configuredDelayMs": row.get("configuredDelayMs"),
            "elapsedBeforeOffMs": row.get("elapsedBeforeOffMs"),
            "assessment": row.get("assessment"),
            "interpretation": {
                "too-soon-for-new-timer": (
                    "This recorded sensor edge cannot have started a fresh "
                    "timer which expired before the OFF event."
                ),
                "edge-after-off": (
                    "This sensor edge happened after the OFF transition."
                ),
                "timing-compatible-not-execution-proof": (
                    "Timing allows a fresh timer but does not prove it ran."
                ),
            }.get(str(row.get("assessment")), "No causal conclusion"),
        })
    controller_note = None
    if controller:
        if controller.get("status") == "ambiguous-multiple-controller-candidates":
            controller_note = {
                "relationship": "ambiguous-temporal-association",
                "mappingVerified": False,
            }
        else:
            controller_note = {
                "label": controller.get("label"),
                "event": controller.get("event"),
                "signedDeltaMs": controller.get("signedDeltaMs"),
                "repeatedAlignedStarts": controller.get("repeatedAlignedStarts"),
                "relationship": "temporal-association-not-verified-trigger",
                "recordedOrder": controller.get("recordedOrder"),
                "mappingVerified": bool(
                    controller.get("directControllerToDeviceMappingProven")
                ),
            }

    return {
        "schema": "causal-answer-plan/v1",
        "focus": {
            "subject": focus.get("subject"),
            "off": off.get("time"),
            "on": focus.get("on"),
            "durationSeconds": focus.get("durationSeconds"),
        },
        "evidence": {
            "offBoundary": {
                "status": "observed",
                "reporter": reporter.get("label"),
                "reporterRole": "reports-state-not-proven-command-issuer",
            },
            "offCommand": command_observation,
            "sensorEdges": sensor_evidence,
            "sensorHistoryCoverage": off.get("sensorHistoryCoverage") or {},
            "windowedSensorRetrieval": off.get("windowedSensorRetrieval") or [],
            "archivedSensorObservations": {
                "source": "HomeBrain local Historical Journal",
                "count": int(journal.get("archivedObservationCount") or 0),
                "sourceRows": [
                    {"deviceId": row.get("deviceId"), "label": row.get("label"),
                     "value": row.get("value"),
                     "observedAt": row.get("observedAt"),
                     "timestampBasis": row.get("timestampBasis")}
                    for row in journal_observations
                ],
                "verifiedMcpWindowCount": journal.get("verifiedMcpWindowCount"),
                "verifiedMcpReturnedEventCount":
                    journal.get("verifiedMcpReturnedEventCount"),
                "historyComplete": False,
                "collectorReceptionDoesNotProveSensorEventTime": True,
                "notProofOfOffCauseOrTimer": True,
            },
            "archivedAppLogReconciliation":
                off.get("archivedAppLogReconciliation") or {},
            "timerComparisons": timer_assessments,
            "appConfiguration": {
                "checked": bool(
                    ((off.get("notifiedListenerContext") or {})
                     .get("configuration") or {}).get("checked")
                    or ((off.get("appProducerContext") or {})
                        .get("configuration") or {}).get("checked")
                ),
                "historicalConfigurationVerified": bool(
                    hypotheses.get("historicalConfigVerified")
                ),
                "timerExecutionVerified": bool(
                    off.get("internalTimerExecutionVerified")
                ),
            },
            "executionLogs": (
                (off.get("appProducerContext") or {}).get("executionLogs")
                if (off.get("appProducerContext") or {})
                   .get("executionLogs", {}).get("checked")
                else (off.get("notifiedListenerContext") or {}).get("executionLogs")
            ),
            "onControllerContext": controller_note,
            "postOnCommands": [
                {"command": item.get("command"),
                 "producer": item.get("producer"),
                 "relationship": "verified-direct-command-not-on-initiator"}
                for item in (graph.get("postOnCommands") or [])[:3]
                if isinstance(item, dict)
            ],
        },
        "hypotheses": hypotheses.get("hypotheses") or [],
        "answerObligations": [
            "Lead with the best-supported OFF verdict, not an ON explanation.",
            "If sensorHistoryCoverage reports pre-focal-not-observed-in-returned-pages, "
            "state that the returned local sensor history does not reach the "
            "focal boundary. Do not infer absence of earlier inactivity or "
            "claim new timer feasibility from missing edges. Stop broad "
            "external speculation without concrete command provenance.",
            "State observed facts before interpretations; mark each proposed "
            "cause as verified, temporally correlated, inconsistent with the "
            "observed timing, or unresolved.",
            "Integrate timing feasibility into the automation assessment, "
            "not as a trailing note. A newly started timer is distinct from "
            "an earlier pending timer.",
            "A command-history page containing older entries is not a zero-"
            "entry result. Absence of a focal match cannot exclude unlogged "
            "Hubitat actions or external control.",
            "Do not call a controller event a confirmed initiating trigger "
            "unless its actual controller-to-light mapping is verified; "
            "transport ordering may place button events after the ON state.",
            "Do not elevate state reporters or event listeners into command "
            "producers. Omit incidental listeners unless the user explicitly "
            "asks for them or their actions are material.",
            *(
                ["Explicitly report the local Historical Journal's "
                 "archived sensor observation count and sensor states alongside "
                 "MCP window results. Do not equate a verified MCP window "
                 "returning zero rows with zero archived observations. Clearly "
                 "label collector-received timestamps as nonauthoritative for "
                 "source-event ordering, and never infer an OFF cause or timer."]
                if journal_observations else []
            ),
            "Use one short conclusion, one relevant timeline if useful, and "
            "a concise assessment of competing causes. Avoid repeated "
            "uncertainty summaries or unsupported absolutes.",
        ],
    }


def render_causal_answer_plan(
    graph: dict[str, Any], original_user: str,
) -> str | None:
    plan = build_causal_answer_plan(graph, original_user)
    if plan is None:
        return None
    return (
        "HOST PRE-SYNTHESIS CAUSAL ANSWER PLAN (typed evidence obligations; "
        "compose one integrated final answer rather than reproducing JSON):\n"
        + json.dumps(plan, ensure_ascii=False, separators=(",", ":"), default=str)
    )


_UNBOUNDED_COMMAND_NEGATIVE = re.compile(
    # Only correct a *globally scoped Hubitat* negative. The old pattern
    # matched the substring "no command was issued" inside a scoped sentence
    # such as "...by this app ... in bounded history", inserting a complete
    # sentence and leaving "by this app" orphaned. Preserve such source-scoped
    # observations rather than fragmenting them.
    r"(?ix)\b(?:"
    r"(?:no|zero)\s+(?:off\s+)?(?:hubitat|hub[- ]side)\s+commands?\s+"
    r"(?:was|were|has\s+been|have\s+been)\s+"
    r"(?:issued|sent|executed)"
    r"|(?:the\s+hub|hubitat)\s+(?:issued|sent|executed)\s+"
    r"no\s+(?:\x60?off\x60?\s+)?commands?"
    r"|(?:no|zero)\s+(?:\x60?off\x60?\s+)?commands?\s+"
    r"(?:was|were|has\s+been|have\s+been)\s+"
    r"(?:issued|sent|executed)\s+by\s+(?:the\s+hub|hubitat)"
    r")\b"
)


def guard_causal_answer_claim_boundaries(
    message: str, graph: dict[str, Any], original_user: str,
) -> tuple[str, bool]:
    """Reject globally negative command claims and false zero-row descriptions.

    The replacement is scoped to returned evidence, even if older rows exist.
    Does not claim an external cause or synthesize a new timeline.
    """
    plan = build_causal_answer_plan(graph, original_user)
    if not plan:
        return str(message or ""), False
    command = plan["evidence"]["offCommand"]
    if command["kind"] == "verified-direct-command":
        return str(message or ""), False
    source = str(message or "")
    # A bounded source-aware clause can appear mid-sentence. Do not insert a
    # capitalized standalone sentence (with a period) into that clause.
    def _replace_global_negative(match: re.Match[str]) -> str:
        scoped = ("no matching focal OFF command was established in "
                  "the returned bounded Hubitat command history; this does "
                  "not prove that the hub issued no command")
        return scoped[0].upper() + scoped[1:] if (
            match.group(0)[:1].isupper()
        ) else scoped
    source, count = _UNBOUNDED_COMMAND_NEGATIVE.subn(
        _replace_global_negative, source
    )
    changed = count > 0

    # A positive number of older command rows must not become a zero-row
    # assertion about the returned history. Do not rewrite "zero *matching*".
    number = command.get("returnedCommandEvents")
    if command.get("historyChecked") and isinstance(number, int) and number > 0:
        erroneous_zero = re.compile(
            r"(?i)(?:command(?:-off)?\s+history|"
            r"(?:command\s+)?history\s+(?:for\s+this\s+(?:specific\s+)?transition))"
            r".{0,65}?\b(?:returned|showed|contained)\s+(?:zero|no|0)\s+entries\b"
        )
        source, replaced = erroneous_zero.subn(
            f"bounded command history returned {number} recorded "
            "command events but no direct command was linked to the focal OFF",
            source,
        )
        changed |= replaced > 0
    return source, changed


__all__ = [
    "build_causal_answer_plan",
    "render_causal_answer_plan",
    "guard_causal_answer_claim_boundaries",
]
