#!/usr/bin/env bash
# observer-agents-cdn-sync.sh
#
# Sincroniza los binarios del agente Observer RMM desde el release de
#   github.com/braincorp-cl/observer-agent-dist
# hacia el docroot del vhost agents.observer.cl (appserver 10.20.0.52).
#
# Es el "mecanismo de copia" del CDN propio de agentes: cada vez que se genera
# un nuevo release de binarios en el repo -dist, correr este script deja esos
# binarios servidos por agents.observer.cl. Idempotente y re-ejecutable.
#
# Uso (EN el appserver, como root o con sudo):
#   observer-agents-cdn-sync.sh            # sincroniza el release "latest"
#   observer-agents-cdn-sync.sh v2.10.7    # sincroniza una version concreta
#   observer-agents-cdn-sync.sh 2.10.7     # (la 'v' es opcional)
#
# Desde el control-plane, sin copiar el script:
#   ssh observer@10.20.0.52 'sudo /usr/local/sbin/observer-agents-cdn-sync [tag]'
#
# Requisitos: curl + GNU grep (-P). El repo -dist debe ser PUBLICO (descarga sin auth).
# Nota: los binarios son unsigned (firma diferida, ADR-018). La firma, cuando exista,
# se aplicaria at-build-time en el release.yml del agente; este script solo publica.

set -euo pipefail

REPO="braincorp-cl/observer-agent-dist"
DOCROOT="/var/www/html/observer-agents"
OWNER_USER="www-data"
OWNER_GROUP="www-data"

log(){ printf '[cdn-sync] %s\n' "$*"; }
die(){ printf '[cdn-sync][ERROR] %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl no esta instalado"

# 1) Resolver el tag de release
if [[ $# -ge 1 && -n "${1:-}" ]]; then
    TAG="$1"
    [[ "$TAG" == v* ]] || TAG="v$TAG"
else
    log "Resolviendo release 'latest' de $REPO ..."
    TAG="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
        | grep -oP '"tag_name":\s*"\K[^"]+')" || die "no pude resolver 'latest'"
fi
[[ -n "${TAG:-}" ]] || die "tag vacio"
log "Version objetivo: $TAG"

# 2) Listar los assets observeragent-* del release
API="https://api.github.com/repos/$REPO/releases/tags/$TAG"
mapfile -t URLS < <(curl -fsSL "$API" \
    | grep -oP '"browser_download_url":\s*"\K[^"]+' \
    | grep -E '/observeragent-' || true)
[[ ${#URLS[@]} -gt 0 ]] || die "el release $TAG no expone assets observeragent-* (¿tag correcto? ¿repo publico?)"
log "Assets encontrados: ${#URLS[@]}"

# 3) Descargar a staging temporal y validar (no tocar el docroot si algo falla)
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for url in "${URLS[@]}"; do
    name="$(basename "$url")"
    log "  descargando $name"
    curl -fsSL --retry 3 -o "$TMP/$name" "$url" || die "fallo al bajar $name"
    [[ -s "$TMP/$name" ]] || die "$name quedo vacio"
done

# 4) Publicar atomicamente en el docroot con permisos correctos
DEST="$DOCROOT/releases/download/$TAG"
mkdir -p "$DEST"
for f in "$TMP"/*; do
    install -m 0644 -o "$OWNER_USER" -g "$OWNER_GROUP" "$f" "$DEST/$(basename "$f")"
done
log "Publicados ${#URLS[@]} binarios en $DEST"

# 5) Resumen
ls -la "$DEST"
log "OK — release $TAG sincronizado en agents.observer.cl."
