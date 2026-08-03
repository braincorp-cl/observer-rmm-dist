#!/usr/bin/env bash

if [ $EUID -ne 0 ]; then
    echo "ERROR: Must be run as root"
    exit 1
fi

if [ "$(uname)" != "Darwin" ]; then
    echo "ERROR: This script is for macOS only"
    exit 1
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

agentBinPath='/opt/observeragent'
binName='observeragent'
agentBin="${agentBinPath}/${binName}"
meshDir='/opt/observermesh'
meshBin="${meshDir}/meshagent"

InstallMesh() {
    meshTmpDir="$(mktemp -d)"
    meshTmpBin="${meshTmpDir}/meshagent"

    echo "Downloading mesh agent..."
    # Mismo chequeo que en agent_linux.sh: sin él una descarga fallida seguía
    # de largo en silencio y el fallo aparecía mucho después, como un equipo
    # enrolado sin «Tomar control».
    #
    # `-f` es imprescindible acá y no es cosmético: sin esa bandera `curl`
    # devuelve rc=0 ante un HTTP 404 y deja la página de error escrita en
    # ${meshTmpBin} como si fuera el binario, así que el chequeo del código de
    # salida por sí solo no atraparía nada. `-s` cubre la respuesta vacía.
    # Para instalar deliberadamente sin mesh está `--nomesh`.
    curl -fL --insecure -o "${meshTmpBin}" "${meshDL}"
    if [ $? -ne 0 ] || [ ! -s "${meshTmpBin}" ]; then
        echo "ERROR: Unable to download mesh agent"
        rm -rf "${meshTmpDir}"
        exit 1
    fi
    chmod +x "${meshTmpBin}"
    mkdir -p "${meshDir}"
    "${meshTmpBin}" -install --installPath="${meshDir}"
    sleep 1
    rm -rf "${meshTmpDir}"
}

RemoveMesh() {
    if [ -f "${meshBin}" ]; then
        # `--no-embedded=1` es OBLIGATORIO y va DESPUÉS del comando, igual que en
        # agent_linux.sh. El binario que MeshCentral entrega para instalar puede
        # traer un instalador JS anexado que se dispara ante CUALQUIER argumento;
        # en Linux, medido en HP-ProOne-400, ante `-fulluninstall` abre un diálogo
        # en el escritorio de la persona y se queda esperando un clic, colgando el
        # uninstall entero sin desinstalar nada.
        #
        # Acá NO se pudo reproducir el cuelgue: medido en el Mac de la flota el
        # 2026-07-28, su binario instalado no trae el bloque anexado (los últimos
        # 16 bytes no son el GUID) y `-nodeid` devuelve lo mismo con y sin la
        # bandera. O sea: la bandera es inocua donde hoy funciona, y cubre el caso
        # que en Linux sí ocurrió. Lo que NO está medido es el cuelgue en macOS
        # con un binario que sí traiga el bloque; no hay forma de montarlo sin
        # desinstalar el mesh del equipo de una persona.
        #
        # El `perl -e alarm` es el cinturón: macOS no trae `timeout`. Si alguna
        # vez aparece una variante que igual quiera interactuar, el uninstall debe
        # FALLAR, nunca quedarse colgado esperando a alguien que no está.
        perl -e 'alarm shift; exec @ARGV' 120 "${meshBin}" -uninstall --no-embedded=1
        sleep 1
    fi
    rm -rf "${meshDir}"
}

# ValidateMeshNodeID descarta cualquier respuesta que no sea un identificador.
#
# MESH_NODE_ID se concatena más abajo en INSTALL_CMD, que termina pasando por
# `eval`: si lo que vuelve no es un id, el shell EJECUTA esas líneas. El binario
# que MeshCentral entrega para instalar no es el agente sino un AUTO-INSTALADOR,
# con un script JS anexado que corre ante cualquier argumento, así que
# `meshagent -nodeid` puede devolver la salida entera de una reinstalación. Se
# detectó en Linux (equipo con el servicio del mesh caído y registrado con su
# MAC como node id) y acá vale igual: el instalador de macOS baja el binario por
# la misma vía.
#
# Desde v2.14.7 el agente pide el id con `--no-embedded=1`; esto cubre a los
# anteriores. Quedarse sin id no impide instalar: SyncMeshNodeID lo corrige.
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

echo "Downloading Observer RMM agent..."
mkdir -p "${agentBinPath}"
curl -L -o "${agentBin}" "${agentDL}"
if [ $? -ne 0 ]; then
    echo "ERROR: Unable to download observer agent"
    exit 1
fi
chmod +x "${agentBin}"

MESH_NODE_ID=""

if [[ $NOMESH -eq 1 ]]; then
    echo "Skipping mesh install"
else
    if [ -f "${meshBin}" ]; then
        RemoveMesh
    fi
    echo "Downloading and installing mesh agent..."
    InstallMesh
    sleep 2
    echo "Getting mesh node id..."
    MESH_NODE_ID=$("${agentBin}" -m nixmeshnodeid)
    ValidateMeshNodeID
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
