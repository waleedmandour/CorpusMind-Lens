#!/usr/bin/env bash
# Regenerate the shared OpenAPI client from the running engine (§8).
# Usage: scripts/generate-client.sh [engine-base-url]
set -euo pipefail
BASE_URL="${1:-http://127.0.0.1:8765}"
OUT_DIR="$(cd "$(dirname "$0")/../shared" && pwd)"

echo "→ Fetching OpenAPI schema from ${BASE_URL}/openapi.json"
curl -fsS "${BASE_URL}/openapi.json" -o "${OUT_DIR}/openapi.json"

if ! command -v npx >/dev/null 2>&1; then
  echo "✗ npx not found — install Node.js 18+ first." >&2
  exit 1
fi

echo "→ Generating TypeScript client into ${OUT_DIR}"
npx --yes openapi-typescript "${OUT_DIR}/openapi.json" \
  -o "${OUT_DIR}/lens-api.d.ts"

echo "✓ Done. Commit shared/openapi.json + shared/lens-api.d.ts together."
