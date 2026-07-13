#!/usr/bin/env bash
# observer-agents-cdn-publish.sh
#
# Mecanismo de copia del CDN propio de agentes: publica los binarios del release
# de github.com/braincorp-cl/observer-agent-dist en el docroot del vhost
# agents.observer.cl (appserver 10.20.0.52).
#
# CORRE EN EL CONTROL-PLANE (no en el appserver). Baja los binarios con `gh`
# (autenticado) y los empuja por SSH. Asi funciona AUNQUE observer-agent-dist sea
# PRIVADO: la credencial de GitHub vive solo aqui (gh keyring / ~/.git-credentials),
# el appserver queda como servidor tonto, sin secretos de GitHub.
#
# Uso (en el control-plane):
#   observer-agents-cdn-publish.sh            # publica el release 'latest'
#   observer-agents-cdn-publish.sh v2.10.7    # publica una version concreta
#   observer-agents-cdn-publish.sh 2.10.7     # (la 'v' es opcional)
#
# Requisitos: gh (con acceso al repo, scope 'repo'), ssh/scp con sudo NOPASS al
# appserver. Override opcional del destino: OBSERVER_APPSERVER=user@host.
#
# Tras publicar, recordar fijar LATEST_AGENT_VER en settings.py a la version servida.
# Binarios unsigned (firma diferida ADR-018).

set -euo pipefail

REPO="braincorp-cl/observer-agent-dist"
SSH_TARGET="${OBSERVER_APPSERVER:-observer@10.20.0.52}"
DOCROOT="/var/www/html/observer-agents"

log(){ printf '[cdn-publish] %s\n' "$*"; }
die(){ printf '[cdn-publish][ERROR] %s\n' "$*" >&2; exit 1; }

command -v gh  >/dev/null 2>&1 || die "gh no esta instalado/autenticado (gh auth status)"
command -v ssh >/dev/null 2>&1 || die "ssh no disponible"
command -v scp >/dev/null 2>&1 || die "scp no disponible"

# 1) Resolver el tag de release
if [[ $# -ge 1 && -n "${1:-}" ]]; then
    TAG="$1"
    [[ "$TAG" == v* ]] || TAG="v$TAG"
else
    log "Resolviendo release 'latest' de $REPO ..."
    TAG="$(gh release view --repo "$REPO" --json tagName -q .tagName)" \
        || die "no pude resolver 'latest' (¿acceso al repo?)"
fi
[[ -n "${TAG:-}" ]] || die "tag vacio"
log "Version objetivo: $TAG"

# 2) Bajar los assets con gh (autenticado → sirve para repo PRIVADO)
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
gh release download "$TAG" --repo "$REPO" --pattern 'observeragent-*' --dir "$TMP" \
    || die "gh release download fallo (¿tag correcto? ¿el token tiene acceso al repo?)"
COUNT="$(find "$TMP" -maxdepth 1 -type f -name 'observeragent-*' | wc -l | tr -d ' ')"
[[ "$COUNT" -gt 0 ]] || die "no se bajaron assets observeragent-* del release $TAG"
log "Assets bajados: $COUNT"

# 3) Publicar en el appserver: staging en /tmp y sudo install en el docroot
REMOTE_TMP="/tmp/observer-agents-${TAG}.$$"
DEST="$DOCROOT/releases/download/$TAG"
log "Publicando en $SSH_TARGET:$DEST ..."
ssh "$SSH_TARGET" "mkdir -p '$REMOTE_TMP'"
scp -q "$TMP"/observeragent-* "$SSH_TARGET:$REMOTE_TMP/"
ssh "$SSH_TARGET" bash -s "$REMOTE_TMP" "$DEST" <<'REMOTE'
set -euo pipefail
REMOTE_TMP="$1"; DEST="$2"
sudo mkdir -p "$DEST"
for f in "$REMOTE_TMP"/observeragent-*; do
    sudo install -m 0644 -o www-data -g www-data "$f" "$DEST/"
done
rm -rf "$REMOTE_TMP"
echo "[cdn-publish][remoto] contenido de $DEST:"
ls -la "$DEST"
REMOTE

log "OK — release $TAG publicado en agents.observer.cl."
