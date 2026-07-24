#!/usr/bin/env bash
# observer-agents-cdn-sync.sh
#
# Variante AUTO (cron, corre EN EL APPSERVER) de publicación al CDN de agentes.
# Modelo PULL: el appserver baja los assets del GitHub release de
# braincorp-cl/observer-agent-dist (privado) y los publica en el docroot del vhost
# agents.observer.cl, en /var/www/html/observer-agents/releases/download/<tag>/.
#
# Por qué existe: desde 2026-07-24 el mecanismo PRIMARIO (push del runner de GitHub
# en release.yml) dejó de funcionar — el runner (IPs Azure, ~7.3k CIDRs dinámicos)
# no cruza el firewall que solo permite `*.github.com`. Este cron cierra ese hueco
# de forma automática (detecta tags nuevos y los publica), sin depender del runner.
#
# MECANISMO OFICIAL (decidido 2026-07-24): el control-plane no debe ser crítico y no se abre
# nada de entrada en el FW, así que la automatización vive aquí (appserver, always-on). Requiere
# un token de GitHub en /etc/observer-agents-sync/token, protegido a 600 root:root (decisión
# operativa: se mantiene el token actual, sin migrar a fine-grained PAT). El push del runner
# (release.yml) se conserva para el futuro (requeriría un self-hosted runner de IP fija). Ver README.md.
#
# Idempotente: solo publica tags que aún no están en el docroot. Instalado por cron.d
# cada 5 min (observer-agents-cdn-sync.cron). Log: syslog + /var/log/observer-agents-cdn-sync.log
set -euo pipefail

REPO="braincorp-cl/observer-agent-dist"
CDN_ROOT="/var/www/html/observer-agents/releases/download"
TOKEN_FILE="/etc/observer-agents-sync/token"
API="https://api.github.com"
OWNER="www-data:www-data"
TAGLABEL="observer-agents-cdn-sync"

log(){ logger -t "$TAGLABEL" -- "$*" 2>/dev/null || true; printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }

# lock: no solaparse entre ejecuciones del cron
exec 9>/run/observer-agents-cdn-sync.lock
flock -n 9 || { log "otra ejecución en curso; salgo"; exit 0; }

# token ausente = etapa de configuración, no es error (evita spam de cron)
if [ ! -r "$TOKEN_FILE" ]; then
  log "token ausente en $TOKEN_FILE; nada que hacer (configúralo: fine-grained PAT, Contents:read)"
  exit 0
fi
TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
[ -n "$TOKEN" ] || { log "token vacío en $TOKEN_FILE; salgo"; exit 0; }

api(){ curl -fsS --retry 3 --retry-delay 3 -m 120 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" "$@"; }

if ! releases_json="$(api "$API/repos/$REPO/releases?per_page=50")"; then
  log "ERROR: no pude listar releases (¿token válido con acceso a $REPO?)"; exit 1
fi

mapfile -t tags < <(printf '%s' "$releases_json" | jq -r '.[] | select(.draft|not) | .tag_name')

published=0
for tag in "${tags[@]}"; do
  [ -n "$tag" ] || continue
  dest="$CDN_ROOT/$tag"
  [ -d "$dest" ] && continue                       # ya publicado -> idempotente

  log "release nuevo detectado: $tag"
  rel="$(api "$API/repos/$REPO/releases/tags/$tag")" || { log "ERROR: metadata de $tag"; continue; }
  expected="$(printf '%s' "$rel" | jq -r '.assets | length')"
  [ "$expected" -gt 0 ] || { log "AVISO: $tag sin assets; omito"; continue; }

  work="$dest.partial"; rm -rf "$work"; install -d -m 755 "$work"
  ok=1
  while IFS=$'\t' read -r id name; do
    [ -n "${id:-}" ] || continue
    if ! curl -fsSL --retry 3 --retry-delay 3 -m 300 \
         -H "Authorization: Bearer $TOKEN" -H "Accept: application/octet-stream" \
         "$API/repos/$REPO/releases/assets/$id" -o "$work/$name"; then
      log "ERROR: fallo bajando $name de $tag"; ok=0; break
    fi
  done < <(printf '%s' "$rel" | jq -r '.assets[] | "\(.id)\t\(.name)"')

  got="$(find "$work" -maxdepth 1 -type f | wc -l)"
  if [ "$ok" -eq 1 ] && [ "$got" -eq "$expected" ]; then
    chown -R "$OWNER" "$work"
    chmod 644 "$work"/*
    mv "$work" "$dest"                              # publicación atómica
    log "PUBLICADO $tag ($got binarios) en $dest"
    published=$((published+1))
  else
    log "ERROR: $tag incompleto ($got/$expected); se reintentará en el próximo ciclo"
    rm -rf "$work"
  fi
done

log "fin del ciclo: $published release(s) nuevos publicados"
