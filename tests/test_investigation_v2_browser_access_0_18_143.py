"""V2 remembered browser access must never persist the raw operator token."""
from __future__ import annotations

from pathlib import Path
import re
import sys
import time

import pytest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.browser_access import (
    COOKIE_NAME, COOKIE_AGE_SECONDS, mint_browser_access,
    verify_browser_access,
)
from investigation_v2.test_service import require_test_access
from investigation_v2.test_webui import render_v2_test_page


def test_hmac_cookie_authenticates_without_containing_raw_operator_secret():
    secret="test-token-very-long-01234567"
    cookie=mint_browser_access(secret,now=1772200000)
    assert cookie.startswith("v1.")
    assert secret not in cookie
    assert len(cookie.split("."))==4
    assert verify_browser_access(cookie,secret,now=1772200001)
    assert cookie != mint_browser_access(secret,now=1772200000)
    assert COOKIE_AGE_SECONDS==30*86400
    assert COOKIE_NAME=="homebrain_v2_browser_access"


@pytest.mark.parametrize("failure",[
    "", None, "v1.bad", "v1.1.abcd.ffffff", "v2.1.abcd.ffffff",
    "<script>alert(1)</script>", "v1."+"a"*300,
])
def test_untrusted_cookie_values_are_rejected(failure):
    assert not verify_browser_access(failure,"0123456789abcdef",now=1772200000)


def test_expired_future_forged_or_rotated_browser_cookie_fails_closed():
    secret="test-token-very-long-01234567"
    now=1772200000
    cookie=mint_browser_access(secret,now=now)
    assert verify_browser_access(cookie,secret,now=now+COOKIE_AGE_SECONDS)
    assert not verify_browser_access(cookie,secret,now=now+COOKIE_AGE_SECONDS+1)
    assert not verify_browser_access(cookie,secret,now=now-61)
    assert not verify_browser_access(cookie,"new-rotated-token-12345678",now=now)
    assert not verify_browser_access(cookie,"short",now=now)
    assert not verify_browser_access(cookie[:-1]+"a",secret,now=now) if cookie[-1]!="a" else not verify_browser_access(cookie[:-1]+"b",secret,now=now)


def test_browser_credential_cannot_skip_explicit_opt_in_or_disabled_v2():
    secret="test-token-very-long-01234567"
    cookie=mint_browser_access(secret,now=1772200000)
    assert verify_browser_access(cookie,secret,now=1772200001)
    with pytest.raises(PermissionError,match="explicit_opt_in_required"):
        require_test_access(enabled=True,configured_token=secret,
                            supplied_token=secret,explicit_opt_in=False)
    with pytest.raises(PermissionError,match="v2_test_disabled"):
        require_test_access(enabled=False,configured_token=secret,
                            supplied_token=secret,explicit_opt_in=True)


def test_v2_page_never_embeds_raw_secret_or_persists_client_side():
    page=render_v2_test_page()
    assert 'id="remember"' in page
    assert 'id="forgetAccess"' in page
    assert "api/v2/auth/status" in page
    assert "api/v2/auth/remember" in page
    assert "api/v2/auth/forget" in page
    assert "savedAccess" in page
    assert "el('secret').value=''" in page
    assert "credentials:'same-origin'" in page
    assert "location.protocol==='http:'" in page
    assert "localStorage" not in page
    assert "sessionStorage" not in page
    assert "document.cookie" not in page
    assert "innerHTML" not in page


def test_test_route_accepts_cookie_only_with_custom_read_only_header():
    app=(APP/"app.py").read_text()
    pos=app.index('@app.post("/api/v2/test")')
    tail=app[pos:app.index("    async def experiment()",pos)]
    assert 'connection.headers.get("x-homebrain-v2-test-token")' in tail
    assert 'connection.headers.get("x-homebrain-v2-request")' in tail
    assert 'browser_intent == "read-only"' in tail
    assert 'verify_browser_access(' in tail
    assert 'connection.cookies.get(COOKIE_NAME)' in tail
    assert "explicit_opt_in=payload.explicit_opt_in" in tail
    assert "require_test_access(" in tail


def test_remember_cookie_is_http_only_strict_samesite_revocable_and_no_store():
    app=(APP/"app.py").read_text()
    start=app.index('@app.post("/api/v2/auth/remember")')
    stop=app.index('@app.post("/api/v2/test")',start)
    slice_=app[start:stop]
    assert 'response.set_cookie(' in slice_
    assert 'httponly=True' in slice_
    assert 'samesite="strict"' in slice_
    assert 'secure=connection.url.scheme == "https"' in slice_
    assert '"Cache-Control": "no-store"' in slice_
    assert 'response.delete_cookie(' in slice_
    assert 'connection.headers.get("x-homebrain-v2-request") != "read-only"' in slice_
    assert 'supplied_token=provided' in slice_
    assert 'explicit_opt_in=True' in slice_
    assert "set_cookie" not in app[app.index('@app.get("/v2-test")'):app.index('@app.get("/api/v2/auth/status")')]


def test_v2_cookie_is_not_a_general_production_chat_auth_method():
    app=(APP/"app.py").read_text()
    v2=app[app.index('@app.get("/api/v2/auth/status")'):app.index('@app.post("/api/chat")')]
    assert "verify_browser_access(" in v2
    assert "agent.process_user_request_result" not in v2
    normal=app[app.index('@app.post("/api/chat")'):]
    assert "verify_browser_access(" not in normal
