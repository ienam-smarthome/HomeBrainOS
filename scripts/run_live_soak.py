from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SoakCase:
    name: str
    prompt: str
    session_id: str
    expect_confirmation: bool | None = None
    require_evidence: bool = False
    require_metrics: bool = True


DEFAULT_CASES = (
    SoakCase("live-read", "Which lights are on?", "soak-read", require_evidence=True),
    SoakCase(
        "history-read",
        "Why did Livingroom Light 1 turn off?",
        "soak-history",
        require_evidence=True,
    ),
    SoakCase(
        "log-grounding",
        "Show recent Hubitat errors from the logs.",
        "soak-logs",
        require_evidence=True,
    ),
    SoakCase(
        "sensitive-confirmation",
        "Disable the automation named Test Soak Rule.",
        "soak-confirmation",
        expect_confirmation=True,
    ),
)

_ALLOWED_OUTCOMES = {"success", "refused", "unresolved", "cancelled", "failed"}
_FORBIDDEN_METRIC_KEYS = {
    "prompt",
    "user_prompt",
    "session",
    "session_id",
    "arguments",
    "tool_arguments",
    "device",
    "device_name",
}


def request_json(
    base_url: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 90,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def _metric_key_errors(value: Any, *, path: str = "metrics") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key).casefold()
            if key in _FORBIDDEN_METRIC_KEYS:
                errors.append(f"privacy-sensitive metric key exposed at {path}.{raw_key}")
            errors.extend(_metric_key_errors(item, path=f"{path}.{raw_key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_metric_key_errors(item, path=f"{path}[{index}]"))
    return errors


def validate_metrics(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return ["metrics object is missing"]

    outcome = metrics.get("outcome")
    if outcome not in _ALLOWED_OUTCOMES:
        errors.append(f"metrics outcome is invalid: {outcome!r}")
    if not isinstance(metrics.get("counters"), dict):
        errors.append("metrics counters object is missing")
    if not isinstance(metrics.get("timings_ms"), dict):
        errors.append("metrics timings_ms object is missing")

    rows = result.get("metric_rows")
    if not isinstance(rows, list):
        errors.append("metric_rows list is missing")
    else:
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"metric_rows[{index}] is not an object")
                continue
            if set(row) != {"label", "value"}:
                errors.append(
                    f"metric_rows[{index}] does not use the stable label/value schema"
                )
            if not str(row.get("label") or "").strip():
                errors.append(f"metric_rows[{index}] label is empty")
            if not str(row.get("value") or "").strip():
                errors.append(f"metric_rows[{index}] value is empty")

    errors.extend(_metric_key_errors(metrics))
    errors.extend(_metric_key_errors(rows, path="metric_rows"))
    return errors


def validate_case(case: SoakCase, result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not result.get("success"):
        errors.append("response did not report success")
    if not str(result.get("message") or "").strip():
        errors.append("response message is empty")
    if case.require_evidence and not result.get("evidence"):
        errors.append("authoritative evidence is missing")
    if (
        case.expect_confirmation is not None
        and bool(result.get("confirmation_required")) is not case.expect_confirmation
    ):
        errors.append(
            "confirmation_required did not match expected "
            f"{case.expect_confirmation}"
        )
    if case.require_metrics:
        errors.extend(validate_metrics(result))
    return errors


def run_case(base_url: str, token: str | None, case: SoakCase) -> bool:
    started = time.perf_counter()
    result = request_json(
        base_url,
        "/api/ask",
        payload={"prompt": case.prompt, "session_id": case.session_id},
        token=token,
    )
    errors = validate_case(case, result)
    elapsed = round((time.perf_counter() - started) * 1000)
    status = "PASS" if not errors else "FAIL"
    print(f"[{status}] {case.name} ({elapsed} ms)")
    print(f"  class={result.get('request_class')} route={result.get('route')}")
    print(f"  outcome={(result.get('metrics') or {}).get('outcome')}")
    print(f"  message={str(result.get('message') or '')[:180]}")
    for error in errors:
        print(f"  error={error}")
    return not errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a non-destructive HomeBrain live deployment soak matrix."
    )
    parser.add_argument("base_url", help="HomeBrain ingress or direct base URL")
    parser.add_argument("--token", help="Optional bearer token for a protected proxy")
    parser.add_argument(
        "--skip-confirmation",
        action="store_true",
        help="Skip the sensitive confirmation proposal case",
    )
    args = parser.parse_args()

    health = request_json(args.base_url, "/health", token=args.token, timeout=20)
    print(
        "HomeBrain",
        f"version={health.get('version')}",
        f"status={health.get('status')}",
        f"model={(health.get('ollama') or {}).get('model')}",
    )
    cases = [
        case
        for case in DEFAULT_CASES
        if not (args.skip_confirmation and case.expect_confirmation)
    ]
    passed = sum(run_case(args.base_url, args.token, case) for case in cases)
    print(f"\n{passed}/{len(cases)} live soak cases passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
