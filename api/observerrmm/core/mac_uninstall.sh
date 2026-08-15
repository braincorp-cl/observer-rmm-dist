#!/bin/bash

agentConf='/etc/observeragent'

# ConfValue lee un valor de tipo string del JSON que escribe viper.
#
# Límite conocido y medido: un valor con comillas o barras invertidas escapadas
# sale truncado en la primera. No importa para lo que leemos acá — `token` es la
# clave de DRF (40 hex), `agentid` es alfanumérico y `baseurl` es una URL — y no
# vale la pena escribir un parser JSON en bash.
ConfValue() {
    grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "${agentConf}" 2>/dev/null |
        head -1 | sed 's/.*:[[:space:]]*"//; s/"$//'
}

JsonEscape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

# NotifyUninstall avisa al servidor ANTES de destruir nada.
#
# Sin esto la desinstalación local es invisible para la consola: este script no
# habla con el servidor, así que la fila del agente sobrevive y el Mac queda
# para siempre como un Offline que ya no existe. El servidor levanta la alerta
# (correo + campanita), deja el registro de auditoría y programa el borrado del
# agente y del nodo Mesh.
#
# Va PRIMERO, antes de tocar el mesh y antes de borrar ${agentConf}, que es de
# donde salen la URL y el token.
#
# Nunca puede hacer fallar la desinstalación: sin red o con el servidor caído se
# calla y sigue. Lo que se pierde es el aviso, no la desinstalación.
NotifyUninstall() {
    [ -f "${agentConf}" ] || return 0

    # ⚠️ `baseurl` y NO `apiurl`: en el config del agente `baseurl` es la URL
    # completa del backend y `apiurl` es sólo el host, que se usa para NATS.
    local baseurl agentid agenttoken actor sudouser loginuser lanips payload
    baseurl=$(ConfValue baseurl)
    agentid=$(ConfValue agentid)
    agenttoken=$(ConfValue token)
    [ -n "${baseurl}" ] && [ -n "${agenttoken}" ] || return 0

    # `SUDO_USER` es lo único que distingue una persona de "root" cuando el
    # comando se lanzó con sudo. `logname` lee el dueño de la sesión de login.
    # Ninguno es prueba: quien tiene root puede exportar SUDO_USER con el nombre
    # que quiera. Sirve para saber qué pasó, no para acusar a nadie.
    sudouser="${SUDO_USER:-}"
    loginuser=$(logname 2>/dev/null || true)
    [ -n "${loginuser}" ] || loginuser=$(who am i 2>/dev/null | awk '{print $1}')
    actor="${sudouser}"
    [ -n "${actor}" ] || actor="${loginuser}"
    [ -n "${actor}" ] || actor=$(id -un 2>/dev/null || echo unknown)

    # macOS no trae `ip`; se usa ifconfig. Si acá no sale nada, el servidor cae
    # a la última IP que reportó el agente.
    lanips=$(ifconfig 2>/dev/null |
        awk '/inet /&&$2!="127.0.0.1"{print $2}' | paste -sd, - 2>/dev/null)

    payload=$(
        printf '{"agent_id":"%s","actor":"%s","sudo_user":"%s","login_user":"%s","lan_ips":"%s","local_time":"%s","source":"script-macos"}' \
            "$(JsonEscape "${agentid}")" \
            "$(JsonEscape "${actor}")" \
            "$(JsonEscape "${sudouser}")" \
            "$(JsonEscape "${loginuser}")" \
            "$(JsonEscape "${lanips}")" \
            "$(JsonEscape "$(date +%Y-%m-%dT%H:%M:%S%z 2>/dev/null || date)")"
    )

    # Timeout corto a propósito: el aviso es lo accesorio, la desinstalación es
    # lo que se pidió. Nunca colgado esperando un servidor que no contesta.
    curl -s -k --max-time 15 -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Token ${agenttoken}" \
        --data "${payload}" \
        "${baseurl}/api/v3/uninstalled/" >/dev/null 2>&1 || true

    return 0
}

NotifyUninstall

# `--no-embedded=1` es OBLIGATORIO y va DESPUÉS del comando. El binario que
# MeshCentral entrega para instalar trae un instalador JS anexado que se dispara
# ante CUALQUIER argumento, también ante `-fulluninstall`: en Linux, medido en
# HP-ProOne-400 el 2026-07-29, abre un diálogo en el escritorio y se queda
# esperando un clic que nadie va a dar, colgando el uninstall entero sin
# desinstalar nada. Este script es el que corre la CONSOLA al borrar un Mac, así
# que un cuelgue acá deja el borrado a medias desde la propia web.
#
# El `perl -e alarm` es el cinturón: macOS no trae `timeout`. Si aparece una
# variante que igual quiera interactuar, esto debe FALLAR, nunca quedarse
# colgado. Mismo patrón que RemoveMesh en agent_macos.sh.
if [ -f /usr/local/mesh_services/meshagent/meshagent ]; then
  perl -e 'alarm shift; exec @ARGV' 120 /usr/local/mesh_services/meshagent/meshagent -fulluninstall --no-embedded=1
fi

if [ -f /opt/observermesh/meshagent ]; then
  perl -e 'alarm shift; exec @ARGV' 120 /opt/observermesh/meshagent -fulluninstall --no-embedded=1
fi

launchctl bootout system /Library/LaunchDaemons/observeragent.plist

# Feature 030 · T016: el ayudante que saca la foto y la captura es un LaunchAgent
# que vive en la sesion de quien tenga la consola abierta, no en el dominio
# system, y ademas es un bundle .app REGISTRADO en LaunchServices. Hay que
# deshacer las dos cosas.
#
# El bootout va ANTES de borrar el plist: al reves queda un trabajo registrado
# apuntando a un archivo que ya no existe, y launchd lo arrastra hasta que la
# persona cierre sesion.
#
# Y el `lsregister -u` no es opcional: el registro es lo que permite que
# `tccutil` nombre al ayudante, y un registro huerfano apuntando a un bundle
# borrado ensucia LaunchServices hasta que se reconstruya la base.
#
# Los dos comandos fallan si nunca se cargo o nunca se registro -- una
# instalacion que jamas saco una foto -- y eso no es un error: de ahi el `|| true`.
CONSOLE_UID=$(stat -f%u /dev/console 2>/dev/null)
if [ -n "${CONSOLE_UID}" ] && [ "${CONSOLE_UID}" != "0" ]; then
  launchctl bootout "gui/${CONSOLE_UID}/cl.observer.agent.captura" || true
fi
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
if [ -x "${LSREGISTER}" ]; then
  "${LSREGISTER}" -u /opt/observeragent/ObserverCaptura.app || true
fi

rm -rf /usr/local/mesh_services
rm -rf /opt/observermesh
rm -f /etc/observeragent
rm -rf /opt/observeragent
rm -f /Library/LaunchDaemons/observeragent.plist
rm -f /Library/LaunchAgents/cl.observer.agent.captura.plist
rm -f /Library/LaunchAgents/meshagent-agent.plist
