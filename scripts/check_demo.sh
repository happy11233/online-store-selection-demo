#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "[1/4] backend contract tests"
(cd "$ROOT_DIR/backend" && PYTHONPATH=. pytest -q)

echo "[2/4] python compile check"
(cd "$ROOT_DIR" && python3 -m compileall -q backend)

echo "[3/4] frontend production build"
(cd "$ROOT_DIR/frontend" && npm run build)

echo "[4/4] isolated browser workflows"
(cd "$ROOT_DIR/frontend" && npm run test:e2e)

echo "Demo checks passed."
