"""Network failure on a write request is an UNKNOWN outcome, not failed write proof."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from app import RequestCoordinator
from webui import render_page


def test_network_exception_from_ask_fetch_marks_unknown_without_retry():
    page = render_page("HomeBrain", "0.18.64")
    assert "failure.name='HomeBrainNetworkError'" in page
    assert "error?.name==='AbortError'" in page
    assert "route:'network-outcome-unknown'" in page
    assert "status_verification:'write-outcome-unknown'" in page
    assert "The result of any requested Hubitat write is UNKNOWN" in page
    assert "'Do NOT submit the '" in page
    assert "'same rule or device command again yet." in page
    assert "check the exact Rule Machine rule name and current state" in page
    assert "Request ID: '+requestId" in page
    assert "Browser error:" in page
    # No automatic retry loop or an invented successful write state.
    section = page.split("const response=await fetch(apiPath('api/ask')", 1)[1]
    section = section.split("if(sequence===requestSequence", 1)[0]
    assert section.count("fetch(") == 1
    assert "signal:controller.signal" in section


@pytest.mark.asyncio
async def test_backend_disconnect_cancels_and_logs_request_id_not_payload(caplog):
    caplog.set_level(logging.WARNING, logger="HomeBrainOS.App")
    coordinator = RequestCoordinator()
    cancelled = asyncio.Event()

    class Disconnected:
        async def is_disconnected(self):
            return True

    async def operation():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    try:
        with pytest.raises(HTTPException) as exc:
            await coordinator.run(
                "test-session", operation(), connection=Disconnected(),
                request_id="test-request-123",
            )
        assert exc.value.status_code == 499
        assert cancelled.is_set()
        assert any(
            "request_id=test-request-123" in record.getMessage()
            and "direct verification" in record.getMessage()
            for record in caplog.records
        )
        assert coordinator.progress("test-session", "test-request-123")["completed"] is False
    finally:
        await coordinator.close()


def test_no_automatic_rule_retry_or_write_claim_in_network_error_path():
    source = (APP / "webui.py").read_text(encoding="utf-8")
    assert "The backend may already have submitted a write" in source
    assert "Never automatically retry" in source
    assert "success:false,route:'network-outcome-unknown'" in source
    assert "result of any requested Hubitat write is UNKNOWN" in source
