"""Multi-household Ollama account security, failover and local fallback tests."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from chat_transport import ChatTransport
from household_ollama_accounts import (
    HouseholdCloudAccount, permissible_cloud_failover,
    read_authorized_household_accounts,
)


def _account(**overrides):
    item = {
        "id": "adult_b", "owner_label": "Household adult B",
        "api_key": "private-secondary-key", "enabled": True,
        "adult_owner_confirmed": True,
        "owner_consented_to_homebrain": True,
        "provider_shared_use_authorized": True,
    }
    item.update(overrides)
    return item


@pytest.mark.parametrize("field", [
    "adult_owner_confirmed",
    "owner_consented_to_homebrain",
    "provider_shared_use_authorized",
    "enabled",
])
def test_no_secondary_credential_without_all_explicit_gates(field):
    raw = _account(**{field: False})
    assert read_authorized_household_accounts(
        json.dumps([raw]), enabled=True
    ) == ()


def test_configuration_disabled_by_default_and_only_enabled_with_consent():
    raw = json.dumps([_account()])
    assert read_authorized_household_accounts(raw, enabled=False) == ()
    accounts = read_authorized_household_accounts(raw, enabled=True)
    assert len(accounts) == 1
    assert accounts[0].account_id == "adult_b"
    assert accounts[0].api_key == "private-secondary-key"


@pytest.mark.parametrize("payload", [
    "not-json", "{}", json.dumps([_account(id="primary")]),
    json.dumps([_account(id="adult_b"), _account()]),
    json.dumps([_account(api_key="")]),
    json.dumps([_account()] * 4),
])
def test_invalid_authorized_account_config_fails_closed_without_key_echo(payload):
    with pytest.raises(ValueError) as failure:
        read_authorized_household_accounts(payload, enabled=True)
    assert "private-secondary-key" not in str(failure.value)


def _error(status):
    req = httpx.Request("POST", "https://ollama.com/api/chat")
    resp = httpx.Response(status, request=req, text="provider diagnostic")
    return httpx.HTTPStatusError("Provider error", request=req, response=resp)


@pytest.mark.parametrize("status", [502, 503, 504])
def test_failover_eligibility_only_explicit_infrastructure_errors(status):
    assert permissible_cloud_failover(_error(status))


@pytest.mark.parametrize("status", [400, 401, 402, 403, 408, 409, 422, 429, 500])
def test_rate_auth_usage_and_other_statuses_never_rotate_accounts(status):
    assert not permissible_cloud_failover(_error(status))
    assert not permissible_cloud_failover(httpx.ReadTimeout("slow"))
    assert not permissible_cloud_failover(TimeoutError("stream stalled"))


class StatusClient:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    async def post(self, url, **kwargs):
        bearer = kwargs["headers"].get("Authorization", "")
        self.calls.append((url, bearer))
        target = "local" if "192.168.1.50" in url else bearer
        decision = self.outcomes[target]
        if isinstance(decision, BaseException):
            raise decision
        request = httpx.Request("POST", url)
        return httpx.Response(
            decision if isinstance(decision, int) else 200,
            request=request,
            json={"message": {"role": "assistant", "content": "ok-" + target}},
        )


def _transport(outcomes, *, allowed=True, cloud_first=False, local=False):
    client = StatusClient(outcomes)
    transport = ChatTransport(
        api_key="primary-secret", model_name="gemma4:31b-cloud",
        client=client, cloud_first=cloud_first,
        household_cloud_failover_enabled=allowed,
        household_cloud_accounts=(HouseholdCloudAccount(
            "adult_b", "private-secondary-key", "Household adult B",
        ),),
        local_base_url="http://192.168.1.50:11434" if local else "",
        local_model_name="qwen3.5:4b" if local else "",
    )
    return transport, client


@pytest.mark.asyncio
async def test_authorized_failover_after_cloud_503_without_key_exposure():
    obj, client = _transport({
        "Bearer primary-secret": 503,
        "Bearer private-secondary-key": "ok",
    })
    result = await obj.chat([{"role": "user", "content": "Inspect device"}], [])
    assert result["content"] == "ok-Bearer private-secondary-key"
    assert [key for _, key in client.calls] == [
        "Bearer primary-secret", "Bearer private-secondary-key"
    ]


@pytest.mark.asyncio
async def test_429_does_not_rotate_secondary_account():
    obj, client = _transport({
        "Bearer primary-secret": 429,
        "Bearer private-secondary-key": "ok",
    })
    with pytest.raises(httpx.HTTPStatusError) as exc:
        await obj.chat([{"role": "user", "content": "Investigate"}], [])
    assert exc.value.response.status_code == 429
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_cannot_rotate_when_approval_switch_is_off():
    obj, client = _transport({
        "Bearer primary-secret": 503,
        "Bearer private-secondary-key": "ok",
    }, allowed=False)
    with pytest.raises(httpx.HTTPStatusError):
        await obj.chat([{"role": "user", "content": "Investigate"}], [])
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_cloud_first_429_can_fall_back_to_configured_local():
    obj, client = _transport({
        "Bearer primary-secret": 429,
        "Bearer private-secondary-key": "ok",
        "local": "ok",
    }, cloud_first=True, local=True)
    result = await obj.chat([{"role": "user", "content": "Inspect"}], [])
    assert result["content"] == "ok-local"
    assert len(client.calls) == 2
    assert client.calls[-1][1] == ""
    assert all(k != "Bearer private-secondary-key" for _, k in client.calls)


@pytest.mark.asyncio
async def test_local_first_preserved_even_if_household_cloud_configured():
    obj, client = _transport({
        "Bearer primary-secret": 429,
        "Bearer private-secondary-key": "ok",
        "local": "ok",
    }, cloud_first=False, local=True)
    result = await obj.chat([{"role": "user", "content": "Inspect"}], [])
    assert result["content"] == "ok-local"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_read_timeout_never_automatically_switches_personal_cloud_account():
    obj, client = _transport({
        "Bearer primary-secret": httpx.ReadTimeout("timeout"),
        "Bearer private-secondary-key": "ok",
    })
    with pytest.raises(httpx.ReadTimeout):
        await obj.chat([{"role": "user", "content": "Inspect"}], [])
    assert len(client.calls) == 1
