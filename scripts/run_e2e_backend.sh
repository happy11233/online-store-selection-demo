#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DATA_DIR="$(mktemp -d /tmp/aimid-e2e.XXXXXX)"
trap 'rm -rf "$TEST_DATA_DIR"' EXIT

cp "$ROOT_DIR/backend/data/products.json" "$ROOT_DIR/backend/data/hotspots.json" "$ROOT_DIR/backend/data/hotspot_history.json" "$ROOT_DIR/backend/data/feedback.json" "$TEST_DATA_DIR/"

cd "$ROOT_DIR/backend"
AIMID_DATA_DIR="$TEST_DATA_DIR" LLM_PROVIDER=demo python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8012
