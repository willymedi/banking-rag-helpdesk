#!/usr/bin/env bash
# Upload .txt to docs_kb/, register in manifest.json, trigger ingest.
# Usage: ./scripts/add_doc.sh <path> <doc_id> <title> <domain>
#   domain ∈ {architecture, security, production}

set -euo pipefail

FILE="${1:?usage: add_doc.sh <path> <doc_id> <title> <domain>}"
DOC_ID="${2:?missing doc_id}"
TITLE="${3:?missing title}"
DOMAIN="${4:?missing domain}"
API_KEY="${API_KEY:-mesa-demo-key}"
API_URL="${API_URL:-http://localhost:8080}"

NAME=$(basename "$FILE")
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$REPO_ROOT/docs_kb/manifest.json"

cp "$FILE" "$REPO_ROOT/docs_kb/$NAME"
echo "[1/3] copied → docs_kb/$NAME"

python3 - <<PY
import json, pathlib
p = pathlib.Path("$MANIFEST")
data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
data["$NAME"] = {"doc_id": "$DOC_ID", "title": "$TITLE", "domain": "$DOMAIN"}
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("[2/3] manifest.json updated")
PY

echo "[3/3] triggering /admin/ingest"
curl -sS -X POST "$API_URL/admin/ingest" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
