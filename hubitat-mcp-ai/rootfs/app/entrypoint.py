from __future__ import annotations

import uvicorn

import app as application


RELEASE_VERSION = "0.2.1-alpha"

# Keep the release version in one small bootstrap file so the FastAPI handlers,
# status endpoint and HomeBrain-style page all report the same add-on version.
application.VERSION = RELEASE_VERSION
application.app.version = RELEASE_VERSION
app = application.app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8788,
        log_level="info",
        proxy_headers=True,
    )
