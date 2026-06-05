#!/usr/bin/env bash
set -euo pipefail

python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
