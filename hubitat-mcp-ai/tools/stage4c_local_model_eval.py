#!/usr/bin/env python3
"""Manually run Stage 4C local Ollama reviewers on an OFFLINE dataset.

No Hubitat/HA credentials, endpoints, agent imports, cloud inference,
telemetry upload or output files. This command only talks to the local
Ollama HTTP API bound at 127.0.0.1, after TWO explicit command-line opt-ins.

Examples:
  python tools/stage4c_local_model_eval.py --demo-constructed \\
      --reviewer-1 qwen3.5:4b --reviewer-2 llama3.2:3b \\
      --enable-local-inference --ack-local-data-processing

  python tools/stage4c_local_model_eval.py --input /private/data.json \\
      --generate-drafts --author qwen3.5:4b \\
      --reviewer-1 llama3.2:3b --reviewer-2 qwen2.5:3b \\
      --enable-local-inference --ack-local-data-processing

Your local Ollama instance must already be running and both reviewer models
installed. No API keys needed. Model tags ending with cloud are rejected;
however an operator must independently verify the local Ollama configuration
does not itself forward inference to a remote backend.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import URLError, HTTPError
from urllib.request import (
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

_APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(_APP))

from stage4_offline_model_evaluation import (  # noqa: E402
    run_stage4c_offline_model_evaluation, _safe_model_name,
)

_MAX_FILE = 512 * 1024
_MAX_HTTP_RESPONSE = 32 * 1024
_MAX_PROMPT = 96 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect prohibited")


class LoopbackOllama:
    """Strict loopback HTTP client. Never logs or exports prompts/outputs."""

    def __init__(self, *, port: int = 11434, timeout_seconds: int = 60):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid local port")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
            raise ValueError("invalid local timeout")
        self._url = f"http://127.0.0.1:{port}/api/chat"
        self._timeout = timeout_seconds
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.attempted = 0
        self.succeeded = 0

    def __call__(self, model: str, job: dict) -> dict:
        if not _safe_model_name(model):
            raise ValueError("invalid or cloud model identifier")
        if not isinstance(job, dict) or job.get("task") not in ("author", "review"):
            raise ValueError("invalid local inference job")
        system = str(job["instructions"])
        if job["task"] == "author":
            user = json.dumps({"packet": job["packet"],
                               "required_schema": "homebrain-stage4-draft.v1"},
                              separators=(",", ":"), ensure_ascii=True)
        else:
            user = json.dumps({
                "sentences": job["sentences"],
                "source_coverage_cannot_establish_absence": True,
                "source_facts_may_be_truncated":
                    job["source_facts_may_be_truncated"],
                "required_schema": "homebrain-stage4b-semantic-review.v1",
                "required_fields": {
                    "schema": "homebrain-stage4b-semantic-review.v1",
                    "assessments": [
                        {"sentence_id": "s001", "verdict": "insufficient",
                         "supporting_fact_ids": []},
                    ],
                },
            }, separators=(",", ":"), ensure_ascii=True)
        if len(system) + len(user) > _MAX_PROMPT:
            raise ValueError("local prompt too long")
        body = json.dumps({
            "model": model, "stream": False, "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0, "num_predict": 2048},
        }, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        request = Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        self.attempted += 1
        # urllib could follow HTTP 30x without _NoRedirect. No proxies used.
        with self._opener.open(request, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError("unexpected local inference response")
            raw = response.read(_MAX_HTTP_RESPONSE + 1)
        if len(raw) > _MAX_HTTP_RESPONSE:
            raise ValueError("local inference response too large")
        outer = json.loads(raw)
        if not isinstance(outer, dict) or not isinstance(outer.get("message"), dict):
            raise ValueError("invalid local model transport response")
        content = outer["message"].get("content")
        if not isinstance(content, str) or not 1 <= len(content) <= 24000:
            raise ValueError("local model output invalid")
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("local model output must be JSON object")
        self.succeeded += 1
        return payload


def _constructed_cases() -> list[dict]:
    """Eight independently labelled *constructed* examples (not live truth)."""
    from stage4_narrative_contract import build_stage4_evidence_packet

    def event(device: str, app: str, attr: str):
        return {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": device}},
            "details": {"observedEvents": [{
                "name": "command-" + attr,
                "date": "2026-01-01T12:00:00Z",
                "producedBy": {"appId": app, "name": "Synthetic Controller"},
            }]},
        }

    rows = [
        event("101", "201", "setLevel"),
        event("102", "202", "setHeatingSetpoint"),
        event("103", "203", "off"),
        {"tool": "homebrain_evidence_journal",
         "success": True, "effect": "read",
         "evidence_kind": "group_archived_input_history",
         "arguments": {"device_id": "104"},
         "details": {"deviceId": "104", "gapCount": 2, "truncated": True,
                     "observations": [{
                         "device_id": "104", "attribute": "contact",
                         "value": "open", "timestamp_basis": "collector-received",
                         "date": "2026-01-01T12:01:00Z",
                     }]}},
    ]
    p = build_stage4_evidence_packet(rows)
    def get(kind, device, attribute=None):
        return next(f for f in p["facts"] if f["kind"] == kind
                    and f["entity_id"] == device
                    and (attribute is None or f.get("attribute") == attribute))
    def draft_fact(f, text):
        fields = (
            ("fact_id", "kind", "entity_id", "source", "gap_count", "truncated", "complete")
            if f["kind"] == "coverage_limit" else
            ("fact_id", "kind", "entity_id", "attribute", "value", "clock_basis",
             "time_utc", "issuer_app_id", "physical_ack_verified")
        )
        return {
            "schema": "homebrain-stage4-draft.v1",
            "sections": [{"name": "evidence", "sentences": [{
                "text": text,
                "citations": [f["fact_id"]],
                "claims": [{key: f[key] for key in fields}],
            }]}],
        }
    examples = [
        ("light-issued", "lighting", get("issued_command", "101"),
         "The source recorded a brightness command.", "entailed"),
        ("light-false-trigger", "lighting", get("issued_command", "101"),
         "A motion sensor started the light cycle.", "not-entailed"),
        ("heating-issued", "heating", get("issued_command", "102"),
         "A heating setpoint command was issued.", "entailed"),
        ("heating-physical", "heating", get("issued_command", "102"),
         "The boiler fired and every radiator valve opened.", "not-entailed"),
        ("fan-issued", "ventilation", get("issued_command", "103"),
         "The source records a fan off command.", "entailed"),
        ("fan-humidity-cause", "ventilation", get("issued_command", "103"),
         "Humidity caused the fan to switch off.", "not-entailed"),
        ("contact-reception", "history", get("reported_state", "104", "contact"),
         "Contact was recorded on the collector clock.", "entailed"),
        ("history-no-commands", "history", get("coverage_limit", "104"),
         "The complete archive proves that no commands occurred.", "not-entailed"),
    ]
    return [{
        "case_id": ident, "domain": domain,
        "trace_origin": "constructed-fixture",
        "packet": p, "draft": draft_fact(f, text), "oracle": [oracle],
    } for ident, domain, f, text, oracle in examples]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo-constructed", action="store_true")
    source.add_argument("--input", help="Private offline case JSON file; root {cases:[...]}")
    parser.add_argument("--generate-drafts", action="store_true",
                        help="Generate new model answers; oracle labels are discarded")
    parser.add_argument("--author")
    parser.add_argument("--reviewer-1", required=True)
    parser.add_argument("--reviewer-2", required=True)
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--enable-local-inference", action="store_true")
    parser.add_argument("--ack-local-data-processing", action="store_true")
    args = parser.parse_args(argv)
    # Check both flags before loading a private file or calling a model.
    if not args.enable_local_inference or not args.ack_local_data_processing:
        print("Refused: local inference and local data-processing flags required.",
              file=sys.stderr)
        return 2
    try:
        if args.demo_constructed:
            cases = _constructed_cases()
        else:
            with Path(args.input).open("rb") as handle:
                raw = handle.read(_MAX_FILE + 1)
            if len(raw) > _MAX_FILE:
                raise ValueError("input too large")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict) or set(parsed) != {"cases"}:
                raise ValueError("invalid input root")
            cases = parsed["cases"]
        if args.generate_drafts:
            if args.author is None:
                raise ValueError("author required for generated answers")
            cases = [
                {k: v for k, v in case.items() if k not in ("draft", "oracle")}
                for case in cases
            ]
        client = LoopbackOllama(port=args.port, timeout_seconds=args.timeout_seconds)
        report = run_stage4c_offline_model_evaluation(
            cases,
            author_model=args.author if args.generate_drafts else None,
            reviewer_models=(args.reviewer_1, args.reviewer_2),
            invoke=client,
        )
        if not report["completed_review_sets"]:
            print("No complete local model review sets; no result accepted.",
                  file=sys.stderr)
            return 2
        # Only fixed allowlisted counts. Input data and model outputs never
        # appear here, even if an HTTP/model exception contains private text.
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        print("Refused: invalid local input or model evaluation failure. "
              "No prompt, model reply or source information was printed.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
