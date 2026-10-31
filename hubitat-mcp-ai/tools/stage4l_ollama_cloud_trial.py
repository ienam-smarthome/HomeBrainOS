#!/usr/bin/env python3
"""Stage 4L: consent-gated Ollama Cloud *authoring* evaluation, never publication.

Only hard-coded, constructed evidence is allowed to leave this process. This
module does not access Hubitat/HA, installed add-on settings, or live agent
tools. Its cloud path is strictly opt-in, one request per case, no retries.
Model prose is NOT validated for semantic completeness by typed citations.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage4_narrative_contract import (  # noqa: E402
    build_stage4_evidence_packet, validate_stage4_model_draft,
    stage4_model_authoring_instructions,
)
from stage4k_frozen_answer_audit import freeze_stage4k_answer  # noqa: E402

SCHEMA = "homebrain-stage4l-authored-proposal.v1"
HOST = "https://ollama.com/api/chat"
DIRECT_MODEL = "gemma4:31b"  # Direct cloud API: no -cloud tag.
MAX_RESPONSE = 32768
MAX_PROMPT = 16384


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect rejected")


def _synthetic_cases() -> list[dict]:
    """Fixed, constructed, explicitly non-household read receipts."""
    def command(device, app, name):
        return {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": device}},
            "details": {"observedEvents": [{
                "name": "command-" + name, "date": "2026-01-01T12:00:00Z",
                "producedBy": {"appId": app, "name": "Synthetic Controller"},
            }]},
        }

    history = {
        "tool": "homebrain_evidence_journal", "success": True, "effect": "read",
        "evidence_kind": "group_archived_input_history",
        "arguments": {"device_id": "104"},
        "details": {
            "deviceId": "104", "gapCount": 2, "truncated": True,
            "observations": [{
                "device_id": "104", "attribute": "contact", "value": "open",
                "timestamp_basis": "collector-received",
                "date": "2026-01-01T12:01:00Z",
            }],
        },
    }
    return [
        {"domain": "lighting", "question": "What does a recorded light level command prove, and what remains unknown?",
         "receipts": [command("101", "201", "setLevel")]},
        {"domain": "heating", "question": "Can a setpoint command establish that the boiler or valve physically operated?",
         "receipts": [command("102", "202", "setHeatingSetpoint")]},
        {"domain": "ventilation", "question": "What can a fan OFF command establish about the fan motor or humidity cause?",
         "receipts": [command("103", "203", "off")]},
        {"domain": "history", "question": "Explain collector clock timestamps and why the archive gap prevents absence claims.",
         "receipts": [history]},
    ]


def _proposal_schema(packet: dict) -> dict:
    ids = [fact["fact_id"] for fact in packet["facts"]]
    if not 1 <= len(ids) <= 8 or len(set(ids)) != len(ids):
        raise ValueError("invalid source facts")
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "schema": {"const": SCHEMA},
            "sections": {"type": "array", "minItems": 1, "maxItems": 1,
                         "items": {
                             "type": "object", "additionalProperties": False,
                             "properties": {
                                 "name": {"enum": ["summary", "evidence", "limitations", "next_checks"]},
                                 "sentences": {"type": "array", "minItems": 1, "maxItems": 3,
                                               "items": {"type": "object", "additionalProperties": False,
                                                         "properties": {
                                                             "text": {"type": "string", "minLength": 1, "maxLength": 500},
                                                             "fact_ids": {"type": "array", "minItems": 1, "maxItems": 2,
                                                                          "uniqueItems": True,
                                                                          "items": {"type": "string", "enum": ids}},
                                                         },
                                                         "required": ["text", "fact_ids"]}},
                             },
                             "required": ["name", "sentences"],
                         }},
        },
        "required": ["schema", "sections"],
    }


def _to_stage4a_draft(proposal: object, packet: dict) -> dict:
    """Host supplies exact structured witnesses; model supplies prose/selection."""
    if not isinstance(proposal, dict) or set(proposal) != {"schema", "sections"} or proposal["schema"] != SCHEMA:
        raise ValueError("invalid proposal")
    sections = proposal["sections"]
    if not isinstance(sections, list) or len(sections) != 1:
        raise ValueError("invalid sections")
    section = sections[0]
    if not isinstance(section, dict) or set(section) != {"name", "sentences"} or section["name"] not in (
        "summary", "evidence", "limitations", "next_checks"
    ):
        raise ValueError("invalid section")
    rows = section["sentences"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
        raise ValueError("invalid sentences")
    facts = {f["fact_id"]: f for f in packet["facts"]}
    output = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"text", "fact_ids"}:
            raise ValueError("invalid sentence shape")
        content, ids = row["text"], row["fact_ids"]
        if (not isinstance(content, str) or not 1 <= len(content) <= 500
                or not content.strip() or "\x00" in content
                or not isinstance(ids, list) or not 1 <= len(ids) <= 2
                or any(not isinstance(i, str) or i not in facts for i in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("invalid sentence or source ids")
        claims = []
        for fid in ids:
            fact = facts[fid]
            if fact["kind"] == "coverage_limit":
                keys = ("fact_id", "kind", "entity_id", "source", "gap_count", "truncated", "complete")
            elif fact["kind"] in ("issued_command", "reported_state", "input_report"):
                keys = ("fact_id", "kind", "entity_id", "attribute", "value",
                        "clock_basis", "time_utc", "issuer_app_id", "physical_ack_verified")
            else:
                raise ValueError("unsupported source fact")
            claims.append({key: fact[key] for key in keys})
        output.append({"text": content, "citations": ids[:], "claims": claims})
    return {"schema": "homebrain-stage4-draft.v1",
            "sections": [{"name": section["name"], "sentences": output}]}


class DirectCloudOllama:
    """Fixed HTTPS host and model. No redirects, proxies, retries or raw logging."""

    def __init__(self, api_key: str, *, opener=None):
        if not isinstance(api_key, str) or not 16 <= len(api_key) <= 512 or api_key != api_key.strip():
            raise ValueError("OLLAMA_API_KEY missing or invalid")
        self._key = api_key
        self._opener = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())

    def __call__(self, packet: dict, question: str) -> dict:
        schema = _proposal_schema(packet)
        instructions = (stage4_model_authoring_instructions(packet)
                        + " For this offline evaluation use ONLY the requested "
                          + SCHEMA + " proposal schema with fact_ids instead of claims. "
                          "Describe limitations explicitly. Never assume a command "
                          "proves a physical effect, cause, or complete history.")
        prompt = json.dumps({"question": question, "packet": packet,
                             "required_schema": SCHEMA},
                            separators=(",", ":"), ensure_ascii=True)
        if len(instructions) + len(prompt) > MAX_PROMPT:
            raise ValueError("prompt limit exceeded")
        body = json.dumps({
            "model": DIRECT_MODEL, "stream": False, "format": schema,
            "messages": [{"role": "system", "content": instructions},
                         {"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_predict": 1200},
        }, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        request = Request(HOST, data=body, method="POST",
                          headers={"Authorization": "Bearer " + self._key,
                                   "Content-Type": "application/json"})
        with self._opener.open(request, timeout=120) as response:
            if response.status != 200:
                raise ValueError("cloud HTTP status not successful")
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("cloud response too large")
        envelope = json.loads(raw)
        if not isinstance(envelope, dict) or not isinstance(envelope.get("message"), dict):
            raise ValueError("invalid cloud envelope")
        answer = envelope["message"].get("content")
        if not isinstance(answer, str) or not 1 <= len(answer) <= 24000:
            raise ValueError("invalid model content")
        result = json.loads(answer)
        if not isinstance(result, dict):
            raise ValueError("cloud proposal is not a JSON object")
        return result


def _offline_author(packet: dict, question: str) -> dict:
    """Deterministic fake transport; not a claim about cloud model accuracy."""
    return {"schema": SCHEMA, "sections": [{
        "name": "evidence", "sentences": [{
            "text": "A source record is present, but it does not establish an upstream cause.",
            "fact_ids": [packet["facts"][0]["fact_id"]],
        }],
    }]}


def run_constructed_trial(invoke, *, case_limit: int = 4) -> tuple[dict, list[dict]]:
    """Build aggregate-only diagnostics plus optional private post-hoc cases.

    Authored text is never printed. No reference/oracle labels are in prompts.
    The created bundle is suitable for later *independent* post-generation
    annotation and Stage 4K adjudication; it does not itself score semantics.
    """
    if type(case_limit) is not int or not 1 <= case_limit <= 4:
        raise ValueError("case limit")
    counts = {"attempted": 0, "responses": 0, "typed_valid": 0,
              "frozen": 0, "failed": 0}
    bundles = []
    for case in _synthetic_cases()[:case_limit]:
        counts["attempted"] += 1
        try:
            packet = build_stage4_evidence_packet(case["receipts"])
            result = invoke(packet, case["question"])
            counts["responses"] += 1
            draft = _to_stage4a_draft(result, packet)
            typed = validate_stage4_model_draft(draft, packet)
            if typed["structured_claims_valid"] is not True:
                raise ValueError("typed claims invalid")
            counts["typed_valid"] += 1
            frozen = freeze_stage4k_answer(case["receipts"], draft)
            bundles.append({"domain": case["domain"], "receipts": case["receipts"],
                            "draft": draft, "frozen": frozen})
            counts["frozen"] += 1
        except Exception:
            # Never leak provider errors, tokens, prompts, device IDs or prose.
            counts["failed"] += 1
    report = {
        "schema": "homebrain-stage4l-cloud-staging-report.v1",
        "synthetic_only": True,
        "real_cloud_quality_measured": False,
        "post_generation_independent_labels_present": False,
        "semantic_completeness_proven": False,
        "publication_approval": False,
        "live_hubitat_or_ha_access": False,
        "active_agent_or_model_routing_changed": False,
        "cases": counts,
    }
    return report, bundles


def _private_save(path: str, bundles: list[dict]) -> None:
    """Write a deliberately requested local adjudication bundle, never stdout."""
    target = Path(path).expanduser()
    if not target.is_absolute() or target.is_symlink():
        raise ValueError("private output needs a new absolute file path")
    payload = json.dumps({"schema": "homebrain-stage4l-private-bundle.v1",
                          "cases": bundles}, ensure_ascii=True).encode("utf-8")
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage 4L source-only cloud staging")
    parser.add_argument("--enable-cloud-inference", action="store_true")
    parser.add_argument("--ack-cloud-billing", action="store_true")
    parser.add_argument("--ack-constructed-data-only", action="store_true")
    parser.add_argument("--case-limit", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--private-output", help="new, absolute, local path for later post-hoc labelling")
    args = parser.parse_args(argv)
    if args.enable_cloud_inference:
        if not (args.ack_cloud_billing and args.ack_constructed_data_only):
            parser.error("both cloud billing and constructed-only acknowledgement are required")
        key = os.environ.get("OLLAMA_API_KEY", "")
        if not key:
            parser.error("OLLAMA_API_KEY must be configured privately")
        try:
            author = DirectCloudOllama(key)
        except ValueError:
            parser.error("invalid private cloud API key configuration")
    else:
        if args.ack_cloud_billing or args.ack_constructed_data_only:
            parser.error("cloud acknowledgements require --enable-cloud-inference")
        author = _offline_author
    report, bundles = run_constructed_trial(author, case_limit=args.case_limit)
    if args.private_output:
        _private_save(args.private_output, bundles)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["cases"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
