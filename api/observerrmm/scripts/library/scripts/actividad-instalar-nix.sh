#!/bin/bash
# Observer Actividad - instalador del muestreador para macOS y Linux (feature 048).
#
# Equivalente de actividad-instalar.ps1. El muestreador corre DENTRO de la sesion
# grafica del usuario (un daemon de root no ve la ventana activa):
#   macOS: LaunchAgent /Library/LaunchAgents/cl.observer.actividad.plist, KeepAlive
#          (si lo matan, launchd lo relanza).
#   Linux: /etc/xdg/autostart/observer-actividad.desktop (arranca al iniciar sesion).
#
# Que se puede medir en cada plataforma, y que NO:
#   macOS: proceso en primer plano (lsappinfo) e inactividad (ioreg) sin permisos.
#          El TITULO de ventana pide Accesibilidad y la CAPTURA pide Grabacion de
#          pantalla (TCC): sin un perfil PPPC por MDM el usuario ve el dialogo de
#          permiso o la captura sale solo con el fondo de pantalla.
#   Linux: solo sesiones X11 (xdotool, xprintidle, ImageMagick `import`). En Wayland
#          no hay API generica para la ventana activa: el muestreador lo anota y el
#          reporte lo muestra como "no soportado".
#
# Datos por usuario (el recolector los lee como root):
#   macOS: ~/Library/Application Support/ObserverActividad/{datos,capturas}
#   Linux: ~/.local/share/observer-actividad/{datos,capturas}
#
# Uso:
#   actividad-instalar-nix.sh estado
#   actividad-instalar-nix.sh instalar [--intervalo 60] [--inactivo-seg 120]
#       [--titulos on|off] [--capturas on|off] [--cada-captura 10]
#       [--retencion-capturas 7] [--retencion-datos 35] [--aviso "texto"]
#       [--sin-aviso] [--deps]
#   actividad-instalar-nix.sh desinstalar [--borrar-datos]
#
# --deps (Linux): instala xdotool, xprintidle e ImageMagick con apt o dnf.

set -u
export LC_ALL=C

MODO="${1:-estado}"
[ $# -gt 0 ] && shift

INTERVALO=60
INACTIVO_SEG=120
TITULOS=on
CAPTURAS=on
CADA_CAPTURA=10
RET_CAPTURAS=7
RET_DATOS=35
AVISO=""
SIN_AVISO=0
DEPS=0
BORRAR_DATOS=0

numero() {
    case "$2" in
        ''|*[!0-9]*) echo "ERROR: $1 espera un numero, llego '$2'" >&2; exit 2 ;;
    esac
}

while [ $# -gt 0 ]; do
    case "$1" in
        --intervalo) numero "$1" "${2:-}"; INTERVALO="$2"; shift 2 ;;
        --inactivo-seg) numero "$1" "${2:-}"; INACTIVO_SEG="$2"; shift 2 ;;
        --titulos) TITULOS="${2:-on}"; shift 2 ;;
        --capturas) CAPTURAS="${2:-on}"; shift 2 ;;
        --cada-captura) numero "$1" "${2:-}"; CADA_CAPTURA="$2"; shift 2 ;;
        --retencion-capturas) numero "$1" "${2:-}"; RET_CAPTURAS="$2"; shift 2 ;;
        --retencion-datos) numero "$1" "${2:-}"; RET_DATOS="$2"; shift 2 ;;
        --aviso) AVISO="${2:-}"; shift 2 ;;
        --sin-aviso) SIN_AVISO=1; shift ;;
        --deps) DEPS=1; shift ;;
        --borrar-datos) BORRAR_DATOS=1; shift ;;
        *) echo "ERROR: argumento desconocido: $1" >&2; exit 2 ;;
    esac
done

[ "$INTERVALO" -lt 15 ] && INTERVALO=15
[ "$CADA_CAPTURA" -lt 1 ] && CADA_CAPTURA=1

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: hay que correrlo como root." >&2
    exit 1
fi

SO="$(uname -s)"
case "$SO" in
    Darwin)
        BASE="/Library/Application Support/ObserverActividad"
        PLIST="/Library/LaunchAgents/cl.observer.actividad.plist"
        REL_DATOS="Library/Application Support/ObserverActividad"
        ;;
    Linux)
        BASE="/opt/observer-actividad"
        AUTOSTART="/etc/xdg/autostart/observer-actividad.desktop"
        REL_DATOS=".local/share/observer-actividad"
        ;;
    *)
        echo "ERROR: sistema no soportado: $SO" >&2
        exit 1
        ;;
esac

# Aviso por defecto. Este archivo debe ser ASCII (gate de la biblioteca), asi que
# los acentos se escriben como secuencias octales UTF-8 y printf las expande.
aviso_defecto() {
    local detalle=""
    [ "$TITULOS" = on ] && detalle=", el t\303\255tulo de la ventana activa"
    [ "$CAPTURAS" = on ] && detalle="$detalle y capturas de pantalla peri\303\263dicas"
    printf "Este equipo es de propiedad de su empleador y registra su uso: qu\303\251 aplicaci\303\263n est\303\241 en primer plano, el tiempo activo e inactivo${detalle}. La informaci\303\263n se usa para medir la productividad seg\303\272n la pol\303\255tica de uso aceptable de su organizaci\303\263n. Si tiene dudas, consulte con su jefatura o con el \303\241rea de TI."
}

escribir_muestreador() {
    cat > "$BASE/muestreo.sh" <<'MUESTREO'
#!/bin/sh
# Observer Actividad - muestreador macOS/Linux (feature 048). Lo instala
# actividad-instalar-nix.sh. Una linea TSV por muestra:
#   ts <TAB> usuario <TAB> proceso <TAB> activo(0/1) <TAB> intervalo(s) <TAB> titulo
# Eventos: "#inicio" (titulo = boot=<epoch>;sesion=<epoch>) y "#nota" (texto libre).
export LC_ALL=C
SO="$(uname -s)"
if [ "$SO" = Darwin ]; then
    BASE="/Library/Application Support/ObserverActividad"
    RAIZ="$HOME/Library/Application Support/ObserverActividad"
else
    BASE="/opt/observer-actividad"
    RAIZ="${XDG_DATA_HOME:-$HOME/.local/share}/observer-actividad"
fi
DATOS="$RAIZ/datos"
CAPS="$RAIZ/capturas"
mkdir -p "$DATOS" "$CAPS" || exit 1
USUARIO="$(id -un)"

# Instancia unica por usuario.
LOCK="$RAIZ/.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    OTRO="$(cat "$LOCK/pid" 2>/dev/null)"
    if [ -n "$OTRO" ] && kill -0 "$OTRO" 2>/dev/null; then exit 0; fi
fi
mkdir -p "$LOCK"; echo $$ > "$LOCK/pid"

leer_config() {
    INTERVALO=60; INACTIVO_SEG=120; TITULOS=0; CAPTURAS=0; CADA_CAPTURA_MIN=10
    ANCHO_CAPTURA=1280; CALIDAD_CAPTURA=40; RETENCION_CAPTURAS_DIAS=7; RETENCION_DATOS_DIAS=35
    [ -r "$BASE/config.env" ] && . "$BASE/config.env"
}

linea() {
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date +%Y-%m-%dT%H:%M:%S)" "$USUARIO" "$1" "$2" "$3" "$4" \
        >> "$DATOS/$(date +%Y-%m-%d).tsv"
}

limpio() { tr '\t\r\n' '   ' | cut -c1-200; }

# etime de ps ([[dd-]hh:]mm:ss) a segundos.
etime_seg() {
    echo "$1" | awk '{ n = split($1, d, "-"); dias = (n == 2) ? d[1] : 0; t = (n == 2) ? d[2] : d[1];
        m = split(t, p, ":"); s = 0; for (k = 1; k <= m; k++) s = s * 60 + p[k]; print dias * 86400 + s }'
}

leer_config

if [ "$SO" = Darwin ]; then
    BOOT="$(sysctl -n kern.boottime | sed 's/.*sec = \([0-9]*\).*/\1/')"
    PID_SESION="$(pgrep -u "$(id -u)" -x Finder | head -1)"
else
    BOOT="$(awk '/^btime/ {print $2}' /proc/stat)"
    PID_SESION="$(ps -o sess= -p $$ | tr -d ' ')"
fi
SESION=0
if [ -n "$PID_SESION" ]; then
    ET="$(ps -o etime= -p "$PID_SESION" | tr -d ' ')"
    [ -n "$ET" ] && SESION=$(( $(date +%s) - $(etime_seg "$ET") ))
fi
linea "#inicio" 0 0 "boot=${BOOT:-0};sesion=$SESION"

# Aviso: una vez por usuario, hasta que lo acepte.
if [ -s "$BASE/aviso.txt" ] && [ ! -f "$RAIZ/aviso-aceptado.txt" ]; then
    OACT_AVISO="$(cat "$BASE/aviso.txt")"; export OACT_AVISO
    if [ "$SO" = Darwin ]; then
        osascript -e 'display dialog (system attribute "OACT_AVISO") buttons {"Aceptar"} default button 1 with title "Observer RMM" with icon note' >/dev/null 2>&1
    elif command -v zenity >/dev/null 2>&1; then
        zenity --info --title="Observer RMM" --text="$OACT_AVISO" >/dev/null 2>&1
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --title "Observer RMM" --msgbox "$OACT_AVISO" >/dev/null 2>&1
    elif command -v xmessage >/dev/null 2>&1; then
        xmessage -center "$OACT_AVISO" >/dev/null 2>&1
    fi
    date +%Y-%m-%dT%H:%M:%S > "$RAIZ/aviso-aceptado.txt"
fi

if [ "$SO" = Linux ] && [ "${XDG_SESSION_TYPE:-}" = wayland ]; then
    # Sin API generica de ventana activa en Wayland: se deja constancia y se espera.
    while true; do linea "#nota" 0 0 "wayland: sesion no soportada"; sleep 3600; done
fi
if [ "$SO" = Linux ] && ! command -v xdotool >/dev/null 2>&1; then
    while true; do linea "#nota" 0 0 "falta xdotool (instalar con --deps)"; sleep 3600; done
fi

VUELTA=0
ULTIMA_CAPTURA=0
ULTIMA_LIMPIEZA=0
while true; do
    T0="$(date +%s)"
    [ $((VUELTA % 10)) -eq 0 ] && leer_config
    VUELTA=$((VUELTA + 1))

    PROC="(escritorio)"; TITULO=""; IDLE=0; BLOQ=0
    if [ "$SO" = Darwin ]; then
        ASN="$(lsappinfo front 2>/dev/null)"
        if [ -n "$ASN" ] && [ "$ASN" != "[ NULL ]" ]; then
            RUTA="$(lsappinfo info -only executablepath "$ASN" 2>/dev/null | sed 's/.*"=//; s/"//g')"
            [ -n "$RUTA" ] && PROC="$(basename "$RUTA" | tr 'A-Z' 'a-z')"
        fi
        IDLE="$(ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF / 1000000000); exit}')"
        if [ "$TITULOS" = 1 ]; then
            TITULO="$(osascript -e 'tell application "System Events" to tell (first process whose frontmost is true) to get name of front window' 2>/dev/null | limpio)"
        fi
    else
        WID="$(xdotool getactivewindow 2>/dev/null)"
        if [ -n "$WID" ]; then
            PID_V="$(xdotool getwindowpid "$WID" 2>/dev/null)"
            [ -n "$PID_V" ] && [ -r "/proc/$PID_V/comm" ] && PROC="$(tr 'A-Z' 'a-z' < "/proc/$PID_V/comm")"
            [ "$TITULOS" = 1 ] && TITULO="$(xdotool getwindowname "$WID" 2>/dev/null | limpio)"
        fi
        if command -v xprintidle >/dev/null 2>&1; then
            IDLE=$(( $(xprintidle 2>/dev/null || echo 0) / 1000 ))
        fi
        if [ -n "${XDG_SESSION_ID:-}" ] && [ "$(loginctl show-session "$XDG_SESSION_ID" -p LockedHint --value 2>/dev/null)" = yes ]; then
            BLOQ=1
        fi
    fi
    ACTIVO=0
    [ "${IDLE:-0}" -lt "$INACTIVO_SEG" ] && [ "$BLOQ" = 0 ] && [ "$PROC" != "(escritorio)" ] && ACTIVO=1
    linea "$PROC" "$ACTIVO" "$INTERVALO" "$TITULO"

    if [ "$CAPTURAS" = 1 ] && [ "$ACTIVO" = 1 ] && [ $((T0 - ULTIMA_CAPTURA)) -ge $((CADA_CAPTURA_MIN * 60)) ]; then
        DIA="$CAPS/$(date +%Y-%m-%d)"; mkdir -p "$DIA"
        F="$DIA/$(date +%H%M%S).jpg"
        if [ "$SO" = Darwin ]; then
            screencapture -x -t jpg "$F" 2>/dev/null && sips -Z "$ANCHO_CAPTURA" -s formatOptions "$CALIDAD_CAPTURA" "$F" >/dev/null 2>&1
        elif command -v import >/dev/null 2>&1; then
            import -silent -window root -resize "${ANCHO_CAPTURA}x" -quality "$CALIDAD_CAPTURA" "$F" 2>/dev/null
        fi
        ULTIMA_CAPTURA="$T0"
    fi
    if [ $((T0 - ULTIMA_LIMPIEZA)) -ge 3600 ]; then
        find "$CAPS" -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENCION_CAPTURAS_DIAS" -exec rm -rf {} + 2>/dev/null
        find "$DATOS" -name '*.tsv' -type f -mtime +"$RETENCION_DATOS_DIAS" -exec rm -f {} + 2>/dev/null
        ULTIMA_LIMPIEZA="$T0"
    fi

    RESTO=$(( INTERVALO - ($(date +%s) - T0) ))
    [ "$RESTO" -gt 0 ] && sleep "$RESTO"
done
MUESTREO
    chmod 0755 "$BASE/muestreo.sh"
}

flag01() { [ "$1" = on ] && echo 1 || echo 0; }

usuario_consola_mac() {
    stat -f %u /dev/console 2>/dev/null
}

homes() {
    # Homes de usuarios reales: lo que haya bajo /Users o /home.
    for h in /Users/* /home/*; do
        [ -d "$h/$REL_DATOS" ] && echo "$h"
    done
}

estado() {
    echo "== Observer Actividad: estado ($SO) =="
    if [ ! -f "$BASE/config.env" ]; then
        echo "No instalado (no existe $BASE/config.env)."
        return
    fi
    echo "Configuracion:"; sed 's/^/  /' "$BASE/config.env"
    if [ "$SO" = Darwin ]; then
        [ -f "$PLIST" ] && echo "LaunchAgent: presente" || echo "LaunchAgent: NO EXISTE"
        echo "Permisos TCC: titulo=Accesibilidad, captura=Grabacion de pantalla (perfil PPPC por MDM)."
    else
        [ -f "$AUTOSTART" ] && echo "Autostart: presente" || echo "Autostart: NO EXISTE"
        for b in xdotool xprintidle import; do
            command -v "$b" >/dev/null 2>&1 && echo "  $b: ok" || echo "  $b: FALTA"
        done
    fi
    echo "Muestreadores en ejecucion: $(pgrep -f "$BASE/muestreo.sh" | wc -l | tr -d ' ')"
    homes | while read -r h; do
        ultimo="$(ls -1 "$h/$REL_DATOS/datos/"*.tsv 2>/dev/null | tail -1)"
        ncap="$(find "$h/$REL_DATOS/capturas" -name '*.jpg' -type f 2>/dev/null | wc -l | tr -d ' ')"
        if [ -n "$ultimo" ]; then
            echo "$h: ultimo archivo $(basename "$ultimo") ($(du -k "$ultimo" | cut -f1) KB); capturas guardadas: $ncap"
            tail -1 "$ultimo" | grep '#nota' | sed 's/^/  nota: /'
        else
            echo "$h: sin datos todavia; capturas guardadas: $ncap"
        fi
    done
}

instalar_deps() {
    if command -v apt-get >/dev/null 2>&1; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y xdotool xprintidle imagemagick
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y xdotool xprintidle ImageMagick
    else
        echo "AVISO: sin apt ni dnf; instalar a mano xdotool, xprintidle e ImageMagick." >&2
    fi
}

case "$MODO" in
    estado)
        estado
        ;;
    instalar)
        mkdir -p "$BASE" || exit 1
        chown root "$BASE"; chmod 0755 "$BASE"
        escribir_muestreador
        {
            echo "# Observer Actividad - configuracion (la regenera actividad-instalar-nix.sh)"
            echo "INTERVALO=$INTERVALO"
            echo "INACTIVO_SEG=$INACTIVO_SEG"
            echo "TITULOS=$(flag01 "$TITULOS")"
            echo "CAPTURAS=$(flag01 "$CAPTURAS")"
            echo "CADA_CAPTURA_MIN=$CADA_CAPTURA"
            echo "ANCHO_CAPTURA=1280"
            echo "CALIDAD_CAPTURA=40"
            echo "RETENCION_CAPTURAS_DIAS=$RET_CAPTURAS"
            echo "RETENCION_DATOS_DIAS=$RET_DATOS"
        } > "$BASE/config.env"
        chmod 0644 "$BASE/config.env"
        if [ "$SIN_AVISO" = 1 ]; then
            : > "$BASE/aviso.txt"
        elif [ -n "$AVISO" ]; then
            printf '%s' "$AVISO" > "$BASE/aviso.txt"
        else
            aviso_defecto > "$BASE/aviso.txt"
        fi
        chmod 0644 "$BASE/aviso.txt"

        if [ "$SO" = Darwin ]; then
            cat > "$PLIST" <<PLISTXML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>cl.observer.actividad</string>
    <key>ProgramArguments</key>
    <array><string>/bin/sh</string><string>$BASE/muestreo.sh</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>60</integer>
    <key>ProcessType</key><string>Background</string>
    <key>LimitLoadToSessionType</key><string>Aqua</string>
</dict>
</plist>
PLISTXML
            chown root:wheel "$PLIST"; chmod 0644 "$PLIST"
            uid="$(usuario_consola_mac)"
            if [ -n "$uid" ] && [ "$uid" -gt 0 ]; then
                launchctl bootout "gui/$uid" "$PLIST" >/dev/null 2>&1
                launchctl bootstrap "gui/$uid" "$PLIST" && echo "Arrancado en la sesion del usuario uid $uid."
            fi
        else
            [ "$DEPS" = 1 ] && instalar_deps
            mkdir -p "$(dirname "$AUTOSTART")"
            cat > "$AUTOSTART" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Observer Actividad
Exec=$BASE/muestreo.sh
NoDisplay=true
X-GNOME-Autostart-enabled=true
DESKTOP
            chmod 0644 "$AUTOSTART"
            echo "En Linux arranca en el proximo inicio de sesion grafico de cada usuario."
        fi
        echo "Observer Actividad instalado/actualizado."
        estado
        ;;
    desinstalar)
        if [ "$SO" = Darwin ]; then
            uid="$(usuario_consola_mac)"
            [ -n "$uid" ] && [ "$uid" -gt 0 ] && launchctl bootout "gui/$uid" "$PLIST" >/dev/null 2>&1
            rm -f "$PLIST"
        else
            rm -f "$AUTOSTART"
        fi
        pkill -f "$BASE/muestreo.sh" 2>/dev/null
        if [ "$BORRAR_DATOS" = 1 ]; then
            homes | while read -r h; do rm -rf "${h:?}/$REL_DATOS" && echo "Datos borrados: $h/$REL_DATOS"; done
        else
            echo "Datos de los usuarios conservados (usar --borrar-datos para borrarlos)."
        fi
        rm -rf "$BASE"
        echo "Observer Actividad desinstalado."
        ;;
    *)
        echo "ERROR: modo desconocido '$MODO' (estado | instalar | desinstalar)" >&2
        exit 2
        ;;
esac
