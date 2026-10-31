"""Explicit, non-inference Ollama Cloud connection check for the primary account.

Only GET /api/balance on the official Ollama HTTPS origin. Never starts an
LLM completion, reads a hub, follows redirects, prints provider bodies,
returns balance amounts, discloses credentials, or retries. The endpoint can
confirm account credential access, not that a particular model's chat call
will succeed.
"""
from __future__ import annotations

import asyncio
from collections import deque
import time
from typing import Any

import httpx

from cloud_benchmark import BenchmarkError, benchmark_status


class CloudConnectionDiagnostics:
    def __init__(self, *, clock=None):
        self._clock = clock or time.monotonic
        self._lock = asyncio.Lock()
        self._attempts: deque[float] = deque()

    async def check(self, transport: Any) -> dict[str, Any]:
        if not benchmark_status(transport)["available"]:
            raise BenchmarkError(503, "Primary Ollama Cloud HTTPS credentials are not configured.")
        if self._lock.locked():
            raise BenchmarkError(429, "Cloud connection check is already running.")
        now = self._clock()
        while self._attempts and now - self._attempts[0] >= 3600:
            self._attempts.popleft()
        if len(self._attempts) >= 6:
            raise BenchmarkError(429, "Connection-check hourly limit reached.")
        if self._attempts and now - self._attempts[-1] < 10:
            raise BenchmarkError(429, "Connection-check cooldown active.")
        async with self._lock:
            self._attempts.append(self._clock())
            try:
                response = await transport.client.get(
                    "https://ollama.com/api/balance",
                    headers={"Authorization": f"Bearer {transport.api_key}"},
                    timeout=httpx.Timeout(15.0),
                    follow_redirects=False,
                )
                code = response.status_code
            except httpx.TimeoutException:
                code = None
                category = "connection_timeout"
                guidance = "The authentication check timed out. This does not establish that the key is invalid."
            except httpx.RequestError:
                code = None
                category = "network_error"
                guidance = "The connection could not complete. Check network access; the key was not judged."
            except Exception:
                code = None
                category = "unexpected_error"
                guidance = "The connection check could not complete. No provider details were exposed."
            else:
                if code == 200:
                    category = "account_key_accepted"
                    guidance = ("Ollama accepted the primary account key for a non-inference account request. "
                                "This does not guarantee chat-model access.")
                elif code == 401:
                    category = "unauthorized"
                    guidance = "Ollama rejected this key (HTTP 401). Check the existing configured API key."
                elif code == 403:
                    category = "access_denied"
                    guidance = ("Ollama denied the account check (HTTP 403). This does not prove the key is invalid. "
                                "Account access or provider security controls may be involved.")
                elif code == 402:
                    category = "payment_required"
                    guidance = "Ollama requires plan or billing action (HTTP 402). Review credits privately."
                elif code == 429:
                    category = "provider_rate_limited"
                    guidance = "Ollama rate limited the account check (HTTP 429). Avoid repeated requests."
                elif code == 404:
                    category = "check_endpoint_unavailable"
                    guidance = "The Ollama account diagnostic endpoint was not available (HTTP 404). Key validity is unknown."
                elif 500 <= code <= 599:
                    category = "provider_server_error"
                    guidance = "Ollama returned a server error. Key validity is unknown."
                else:
                    category = "other_provider_response"
                    guidance = "Ollama returned an unexpected account-check status. Key validity is unknown."
            return {
                "checked": True,
                "provider": "Ollama Cloud",
                "endpoint_kind": "authenticated_account_balance_check",
                "http_status": code,
                "category": category,
                "guidance": guidance,
                "model_inference_requests": 0,
                "no_token_balance_or_account_details_exposed": True,
                "diagnostic_is_not_chat_authorization_proof": True,
                "no_live_home_access": True,
                "no_automatic_retry": True,
            }


__all__ = ["CloudConnectionDiagnostics"]
