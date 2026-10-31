"""Stage 6: synthetic adaptive read decisions and conflicting evidence.

Isolated from the HomeBrain agent and production publisher. The real primary
Ollama Cloud model may request up to three *fictional*, host-owned source
records, then author its own sentences. Host validates only declared typed
claims and source references, never arbitrary prose semantics or true causality.
"""
from __future__ import annotations

import asyncio
from collections import deque
import json
import time
from typing import Any

import httpx

from chat_transport import EmptyOllamaAssistantMessage
from cloud_benchmark import BenchmarkError, benchmark_status
from stage5_autonomous_benchmark import _json_object, _safe_cloud_error

_MAX_READS = 3
_MAX_CLOUD = 4
_MAX_HOURLY = 12
_TYPES = frozenset({
    "state_report", "command_record", "device_telemetry", "broker_session",
    "rule_decision", "timestamp_basis", "time_order_conflict",
    "competing_commands", "physical_confirmation", "unique_cause",
    "absence_proven",
})
# A model may cite a real state report while misnaming it telemetry. These
# are separate questions: is the value actually in the cited source, and is
# the model-supplied provenance label correct? Never convert an observation
# into independently confirmed device telemetry.
_ATOM_FIELDS = frozenset({
    "state", "source_time", "received_at", "clock_basis", "command",
    "issuer", "level", "at", "reported_at", "driver_connected_to_broker",
    "independent_device_packet", "physical_acknowledgement",
})
_RELATIONS = frozenset({"time_order_conflict", "competing_commands"})
_HIGH_RISK = frozenset({"physical_confirmation", "unique_cause", "absence_proven"})


def _src(sid: str, title: str, event: str, kind: str, **fields: Any) -> dict:
    return {"id": sid, "title": title, "records": [
        {"id": event, "kind": kind, "synthetic": True, **fields}
    ]}


# All reference labels remain strictly host-only. The model sees only the
# initial record and *titles* until it explicitly selects further records.
_CASES = {
    "clock_conflict": {
        "title": "Late bridge report versus earlier device time",
        "question": "Investigate whether the lounge light really turned off after it came on. Explain the different clock bases and uncertainty.",
        "initial": {"id": "I1", "kind": "state_report",
                    "device": "Fictional Lounge Light", "state": "on",
                    "received_at": "20:02:10Z", "clock_basis": "collector"},
        "catalog": [
            _src("S4", "Hallway temperature sensor near the incident",
                 "E4", "sensor_report", received_at="20:02:11Z", temperature_c=22.1),
            _src("S2", "Delayed bridge OFF observation with device source timestamp",
                 "E2", "state_report", device="Fictional Lounge Light",
                 state="off", source_time="20:01:10Z", received_at="20:02:18Z",
                 clock_basis="device-source"),
            _src("S5", "Router timezone configuration",
                 "E5", "configuration", timezone="Europe/London", reviewed_at="19:00:00Z"),
            _src("S1", "Application brightness command before light report",
                 "E1", "command_record", command="setLevel", level=60,
                 issuer="Fictional Lighting Routine", at="20:02:07Z",
                 physical_acknowledgement=False),
            _src("S3", "Light ON observation with independent device source timestamp",
                 "E3", "state_report", device="Fictional Lounge Light",
                 state="on", source_time="20:02:09Z", received_at="20:02:13Z",
                 clock_basis="device-source"),
        ],
        "gold_sources": ("S1", "S2", "S3"),
        "required_types": ("state_report", "command_record", "time_order_conflict"),
    },
    "competing_commands": {
        "title": "Competing applications and an OFF report",
        "question": "Explain which applications issued conflicting commands and whether the final OFF report proves which one caused it.",
        "initial": {"id": "I1", "kind": "state_report",
                    "device": "Fictional Hall Light", "state": "off",
                    "received_at": "23:10:30Z", "clock_basis": "collector"},
        "catalog": [
            _src("S4", "Unrelated garden motion report",
                 "E4", "sensor_report", state="active", at="23:10:29Z"),
            _src("S2", "App B dimming command",
                 "E2", "command_record", command="setLevel", level=40,
                 issuer="Fictional Button App", at="23:10:29Z",
                 physical_acknowledgement=False),
            _src("S5", "App settings saved earlier that day",
                 "E5", "configuration", timeout_seconds=30, at="13:00:00Z"),
            _src("S1", "App A OFF command",
                 "E1", "command_record", command="off",
                 issuer="Fictional Inactivity App", at="23:10:27Z",
                 physical_acknowledgement=False),
            _src("S3", "Controller execution acknowledgement coverage",
                 "E3", "coverage_gap", at="23:10:31Z",
                 gap="No independently recorded command acknowledgement",
                 device_confirmation=False),
        ],
        "gold_sources": ("S1", "S2", "S3"),
        "required_types": ("state_report", "command_record", "competing_commands"),
    },
    "stale_connectivity": {
        "title": "Offline plug despite connected MQTT driver",
        "question": "Assess whether the plug is online, whether the scheduled OFF command caused its last contact, and which timestamps are authentic.",
        "initial": {"id": "I1", "kind": "state_report",
                    "device": "Fictional Bedroom Mesh Plug", "state": "offline",
                    "reported_at": "01:50:00Z", "clock_basis": "watchdog"},
        "catalog": [
            _src("S5", "Unrelated local weather values",
                 "E5", "sensor_report", at="01:40:00Z", temperature_c=6),
            _src("S1", "MQTT driver's broker connection status",
                 "E1", "broker_session", at="01:45:20Z",
                 driver_connected_to_broker=True, proves_plug_online=False),
            _src("S4", "Driver's periodic health watchdog heartbeat",
                 "E4", "watchdog_tick", at="01:49:00Z",
                 actual_plug_packet=False),
            _src("S3", "Overnight power rule command",
                 "E3", "command_record", at="01:30:01Z",
                 command="off", issuer="Fictional Night Power Rule",
                 physical_acknowledgement=False),
            _src("S2", "Last actual plug telemetry packet",
                 "E2", "device_telemetry", source_time="01:29:58Z",
                 received_at="01:29:59Z", state="on",
                 independent_device_packet=True),
        ],
        "gold_sources": ("S1", "S2", "S3"),
        "required_types": ("state_report", "broker_session", "device_telemetry", "command_record"),
    },
}


def _validate_plan(raw: str, remaining: set[str], *, can_read: bool) -> dict:
    plan = _json_object(raw)
    if set(plan) != {"schema", "action", "source_id", "reason"}:
        raise ValueError("unexpected plan keys")
    if plan["schema"] != "homebrain-stage6-next.v1":
        raise ValueError("unexpected plan schema")
    if not isinstance(plan["reason"], str) or not 1 <= len(plan["reason"].strip()) <= 240:
        raise ValueError("invalid investigation rationale")
    if plan["action"] == "stop" and plan["source_id"] is None:
        return plan
    if (plan["action"] != "read" or not can_read
            or not isinstance(plan["source_id"], str)
            or plan["source_id"] not in remaining):
        raise ValueError("invalid or repeated source selection")
    return plan


def _validate_answer(raw: str, records: list[dict]) -> dict:
    result = _json_object(raw)
    if (set(result) != {"schema", "sentences", "uncertainties", "next_evidence"}
            or result["schema"] not in ("homebrain-stage6-answer.v1",
                                       "homebrain-stage6-answer.v2")):
        raise ValueError("invalid answer structure")
    v2 = result["schema"] == "homebrain-stage6-answer.v2"
    sentences = result["sentences"]
    if not isinstance(sentences, list) or not 1 <= len(sentences) <= 7:
        raise ValueError("invalid sentence count")
    allowed = {r["id"] for r in records}
    total_chars = 0
    for sent in sentences:
        allowed_keys = ({"text", "kind", "evidence_ids", "atoms"} if v2
                        else {"text", "kind", "evidence_ids"})
        if not isinstance(sent, dict) or set(sent) != allowed_keys:
            raise ValueError("sentence/claim alignment required")
        txt = sent["text"]
        if not isinstance(txt, str) or not 6 <= len(txt.strip()) <= 360:
            raise ValueError("invalid sentence text")
        total_chars += len(txt)
        ids = sent["evidence_ids"]
        if (sent["kind"] not in _TYPES or not isinstance(ids, list)
                or not 1 <= len(ids) <= 3 or len(ids) != len(set(ids))
                or any(not isinstance(sid, str) or sid not in allowed for sid in ids)):
            raise ValueError("unsupported or unknown sentence citation")
        if v2:
            atoms = sent["atoms"]
            if (not isinstance(atoms, list) or len(atoms) > 4
                    or (not atoms and sent["kind"] not in _RELATIONS)):
                raise ValueError("missing or excessive atomic evidence assertions")
            seen_atoms = set()
            for atom in atoms:
                if (not isinstance(atom, dict)
                        or set(atom) != {"record_id", "field", "value"}
                        or not isinstance(atom["record_id"], str)
                        or atom["record_id"] not in ids
                        or not isinstance(atom["field"], str)
                        or atom["field"] not in _ATOM_FIELDS
                        or type(atom["value"]) not in (str, int, float, bool)
                        or (isinstance(atom["value"], str)
                            and len(atom["value"]) > 100)):
                    raise ValueError("invalid or uncited atomic assertion")
                signature = (atom["record_id"], atom["field"], str(atom["value"]))
                if signature in seen_atoms:
                    raise ValueError("duplicate atomic assertion")
                seen_atoms.add(signature)
    if total_chars > 2100:
        raise ValueError("response too long")
    limits = result["uncertainties"]
    if (not isinstance(limits, list) or not 1 <= len(limits) <= 4
            or any(not isinstance(s, str) or not 4 <= len(s.strip()) <= 220
                   for s in limits)):
        raise ValueError("uncertainty required")
    next_evidence = result["next_evidence"]
    if not isinstance(next_evidence, str) or not 5 <= len(next_evidence.strip()) <= 220:
        raise ValueError("specific useful follow-up required")
    return result


def _host_proof(kind: str, witness: list[dict]) -> bool:
    if not witness:
        return False
    if kind in _HIGH_RISK:
        # These synthetic records do not prove unique causality, physical
        # execution, or the absence of unobserved events.
        return False
    if kind == "time_order_conflict":
        if len(witness) != 2 or any(w["kind"] != "state_report" for w in witness):
            return False
        first, second = witness
        if not all("source_time" in w and "received_at" in w for w in witness):
            return False
        if first.get("device") != second.get("device"):
            return False
        return ((first["source_time"] < second["source_time"]
                 and first["received_at"] > second["received_at"])
                or (first["source_time"] > second["source_time"]
                    and first["received_at"] < second["received_at"]))
    if kind == "competing_commands":
        if len(witness) != 2 or any(w["kind"] != "command_record" for w in witness):
            return False
        return (witness[0].get("issuer") != witness[1].get("issuer")
                and witness[0].get("command") != witness[1].get("command"))
    required = {
        "state_report": "state",
        "command_record": "command",
        "device_telemetry": "independent_device_packet",
        "broker_session": "driver_connected_to_broker",
        "rule_decision": "decision",
        "timestamp_basis": "clock_basis",
    }
    field = required.get(kind)
    if field is None:
        return False
    if kind == "timestamp_basis":
        return all(bool(w.get(field)) for w in witness)
    return all(w["kind"] == kind and bool(w.get(field)) for w in witness)


def _audit(case: dict, selections: list[str], draft: dict) -> dict:
    sources = {s["id"]: s for s in case["catalog"]}
    gathered = [case["initial"]] + [
        r for sid in selections for r in sources[sid]["records"]
    ]
    by_id = {r["id"]: r for r in gathered}
    findings = []
    proven = set()
    source_type_mismatches = 0
    atom_matches = 0
    atom_mismatches = 0
    for sentence in draft["sentences"]:
        witnesses = [by_id[sid] for sid in sentence["evidence_ids"]]
        ok = _host_proof(sentence["kind"], witnesses)
        # Keep a provenance *mismatch* separate from an unsourced fact.
        # E2/E3 are device-origin timestamps inside state reports, NOT
        # independently authenticated physical device telemetry.
        mismatch = (not ok and sentence["kind"] == "device_telemetry"
                    and all(w["kind"] == "state_report"
                            and "source_time" in w for w in witnesses))
        source_type_mismatches += int(mismatch)
        atoms = sentence.get("atoms")
        checks = []
        if atoms is not None:
            for atom in atoms:
                record = by_id[atom["record_id"]]
                exact = (atom["field"] in record
                         and type(record[atom["field"]]) is type(atom["value"])
                         and record[atom["field"]] == atom["value"])
                atom_matches += int(exact)
                atom_mismatches += int(not exact)
                checks.append({"record_id": atom["record_id"],
                               "field": atom["field"],
                               "exact_source_value_match": exact})
        findings.append({
            "text": sentence["text"],
            "kind": sentence["kind"],
            "evidence_ids": sentence["evidence_ids"],
            "typed_source_supported": ok,
            "source_type_mismatch": mismatch,
            "atomic_source_value_checks": checks,
            "factual_prose_verified": False,
        })
        if ok:
            proven.add(sentence["kind"])
    relevant = set(case["gold_sources"])
    selected = set(selections)
    missing = set(case["required_types"]) - proven
    unsupported = sum(not item["typed_source_supported"] for item in findings)
    return {
        "selected_sources": [{"id": sid, "relevant_reference_source": sid in relevant}
                             for sid in selections],
        "relevant_source_recall": f"{len(selected & relevant)}/{len(relevant)}",
        "irrelevant_sources_selected": len(selected - relevant),
        "premature_stop_missing_relevant_sources": bool(relevant - selected),
        "expected_finding_type_coverage":
            f"{len(set(case['required_types']) - missing)}/{len(case['required_types'])}",
        "missing_expected_finding_types": sorted(missing),
        "sentence_citation_checks": findings,
        "typed_source_supported_sentences": len(findings) - unsupported,
        "unsupported_typed_sentence_citations": unsupported,
        "source_type_mismatches": source_type_mismatches,
        "unmatched_source_types_other": unsupported - source_type_mismatches,
        "source_value_atoms_verified": atom_matches,
        "source_value_atoms_mismatched": atom_mismatches,
        "sentences_with_unverified_free_prose": len(findings),
        "high_risk_unsupported_sentences": sum(
            not row["typed_source_supported"] and row["kind"] in _HIGH_RISK
            for row in findings),
        "model_sentence_count": len(findings),
        "prose_semantics_fully_verified": False,
        "sentence_labels_are_model_supplied": True,
        "unlabelled_implications_not_proven_absent": True,
        "independent_human_review_required": True,
        "publisher_approval": False,
    }


def stage6_status(transport: Any) -> dict:
    base = benchmark_status(transport)
    return {
        "available": base["available"],
        "reason": base["reason"],
        "model": base["model"],
        "cases": [{"id": sid, "title": case["title"]} for sid, case in _CASES.items()],
        "maximum_cloud_requests_per_test": _MAX_CLOUD,
        "maximum_extra_source_reads": _MAX_READS,
        "existing_primary_account_only": True,
        "live_device_access": False,
        "publisher_approval": False,
    }


def _safe_stage6_error(exc: Exception, phase: str) -> BenchmarkError:
    # Authentication and access controls are not interchangeable. The prior
    # combined label hid whether the user should inspect the configured key
    # or investigate a provider-side access policy. Keep raw body/headers out.
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return BenchmarkError(502,
                f"Stage 6 {phase} was rejected (Ollama HTTP 401: key not accepted). "
                "No retry was attempted. Use Check cloud connection.")
        if status == 403:
            return BenchmarkError(502,
                f"Stage 6 {phase} was denied (Ollama HTTP 403: provider access denied). "
                "This does not prove the key is invalid. No retry was attempted. "
                "Use Check cloud connection.")
    original = _safe_cloud_error(exc, phase)
    return BenchmarkError(original.status, original.detail.replace("Stage 5 ", "Stage 6 ", 1))


class Stage6Benchmark:
    def __init__(self, *, clock=None):
        self._clock = clock or time.monotonic
        self._lock = asyncio.Lock()
        self._attempts: deque[float] = deque()

    async def _call(self, transport: Any, messages: list[dict]) -> str:
        self._attempts.append(self._clock())
        response = await transport._chat_post(
            messages, [], base_url=transport.base_url,
            model_name=transport.model_name, api_key=transport.api_key,
            timeout=httpx.Timeout(min(90.0, max(10.0, transport.timeout_seconds))),
            keep_alive=None, disable_thinking=True,
        )
        if response.get("tool_calls"):
            raise ValueError("Cloud must not request any MCP tools")
        return response.get("content", "")

    async def run_case(self, transport: Any, case_id: str, *, confirmed: bool) -> dict:
        if confirmed is not True:
            raise BenchmarkError(400, "Confirm up to four Ollama Cloud requests using your existing allowance.")
        if case_id not in _CASES:
            raise BenchmarkError(400, "Unknown Stage 6 synthetic case.")
        meta = stage6_status(transport)
        if not meta["available"]:
            raise BenchmarkError(503, "The existing primary Ollama Cloud account is not available.")
        if self._lock.locked():
            raise BenchmarkError(429, "Another Stage 6 investigation is running.")
        now = self._clock()
        while self._attempts and now - self._attempts[0] >= 3600:
            self._attempts.popleft()
        if len(self._attempts) > _MAX_HOURLY - _MAX_CLOUD:
            raise BenchmarkError(429, "Stage 6 hourly cloud-call limit reached.")
        if self._attempts and now - self._attempts[-1] < 10:
            raise BenchmarkError(429, "Stage 6 ten-second cooldown is active.")
        case = _CASES[case_id]
        async with self._lock:
            selected: list[str] = []
            all_sources = {s["id"]: s for s in case["catalog"]}
            planning_reasons = []
            stopped_while_critical_titles_remained = False
            started = self._clock()
            before = len(self._attempts)
            stop_reason = "read_budget_exhausted"
            # Up to three successive source choices, one per model turn.
            for step in range(_MAX_READS):
                gathered = [{"source_id": sid, "records": all_sources[sid]["records"]}
                            for sid in selected]
                listing = [{"id": src["id"], "title": src["title"]}
                           for src in case["catalog"] if src["id"] not in selected]
                plan_messages = [
                    {"role": "system", "content": (
                        "You are conducting a wholly FICTIONAL, read-only smart-home "
                        "investigation. Decide whether another source would materially "
                        "help, using only the source TITLES below. Before STOP, audit "
                        "whether the QUESTION is answered and whether any UNREAD "
                        "command history, independently sourced state/timestamp "
                        "report, execution acknowledgement, or alternative issuer "
                        "could change the explanation. If one can, READ it when "
                        "budget permits. Do not stop simply because two plausible "
                        "records form a timeline. Stop when no remaining source "
                        "appears materially informative or you can explain what "
                        "is unresolvable. Never assert a unique cause from nearby "
                        "timestamps or confusing broker health. "
                        "Return ONLY JSON {schema,action,source_id,reason}: "
                        "schema homebrain-stage6-next.v1; action read or stop. "
                        "Use source_id null when stopping, else exactly one remaining "
                        "source ID. Reason <= 240 characters."
                    )},
                    {"role": "user", "content": json.dumps({
                        "question": case["question"],
                        "initial_observation": case["initial"],
                        "sources_already_examined": gathered,
                        "remaining_source_titles": listing,
                        "maximum_remaining_reads": _MAX_READS - step,
                    }, separators=(",", ":"), ensure_ascii=True)},
                ]
                try:
                    plan = _validate_plan(
                        await self._call(transport, plan_messages),
                        {s["id"] for s in case["catalog"] if s["id"] not in selected},
                        can_read=True,
                    )
                except Exception as exc:
                    raise _safe_stage6_error(exc, "adaptive evidence selection") from None
                planning_reasons.append(plan["reason"])
                if plan["action"] == "stop":
                    stop_reason = "model_stopped"
                    # Strictly evaluation-side: do NOT reveal the hidden
                    # reference source IDs or force a gold source into the
                    # model's plan. That would inflate discovery scores.
                    stopped_while_critical_titles_remained = bool(
                        set(case["gold_sources"]) - set(selected))
                    break
                selected.append(plan["source_id"])
            gathered = [{"source_id": sid, "records": all_sources[sid]["records"]}
                        for sid in selected]
            answer_messages = [
                {"role": "system", "content": (
                    "Write your own concise, natural explanation of this fictional "
                    "incident from the supplied records. No suggested conclusions "
                    "are provided. Keep receipt clock time distinct from source "
                    "event time. Report observations as REPORTS, not independently "
                    "confirmed hardware changes. IMPORTANT: a state_report with "
                    "a device-source timestamp is STILL a state_report; only a "
                    "record explicitly labelled device_telemetry with "
                    "independent_device_packet true qualifies as device_telemetry. "
                    "Distinguish competing commands, physical outcomes, and "
                    "unproven causes. Use one typed label per sentence and exact "
                    "source record IDs. Also extract up to four exact SOURCE "
                    "field/value atoms stated by the sentence; do not invent "
                    "values. A sentence may carry other unlabelled implications. "
                    "Return ONLY JSON {schema,sentences,uncertainties,next_evidence}. "
                    "schema: homebrain-stage6-answer.v2; sentences array 1-7 "
                    "of {text,kind,evidence_ids,atoms}. kind one of "
                    "state_report,command_record,device_telemetry,broker_session,"
                    "rule_decision,timestamp_basis,time_order_conflict,"
                    "competing_commands,physical_confirmation,unique_cause,"
                    "absence_proven. evidence_ids 1-3 shown IDs. atoms array "
                    "of {record_id,field,value} with field exactly as in source "
                    "record and value exact JSON primitive; use [] only for "
                    "time_order_conflict or competing_commands relations. "
                    "Allowed fields: state,source_time,received_at,clock_basis,"
                    "command,issuer,level,at,reported_at,driver_connected_to_broker,"
                    "independent_device_packet,physical_acknowledgement. "
                    "uncertainties 1-4 short strings; next_evidence a specific "
                    "useful follow-up. No extra JSON keys or markdown."
                )},
                {"role": "user", "content": json.dumps({
                    "question": case["question"],
                    "initial_observation": case["initial"],
                    "examined_source_records": gathered,
                    "stopped_by": stop_reason,
                }, separators=(",", ":"), ensure_ascii=True)},
            ]
            records = [case["initial"]] + [
                record for group in gathered for record in group["records"]
            ]
            try:
                answer = _validate_answer(
                    await self._call(transport, answer_messages), records)
                audit = _audit(case, selected, answer)
            except Exception as exc:
                raise _safe_stage6_error(exc, "independent explanation") from None
            return {
                "success": True, "scenario": case_id, "title": case["title"],
                "model": meta["model"],
                "elapsed_ms": round((self._clock() - started) * 1000),
                "cloud_requests_attempted": len(self._attempts) - before,
                "requested_source_reads": len(selected),
                "stop_reason": stop_reason,
                "model_stop_justification": planning_reasons[-1] if stop_reason == "model_stopped" else None,
                "stop_left_host_reference_sources_unexamined":
                    stopped_while_critical_titles_remained,
                "answer": " ".join(s["text"] for s in answer["sentences"]),
                "uncertainties": answer["uncertainties"],
                "recommended_next_evidence": answer["next_evidence"],
                "synthetic_only": True, "no_hub_or_device_calls": True,
                **audit,
            }


__all__ = ["Stage6Benchmark", "stage6_status", "BenchmarkError"]
