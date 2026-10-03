#!/usr/bin/env bash
# Arma el bundle del instalador interactivo (observer-installer-<ver>.tar.gz) desde el
# commit HEAD del dist. Corre en el control-plane (necesita git, node/npm, ansible-galaxy).
#
#   bash scripts/installer/build-bundle.sh [--out DIR]
#
# Salida en DIR (default: ./installer-dist/):
#   observer-installer-<ver>.tar.gz(.sha256)  el bundle que descarga install.sh
#   install.sh                                el bootstrap publico (mismo archivo del repo)
#   update.sh                                 el wrapper de actualizacion (tambien va en el bundle)
#   LATEST                                    la version, para el "latest" de install.sh
#
# El bundle trae, ademas del arbol del dist en HEAD (sin .git ni lo que no se instala):
#   web/dist/                 frontend YA compilado: el servidor no necesita Node
#   vendor/collections/       colecciones Ansible pineadas (collections.lock.yml): sin Galaxy en el cliente
#   vendor/Python-X.tgz       fuente oficial de python.org para Ansible en Ubuntu 22.04
#   VERSION, MANIFEST.sha256
# Se arma desde HEAD (git archive), no desde el arbol de trabajo: lo publicado es exactamente
# lo commiteado. Con cambios sin commitear avisa.
set -Eeuo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8   # ansible-galaxy exige locale UTF-8

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/installer-dist"
ALLOW_OLD_AGENT=0
PY_VERSION="$(grep -oE '^PY_BUILD_VERSION="[^"]+"' "$ROOT/install.sh" | cut -d'"' -f2)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/observer-installer"

while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --allow-old-agent) ALLOW_OLD_AGENT=1; shift ;;
    *) echo "opcion desconocida: $1" >&2; exit 2 ;;
  esac
done

die() { echo "ERROR: $*" >&2; exit 1; }
for c in git npm tar sha256sum curl ansible-galaxy; do
  command -v "$c" >/dev/null || die "falta '$c' en el control-plane"
done
[ -n "$PY_VERSION" ] || die "no se pudo leer PY_BUILD_VERSION de install.sh"

cd "$ROOT"
[ -z "$(git status --porcelain --untracked-files=no)" ] \
  || echo "AVISO: hay cambios sin commitear; el bundle usa HEAD ($(git rev-parse --short HEAD)), no el arbol de trabajo" >&2

ORMM="$(git show HEAD:api/observerrmm/observerrmm/settings.py | grep -oE '^ORMM_VERSION = "[^"]+"' | cut -d'"' -f2)"
[ -n "$ORMM" ] || die "no se pudo leer ORMM_VERSION"
# Un HEAD que no es el tag de la version lleva el commit en el nombre: nunca se pisa un
# bundle publicado de una version con otro contenido.
if [ "$(git rev-parse HEAD)" = "$(git rev-parse -q --verify "refs/tags/v$ORMM^{commit}" || true)" ]; then
  VER="$ORMM"
else
  VER="$ORMM-g$(git rev-parse --short HEAD)"
fi
echo "==> bundle $VER (HEAD $(git rev-parse --short HEAD))"

# El agente que el bundle ofrece a la flota (install.sh/update.sh lo toman de settings.py)
# debe ser la ULTIMA release publicada del agente. Subirlo es un paso manual del release
# del agente que se olvido con la 2.17.3 (settings.py quedo en 2.17.2): aqui se frena.
AGENT_SETTINGS="$(git show HEAD:api/observerrmm/observerrmm/settings.py | grep -oE '^LATEST_AGENT_VER = "[^"]+"' | cut -d'"' -f2)"
if AGENT_LATEST="$(gh release view -R braincorp-cl/observer-agent-dist --json tagName -q .tagName 2>/dev/null)"; then
  AGENT_LATEST="${AGENT_LATEST#v}"
  if [ "$AGENT_SETTINGS" != "$AGENT_LATEST" ] && [ "$(printf '%s\n%s\n' "$AGENT_SETTINGS" "$AGENT_LATEST" | sort -V | head -1)" = "$AGENT_SETTINGS" ]; then
    [ "$ALLOW_OLD_AGENT" = 1 ] || die "settings.py ofrece el agente $AGENT_SETTINGS pero la ultima release es $AGENT_LATEST.
  Suba LATEST_AGENT_VER en api/observerrmm/observerrmm/settings.py (o --allow-old-agent si es a proposito)."
    echo "AVISO: bundle con agente $AGENT_SETTINGS (ultima release: $AGENT_LATEST), por --allow-old-agent" >&2
  fi
  echo "==> agente ofrecido: $AGENT_SETTINGS (ultima release: $AGENT_LATEST)"
else
  echo "AVISO: no se pudo consultar la ultima release del agente con gh; no se verifico LATEST_AGENT_VER ($AGENT_SETTINGS)" >&2
fi

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
SRC="$WORK/src"; mkdir -p "$SRC"
git archive --format=tar HEAD | tar -x -C "$SRC"

echo "==> compilando el frontend (npm ci + quasar build)"
(cd "$SRC/web/app" && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null)
OUTSPA="$SRC/web/app/dist"; [ -f "$OUTSPA/spa/index.html" ] && OUTSPA="$OUTSPA/spa"
rm -rf "$SRC/web/dist" && cp -r "$OUTSPA" "$SRC/web/dist"
test -s "$SRC/web/dist/index.html" || die "el build del frontend no dejo index.html"
# Fuente y toolchain del frontend no se instalan: fuera del bundle (cientos de MB).
rm -rf "$SRC/web/app"

# Lo que no se instala en el servidor.
rm -rf "$SRC/.github" "$SRC/molecule" "$SRC/docs-site" "$SRC/installer-dist"

echo "==> colecciones Ansible"
mkdir -p "$SRC/vendor/collections"
ansible-galaxy collection download -r "$SRC/scripts/installer/collections.lock.yml" -p "$SRC/vendor/collections" >/dev/null
ls "$SRC"/vendor/collections/*.tar.gz >/dev/null 2>&1 || die "no se descargaron colecciones"

echo "==> Python $PY_VERSION (fuente oficial python.org)"
mkdir -p "$CACHE"
PYTGZ="Python-$PY_VERSION.tgz"
if [ ! -s "$CACHE/$PYTGZ" ]; then
  curl -fsSL -o "$CACHE/$PYTGZ.part" "https://www.python.org/ftp/python/$PY_VERSION/$PYTGZ"
  mv "$CACHE/$PYTGZ.part" "$CACHE/$PYTGZ"
fi
tar -tzf "$CACHE/$PYTGZ" >/dev/null || die "$PYTGZ corrupto (borre $CACHE/$PYTGZ)"
cp "$CACHE/$PYTGZ" "$SRC/vendor/"

echo "$VER" >"$SRC/VERSION"
(cd "$SRC" && find . -type f -print0 | sort -z | xargs -0 sha256sum >"$WORK/MANIFEST.sha256")
mv "$WORK/MANIFEST.sha256" "$SRC/MANIFEST.sha256"

mkdir -p "$OUT"
BUNDLE="observer-installer-$VER.tar.gz"
tar -C "$SRC" --owner=0 --group=0 -czf "$OUT/$BUNDLE" .
(cd "$OUT" && sha256sum "$BUNDLE" >"$BUNDLE.sha256")
cp "$ROOT/install.sh" "$OUT/install.sh"
cp "$ROOT/update.sh" "$OUT/update.sh"
echo "$VER" >"$OUT/LATEST"

echo "==> listo: $OUT/$BUNDLE ($(du -h "$OUT/$BUNDLE" | cut -f1))"
