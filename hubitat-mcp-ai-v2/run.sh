#!/usr/bin/env bash
set -euo pipefail
cd /app
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8789 --proxy-headers --forwarded-allow-ips 127.0.0.1
