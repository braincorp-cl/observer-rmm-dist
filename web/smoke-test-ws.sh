#!/usr/bin/env bash
# smoke-test-ws.sh — Verifica que el WebSocket Django Channels responde correctamente
# Requiere: wscat (npm install -g wscat) y un token Knox válido de smoke-test-api.sh
#
# Uso: ./smoke-test-ws.sh <TOKEN> [HOST]
# Ejemplo: ./smoke-test-ws.sh abc123tokenknox localhost:8000

set -euo pipefail

TOKEN="${1:-}"
HOST="${2:-localhost:8000}"
WS_URL="ws://${HOST}/ws/?token=${TOKEN}"

if [[ -z "$TOKEN" ]]; then
    echo "❌ Uso: $0 <KNOX_TOKEN> [HOST]"
    echo "   Obtener token con: ./smoke-test-api.sh localhost:8000 admin password"
    exit 1
fi

if ! command -v wscat &>/dev/null; then
    echo "❌ wscat no encontrado. Instalar con: npm install -g wscat"
    exit 1
fi

echo "=== Smoke Test WebSocket Observer RMM ==="
echo "URL: ${WS_URL}"
echo ""
echo "Conectando (timeout 5s)..."
echo ""

# Intentar conexión, esperar 5 segundos, si no hay cierre inmediato = OK
RESULT=$(timeout 5 wscat -c "$WS_URL" 2>&1 || true)

if echo "$RESULT" | grep -qi "connected\|Error\|close\|401\|403"; then
    if echo "$RESULT" | grep -qi "401\|403\|Unauthorized\|Forbidden"; then
        echo "❌ Autenticación rechazada — verificar token Knox"
        echo "   Respuesta: $RESULT"
        exit 1
    elif echo "$RESULT" | grep -qi "Error\|ECONNREFUSED\|not found"; then
        echo "❌ No se pudo conectar al WebSocket"
        echo "   Respuesta: $RESULT"
        echo "   Verificar: ¿Daphne corriendo? ¿Redis disponible? ¿CHANNEL_LAYERS configurado?"
        exit 1
    else
        echo "✅ Conexión WebSocket establecida correctamente"
        echo "   (Conexión cerró normalmente al expirar el timeout — comportamiento esperado)"
        exit 0
    fi
else
    echo "✅ Conexión WebSocket aceptada (no hubo cierre inmediato)"
    exit 0
fi
