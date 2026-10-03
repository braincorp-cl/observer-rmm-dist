#!/usr/bin/env bash
# =============================================================================
# Observer RMM - instalador interactivo (greenfield, all-in-one, en el propio servidor)
# =============================================================================
#
# Corre EN el servidor del cliente (Ubuntu 22.04/24.04 recien instalado). Pregunta los
# datos del cliente, deriva lo derivable, valida, arma el inventario y ejecuta los MISMOS
# playbooks Ansible del dist en modo local. Al final informa las cuentas de acceso.
# No requiere un clon de GitHub ni un control-plane: el bundle se descarga del CDN.
#
# Uso tipico (como usuario con sudo, NO hace falta ser root):
#   curl -fsSL -u <USUARIO>:<TOKEN> https://agents.observer.cl/installer/install.sh -o install.sh
#   bash install.sh --user <USUARIO> --token <TOKEN>     (usuario y token los entrega BrainCorp)
#
# Opciones:
#   --token TOKEN        token del CDN (o variable OBS_INSTALLER_TOKEN; si falta, se pregunta)
#   --user USUARIO       usuario del token en el CDN (o OBS_INSTALLER_USER; default: installer).
#                        BrainCorp da un usuario+token por cliente (htpasswd), revocable por separado
#   --version X.Y.Z      version del bundle (default: la publicada como LATEST)
#   --bundle ARCHIVO     usar un bundle local (.tar.gz) en vez de descargarlo
#   --answers ARCHIVO    respuestas en formato KEY=valor (modo no interactivo, ver abajo)
#   --yes                no pedir confirmacion final (para --answers)
#   --verify             solo re-ejecutar el healthcheck y mostrar el resumen (post-reboot)
#
# Actualizar un servidor ya instalado con este script (o: bash /opt/observer-installer/update.sh):
#   --update             baja la version publicada (o --version), respalda, migra el estado
#                        (vault, respuestas) y re-aplica install.yml con el codigo nuevo
#   --force              con --update: re-aplica aunque ya este en esa version
#   --allow-downgrade    con --update: permite bajar de version (las migraciones NO se revierten)
#   --reapply            re-aplica install.yml + healthcheck con la release ACTUAL (reparar o
#                        volver atras: bash /opt/observer-installer/releases/<ver>/install.sh --reapply)
#
# Claves de --answers (los secretos NUNCA van en el archivo: se leen de variables de
# entorno OBS_GODADDY_KEY / OBS_GODADDY_SECRET o se preguntan):
#   OBS_SLUG, OBS_API_FQDN, OBS_RMM_FQDN, OBS_MESH_FQDN, OBS_ACME_EMAIL,
#   OBS_PROXY_IP (vacio = sin proxy reverso), OBS_TIMEZONE, OBS_AGENT_VER,
#   OBS_HUGEPAGES (s/n), OBS_REBOOT (s/n)
#
# Lecciones de los greenfields que este script codifica (no repetirlas a mano):
#   - observer_base_domain se DERIVA de los 3 FQDN (base del wildcard, un solo nivel).
#   - la IP del proxy es la LAN/privada (desde donde conecta al servidor), nunca la publica.
#   - la zona horaria se CONFIRMA con el tecnico (no todos los clientes estan en Chile) y se
#     aplica en las 3 capas: sistema operativo, PostgreSQL y default de la consola.
#   - el pin de hash del Mesh tras el proxy lo deriva el rol de observer_trusted_proxy_ip.
#
# Este archivo es ASCII a proposito (sin tildes): corre en servidores minimizados (C.UTF-8).
# =============================================================================
set -Eeuo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8   # Ansible exige locale UTF-8; C.UTF-8 viene en glibc (sin paquete locales)

CDN_BASE="${OBS_CDN_BASE:-https://agents.observer.cl/installer}"
BASE_DIR="${OBS_BASE_DIR:-/opt/observer-installer}"
LOG_FILE="${OBS_LOG_FILE:-/var/log/observer-install.log}"
PY_BUILD_VERSION="3.12.15"     # solo si el python3 del sistema es < 3.12 (Ubuntu 22.04)
MIN_RAM_KB=7500000             # ~8 GB
MIN_DISK_GB=40

# pwd -P: la ruta REAL de la release. Invocado como .../current/install.sh, con 'pwd' a secas
# REL seria el symlink 'current' y 'ln -sfn $REL current' lo dejaria apuntando a si mismo.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TOKEN="${OBS_INSTALLER_TOKEN:-}"
TOKEN_USER="${OBS_INSTALLER_USER:-}"
WANT_VERSION=""
LOCAL_BUNDLE=""
ANSWERS_FILE=""
ASSUME_YES=0
VERIFY_ONLY=0
UPDATE_MODE=0
FROM_REL=""
FORCE=0
ALLOW_DOWNGRADE=0
REAPPLY=0
ORIG_ARGS=("$@")

# ----------------------------------------------------------------------------- utilidades
c_red=$'\033[31m'; c_grn=$'\033[32m'; c_ylw=$'\033[33m'; c_bld=$'\033[1m'; c_rst=$'\033[0m'
[ -t 1 ] || { c_red=""; c_grn=""; c_ylw=""; c_bld=""; c_rst=""; }

info() { printf '%s\n' "${c_grn}==>${c_rst} $*"; }
warn() { printf '%s\n' "${c_ylw}AVISO:${c_rst} $*" >&2; }
die()  { printf '%s\n' "${c_red}ERROR:${c_rst} $*" >&2; exit 1; }
hr()   { printf '%s\n' "------------------------------------------------------------"; }

trap 'die "fallo inesperado en la linea $LINENO (ver $LOG_FILE si existe)"' ERR

# Lee de la terminal aunque el script venga por una tuberia.
tty_read() {  # tty_read VAR "pregunta" [default] [secreto=0]
  local __var="$1" __q="$2" __def="${3:-}" __secret="${4:-0}" __ans=""
  local __prompt="$__q"
  [ -n "$__def" ] && __prompt="$__q [$__def]"
  if [ "$__secret" = 1 ]; then
    read -r -s -p "$__prompt: " __ans </dev/tty; echo >/dev/tty
  else
    read -r -p "$__prompt: " __ans </dev/tty
  fi
  [ -z "$__ans" ] && __ans="$__def"
  printf -v "$__var" '%s' "$__ans"
}

yes_no() {  # yes_no "pregunta" default(s|n) -> rc 0 si si
  local ans
  tty_read ans "$1 (s/n)" "$2"
  case "$ans" in s|S|si|SI|y|Y|yes) return 0 ;; *) return 1 ;; esac
}

is_yes() { case "${1:-}" in s|S|si|SI|y|Y|yes|true|1) return 0 ;; *) return 1 ;; esac; }

run_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo -n "$@"; fi; }

# ----------------------------------------------------------------------------- argumentos
while [ $# -gt 0 ]; do
  case "$1" in
    --token)   TOKEN="${2:-}"; shift 2 ;;
    --user)    TOKEN_USER="${2:-}"; shift 2 ;;
    --version) WANT_VERSION="${2:-}"; shift 2 ;;
    --bundle)  LOCAL_BUNDLE="${2:-}"; shift 2 ;;
    --answers) ANSWERS_FILE="${2:-}"; shift 2 ;;
    --yes)     ASSUME_YES=1; shift ;;
    --verify)  VERIFY_ONLY=1; shift ;;
    --update)  UPDATE_MODE=1; shift ;;
    --from)    FROM_REL="${2:-}"; shift 2 ;;
    --force)   FORCE=1; shift ;;
    --allow-downgrade) ALLOW_DOWNGRADE=1; shift ;;
    --reapply) REAPPLY=1; shift ;;
    -h|--help) sed -n '2,48p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) die "opcion desconocida: $1 (use --help)" ;;
  esac
done

if [ -n "$ANSWERS_FILE" ]; then
  [ -r "$ANSWERS_FILE" ] || die "no se puede leer $ANSWERS_FILE"
  ANSWERS_FILE="$(cd "$(dirname "$ANSWERS_FILE")" && pwd)/$(basename "$ANSWERS_FILE")"
fi

require_sudo() {
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null || die "falta sudo; ejecute como un usuario con sudo"
    sudo -n true 2>/dev/null || die "el usuario '$(id -un)' necesita sudo SIN password (NOPASSWD).
  Configurelo con 'sudo visudo' (linea: %sudo ALL=(ALL:ALL) NOPASSWD:ALL) o ejecute como root."
  fi
}

# =============================================================================
# MODO BOOTSTRAP: el script corre suelto (no esta dentro de un bundle extraido)
# =============================================================================
# Comparacion de versiones (sort -V): ver_lt A B -> rc 0 si A < B estricto.
ver_lt() { [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$1" ]; }

resolve_token() {
  # Orden: --token/--user (o variables), el guardado por una instalacion previa
  # ("usuario:token"; un archivo sin ':' es de antes de --user => usuario installer), o preguntar.
  if [ -z "$TOKEN" ] && [ -r "$BASE_DIR/token" ]; then
    local saved
    saved="$(tr -d '[:space:]' <"$BASE_DIR/token")"
    if [[ "$saved" == *:* ]]; then
      [ -n "$TOKEN_USER" ] || TOKEN_USER="${saved%%:*}"
      TOKEN="${saved#*:}"
    else
      TOKEN="$saved"
    fi
  fi
  [ -n "$TOKEN_USER" ] || TOKEN_USER="installer"
  [[ "$TOKEN_USER" =~ ^[A-Za-z0-9._-]+$ ]] || die "usuario de token invalido: '$TOKEN_USER'"
  [ -n "$TOKEN" ] || tty_read TOKEN "Token de descarga del instalador para '$TOKEN_USER' (lo entrega BrainCorp)" "" 1
  [ -n "$TOKEN" ] || die "se requiere el token de descarga"
}

save_token() {  # guarda usuario:token que funciono, para update.sh (0600, revocable en el CDN)
  [ -n "$TOKEN" ] && [ -d "$BASE_DIR" ] || return 0
  (umask 077; printf '%s:%s\n' "${TOKEN_USER:-installer}" "$TOKEN" >"$BASE_DIR/token")
  chmod 0600 "$BASE_DIR/token"   # umask no corrige el modo de un archivo que ya existia
}

remote_latest() {
  curl -fsS -u "$TOKEN_USER:$TOKEN" "$CDN_BASE/LATEST" | tr -d '[:space:]' \
    || die "no se pudo consultar $CDN_BASE/LATEST (token invalido o sin salida a agents.observer.cl)"
}

fetch_bundle() {  # fetch_bundle [version] -> deja BUNDLE_FILE (verificado) y WORKDIR
  WORKDIR="$(mktemp -d)"
  if [ -n "$LOCAL_BUNDLE" ]; then
    [ -r "$LOCAL_BUNDLE" ] || die "no se puede leer el bundle $LOCAL_BUNDLE"
    BUNDLE_FILE="$LOCAL_BUNDLE"
    if [ -r "$LOCAL_BUNDLE.sha256" ]; then
      (cd "$(dirname "$BUNDLE_FILE")" && sha256sum -c "$(basename "$BUNDLE_FILE").sha256" >/dev/null) \
        || die "el sha256 del bundle no coincide"
      info "bundle local verificado (sha256)"
    else
      warn "no hay $LOCAL_BUNDLE.sha256: el bundle local NO se verifico"
    fi
    return
  fi
  local ver="${1:-}"
  [ -n "$ver" ] || ver="$(remote_latest)"
  [[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)?$ ]] || die "version invalida: '$ver'"
  local auth=(-u "$TOKEN_USER:$TOKEN")
  BUNDLE_FILE="$WORKDIR/observer-installer-$ver.tar.gz"
  info "descargando el bundle $ver desde $CDN_BASE"
  curl -fS --progress-bar "${auth[@]}" -o "$BUNDLE_FILE" "$CDN_BASE/observer-installer-$ver.tar.gz" \
    || die "no se pudo descargar el bundle $ver"
  curl -fsS "${auth[@]}" -o "$BUNDLE_FILE.sha256" "$CDN_BASE/observer-installer-$ver.tar.gz.sha256" \
    || die "no se pudo descargar el sha256 del bundle"
  (cd "$WORKDIR" && sha256sum -c "$(basename "$BUNDLE_FILE").sha256" >/dev/null) \
    || die "el sha256 del bundle descargado NO coincide: descarga corrupta o alterada"
  info "bundle verificado (sha256)"
}

bundle_version() { tar -xzOf "$1" ./VERSION 2>/dev/null | tr -d '[:space:]'; }

extract_bundle() {  # extrae BUNDLE_FILE en releases/<ver> -> deja NEW_REL
  local ver
  ver="$(bundle_version "$BUNDLE_FILE")" || true
  [ -n "$ver" ] || die "el bundle no trae VERSION (bundle invalido)"
  NEW_REL="$BASE_DIR/releases/$ver"
  if [ -e "$NEW_REL/install.yml" ]; then
    info "la version $ver ya esta extraida en $NEW_REL"
  else
    run_root mkdir -p "$NEW_REL"
    run_root tar -xzf "$BUNDLE_FILE" -C "$NEW_REL"
  fi
  # El arbol del bundle (y los vault que generara) es del usuario que instala, 0700.
  run_root chown -R "$(id -u):$(id -g)" "$BASE_DIR"
  chmod 0700 "$BASE_DIR"
  rm -rf "$WORKDIR"
  info "bundle $ver listo en $NEW_REL"
}

bootstrap() {
  require_sudo
  command -v curl >/dev/null || run_root apt-get install -y -qq curl ca-certificates >/dev/null
  [ -n "$LOCAL_BUNDLE" ] || resolve_token
  fetch_bundle "$WANT_VERSION"
  extract_bundle
  ln -sfn "$NEW_REL" "$BASE_DIR/current"
  save_token
  # Continua el mismo script, ya dentro del bundle (sin --bundle/--token: ya no hacen falta).
  local pass=()
  [ -n "$ANSWERS_FILE" ] && pass+=(--answers "$ANSWERS_FILE")
  [ "$ASSUME_YES" = 1 ] && pass+=(--yes)
  [ "$VERIFY_ONLY" = 1 ] && pass+=(--verify)
  exec bash "$NEW_REL/install.sh" "${pass[@]}"
}

# Update, fase 1 (con el install.sh que sea: el de la release actual, o uno suelto bajado
# del CDN): baja la version nueva SIN tocar 'current' y le pasa el control al install.sh
# NUEVO, que es el que sabe migrar el estado a su version.
bootstrap_update() {
  require_sudo
  local cur old_ver ver
  cur="$(readlink -f "$BASE_DIR/current" 2>/dev/null || true)"
  [ -n "$cur" ] && [ -f "$cur/VERSION" ] && [ -s "$BASE_DIR/answers.env" ] \
    || die "no hay una instalacion hecha con install.sh en $BASE_DIR (falta current o answers.env)"
  old_ver="$(tr -d '[:space:]' <"$cur/VERSION")"
  command -v curl >/dev/null || run_root apt-get install -y -qq curl ca-certificates >/dev/null
  if [ -n "$LOCAL_BUNDLE" ]; then
    ver="$(bundle_version "$LOCAL_BUNDLE")"
  else
    resolve_token
    ver="${WANT_VERSION:-$(remote_latest)}"
    save_token   # el CDN ya lo acepto (o lo valida la descarga): queda para la proxima vez
  fi
  info "version instalada: $old_ver  ->  disponible: $ver"
  if [ "$ver" = "$old_ver" ] && [ "$FORCE" != 1 ]; then
    info "ya esta al dia (use --force para re-aplicar igual)"
    exit 0
  fi
  fetch_bundle "$ver"
  extract_bundle
  save_token
  local pass=(--update --from "$cur")
  [ "$ASSUME_YES" = 1 ] && pass+=(--yes)
  [ "$FORCE" = 1 ] && pass+=(--force)
  [ "$ALLOW_DOWNGRADE" = 1 ] && pass+=(--allow-downgrade)
  exec bash "$NEW_REL/install.sh" "${pass[@]}"
}

# =============================================================================
# MODO BUNDLE: el script esta junto a install.yml
# =============================================================================
REL="$SCRIPT_DIR"
INV="$REL/inventory/produccion.yml"
VENV="$REL/.venv"
ANSWERS_SAVED="$BASE_DIR/answers.env"

setup_log() {
  run_root touch "$LOG_FILE"
  run_root chown "$(id -u):$(id -g)" "$LOG_FILE"
  chmod 0600 "$LOG_FILE"   # contendra las credenciales iniciales (resumen de acceso)
  exec > >(tee -a "$LOG_FILE") 2>&1
  echo "===== $(date -Is) observer install.sh (${ORIG_ARGS[*]:-}) ====="
}

# ----------------------------------------------------------------------------- preflight
preflight() {
  info "preflight del servidor"
  # shellcheck disable=SC1091
  . /etc/os-release
  [ "${ID:-}" = ubuntu ] || die "sistema no soportado: ${PRETTY_NAME:-?} (requiere Ubuntu 22.04 o 24.04)"
  case "${VERSION_ID:-}" in 22.04|24.04) ;; *) die "Ubuntu ${VERSION_ID:-?} no soportado (22.04 o 24.04)";; esac
  case "$(uname -m)" in
    x86_64) ;; aarch64) warn "arquitectura arm64: soportada, pero menos probada que x86_64" ;;
    *) die "arquitectura $(uname -m) no soportada" ;;
  esac
  require_sudo
  local mem_kb disk_gb
  mem_kb="$(awk '/^MemTotal:/{print $2}' /proc/meminfo)"
  [ "$mem_kb" -ge "$MIN_RAM_KB" ] || die "RAM insuficiente: $((mem_kb/1024/1024)) GB (minimo 8 GB)"
  disk_gb="$(df -BG --output=avail / | tail -1 | tr -dc '0-9')"
  [ "$disk_gb" -ge "$MIN_DISK_GB" ] || die "disco libre insuficiente en /: ${disk_gb} GB (minimo ${MIN_DISK_GB} GB)"
  if [ -e /opt/observer ] || [ -e /meshcentral ]; then
    die "ya hay una instalacion de Observer RMM en este servidor (/opt/observer o /meshcentral).
  install.sh es solo para servidores NUEVOS. Para actualizar use el procedimiento de upgrade."
  fi
  if ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:)(80|443)$'; then
    die "los puertos 80/443 ya estan en uso: este servidor debe estar limpio"
  fi
  info "SO ${PRETTY_NAME}, $(nproc) CPU, $(( (mem_kb + 524288) / 1048576 )) GB RAM, ${disk_gb} GB libres: OK"
}

check_egress() {
  # Lo que install.yml descarga durante la instalacion. Un firewall de salida que bloquee
  # (o intercepte TLS) cualquiera de estos hace fallar el install a mitad de camino.
  info "verificando salida HTTPS a los origenes de la instalacion"
  local hosts=(
    github.com objects.githubusercontent.com pypi.org files.pythonhosted.org
    registry.npmjs.org deb.nodesource.com apt.postgresql.org nginx.org
    www.python.org acme-v02.api.letsencrypt.org api.godaddy.com
  )
  local h bad=()
  for h in "${hosts[@]}"; do
    curl -sS -o /dev/null --connect-timeout 8 --max-time 15 "https://$h/" 2>/dev/null || bad+=("$h")
  done
  if [ "${#bad[@]}" -gt 0 ]; then
    die "sin salida HTTPS valida a: ${bad[*]}
  Abra esos destinos en el firewall (sin inspeccion TLS) y vuelva a ejecutar."
  fi
  info "salida HTTPS: OK (${#hosts[@]} destinos)"
}

# ----------------------------------------------------------------------------- validaciones
valid_fqdn() { [[ "$1" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$ ]]; }
valid_email() { [[ "$1" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; }
valid_ipv4() {
  [[ "$1" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1
  local o; for o in "${BASH_REMATCH[@]:1}"; do [ "$o" -le 255 ] || return 1; done
}
is_private_ipv4() {
  local a b; IFS=. read -r a b _ _ <<<"$1"
  [ "$a" -eq 10 ] || { [ "$a" -eq 172 ] && [ "$b" -ge 16 ] && [ "$b" -le 31 ]; } || { [ "$a" -eq 192 ] && [ "$b" -eq 168 ]; }
}
base_of() { printf '%s' "${1#*.}"; }   # quita el primer label: api.x.observer.cl -> x.observer.cl

# ----------------------------------------------------------------------------- respuestas
load_answers() {
  # Formato KEY=valor, sin ejecutar el archivo (no se hace 'source' de datos ajenos).
  local line key val
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"; [ -z "${line//[[:space:]]/}" ] && continue
    key="${line%%=*}"; val="${line#*=}"
    key="${key//[[:space:]]/}"; val="${val#"${val%%[![:space:]]*}"}"; val="${val%"${val##*[![:space:]]}"}"
    val="${val%\"}"; val="${val#\"}"
    case "$key" in
      OBS_SLUG|OBS_API_FQDN|OBS_RMM_FQDN|OBS_MESH_FQDN|OBS_ACME_EMAIL|OBS_PROXY_IP|\
      OBS_TIMEZONE|OBS_AGENT_VER|OBS_HUGEPAGES|OBS_REBOOT|OBS_BUNDLE) printf -v "$key" '%s' "$val" ;;
      OBS_GODADDY_KEY|OBS_GODADDY_SECRET) die "$key no puede ir en el archivo de respuestas (use variable de entorno)" ;;
      *) warn "clave desconocida en respuestas: $key (ignorada)" ;;
    esac
  done <"$ANSWERS_FILE"
}

# ask VAR "pregunta" default validador "mensaje si invalido"
ask() {
  local __var="$1" __q="$2" __def="$3" __check="$4" __err="$5" __val
  __val="${!__var:-}"
  if [ -n "$ANSWERS_FILE" ]; then
    [ -z "$__val" ] && __val="$__def"
    "$__check" "$__val" || die "respuestas: $__var='$__val' invalido: $__err"
  else
    while :; do
      tty_read __val "$__q" "${__val:-$__def}"
      "$__check" "$__val" && break
      warn "$__err"; __val=""
    done
  fi
  printf -v "$__var" '%s' "$__val"
}

_any() { return 0; }
_slug() { [[ "$1" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; }
_fqdn() { valid_fqdn "$1"; }
_email() { valid_email "$1"; }
_proxy() { [ -z "$1" ] || [ "$1" = "-" ] || { valid_ipv4 "$1" && is_private_ipv4 "$1"; }; }
_tz() { timedatectl list-timezones 2>/dev/null | grep -qxF "$1"; }
_ver() { [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; }
_yn() { case "$1" in s|S|n|N|si|no|y|yes) return 0 ;; *) return 1 ;; esac; }

godaddy_zone() {  # imprime la zona GoDaddy que contiene la base; rc!=0 si credenciales/zona invalidas
  local cand="$1" code
  while [[ "$cand" == *.* ]]; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
      -H "Authorization: sso-key $OBS_GODADDY_KEY:$OBS_GODADDY_SECRET" \
      "https://api.godaddy.com/v1/domains/$cand")" || code=000
    case "$code" in
      200) printf '%s' "$cand"; return 0 ;;
      401|403) return 2 ;;
    esac
    cand="${cand#*.}"
  done
  return 1
}

collect_answers() {
  [ -n "$ANSWERS_FILE" ] && load_answers
  hr; echo "${c_bld}Datos del cliente nuevo${c_rst}"; hr

  ask OBS_SLUG "Nombre corto del cliente (minusculas, ej. fluitek)" "" _slug \
    "solo minusculas, numeros y guiones"
  ask OBS_API_FQDN  "FQDN del API"         "api.$OBS_SLUG.observer.cl"  _fqdn "FQDN invalido"
  ask OBS_RMM_FQDN  "FQDN de la consola"   "rmm.$OBS_SLUG.observer.cl"  _fqdn "FQDN invalido"
  ask OBS_MESH_FQDN "FQDN de MeshCentral"  "mesh.$OBS_SLUG.observer.cl" _fqdn "FQDN invalido"

  # observer_base_domain se DERIVA: base del wildcard *.<base>, que cubre UN solo nivel.
  OBS_BASE_DOMAIN="$(base_of "$OBS_API_FQDN")"
  if [ "$(base_of "$OBS_RMM_FQDN")" != "$OBS_BASE_DOMAIN" ] || [ "$(base_of "$OBS_MESH_FQDN")" != "$OBS_BASE_DOMAIN" ]; then
    die "los 3 FQDN deben compartir la misma base (ej. api|rmm|mesh.<cliente>.observer.cl):
  el certificado wildcard *.<base> cubre un solo nivel. Recibidos: $OBS_API_FQDN $OBS_RMM_FQDN $OBS_MESH_FQDN"
  fi
  [ "$OBS_API_FQDN" != "$OBS_RMM_FQDN" ] && [ "$OBS_API_FQDN" != "$OBS_MESH_FQDN" ] && [ "$OBS_RMM_FQDN" != "$OBS_MESH_FQDN" ] \
    || die "los 3 FQDN deben ser distintos"

  ask OBS_ACME_EMAIL "Email de registro Let's Encrypt" "" _email "email invalido"

  echo
  echo "Certificado: wildcard *.$OBS_BASE_DOMAIN por DNS de GoDaddy (Let's Encrypt)."
  if [ -z "${OBS_GODADDY_KEY:-}" ]; then
    [ -n "$ANSWERS_FILE" ] && die "defina OBS_GODADDY_KEY y OBS_GODADDY_SECRET en el entorno"
    tty_read OBS_GODADDY_KEY "GoDaddy API key" "" 1
    tty_read OBS_GODADDY_SECRET "GoDaddy API secret" "" 1
  fi
  local rc=0
  OBS_GODADDY_ZONE="$(godaddy_zone "$OBS_BASE_DOMAIN")" || rc=$?
  case "$rc" in
    0) info "GoDaddy: credenciales OK, zona '$OBS_GODADDY_ZONE'" ;;
    2) die "GoDaddy rechazo las credenciales (401/403)" ;;
    *) die "ninguna zona de la cuenta GoDaddy contiene $OBS_BASE_DOMAIN" ;;
  esac

  echo
  echo "Si el servidor se publica detras de un proxy reverso (ej. Nginx Proxy Manager),"
  echo "indique la IP PRIVADA/LAN desde la que el proxy CONECTA a este servidor (no la"
  echo "IP publica del proxy). Responda '-' si NO hay proxy reverso (publicacion directa)."
  local def_proxy="10.20.0.254"
  [ -n "$ANSWERS_FILE" ] && def_proxy=""
  ask OBS_PROXY_IP "IP LAN del proxy reverso" "$def_proxy" _proxy \
    "debe ser una IPv4 PRIVADA (10/8, 172.16/12, 192.168/16): con la publica real_ip nunca coincide"
  [ "$OBS_PROXY_IP" = "-" ] && OBS_PROXY_IP=""

  local tz_now
  tz_now="$(timedatectl show -p Timezone --value 2>/dev/null || echo UTC)"
  echo
  echo "Zona horaria actual del servidor: $tz_now. Confirmela o indique la del cliente"
  echo "(ej. America/Santiago, America/Mexico_City). Se aplica al SO, a PostgreSQL y"
  echo "como zona por defecto de la consola."
  ask OBS_TIMEZONE "Zona horaria del cliente" "$tz_now" _tz "zona desconocida (ver: timedatectl list-timezones)"

  local agent_def
  agent_def="$(grep -oE 'LATEST_AGENT_VER = "[^"]+"' "$REL/api/observerrmm/observerrmm/settings.py" | cut -d'"' -f2)"
  ask OBS_AGENT_VER "Version del agente que ofrecera a la flota" "$agent_def" _ver "formato X.Y.Z"

  ask OBS_HUGEPAGES "Activar HugePages para PostgreSQL (recomendado)" "s" _yn "responda s o n"
  if is_yes "$OBS_HUGEPAGES"; then
    ask OBS_REBOOT "Reiniciar el servidor al terminar (necesario para HugePages)" "s" _yn "responda s o n"
  else
    OBS_REBOOT="n"
  fi
}

pg_sizing_for_gb() {  # fija PG_* para una RAM de $1 GB
  # PG convive con Mesh + Django + Celery + Redis + NATS: no se le da el 25% completo.
  # La fila de 16 GB es la validada en los 6 greenfields.
  if   [ "$1" -lt 12 ]; then PG_SB=1GB; PG_ECS=4GB;  PG_MWM=128MB; PG_MINWAL=256MB; PG_MAXWAL=1GB
  elif [ "$1" -lt 24 ]; then PG_SB=2GB; PG_ECS=6GB;  PG_MWM=256MB; PG_MINWAL=512MB; PG_MAXWAL=2GB
  else                       PG_SB=4GB; PG_ECS=12GB; PG_MWM=512MB; PG_MINWAL=1GB;   PG_MAXWAL=4GB
  fi
  PG_RAM_GB="$1"
}

derive_pg_sizing() {
  # MemTotal de una VM de "16 GB" reporta ~15.6 GiB: se redondea al GB mas cercano.
  pg_sizing_for_gb $(( ($(awk '/^MemTotal:/{print $2}' /proc/meminfo) + 524288) / 1048576 ))
}

show_summary_and_confirm() {
  hr; echo "${c_bld}Resumen de la instalacion${c_rst}"; hr
  cat <<EOF
  Cliente:            $OBS_SLUG
  Consola / API:      https://$OBS_RMM_FQDN  /  https://$OBS_API_FQDN
  MeshCentral:        https://$OBS_MESH_FQDN
  Certificado:        *.$OBS_BASE_DOMAIN (Let's Encrypt via GoDaddy, zona $OBS_GODADDY_ZONE)
  Proxy reverso:      ${OBS_PROXY_IP:-ninguno (publicacion directa)}
  Zona horaria:       $OBS_TIMEZONE
  Agente ofrecido:    $OBS_AGENT_VER
  PostgreSQL:         shared_buffers $PG_SB, HugePages $(is_yes "$OBS_HUGEPAGES" && echo si || echo no) (RAM ${PG_RAM_GB} GB)
  Reinicio al final:  $(is_yes "$OBS_REBOOT" && echo si || echo no)
  Bundle:             $(cat "$REL/VERSION") en $REL
EOF
  hr
  if [ "$ASSUME_YES" != 1 ]; then
    yes_no "Continuar con la instalacion" "n" || die "instalacion cancelada por el usuario"
  fi
}

# ----------------------------------------------------------------------------- ansible local
python_for_ansible() {
  # ansible-core del dist exige Python >= 3.12. Ubuntu 24.04 lo trae; en 22.04 (3.10) se
  # compila desde el fuente oficial de python.org que viaja en el bundle (mismo metodo que
  # el rol observer_python; sin PPAs) a un prefijo propio que NO toca el python del sistema.
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    PYBIN="$(command -v python3)"; return
  fi
  PYBIN="$BASE_DIR/python/bin/python3.12"
  [ -x "$PYBIN" ] && return
  info "compilando Python $PY_BUILD_VERSION para Ansible (solo Ubuntu 22.04, ~5 min)"
  run_root apt-get install -y -qq build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
    libssl-dev libreadline-dev libffi-dev libsqlite3-dev libbz2-dev >/dev/null
  local src
  src="$(mktemp -d)"
  tar -xzf "$REL/vendor/Python-$PY_BUILD_VERSION.tgz" -C "$src"
  # La salida del compilador (miles de lineas de avisos) va a un log aparte; solo se
  # muestra su cola si el build falla.
  local blog="$BASE_DIR/python-build.log"
  if ! (cd "$src/Python-$PY_BUILD_VERSION" && ./configure --prefix="$BASE_DIR/python" \
        && make -j "$(nproc)" && make altinstall) >"$blog" 2>&1; then
    tail -40 "$blog"; die "fallo la compilacion de Python $PY_BUILD_VERSION (log: $blog)"
  fi
  rm -rf "$src"
  [ -x "$PYBIN" ] || die "no se pudo compilar Python $PY_BUILD_VERSION"
}

setup_ansible() {
  info "instalando dependencias base (apt)"
  run_root apt-get update -qq
  run_root apt-get install -y -qq python3-venv curl ca-certificates rsync openssl >/dev/null
  python_for_ansible
  if [ ! -x "$VENV/bin/ansible-playbook" ]; then
    info "creando el entorno de Ansible ($("$PYBIN" -V))"
    "$PYBIN" -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q "$(grep -E '^ansible-core' "$REL/requirements.txt")"
  fi
  # Colecciones desde el bundle (sin depender de Galaxy en el cliente).
  export ANSIBLE_COLLECTIONS_PATH="$REL/.collections"
  if [ ! -d "$ANSIBLE_COLLECTIONS_PATH/ansible_collections/community/general" ]; then
    "$VENV/bin/ansible-galaxy" collection install --offline -p "$ANSIBLE_COLLECTIONS_PATH" \
      "$REL"/vendor/collections/*.tar.gz >/dev/null
  fi
  export ANSIBLE_CONFIG="$REL/ansible.cfg" ANSIBLE_FORCE_COLOR=0 PATH="$VENV/bin:$PATH"
  info "Ansible listo: $(ansible --version </dev/null | head -1)"
}

write_secrets_and_inventory() {
  umask 077
  if [ ! -s "$REL/.vault_pass" ]; then
    openssl rand -base64 32 >"$REL/.vault_pass"
  fi
  chmod 0600 "$REL/.vault_pass"
  # En claro a proposito: el play de autovault de install.yml lo cifra en la primera corrida.
  cat >"$REL/group_vars/observer_proxy/vault.yml" <<EOF
---
# Credenciales GoDaddy (zona $OBS_GODADDY_ZONE) - las escribio install.sh; install.yml las cifra.
vault_godaddy_key: "$OBS_GODADDY_KEY"
vault_godaddy_secret: "$OBS_GODADDY_SECRET"
EOF
  chmod 0600 "$REL/group_vars/observer_proxy/vault.yml"
  umask 022
  render_inventory "$INV"
  save_answers
}

render_inventory() {  # render_inventory destino
  local dest="$1" proxy_line="" huge="off"
  umask 077
  [ -n "$OBS_PROXY_IP" ] && proxy_line="    observer_trusted_proxy_ip: \"$OBS_PROXY_IP\""
  is_yes "$OBS_HUGEPAGES" && huge="try"
  cat >"$dest" <<EOF
---
# inventory/produccion.yml - GENERADO por install.sh $(date -Is). Cliente: $OBS_SLUG
# All-in-One LOCAL: Ansible corre en este mismo servidor (ansible_connection: local).
all:
  vars:
    ansible_python_interpreter: /usr/bin/python3

    observer_domain: $OBS_API_FQDN
    observer_app_domain: $OBS_RMM_FQDN
    observer_mesh_domain: $OBS_MESH_FQDN
    # DERIVADO de los 3 FQDN: base del wildcard *.$OBS_BASE_DOMAIN (un solo nivel).
    observer_base_domain: $OBS_BASE_DOMAIN

    observer_cert_mode: acme
    observer_acme_email: $OBS_ACME_EMAIL

    # IP LAN del proxy reverso (real_ip). Tambien relaja el pin de hash del Mesh.
$proxy_line

    observer_latest_agent_ver: "$OBS_AGENT_VER"

    # Zona horaria del cliente: SO (observer_common) + default de la consola (solo al crear).
    observer_timezone: "$OBS_TIMEZONE"
    observer_default_time_zone: "$OBS_TIMEZONE"

    # PostgreSQL dimensionado por install.sh para ${PG_RAM_GB} GB de RAM.
    pg_shared_buffers: "$PG_SB"
    pg_effective_cache_size: "$PG_ECS"
    pg_maintenance_work_mem: "$PG_MWM"
    pg_autovacuum_work_mem: "$PG_MWM"
    pg_min_wal_size: "$PG_MINWAL"
    pg_max_wal_size: "$PG_MAXWAL"
    observer_db_max_connections: 100
    pg_huge_pages: "$huge"

  children:
    # Los 5 grupos apuntan al MISMO host local. Conexion y zona de PostgreSQL van como
    # HOST-VARS: asi le ganan a group_vars/observer_db/vars.yml (que fija America/Santiago).
    observer_db:
      hosts:
        localhost:
          ansible_connection: local
          observer_db_host: localhost
          observer_redis_host: localhost
          observer_mesh_host: localhost
          observer_nats_host: 127.0.0.1
          pg_timezone: "$OBS_TIMEZONE"
          pg_log_timezone: "$OBS_TIMEZONE"
    observer_redis:
      hosts: { localhost: { ansible_connection: local } }
    observer_mesh:
      hosts: { localhost: { ansible_connection: local } }
    observer_api:
      hosts: { localhost: { ansible_connection: local } }
    observer_proxy:
      hosts: { localhost: { ansible_connection: local } }
EOF
  chmod 0600 "$dest"
  umask 022
}

save_answers() {
  # Respuestas (SIN secretos) para update.sh y para auditoria.
  (umask 077; cat >"$ANSWERS_SAVED" <<EOF
# Respuestas de install.sh $(date -Is) - sin secretos (GoDaddy queda cifrado en el vault).
OBS_SLUG=$OBS_SLUG
OBS_API_FQDN=$OBS_API_FQDN
OBS_RMM_FQDN=$OBS_RMM_FQDN
OBS_MESH_FQDN=$OBS_MESH_FQDN
OBS_ACME_EMAIL=$OBS_ACME_EMAIL
OBS_PROXY_IP=$OBS_PROXY_IP
OBS_TIMEZONE=$OBS_TIMEZONE
OBS_AGENT_VER=$OBS_AGENT_VER
OBS_HUGEPAGES=$OBS_HUGEPAGES
OBS_REBOOT=$OBS_REBOOT
OBS_BUNDLE=$(cat "$REL/VERSION")
EOF
  )
  chmod 0600 "$ANSWERS_SAVED"
}

run_playbook() {  # run_playbook archivo.yml [args...]
  local pb="$1"; shift
  (cd "$REL" && ansible-playbook "$pb" -i "$INV" "$@" </dev/null)
}

vault_value() {  # vault_value group_vars/x/vault.yml clave
  (cd "$REL" && ansible-vault view "$1" </dev/null) | awk -F': ' -v k="$2" '$1==k{gsub(/"/,"",$2); print $2}'
}

final_report() {
  local admin_pw mesh_pw
  admin_pw="$(vault_value group_vars/observer_api/vault.yml vault_observer_admin_password)"
  mesh_pw="$(vault_value group_vars/observer_mesh/vault.yml vault_observer_mesh_password)"
  # shellcheck disable=SC1090
  . <(grep -E '^OBS_(RMM|API|MESH)_FQDN=|^OBS_PROXY_IP=' "$ANSWERS_SAVED")
  hr; echo "${c_bld}  Observer RMM - instalacion completa${c_rst}"; hr
  cat <<EOF
  Consola RMM:   https://$OBS_RMM_FQDN
      usuario:   observeradmin
      password:  $admin_pw
      (en el primer login se pide configurar 2FA/TOTP)

  MeshCentral:   https://$OBS_MESH_FQDN
      usuario:   meshcentral_admin
      password:  $mesh_pw

  GUARDE EN SU GESTOR DE CONTRASENAS (unica copia, sin ellos no hay upgrade):
    - estas dos credenciales
    - $REL/.vault_pass   (descifra los group_vars/*/vault*.yml del bundle)
  Log completo (incluye estas credenciales, permisos 0600): $LOG_FILE
EOF
  if [ -n "${OBS_PROXY_IP:-}" ]; then
    hr
    cat <<EOF
  PUBLICACION EN EL PROXY REVERSO (Nginx Proxy Manager) - cree 3 Proxy Hosts:
    Domain             Scheme  Forward Hostname        Port  Websockets
    $OBS_API_FQDN   https   $OBS_API_FQDN   443   ON
    $OBS_RMM_FQDN   https   $OBS_RMM_FQDN   443   ON
    $OBS_MESH_FQDN  https   $OBS_MESH_FQDN  443   ON
  - SSL: certificado Let's Encrypt propio del proxy para cada host, Force SSL.
  - Advanced del API:  client_max_body_size 300m; proxy_read_timeout 86400; proxy_send_timeout 86400;
  - Advanced del Mesh: proxy_read_timeout 86400; proxy_send_timeout 86400;
    (sin X-Frame-Options ni CSP frame-ancestors en mesh: la consola lo embebe en un iframe)
  - El proxy debe resolver los 3 FQDN a la IP LAN de ESTE servidor ($(hostname -I | awk '{print $1}')),
    no a si mismo (evita el loop).
EOF
  fi
  hr
}

do_verify() {
  setup_ansible
  info "healthcheck"
  run_playbook healthcheck.yml
  final_report
}

# =============================================================================
# UPDATE (fase 2) y REAPPLY: corren con el install.sh de la release NUEVA / ACTUAL
# =============================================================================
settings_value() {  # settings_value archivo CLAVE -> valor de CLAVE = "..." en settings.py
  grep -oE "^$2 = \"[^\"]+\"" "$1" 2>/dev/null | cut -d'"' -f2
}
installed_ormm() { settings_value /opt/observer/api/observerrmm/observerrmm/settings.py ORMM_VERSION; }
bundle_ormm()    { settings_value "$REL/api/observerrmm/observerrmm/settings.py" ORMM_VERSION; }
bundle_agent()   { settings_value "$REL/api/observerrmm/observerrmm/settings.py" LATEST_AGENT_VER; }

# El pin del agente adopta la version del bundle, pero NUNCA baja la flota de version.
pick_agent_version() {  # pick_agent_version pin_actual version_bundle -> imprime la que queda
  if [ -z "$1" ] || ver_lt "$1" "$2"; then printf '%s' "$2"; else printf '%s' "$1"; fi
}

# Cuerpo del inventario sin comentarios ni lineas vacias (el encabezado lleva la fecha).
inv_body() { grep -vE '^[[:space:]]*#' "$1" | sed '/^[[:space:]]*$/d'; }

preflight_update() {
  info "preflight del update"
  # shellcheck disable=SC1091
  . /etc/os-release
  [ "${ID:-}" = ubuntu ] || die "sistema no soportado: ${PRETTY_NAME:-?}"
  require_sudo
  [ -d /opt/observer ] || die "no hay Observer RMM instalado en este servidor (/opt/observer)"
  [ -s "$FROM_REL/.vault_pass" ] && [ -s "$FROM_REL/inventory/produccion.yml" ] \
    || die "la release anterior $FROM_REL no tiene su estado (.vault_pass / inventario)"
  local disk_gb
  disk_gb="$(df -BG --output=avail / | tail -1 | tr -dc '0-9')"
  [ "$disk_gb" -ge 10 ] || die "disco libre insuficiente en /: ${disk_gb} GB (minimo 10 GB para el update)"
  ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:)443$' \
    || warn "nada escucha en 443: los servicios parecen detenidos (lo confirmara el healthcheck)"
}

migrate_state() {
  # Secretos de la release anterior (unica copia: .vault_pass + vaults cifrados).
  [ "$FROM_REL" = "$REL" ] && return 0
  info "migrando el estado desde $(basename "$FROM_REL")"
  cp -p "$FROM_REL/.vault_pass" "$REL/.vault_pass"
  local f n=0
  for f in "$FROM_REL"/group_vars/*/vault*.yml; do
    [ -e "$f" ] || continue
    [ "$(head -c 14 "$f")" = "\$ANSIBLE_VAULT" ] || die "$f no esta cifrado: estado inconsistente"
    cp -p "$f" "$REL/group_vars/$(basename "$(dirname "$f")")/"
    n=$((n+1))
  done
  [ "$n" -ge 4 ] || die "la release anterior tiene solo $n vaults (se esperaban 5)"
}

pre_backup() {
  info "respaldo previo al update (backup.sh)"
  local out file member hdr
  out="$(run_root /opt/observer/scripts/backup.sh 2>&1)" || die "backup.sh fallo:
$out"
  printf '%s\n' "$out"
  file="$(printf '%s\n' "$out" | sed -n 's/^Backup guardado en //p' | tail -1)"
  if [ -z "$file" ] || ! run_root test -s "$file"; then die "backup.sh no dejo el archivo de respaldo"; fi
  # backup.sh hace pg_dump | gzip sin pipefail: un dump fallido deja un .gz VACIO y solo
  # avisa. Se verifica el contenido real antes de dejar que migrate toque la BD.
  member="$(run_root tar -tf "$file" | grep -E '/postgres/db-.*\.psql\.gz$' | head -1)"
  [ -n "$member" ] || die "el respaldo no trae el dump de la BD principal: no se actualiza"
  hdr="$( (run_root tar -xOf "$file" "$member" | gunzip -c | head -c 4096) 2>/dev/null || true)"
  [[ "$hdr" == *"PostgreSQL database dump"* ]] || die "el dump de la BD del respaldo esta vacio o es invalido: no se actualiza"
  BACKUP_FILE="$file"
  info "respaldo verificado: $BACKUP_FILE"
}

rollback_help() {
  hr
  cat <<EOF
  VOLVER ATRAS ('current' sigue apuntando a $(basename "$FROM_REL")):
   - Si el log NO llego a la tarea "Ejecutar Django migrate":
       bash $FROM_REL/install.sh --reapply
   - Si ya migro: restaurar la BD desde ${BACKUP_FILE:-el respaldo previo} (README, seccion
     "Actualizar") y luego:  bash $FROM_REL/install.sh --reapply
  Log: $LOG_FILE
EOF
  hr
}

prune_releases() {  # conserva la release nueva y la anterior; borra las demas
  # --force sobre la MISMA release: no hay "anterior" nueva que conservar, asi que no se
  # poda (si no, se borraria la release previa, que es la del rollback).
  [ "$(readlink -f "$REL")" = "$(readlink -f "$FROM_REL")" ] && return 0
  local d keep_new keep_old
  keep_new="$(readlink -f "$REL")"; keep_old="$(readlink -f "$FROM_REL")"
  for d in "$BASE_DIR"/releases/*/; do
    d="$(readlink -f "${d%/}")"
    if [ "$d" = "$keep_new" ] || [ "$d" = "$keep_old" ]; then continue; fi
    info "borrando release antigua $(basename "$d")"
    rm -rf "$d"
  done
}

install_update_wrapper() {
  [ -f "$REL/update.sh" ] && install -m 0700 "$REL/update.sh" "$BASE_DIR/update.sh"
  return 0
}

update_main() {
  [ -f "$REL/install.yml" ] && [ -f "$REL/VERSION" ] || die "bundle incompleto en $REL"
  setup_log
  FROM_REL="$(readlink -f "$FROM_REL")"
  local new_ver old_ver inst new_ormm bnd picked d
  new_ver="$(tr -d '[:space:]' <"$REL/VERSION")"
  old_ver="$(tr -d '[:space:]' <"$FROM_REL/VERSION" 2>/dev/null || echo '?')"
  info "update de Observer RMM: $old_ver -> $new_ver"
  preflight_update

  inst="$(installed_ormm)"; new_ormm="$(bundle_ormm)"
  [ -n "$inst" ] && [ -n "$new_ormm" ] || die "no se pudo leer la version instalada o la del bundle"
  if ver_lt "$new_ormm" "$inst" && [ "$ALLOW_DOWNGRADE" != 1 ]; then
    die "el bundle ($new_ormm) es MENOR que lo instalado ($inst): las migraciones de la BD no se
  revierten. Si de verdad quiere bajar de version use --allow-downgrade (bajo su responsabilidad)."
  fi

  # Respuestas de la instalacion (sin secretos) -> mismas variables que install.
  local saved_answers="$ANSWERS_FILE"
  ANSWERS_FILE="$ANSWERS_SAVED"; load_answers; ANSWERS_FILE="$saved_answers"
  OBS_BASE_DOMAIN="$(base_of "$OBS_API_FQDN")"
  bnd="$(bundle_agent)"
  picked="$(pick_agent_version "${OBS_AGENT_VER:-}" "$bnd")"
  if [ "$picked" != "${OBS_AGENT_VER:-}" ]; then
    info "agente ofrecido a la flota: ${OBS_AGENT_VER:-?} -> $picked (version del bundle)"
  elif ver_lt "$bnd" "$picked"; then
    warn "el bundle trae el agente $bnd, MENOR que el pin $picked: se conserva $picked"
  fi
  OBS_AGENT_VER="$picked"
  derive_pg_sizing

  migrate_state
  render_inventory "$INV"
  if [ "$FROM_REL" != "$REL" ]; then
    d="$(diff <(inv_body "$FROM_REL/inventory/produccion.yml") <(inv_body "$INV") || true)"
    if [ -n "$d" ]; then
      hr; echo "Cambios del inventario (plantilla nueva, agente o ediciones manuales previas):"
      printf '%s\n' "$d"; hr
      [ "$ASSUME_YES" = 1 ] || yes_no "Aplicar el inventario regenerado" "s" || die "update cancelado"
    fi
  fi
  if [ "$ASSUME_YES" != 1 ]; then
    yes_no "Actualizar $old_ver -> $new_ver ahora (reinicia servicios unos minutos)" "n" \
      || die "update cancelado por el usuario"
  fi

  setup_ansible
  info "healthcheck previo"
  if ! run_playbook healthcheck.yml; then
    [ "$ASSUME_YES" = 1 ] && die "el healthcheck previo fallo: no se actualiza un servidor con problemas
  (sin --yes puede confirmarlo a mano)"
    yes_no "El healthcheck previo FALLO. Actualizar igual" "n" || die "update cancelado"
  fi
  pre_backup

  info "ejecutando install.yml con $new_ver (8-15 min)"
  if ! run_playbook install.yml -e observer_frontend_build=false; then
    rollback_help; die "install.yml fallo durante el update"
  fi
  info "healthcheck"
  if ! run_playbook healthcheck.yml; then rollback_help; die "el healthcheck fallo tras el update"; fi
  [ "$(installed_ormm)" = "$new_ormm" ] || { rollback_help; die "la version instalada no quedo en $new_ormm"; }

  ln -sfn "$REL" "$BASE_DIR/current"
  save_answers
  install_update_wrapper
  prune_releases
  final_report
  info "update completo: $old_ver -> $new_ver (respaldo previo: $BACKUP_FILE)"
}

reapply_main() {
  [ -f "$REL/install.yml" ] || die "bundle incompleto en $REL"
  [ -s "$INV" ] && [ -s "$REL/.vault_pass" ] \
    || die "esta release no tiene estado (inventario/.vault_pass): no fue instalada ni actualizada"
  setup_log
  require_sudo
  setup_ansible
  info "re-aplicando install.yml con $(cat "$REL/VERSION")"
  run_playbook install.yml -e observer_frontend_build=false || die "install.yml fallo (ver $LOG_FILE)"
  run_playbook healthcheck.yml || warn "el healthcheck reporto fallas (ver arriba)"
  ln -sfn "$REL" "$BASE_DIR/current"
  install_update_wrapper
  final_report
}

main_bundle() {
  [ -f "$REL/install.yml" ] && [ -f "$REL/VERSION" ] || die "bundle incompleto en $REL"
  setup_log
  if [ "$VERIFY_ONLY" = 1 ]; then
    [ -s "$INV" ] || die "no hay instalacion previa de este bundle ($INV)"
    do_verify; exit 0
  fi
  preflight
  check_egress
  collect_answers
  derive_pg_sizing
  show_summary_and_confirm
  setup_ansible
  write_secrets_and_inventory

  if [ "$OBS_TIMEZONE" != "$(timedatectl show -p Timezone --value 2>/dev/null)" ]; then
    info "fijando la zona horaria del sistema: $OBS_TIMEZONE"
    run_root timedatectl set-timezone "$OBS_TIMEZONE"
  fi

  info "ejecutando install.yml (30-40 min; el certificado wildcard solo tarda ~11 min)"
  run_playbook install.yml -e observer_frontend_build=false \
    || die "install.yml fallo. Revise $LOG_FILE; corregido el problema puede re-ejecutar:
  cd $REL && ANSIBLE_CONFIG=ansible.cfg .venv/bin/ansible-playbook install.yml -i $INV -e observer_frontend_build=false"

  info "healthcheck"
  run_playbook healthcheck.yml || warn "el healthcheck reporto fallas (ver arriba)"
  install_update_wrapper
  final_report

  if is_yes "$OBS_REBOOT"; then
    info "reiniciando en 15 s para fijar HugePages (Ctrl+C para cancelar)."
    info "Tras el reinicio verifique con:  bash $REL/install.sh --verify"
    sleep 15
    run_root systemctl reboot
  elif is_yes "$OBS_HUGEPAGES"; then
    warn "HugePages queda solo en runtime hasta el proximo reinicio: reinicie cuando pueda y luego
  ejecute  bash $REL/install.sh --verify"
  fi
}

# ----------------------------------------------------------------------------- entrada
# Modo libreria para las pruebas (scripts/installer/test-install-sh.sh): solo define funciones.
# shellcheck disable=SC2317  # el exit es el fallback cuando no se ejecuta via source
if [ "${OBS_INSTALLER_LIB_ONLY:-0}" = 1 ]; then return 0 2>/dev/null || exit 0; fi
IN_BUNDLE=0
[ -f "$SCRIPT_DIR/install.yml" ] && [ -f "$SCRIPT_DIR/VERSION" ] && IN_BUNDLE=1
if [ "$UPDATE_MODE" = 1 ] && [ -z "$FROM_REL" ]; then
  bootstrap_update                       # baja la version nueva y le pasa el control
elif [ "$UPDATE_MODE" = 1 ]; then
  [ "$IN_BUNDLE" = 1 ] || die "--from solo se usa dentro de una release extraida"
  update_main
elif [ "$REAPPLY" = 1 ]; then
  [ "$IN_BUNDLE" = 1 ] || die "--reapply se ejecuta con el install.sh de una release: $BASE_DIR/releases/<ver>/install.sh"
  reapply_main
elif [ "$IN_BUNDLE" = 1 ] && [ -z "$LOCAL_BUNDLE" ]; then
  main_bundle
else
  bootstrap
fi
