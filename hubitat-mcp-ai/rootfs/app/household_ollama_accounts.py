"""Explicitly consented Ollama household cloud account routing policy.

Provider permission is separate from owner consent; the app cannot verify
provider authorization. All secondary credentials are disabled by default.
Account-level throttles/auth failures NEVER trigger key rotation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

import httpx

_ALLOWED_ID = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
_MAX_SECONDARY = 3


@dataclass(frozen=True)
class HouseholdCloudAccount:
    account_id: str
    api_key: str
    owner_label: str


def read_authorized_household_accounts(
    raw: str | None, *, enabled: bool
) -> tuple[HouseholdCloudAccount, ...]:
    """Return only explicitly consented and provider-approved adult accounts.

    Passwords should be supplied in the add-on password-type config field,
    never displayed in the UI/status, URL, prompt or technical evidence.
    Treat malformed or incomplete authorizations as disabled accounts.
    """
    if not enabled or not raw:
        return ()
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Household Ollama account configuration is invalid JSON") from None
    if not isinstance(payload, list) or len(payload) > _MAX_SECONDARY:
        raise ValueError("Household Ollama accounts must be a list of up to three entries")
    output: list[HouseholdCloudAccount] = []
    ids: set[str] = set()
    secrets: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Household Ollama account entry must be an object")
        alias = str(item.get("id") or "").strip().lower()
        label = str(item.get("owner_label") or "").strip()
        key = str(item.get("api_key") or "").strip()
        if (
            not _ALLOWED_ID.fullmatch(alias)
            or alias == "primary"
            or alias in ids
            or len(label) > 48
            or not label
        ):
            raise ValueError("Invalid or repeated household account identifier")
        ids.add(alias)
        # These booleans attest to *separate* safeguards, rather than making
        # one adult's consent automatically imply vendor authorization.
        if not item.get("enabled", False):
            continue
        if not all(item.get(k) is True for k in (
            "adult_owner_confirmed",
            "owner_consented_to_homebrain",
            "provider_shared_use_authorized",
        )):
            continue
        if not key or key in secrets:
            raise ValueError("Enabled household accounts need distinct API credentials")
        secrets.add(key)
        output.append(HouseholdCloudAccount(alias, key, label))
    return tuple(output)


def permissible_cloud_failover(error: BaseException) -> bool:
    """Only an unstarted connection or explicitly retryable server rejection.

    DO NOT switch accounts for HTTP 429, 401, 403, network timeouts after
    request submission, streaming failures, JSON failures or empty responses.
    A timeout may have consumed tokens and should not duplicate billing.
    """
    if isinstance(error, httpx.ConnectError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {502, 503, 504}
    return False


__all__ = [
    "HouseholdCloudAccount", "read_authorized_household_accounts",
    "permissible_cloud_failover",
]
