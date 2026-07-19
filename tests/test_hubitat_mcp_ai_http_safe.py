from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from webui_http_safe import patch_http_errors  # noqa: E402


def test_ask_response_is_parsed_as_text_before_json():
    page = """
    <script>
    if(response.status===409)return;const answer=await response.json();showAnswer(answer);pendingUser=null;history.push({role:'assistant',content:answer.message||''});save()
    </script>
    """

    patched = patch_http_errors(page)

    assert "const raw=await response.text()" in patched
    assert "JSON.parse(raw)" in patched
    assert "HomeBrain returned HTTP ${response.status}" in patched
    assert "Content-Type:" in patched
    assert "await response.json()" not in patched


def test_http_patch_is_idempotent():
    page = """
    <script>
    if(response.status===409)return;const answer=await response.json();showAnswer(answer);pendingUser=null;history.push({role:'assistant',content:answer.message||''});save()
    </script>
    """

    first = patch_http_errors(page)
    second = patch_http_errors(first)

    assert second == first
