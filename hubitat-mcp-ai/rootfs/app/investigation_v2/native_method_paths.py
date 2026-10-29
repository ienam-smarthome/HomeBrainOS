"""Privacy-filtered, bounded static call-path evidence for a verified Groovy file.

This is deliberately NOT an execution trace. No source body, literals, settings,
endpoints or arguments are projected. Unrecognised Groovy syntax fails closed.
The model chooses whether and how to retrieve source; this module never makes
a Hubitat tool call.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from groovy_method_scope import _definitions, _mask_non_code

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_PRIVATE = re.compile(
    r"(?i)(?:token|secret|password|credential|authorization|api_?key|"
    r"bearer|cookie|passphrase|private_?key)"
)
# This allowlist names platform operations only. It does not assert that
# an asynchronous callback completed or which runtime branch was followed.
_PLATFORM = frozenset({
    "asynchttpGet", "asynchttpPost", "asynchttpPut", "asynchttpDelete",
    "httpGet", "httpPost", "httpPut", "httpDelete",
    "runIn", "runOnce", "runEvery1Minute", "runEvery5Minutes",
    "runEvery10Minutes", "runEvery15Minutes", "runEvery30Minutes",
    "runEvery1Hour", "schedule", "unschedule",
    "sendEvent", "sendHubCommand", "subscribe", "unsubscribe",
})


def _safe_name(value: Any) -> bool:
    return isinstance(value, str) and bool(_IDENT.fullmatch(value)) and not _PRIVATE.search(value)


def static_method_paths(
    source: str, *, focus_methods: Sequence[str] = (),
    max_methods: int = 24, max_edges: int = 80,
) -> dict[str, Any]:
    """Return bounded lexical method-to-method/API references, not code.

    Only balanced, lexer-supported method bodies produce references. Focus
    names must be identifiers learned from source-backed WARNs and are not
    executable commands. A missing parsed method is never proof of absence.
    """
    output: dict[str, Any] = {
        "analysis_kind": "lexical_static_calls_only",
        "runtime_execution_verified": False,
        "network_or_cpu_cause_verified": False,
        "method_paths": [],
        "limits": (
            "Only direct syntactic calls in recognised, balanced Groovy method "
            "bodies; dynamic dispatch, callbacks, closures, inheritance, "
            "platform internals and executed branches are not resolved."
        ),
    }
    if not isinstance(source, str) or not source or len(source) > 250000:
        output["status"] = "source_unavailable_or_oversized"
        return output
    mask = _mask_non_code(source)
    candidates = _definitions(source, mask)
    safe = [m for m in candidates if _safe_name(m.name)]
    named = {m.name for m in safe}
    focus: list[str] = []
    for raw in list(focus_methods)[:20]:
        if _safe_name(raw) and raw not in focus:
            focus.append(raw)
    order = sorted(safe, key=lambda m: (
        0 if m.name.casefold() in {x.casefold() for x in focus} else 1,
        m.first,
    ))
    entries: list[dict[str, Any]] = []
    edges = 0
    for method in order[:max(1, min(40, max_methods))]:
        start_line = source.count("\n", 0, method.first) + 1
        end_line = source.count("\n", 0, method.last) + 1
        valid = method.brace_closed and not method.lexical_uncertainty
        entry: dict[str, Any] = {
            "method": method.name,
            "first_line": start_line, "last_line": end_line,
            "body_boundary_verified": valid,
        }
        if valid:
            brace = mask.find("{", method.first, min(method.last, method.first + 800))
            if brace >= 0:
                calls = [m.group(1) for m in _CALL.finditer(mask[brace+1:method.last])]
                own = list(dict.fromkeys(
                    c for c in calls if c in named and _safe_name(c)
                ))[:12]
                platform = list(dict.fromkeys(
                    c for c in calls if c in _PLATFORM
                ))[:12]
                budget = max(0, max_edges - edges)
                entry["declared_method_calls"] = own[:budget]
                edges += len(entry["declared_method_calls"])
                entry["platform_api_mentions"] = platform
                entry["call_list_truncated"] = len(own) > budget or len(calls) > 600
            else:
                entry["body_boundary_verified"] = False
        if not entry["body_boundary_verified"]:
            entry["static_calls_unavailable"] = "uncertain_groovy_method_boundary"
        entries.append(entry)
    found_focus = {m.name.casefold() for m in safe}
    output.update({
        "status": "lexical_methods_indexed",
        "recognized_method_count": len(safe),
        "method_rows_returned": len(entries),
        "method_rows_capped": len(entries) < len(safe),
        "focused_method_names_not_recognized": [
            f for f in focus if f.casefold() not in found_focus
        ][:12],
        "method_paths": entries,
    })
    return output


__all__ = ["static_method_paths"]
