#!/usr/bin/env bash

if [ $EUID -ne 0 ]; then
    echo "ERROR: Must be run as root"
    exit 1
fi

HAS_SYSTEMD=$(ps --no-headers -o comm 1)
if [ "${HAS_SYSTEMD}" != 'systemd' ]; then
    echo "This install script only supports systemd"
    echo "Please install systemd or manually create the service using your systems's service manager"
    exit 1
fi

if [[ $DISPLAY ]]; then
    # A set DISPLAY only matters to the mesh agent installer, which would try to
    # launch in interactive/GUI mode instead of installing as a headless service.
    # The mesh calls below already force DISPLAY=bar XAUTHORITY=foo, so we can
    # simply clear these here and continue: a graphical workstation is fine to
    # install on. (Remote control via the mesh agent still works afterwards.)
    echo "Display detected; clearing DISPLAY/XAUTHORITY for a headless install."
    unset DISPLAY XAUTHORITY
fi

DEBUG=0
INSECURE=0
NOMESH=0

agentDL='agentDLChange'
meshDL='meshDLChange'

apiURL='apiURLChange'
token='tokenChange'
clientID='clientIDChange'
siteID='siteIDChange'
agentType='agentTypeChange'
proxy=''

agentBinPath='/usr/local/bin'
binName='observeragent'
agentBin="${agentBinPath}/${binName}"
agentConf='/etc/observeragent'
agentSvcName='observeragent.service'
agentSysD="/etc/systemd/system/${agentSvcName}"
agentDir='/opt/observeragent'
meshDir='/opt/observermesh'
meshSystemBin="${meshDir}/meshagent"
meshSvcName='meshagent.service'
meshSysD="/lib/systemd/system/${meshSvcName}"

deb=(ubuntu debian raspbian kali linuxmint)
rhe=(fedora rocky centos rhel amzn arch opensuse)

set_locale_deb() {
    locale-gen "en_US.UTF-8"
    localectl set-locale LANG=en_US.UTF-8
    . /etc/default/locale
}

set_locale_rhel() {
    localedef -c -i en_US -f UTF-8 en_US.UTF-8 >/dev/null 2>&1
    localectl set-locale LANG=en_US.UTF-8
    . /etc/locale.conf
}

RemoveOldAgent() {
    if [ -f "${agentSysD}" ]; then
        systemctl disable ${agentSvcName}
        systemctl stop ${agentSvcName}
        rm -f "${agentSysD}"
        systemctl daemon-reload
    fi

    if [ -f "${agentConf}" ]; then
        rm -f "${agentConf}"
    fi

    if [ -f "${agentBin}" ]; then
        rm -f "${agentBin}"
    fi

    if [ -d "${agentDir}" ]; then
        rm -rf "${agentDir}"
    fi
}

InstallMesh() {
    if [ -f /etc/os-release ]; then
        distroID=$(
            . /etc/os-release
            echo $ID
        )
        distroIDLIKE=$(
            . /etc/os-release
            echo $ID_LIKE
        )
        if [[ " ${deb[*]} " =~ " ${distroID} " ]]; then
            set_locale_deb
        elif [[ " ${deb[*]} " =~ " ${distroIDLIKE} " ]]; then
            set_locale_deb
        elif [[ " ${rhe[*]} " =~ " ${distroID} " ]]; then
            set_locale_rhel
        else
            set_locale_rhel
        fi
    fi

    meshTmpDir='/root/meshtemp'
    mkdir -p $meshTmpDir

    meshTmpBin="${meshTmpDir}/meshagent"
    wget --no-check-certificate -q -O ${meshTmpBin} "${meshDL}"
    chmod +x ${meshTmpBin}
    mkdir -p ${meshDir}
    env LC_ALL=en_US.UTF-8 LANGUAGE=en_US XAUTHORITY=foo DISPLAY=bar ${meshTmpBin} -install --installPath=${meshDir}
    sleep 1
    rm -rf ${meshTmpDir}
}

RemoveMesh() {
    if [ -f "${meshSystemBin}" ]; then
        # -fulluninstall (no -uninstall): el agente remueve su PROPIO nodo en el
        # server MeshCentral al desconectarse, no sólo el servicio local. Evita
        # el race del borrado de un agente vivo desde la UI, donde el keepalive
        # del meshagent re-agrega el nodo justo después del removedevices del RMM
        # y lo deja huérfano. En reinstalación, además limpia el nodo viejo.
        #
        # `--no-embedded=1` es OBLIGATORIO y va DESPUÉS del comando. El binario que
        # MeshCentral entrega para instalar trae un instalador JS anexado que se
        # dispara ante CUALQUIER argumento, también ante `-fulluninstall`. Sin la
        # bandera, medido en HP-ProOne-400 el 2026-07-29: abre un diálogo `zenity`
        # en el escritorio de la persona ("MeshCentral Agent Setup", `--timeout=99999`)
        # y se queda bloqueado esperando un clic que nadie va a dar. Como esta
        # función corre ANTES que RemoveOldAgent, el uninstall entero se cuelga y
        # **no se desinstala nada**. Con la bandera: 6 s, sin diálogo, y el mesh
        # efectivamente borrado. El `timeout` es el cinturón por si aparece otra
        # variante que igual quiera interactuar: nunca dejar colgado un uninstall.
        env XAUTHORITY=foo DISPLAY=bar timeout 120 ${meshSystemBin} -fulluninstall --no-embedded=1
        sleep 1
    fi

    if [ -f "${meshSysD}" ]; then
        systemctl stop ${meshSvcName} >/dev/null 2>&1
        systemctl disable ${meshSvcName} >/dev/null 2>&1
        rm -f ${meshSysD}
    fi

    rm -rf ${meshDir}
    systemctl daemon-reload
}

# ValidateMeshNodeID descarta cualquier respuesta que no sea un identificador.
#
# MESH_NODE_ID se concatena más abajo en INSTALL_CMD, que termina pasando por
# `eval`: si lo que vuelve no es un id, el shell EJECUTA esas líneas. No es
# hipotético, pasó en terreno. El binario que MeshCentral entrega para instalar
# (`/meshagents?id=<meshid>&meshinstall=<arch>`) no es el agente sino un
# AUTO-INSTALADOR, con un script JS anexado que corre ante cualquier argumento;
# `meshagent -nodeid` devolvía entonces la salida completa de una reinstalación,
# y `eval` la ejecutó línea por línea. El equipo quedó con el servicio del mesh
# caído y registrado con su MAC en vez de un node id.
#
# Desde v2.14.7 el agente pide el id con `--no-embedded=1` y ya no devuelve
# basura; esta validación cubre a los agentes anteriores —que se siguen bajando
# desde el CDN mientras no cambie LATEST_AGENT_VER— y a cualquier salida nueva
# que no hayamos previsto.
#
# Quedarse sin id no impide instalar: el agente lo sincroniza solo en el primer
# ciclo (SyncMeshNodeID). Instalar con un id falso, en cambio, deja "Tomar
# control" roto y sin aviso.
ValidateMeshNodeID() {
    # La expresión va en una variable y SIN comillas en el [[ =~ ]]: es la única
    # forma en que bash la trata como patrón y no vuelve a expandirla.
    local meshNodeIdRe='^[0-9A-Fa-f]{64,}$'

    if [[ "${MESH_NODE_ID}" =~ ${meshNodeIdRe} ]]; then
        return 0
    fi

    echo "WARNING: el mesh node id recibido no tiene forma de identificador."
    echo "         Se continúa sin él; el agente lo sincronizará al conectarse."
    MESH_NODE_ID=""
}

Uninstall() {
    RemoveMesh
    RemoveOldAgent
}

if [ $# -ne 0 ] && [[ $1 =~ ^(uninstall|-uninstall|--uninstall)$ ]]; then
    Uninstall
    # Remove the current script
    rm "$0"
    exit 0
fi

while [[ "$#" -gt 0 ]]; do
    case $1 in
    -debug | --debug | debug) DEBUG=1 ;;
    -insecure | --insecure | insecure) INSECURE=1 ;;
    -nomesh | --nomesh | nomesh) NOMESH=1 ;;
    *)
        echo "ERROR: Unknown parameter: $1"
        exit 1
        ;;
    esac
    shift
done

RemoveOldAgent

echo "Downloading observer agent..."
wget -q -O ${agentBin} "${agentDL}"
if [ $? -ne 0 ]; then
    echo "ERROR: Unable to download observer agent"
    exit 1
fi
chmod +x ${agentBin}

MESH_NODE_ID=""

if [[ $NOMESH -eq 1 ]]; then
    echo "Skipping mesh install"
else
    if [ -f "${meshSystemBin}" ]; then
        RemoveMesh
    fi
    echo "Downloading and installing mesh agent..."
    InstallMesh
    sleep 2
    echo "Getting mesh node id..."
    MESH_NODE_ID=$(env XAUTHORITY=foo DISPLAY=bar ${agentBin} -m nixmeshnodeid)
    ValidateMeshNodeID
fi

if [ ! -d "${agentBinPath}" ]; then
    echo "Creating ${agentBinPath}"
    mkdir -p ${agentBinPath}
fi

INSTALL_CMD="${agentBin} -m install -api ${apiURL} -client-id ${clientID} -site-id ${siteID} -agent-type ${agentType} -auth ${token}"

if [ "${MESH_NODE_ID}" != '' ]; then
    INSTALL_CMD+=" --meshnodeid ${MESH_NODE_ID}"
fi

if [[ $DEBUG -eq 1 ]]; then
    INSTALL_CMD+=" --log debug"
fi

if [[ $INSECURE -eq 1 ]]; then
    INSTALL_CMD+=" --insecure"
fi

if [ "${proxy}" != '' ]; then
    INSTALL_CMD+=" --proxy ${proxy}"
fi

eval "${INSTALL_CMD}"

agentsvc="$(
    cat <<EOF
[Unit]
Description=Observer RMM Linux Agent

[Service]
Type=simple
ExecStart=${agentBin} -m svc
User=root
Group=root
Restart=always
RestartSec=5s
LimitNOFILE=1000000
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
)"
echo "${agentsvc}" | tee ${agentSysD} >/dev/null

systemctl daemon-reload
systemctl enable ${agentSvcName}
systemctl start ${agentSvcName}
