#!/usr/bin/env bash
# shellcheck disable=SC2016,SC2034,SC1091  # asserts en comillas simples (eval) y vars que lee install.sh
# Pruebas de las derivaciones y validaciones de install.sh (sin instalar nada).
# Uso: bash scripts/installer/test-install-sh.sh
set -uo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OBS_INSTALLER_LIB_ONLY=1
# shellcheck source=../../install.sh
. "$ROOT/install.sh"
set +e; trap - ERR

fails=0; n=0
ok()  { n=$((n+1)); if eval "$1"; then :; else echo "FALLA: $1"; fails=$((fails+1)); fi; }
nok() { n=$((n+1)); if eval "$1"; then echo "FALLA (debia fallar): $1"; fails=$((fails+1)); fi; }

# observer_base_domain = base del wildcard (un nivel), NO la zona raiz (leccion tns)
ok  '[ "$(base_of api.tns.observer.cl)" = tns.observer.cl ]'
ok  '[ "$(base_of rmm.cliente.com.mx)" = cliente.com.mx ]'

# IP del proxy: solo privada (leccion tns/unitec: la publica deja real_ip inerte)
ok  '_proxy 10.20.0.254'; ok '_proxy 172.16.0.1'; ok '_proxy 172.31.255.1'; ok '_proxy 192.168.1.10'
ok  '_proxy ""'; ok '_proxy -'
nok '_proxy 164.77.113.189'; nok '_proxy 172.32.0.1'; nok '_proxy 10.0.0.256'; nok '_proxy abc'

ok  '_slug fluitek'; ok '_slug neo-genesys2'; nok '_slug Fluitek'; nok '_slug -x'; nok '_slug "a b"'
ok  '_fqdn api.fluitek.observer.cl'; nok '_fqdn api'; nok '_fqdn "api .x.cl"'
ok  '_email ops@braincorp.cl'; nok '_email ops@'; nok '_email "a b@c.cl"'
ok  '_ver 2.17.3'; nok '_ver 2.17'; nok '_ver v2.17.3'
ok  '_yn s'; ok '_yn n'; nok '_yn talvez'

# Respuestas: se parsean sin ejecutar el archivo, y los secretos estan prohibidos.
tmp="$(mktemp)"
printf '%s\n' '# comentario' 'OBS_SLUG=fluitek' 'OBS_TIMEZONE = "America/Mexico_City"' 'OBS_PROXY_IP=' 'X=$(touch /tmp/pwned)' >"$tmp"
ANSWERS_FILE="$tmp"; load_answers 2>/dev/null
ok  '[ "$OBS_SLUG" = fluitek ]'
ok  '[ "$OBS_TIMEZONE" = America/Mexico_City ]'
ok  '[ -z "$OBS_PROXY_IP" ]'
ok  '[ ! -e /tmp/pwned ]'
printf 'OBS_GODADDY_KEY=x\n' >"$tmp"
nok '( load_answers ) 2>/dev/null'
rm -f "$tmp"

# Sizing de PG por RAM (la fila de 16 GB es la validada en produccion)
pg_sizing_for_gb 8;  ok '[ "$PG_SB" = 1GB ] && [ "$PG_ECS" = 4GB ]'
pg_sizing_for_gb 16; ok '[ "$PG_SB" = 2GB ] && [ "$PG_ECS" = 6GB ] && [ "$PG_MAXWAL" = 2GB ]'
pg_sizing_for_gb 32; ok '[ "$PG_SB" = 4GB ] && [ "$PG_ECS" = 12GB ]'

echo "$((n-fails))/$n pruebas OK"
[ "$fails" -eq 0 ]
