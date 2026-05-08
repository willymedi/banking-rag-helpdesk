#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] waiting for chroma at $CHROMA_HOST:$CHROMA_PORT ..."
for i in {1..30}; do
  if curl -sf "http://$CHROMA_HOST:$CHROMA_PORT/api/v2/heartbeat" > /dev/null; then
    echo "[entrypoint] chroma is up"
    break
  fi
  sleep 1
done

echo "[entrypoint] running ingest (idempotent)"
python -m scripts.ingest --skip-if-populated || echo "[entrypoint] ingest skipped or failed (continuing)"

RELOAD_FLAG=""
if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
  RELOAD_FLAG="--reload --reload-dir /app/src"
  echo "[entrypoint] launching uvicorn (reload mode)"
else
  echo "[entrypoint] launching uvicorn"
fi
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --proxy-headers $RELOAD_FLAG
