from __future__ import annotations

import uvicorn

import entrypoint_core as _core
from entrypoint_core import *  # noqa: F401,F403

PREVIOUS_RELEASE_VERSION = "0.10.55"
RELEASE_VERSION = "0.10.56"

# The preserved composition root builds the application. Override only the
# release metadata here so the Home Assistant manifest and runtime stay aligned.
_core.PREVIOUS_RELEASE_VERSION = PREVIOUS_RELEASE_VERSION
_core.RELEASE_VERSION = RELEASE_VERSION
_core.application.VERSION = RELEASE_VERSION
_core.application.app.version = RELEASE_VERSION
application = _core.application
app = _core.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
