#!/usr/bin/env python3
"""Read-only, local Colibri HTTP compatibility pilot for HomeBrainOS.

Only sends fictional prompts to the selected private/local endpoint.
Never contacts Hubitat/Home Assistant or executes a returned tool call.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEMO_TOOL = {
    "type": "function",
    "function": {
        "name": "get_demo_switch",
        "description": "Read a fictional demo switch (never a real device).",
        "parameters": {
            "type": "object",
            "properties": {"device": {"type": "string", "enum": ["DEMO-ONLY"]}},
            "required": ["device"],
            "additionalProperties": False,
        },
    },
}


def normalise_base(raw: str, allow_lan: bool = False) -> str:
    parsed = urlsplit(raw.strip().rstrip("/"))
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an http(s) URL without embedded credentials")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/v1"):
        raise ValueError("Base URL must end at the server root or /v1")
    host = parsed.hostname.strip("[]").lower()
    if host != "localhost":
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Use localhost or a numeric loopback/private-network IP only") from exc
        if not (ip.is_loopback or (allow_lan and ip.is_private and not ip.is_link_local)):
            raise ValueError("Non-loopback addresses require --allow-lan and a private-network IP")
    if host != "localhost" and not ipaddress.ip_address(host).is_loopback and not allow_lan:
        raise ValueError("A private-network address requires --allow-lan")
    return urlunsplit((parsed.scheme, parsed.netloc, "/v1", "", ""))


class RejectRedirects(HTTPRedirectHandler):
    """Refuse redirects to prevent probing a different host or leaking API keys."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused: Colibri endpoint must respond directly")


def request_json(method: str, url: str, data: dict | None = None, timeout: float = 120) -> dict:
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    headers = {"Accept": "application/json"}
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    token = os.getenv("COLI_API_KEY", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(url=url, data=encoded, headers=headers, method=method)
    with build_opener(RejectRedirects).open(req, timeout=timeout) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Unexpected non-object API response")
    return value


def extract_message(payload: dict) -> dict:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("No choices in completion")
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        raise ValueError("No assistant message in completion")
    return msg


def validate_tool_calls(msg: dict) -> tuple[bool, str]:
    calls = msg.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        return False, "Expected exactly one structured tool call"
    call = calls[0]
    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
        return False, "Tool call does not match OpenAI function-call structure"
    if not isinstance(call.get("id"), str) or not call["id"]:
        return False, "Tool call lacks a call id"
    fn = call["function"]
    if fn.get("name") != "get_demo_switch":
        return False, "Wrong tool selected"
    try:
        args = json.loads(fn.get("arguments", ""))
    except (TypeError, ValueError):
        return False, "Tool arguments are not valid JSON"
    if args != {"device": "DEMO-ONLY"}:
        return False, "Tool arguments do not match fictional DEMO-ONLY device"
    return True, "Synthetic read-only tool call is correctly structured"


def run_probe(base: str, model_id: str | None, timeout: float) -> dict:
    result = {"endpoint": base, "model": model_id, "chat_ok": False,
              "tool_call_ok": False, "tool_roundtrip_ok": False, "elapsed_seconds": {},
              "notes": ["Only fictional prompts are used; no real devices or MCP servers are contacted"]}
    models = request_json("GET", base + "/models", timeout=timeout)
    ids = [item.get("id") for item in models.get("data", [])
           if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if model_id is None:
        if len(ids) != 1:
            raise ValueError("Specify --model; the server reported " + str(len(ids)) + " models")
        model_id = ids[0]
    elif model_id not in ids:
        raise ValueError("Requested model was not listed by /v1/models")
    result["model"] = model_id

    start = time.perf_counter()
    reply = request_json("POST", base + "/chat/completions", {
        "model": model_id, "stream": False, "temperature": 0,
        "max_tokens": 256, "messages": [{"role": "user", "content":
            "Reply with one short sentence: This is a fictional local compatibility check."}]
    }, timeout)
    result["elapsed_seconds"]["chat"] = round(time.perf_counter() - start, 2)
    answer = extract_message(reply).get("content")
    result["chat_ok"] = isinstance(answer, str) and bool(answer.strip())
    if not result["chat_ok"]:
        result["notes"].append("No nonempty chat text was generated")

    messages = [
        {"role": "system", "content": "This is a synthetic test. Always read DEMO-ONLY using the provided function, then report its recorded state. No physical device exists."},
        {"role": "user", "content": "Check the switch named DEMO-ONLY using get_demo_switch. Do not guess its state."},
    ]
    start = time.perf_counter()
    reply = request_json("POST", base + "/chat/completions", {
        "model": model_id, "stream": False, "temperature": 0, "max_tokens": 320,
        "messages": messages, "tools": [DEMO_TOOL], "tool_choice": "required",
    }, timeout)
    result["elapsed_seconds"]["tool_selection"] = round(time.perf_counter() - start, 2)
    msg = extract_message(reply)
    valid, note = validate_tool_calls(msg)
    result["tool_call_ok"] = valid
    result["notes"].append(note)
    if valid:
        # Only a fabricated result is supplied: no real function is called.
        call_id = msg["tool_calls"][0]["id"]
        messages.extend([msg, {"role": "tool", "tool_call_id": call_id,
            "name": "get_demo_switch", "content": json.dumps({"device": "DEMO-ONLY", "switch": "off"})}])
        start = time.perf_counter()
        reply = request_json("POST", base + "/chat/completions", {
            "model": model_id, "stream": False, "temperature": 0, "max_tokens": 256,
            "messages": messages,
        }, timeout)
        result["elapsed_seconds"]["tool_result_answer"] = round(time.perf_counter() - start, 2)
        text = extract_message(reply).get("content")
        result["tool_roundtrip_ok"] = isinstance(text, str) and "off" in text.lower()
        if not result["tool_roundtrip_ok"]:
            result["notes"].append("Could not verify an OFF answer from the synthetic tool result")
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1",
                   help="Colibri OpenAI base URL (default: local Windows machine)")
    p.add_argument("--model", help="Exact model ID from Colibri status")
    p.add_argument("--allow-lan", action="store_true", help="Explicitly allow a numeric private LAN host")
    p.add_argument("--timeout", type=float, default=180, help="Per-request timeout seconds")
    args = p.parse_args(argv)
    try:
        if args.timeout <= 0 or args.timeout > 3600:
            raise ValueError("Timeout must be between 0 and 3600 seconds")
        base = normalise_base(args.base_url, args.allow_lan)
        result = run_probe(base, args.model, args.timeout)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if all(result[k] for k in ("chat_ok", "tool_call_ok", "tool_roundtrip_ok")) else 2
    except (ValueError, HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({"probe_error": str(exc), "completed": False}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
