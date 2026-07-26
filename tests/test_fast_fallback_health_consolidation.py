from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_health import (  # noqa: E402
    AttentionFastFallbackRouter,
    FastFallbackRouter,
    GroupFastFallbackRouter,
    SpeechFastFallbackRouter,
    VerifiedFastFallbackRouter,
    normalise_spoken_device_name,
)
from fast_fallback_live import FastFallbackRouter as LiveFastFallbackRouter  # noqa: E402


def test_health_attention_group_has_one_module_owner():
    for module_name in (
        "fast_fallback_verified",
        "fast_fallback_attention",
        "fast_fallback_groups",
        "fast_fallback_speech",
    ):
        assert not (APP_DIR / f"{module_name}.py").exists()
    assert (APP_DIR / "fast_fallback_device_health.py").is_file()


def test_consolidated_entrypoints_preserve_the_effective_mro():
    assert VerifiedFastFallbackRouter.__bases__ == (LiveFastFallbackRouter,)
    assert AttentionFastFallbackRouter.__bases__ == (VerifiedFastFallbackRouter,)
    assert GroupFastFallbackRouter.__bases__ == (AttentionFastFallbackRouter,)
    assert FastFallbackRouter.__bases__ == (GroupFastFallbackRouter,)
    assert SpeechFastFallbackRouter.__bases__ == (FastFallbackRouter,)
    assert normalise_spoken_device_name("Living Room Light Number Two") == (
        "living room light 2"
    )
