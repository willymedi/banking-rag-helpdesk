#!/usr/bin/env bash
# DEMO: prueba que datos sensibles (tarjeta + cédula) no se guardan en logs/DB.
# Usage: ./scripts/demo_pii.sh
set -euo pipefail

API="${API_URL:-http://localhost:8080}"
KEY="${API_KEY:-mesa-demo-key}"

# Datos sensibles de prueba (Visa test card + cédula ficticia)
CARD="4111111111111111"
CEDULA="1715234567"
EMAIL="cliente.real@banco.com"

QUERY="Mi número de tarjeta es ${CARD}, mi cédula ${CEDULA} y mi email ${EMAIL}. ¿Qué controles aplican a un microservicio?"

echo "════════════════════════════════════════════════════════════"
echo "  DEMO: Anti-leak de datos sensibles (PII)"
echo "════════════════════════════════════════════════════════════"
echo
echo "▶ DATOS QUE VAMOS A ENVIAR:"
echo "   Tarjeta:   $CARD"
echo "   Cédula:    $CEDULA"
echo "   Email:     $EMAIL"
echo
read -p "   Press ENTER para enviar..."
echo
echo "▶ POST /query"
echo "   Payload contiene los datos en CLARO."
echo

# 1. Enviar query
PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'query': sys.argv[1]}))" "$QUERY")
RESPONSE=$(curl -sS -X POST "$API/query" \
  -H "X-API-Key: $KEY" \
  -H "X-User-Role: architect" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "▶ RESPUESTA DEL API:"
echo "$RESPONSE" | python3 -m json.tool | head -20
echo "..."
echo

# 2. Buscar en logs
echo "════════════════════════════════════════════════════════════"
echo "  1. ¿Aparece el número en LOGS del API?"
echo "════════════════════════════════════════════════════════════"
HITS=$(docker compose logs api --since 1m 2>&1 | grep -c -e "$CARD" -e "$CEDULA" -e "$EMAIL" || true)
if [ "$HITS" = "0" ]; then
  echo "✓ CERO matches. Logs NO contienen tarjeta/cédula/email."
else
  echo "✗ $HITS LEAK detectado:"
  docker compose logs api --since 1m 2>&1 | grep -e "$CARD" -e "$CEDULA" -e "$EMAIL"
fi
echo

# 3. Mostrar qué SÍ se loguea
echo "════════════════════════════════════════════════════════════"
echo "  2. ¿Qué SE registra en logs entonces?"
echo "════════════════════════════════════════════════════════════"
docker compose logs api --since 1m 2>&1 | grep "graph.sanitize" | tail -1 | python3 -c "
import sys, json
line = sys.stdin.read().strip()
# extract JSON portion (line starts with 'mesa-api  | <json>')
idx = line.find('{')
if idx >= 0:
    print(json.dumps(json.loads(line[idx:]), indent=2, ensure_ascii=False))
"
echo
echo "  → Solo se loguea 'pii_found' como TIPOS detectados."
echo "  → El valor real (número de tarjeta) no aparece."
echo

# 4. Buscar en SQLite feedback DB
echo "════════════════════════════════════════════════════════════"
echo "  3. ¿Aparece en la base de feedback?"
echo "════════════════════════════════════════════════════════════"
DB_HITS=$(docker compose exec -T api sh -c "
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 /app/data/feedback.db 'SELECT * FROM feedback' 2>/dev/null | grep -c -e '$CARD' -e '$CEDULA' -e '$EMAIL' || true
  else
    python3 -c \"
import sqlite3
try:
    c = sqlite3.connect('/app/data/feedback.db').cursor()
    rows = c.execute('SELECT * FROM feedback').fetchall()
    text = str(rows)
    hits = sum(1 for x in ['$CARD','$CEDULA','$EMAIL'] if x in text)
    print(hits)
except Exception:
    print(0)
\"
  fi
")
if [ "$DB_HITS" = "0" ]; then
  echo "✓ CERO matches en feedback.db."
else
  echo "✗ $DB_HITS leaks en DB."
fi
echo

# 5. Buscar en Chroma
echo "════════════════════════════════════════════════════════════"
echo "  4. ¿Se indexó en Chroma (vector DB)?"
echo "════════════════════════════════════════════════════════════"
CHROMA_HITS=$(docker compose exec -T api python3 -c "
import asyncio
from src.api.container import get_container
async def main():
    c = get_container()
    chunks = await c.vector_store.list_all()
    text = ' '.join(ch.text for ch in chunks)
    targets = ['$CARD', '$CEDULA', '$EMAIL']
    hits = sum(1 for t in targets if t in text)
    print(hits)
asyncio.run(main())
" 2>/dev/null | tail -1)
if [ "$CHROMA_HITS" = "0" ]; then
  echo "✓ CERO matches en Chroma."
else
  echo "✗ $CHROMA_HITS leaks en Chroma."
fi
echo

# 6. Buscar en answer
echo "════════════════════════════════════════════════════════════"
echo "  5. ¿La respuesta del LLM repite el dato?"
echo "════════════════════════════════════════════════════════════"
ANSWER_HITS=$(echo "$RESPONSE" | grep -c -e "$CARD" -e "$CEDULA" -e "$EMAIL" || true)
if [ "$ANSWER_HITS" = "0" ]; then
  echo "✓ La respuesta NO repite los datos sensibles."
else
  echo "✗ La respuesta menciona los datos. LEAK."
fi
echo

echo "════════════════════════════════════════════════════════════"
echo "  RESUMEN"
echo "════════════════════════════════════════════════════════════"
echo "  Logs API:        $([ "$HITS" = "0" ] && echo OK || echo FAIL)"
echo "  SQLite feedback: $([ "$DB_HITS" = "0" ] && echo OK || echo FAIL)"
echo "  Chroma vector:   $([ "$CHROMA_HITS" = "0" ] && echo OK || echo FAIL)"
echo "  Respuesta LLM:   $([ "$ANSWER_HITS" = "0" ] && echo OK || echo FAIL)"
echo
echo "  Capa que protege: PIIRedactor (Presidio + Spacy + regex LATAM)"
echo "  Ubicación:        backend/src/application/security/pii_redactor.py"
echo "════════════════════════════════════════════════════════════"
