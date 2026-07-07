from __future__ import annotations

import uvicorn

import main as app_main
from natural_intelligence import register


app = register(app_main)


def run() -> None:
    uvicorn.run(app, host='0.0.0.0', port=8787)


if __name__ == '__main__':
    run()
