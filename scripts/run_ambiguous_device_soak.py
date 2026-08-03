from __future__ import annotations

import argparse
import sys
from typing import Any

from run_live_soak import request_json, validate_metrics


def validate_ambiguous_device_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not result.get("success"):
        errors.append("response did not report success")

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return errors + ["metrics object is missing"]
    errors.extend(validate_metrics(result))

    if metrics.get("outcome") != "unresolved":
        errors.append(
            f"expected unresolved outcome, got {metrics.get('outcome')!r}"
        )
    counters = metrics.get("counters")
    if not isinstance(counters, dict):
        errors.append("metrics counters object is missing")
    elif int(counters.get("device_resolution_ambiguous") or 0) < 1:
        errors.append("ambiguous resolution counter was not recorded")

    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence list is missing")
        return errors

    resolver_receipts = [
        item
        for item in evidence
        if isinstance(item, dict)
        and item.get("tool") == "homebrain_resolve_device"
    ]
    if not resolver_receipts:
        errors.append("homebrain_resolve_device evidence is missing")
    for receipt in evidence:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("mutates") or receipt.get("effect") not in {None, "read"}:
            errors.append("ambiguous-device probe attempted a mutation")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a live ambiguous device request is safely unresolved."
    )
    parser.add_argument("base_url", help="HomeBrain ingress or direct base URL")
    parser.add_argument(
        "device_name",
        help="An intentionally ambiguous device name, for example 'light 1'",
    )
    parser.add_argument("--token", help="Optional bearer token for a protected proxy")
    args = parser.parse_args()

    result = request_json(
        args.base_url,
        "/api/ask",
        payload={
            "prompt": f"What is the status of {args.device_name}?",
            "session_id": "soak-ambiguous-device",
        },
        token=args.token,
    )
    errors = validate_ambiguous_device_result(result)
    status = "PASS" if not errors else "FAIL"
    print(f"[{status}] ambiguous device: {args.device_name}")
    print(f"  outcome={(result.get('metrics') or {}).get('outcome')}")
    print(f"  message={str(result.get('message') or '')[:180]}")
    for error in errors:
        print(f"  error={error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
