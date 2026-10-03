#!/usr/bin/env bash
# Observer RMM - actualiza un servidor instalado con install.sh a la version publicada.
#
#   bash /opt/observer-installer/update.sh [--version X.Y.Z] [--yes] [--force] [--user U --token T]
#
# Usa el install.sh de la release activa en modo --update: baja la version nueva del CDN
# (con el token guardado al instalar), la verifica y le pasa el control al install.sh NUEVO,
# que respalda la BD, migra el estado (vault, respuestas) y re-aplica install.yml.
# Opciones: las de 'install.sh --help' (seccion "Actualizar").
set -euo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8

BASE_DIR="${OBS_BASE_DIR:-/opt/observer-installer}"
CUR="$BASE_DIR/current/install.sh"
[ -f "$CUR" ] || { echo "ERROR: no hay una instalacion hecha con install.sh en $BASE_DIR" >&2; exit 1; }
if ! grep -q -- '--update' "$CUR"; then
  echo "ERROR: la release instalada es anterior a update.sh. Descargue el install.sh vigente:" >&2
  echo "  curl -fsSL -u <USUARIO>:<TOKEN> https://agents.observer.cl/installer/install.sh -o install.sh" >&2
  echo "  bash install.sh --update --user <USUARIO> --token <TOKEN>" >&2
  exit 1
fi
exec bash "$CUR" --update "$@"
