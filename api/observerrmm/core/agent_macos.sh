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
    curl -L --insecure -o "${meshTmpBin}" "${meshDL}"
    chmod +x "${meshTmpBin}"
    mkdir -p "${meshDir}"
    "${meshTmpBin}" -install --installPath="${meshDir}"
    sleep 1
    rm -rf "${meshTmpDir}"
}

RemoveMesh() {
    if [ -f "${meshBin}" ]; then
        "${meshBin}" -uninstall
        sleep 1
    fi
    rm -rf "${meshDir}"
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
