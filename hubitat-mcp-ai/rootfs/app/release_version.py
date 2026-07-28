from __future__ import annotations

from pathlib import Path


PREVIOUS_RELEASE_VERSION = "0.10.191"
RELEASE_VERSION = "0.10.196"
BAKED_VERSION_PATH = Path("/app/.homebrain-build-version")


def runtime_release_version(
    baked_version_path: Path = BAKED_VERSION_PATH,
) -> str:
    """Return the version baked into the running add-on image when available."""

    try:
        baked = baked_version_path.read_text(encoding="utf-8").strip()
    except OSError:
        baked = ""
    return baked or RELEASE_VERSION


__all__ = [
    "BAKED_VERSION_PATH",
    "PREVIOUS_RELEASE_VERSION",
    "RELEASE_VERSION",
    "runtime_release_version",
]
