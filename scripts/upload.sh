#!/usr/bin/env bash
# One-shot: wait api healthy → copy file → patch manifest → ingest.
# Usage: ./scripts/upload.sh <file> <doc_id> <title> <domain>

set -euo pipefail

FILE="${1:?usage: upload.sh <file> <doc_id> <title> <domain>}"
DOC_ID="${2:?missing doc_id}"
TITLE="${3:?missing title}"
DOMAIN="${4:?missing domain}"

API_KEY="${API_KEY:-mesa-demo-key}"
API_URL="${API_URL:-http://localhost:8080}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$REPO_ROOT/docs_kb/manifest.json"
NAME=$(basename "$FILE")

echo "[1/4] waiting for api healthy..."
until curl -sf "$API_URL/health" >/dev/null 2>&1; do
  sleep 3
  echo "  ... still waiting"
done
echo "  api ready"

echo "[2/4] copying $NAME → docs_kb/"
cp "$FILE" "$REPO_ROOT/docs_kb/$NAME"

echo "[3/4] updating manifest.json"
python3 - <<PY
import json, pathlib
p = pathlib.Path("$MANIFEST")
data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
data["$NAME"] = {"doc_id": "$DOC_ID", "title": "$TITLE", "domain": "$DOMAIN"}
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

echo "[4/4] triggering ingest"
curl -sS -X POST "$API_URL/admin/ingest" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool

echo "done."
