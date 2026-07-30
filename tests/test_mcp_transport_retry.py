from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

APP_DIR = (
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
)
sys.path.insert(0, str(APP_DIR))

from mcp_client import HubitatMCPClient, MCPError  # noqa: E402


class SequencedHTTP:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def post(self, url, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(status: int, body: str) -> httpx.Response:
    return httpx.Response(
        status,
        text=body,
        request=httpx.Request("POST", "http://hub/mcp"),
    )


async def client_with(outcomes, *, attempts: int = 3):
    client = HubitatMCPClient(
        "http://hub/mcp",
        retry_attempts=attempts,
        retry_backoff_seconds=0,
    )
    await client._http.aclose()
    fake = SequencedHTTP(outcomes)
    client._http = fake
    return client, fake


@pytest.mark.asyncio
async def test_retries_transient_server_error_then_succeeds():
    client, fake = await client_with(
        [
            response(503, "temporarily unavailable"),
            response(200, '{"jsonrpc":"2.0","result":{}}'),
        ]
    )

    result = await client._post({"jsonrpc": "2.0", "method": "test"})

    assert result["result"] == {}
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_retries_transport_error_then_succeeds():
    request = httpx.Request("POST", "http://hub/mcp")
    client, fake = await client_with(
        [
            httpx.ConnectError("hub unavailable", request=request),
            response(200, '{"jsonrpc":"2.0","result":{}}'),
        ]
    )

    result = await client._post({"jsonrpc": "2.0", "method": "test"})

    assert result["result"] == {}
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_does_not_retry_client_error():
    client, fake = await client_with([response(401, "unauthorized")])

    with pytest.raises(MCPError, match="MCP HTTP 401"):
        await client._post({"jsonrpc": "2.0", "method": "test"})

    assert fake.calls == 1


@pytest.mark.asyncio
async def test_exhausted_server_errors_raise_last_response():
    client, fake = await client_with(
        [response(503, "try later"), response(502, "bad gateway")],
        attempts=2,
    )

    with pytest.raises(MCPError, match="MCP HTTP 502"):
        await client._post({"jsonrpc": "2.0", "method": "test"})

    assert fake.calls == 2


@pytest.mark.asyncio
async def test_does_not_retry_mutating_tool_call():
    client, fake = await client_with(
        [
            response(503, "unknown mutation outcome"),
            response(200, '{"jsonrpc":"2.0","result":{}}'),
        ]
    )
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "hub_manage_devices",
            "arguments": {"tool": "hub_call_device_command"},
        },
    }

    with pytest.raises(MCPError, match="MCP HTTP 503"):
        await client._post(payload)

    assert fake.calls == 1
