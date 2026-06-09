#!/usr/bin/env bash
# smoke-test-api.sh — Verifica que el backend Feature 002 responde correctamente
# Ejecutar ANTES de iniciar el rebrand del frontend (T001 es bloqueante)
#
# Uso: ./smoke-test-api.sh [HOST] [USERNAME] [PASSWORD]
# Ejemplo: ./smoke-test-api.sh localhost:8000 admin secretpass
#
# Resultado esperado: todos los checks deben pasar (EXIT 0)
# Si cualquiera retorna HTTP 500: detener y resolver en Feature 002 antes de continuar.

set -euo pipefail

HOST="${1:-localhost:8000}"
USERNAME="${2:-admin}"
PASSWORD="${3:-}"

BASE_URL="http://${HOST}"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"
    if [[ "$actual" == *"$expected"* ]]; then
        echo "  ✓ $desc"
        ((PASS++))
    else
        echo "  ✗ $desc — esperado contiene: '$expected', recibido: '$actual'"
        ((FAIL++))
    fi
}

echo "=== Smoke Test Backend Observer RMM ==="
echo "Host: ${BASE_URL}"
echo ""

# 1. GET /api/v4/me/ sin token — debe retornar 401
echo "▶ GET /api/v4/me/ (sin auth)"
RESP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v4/me/")
[[ "$RESP" == "401" ]] && echo "  ✓ 401 Unauthorized" && ((PASS++)) || { echo "  ✗ Esperado 401, recibido $RESP"; ((FAIL++)); }

# 2. POST /api/v3/auth/ con credenciales incorrectas — debe retornar 400
echo "▶ POST /api/v3/auth/ (credenciales incorrectas)"
RESP=$(curl -s -X POST "${BASE_URL}/api/v3/auth/" \
    -H "Content-Type: application/json" \
    -d '{"username":"__nonexistent__","password":"__wrong__"}')
check "Respuesta de error de autenticación" "non_field_errors" "$RESP"

# 3. GET /api/agents/ sin token — debe retornar 401
echo "▶ GET /api/agents/ (sin auth)"
RESP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/agents/")
[[ "$RESP" == "401" ]] && echo "  ✓ 401 Unauthorized" && ((PASS++)) || { echo "  ✗ Esperado 401, recibido $RESP"; ((FAIL++)); }

# 4. POST /api/v3/auth/ con credenciales reales — si se proveyeron
if [[ -n "$PASSWORD" ]]; then
    echo "▶ POST /api/v3/auth/ (credenciales reales: $USERNAME)"
    AUTH_RESP=$(curl -s -X POST "${BASE_URL}/api/v3/auth/" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}")
    TOKEN=$(echo "$AUTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token',''))" 2>/dev/null || echo "")
    if [[ -n "$TOKEN" ]]; then
        echo "  ✓ Token Knox obtenido"
        ((PASS++))
        echo "  → TOKEN=${TOKEN}"
        echo ""
        echo "▶ GET /api/v4/me/ (con token)"
        ME_RESP=$(curl -s "${BASE_URL}/api/v4/me/" -H "Authorization: Token ${TOKEN}")
        check "Campo username en /api/v4/me/" "username" "$ME_RESP"

        echo "▶ GET /api/alerts/ (con token)"
        ALERTS_RESP=$(curl -s -o /dev/null -w "%{http_code}" \
            "${BASE_URL}/api/alerts/" -H "Authorization: Token ${TOKEN}")
        [[ "$ALERTS_RESP" == "200" ]] && echo "  ✓ 200 OK" && ((PASS++)) || { echo "  ✗ Esperado 200, recibido $ALERTS_RESP"; ((FAIL++)); }
    else
        echo "  ✗ Login falló — respuesta: $AUTH_RESP"
        ((FAIL++))
    fi
fi

echo ""
echo "=== Resultado: ${PASS} OK / ${FAIL} FAIL ==="
[[ "$FAIL" -eq 0 ]] && echo "✅ Smoke test PASADO — continuar con T002" && exit 0
echo "❌ Smoke test FALLIDO — resolver errores antes de continuar" && exit 1
