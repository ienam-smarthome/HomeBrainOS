from __future__ import annotations

import argparse
import sys
from typing import Any

from run_live_soak import request_json, validate_metrics


RESOLVER_TOOL = "homebrain_resolve_device"
INVENTORY_TOOL = "hub_read_devices"
_ALLOWED_EXPECTED_OUTCOMES = {
    "success", "refused", "unresolved", "cancelled", "failed",
}


def validate_named_device_result(
    result: dict[str, Any],
    *,
    device_name: str,
    expected_outcome: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not result.get("success"):
        errors.append("response did not report success")
    if not str(result.get("message") or "").strip():
        errors.append("response message is empty")

    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        return [*errors, "evidence list is missing"]

    resolver_receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict) and receipt.get("tool") == RESOLVER_TOOL
    ]
    if len(resolver_receipts) != 1:
        errors.append(
            f"expected one {RESOLVER_TOOL} receipt, found {len(resolver_receipts)}"
        )
    else:
        resolver = resolver_receipts[0]
        if resolver.get("success") is not True:
            errors.append("named-device resolver did not succeed")
        arguments = resolver.get("arguments")
        if not isinstance(arguments, dict) or arguments.get("name") != device_name:
            errors.append("resolver did not receive the requested device name")

    inventory_receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict) and receipt.get("tool") == INVENTORY_TOOL
    ]
    if not inventory_receipts:
        errors.append("complete inventory evidence is missing")
    for receipt in inventory_receipts:
        arguments = receipt.get("arguments")
        if not isinstance(arguments, dict):
            continue
        nested = arguments.get("args")
        if isinstance(nested, dict) and "filter" in nested:
            errors.append("device name was forwarded through Hubitat's filter field")

    errors.extend(validate_metrics(result))
    if expected_outcome is not None:
        actual_outcome = (result.get("metrics") or {}).get("outcome")
        if actual_outcome != expected_outcome:
            errors.append(
                f"metrics outcome {actual_outcome!r} did not match expected "
                f"{expected_outcome!r}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify entity-first named-device resolution on a live deployment."
    )
    parser.add_argument("base_url", help="HomeBrain ingress or direct base URL")
    parser.add_argument("device_name", help="Exact live Hubitat device label")
    parser.add_argument(
        "--attribute",
        default="temperature",
        help="Attribute to ask for; defaults to temperature",
    )
    parser.add_argument(
        "--expect-outcome",
        choices=sorted(_ALLOWED_EXPECTED_OUTCOMES),
        help="Require the live metrics outcome to match this fixed value",
    )
    parser.add_argument("--token", help="Optional bearer token for a protected proxy")
    args = parser.parse_args()

    prompt = f"What is the {args.attribute} reported by {args.device_name}?"
    result = request_json(
        args.base_url,
        "/api/ask",
        payload={"prompt": prompt, "session_id": "soak-named-device"},
        token=args.token,
    )
    errors = validate_named_device_result(
        result,
        device_name=args.device_name,
        expected_outcome=args.expect_outcome,
    )
    status = "PASS" if not errors else "FAIL"
    print(f"[{status}] named-device resolution")
    print(f"  device={args.device_name}")
    print(f"  attribute={args.attribute}")
    print(f"  outcome={(result.get('metrics') or {}).get('outcome')}")
    print(f"  message={str(result.get('message') or '')[:180]}")
    for error in errors:
        print(f"  error={error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
