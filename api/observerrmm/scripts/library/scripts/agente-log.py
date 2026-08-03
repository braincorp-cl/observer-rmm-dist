#!/usr/bin/env python3
"""Últimas líneas de los logs del agente ObserverRMM y del agente Mesh.

Solo LEE. Útil para soporte cuando el agente responde pero se comporta mal: evita
tener que abrir una sesión remota nada más que para mirar un log.

Uso:
    agente-log.py [líneas]

`líneas` es opcional y por defecto son 50. Se acota a 1000 para no devolver una
respuesta gigante por NATS.
"""

import os
import platform
import sys

ES_WINDOWS = platform.system() == "Windows"

LINEAS_POR_DEFECTO = 50
LINEAS_MAXIMAS = 1000

# Ubicaciones tomadas del código del agente (main.go:186-188, agent/agent.go:91-102).
# Del Mesh se prueban varias porque el archivo lo escribe MeshCentral, no nosotros.
if ES_WINDOWS:
    _archivos_programa = os.environ.get("ProgramFiles", r"C:\Program Files")
    LOGS = [
        (
            "agente ObserverRMM",
            os.path.join(_archivos_programa, "ObserverAgent", "agent.log"),
        ),
        (
            "agente Mesh",
            os.path.join(_archivos_programa, "Mesh Agent", "MeshAgent.log"),
        ),
    ]
else:
    LOGS = [
        ("agente ObserverRMM", "/var/log/observeragent.log"),
        ("agente Mesh", "/opt/observermesh/meshagent.log"),
        ("agente Mesh (alterno)", "/usr/local/mesh_services/meshagent/meshagent.log"),
    ]


def leer_cola(ruta, cantidad):
    """Últimas `cantidad` líneas de `ruta`, leyendo solo el final del archivo."""
    tamano_bloque = 8192
    with open(ruta, "rb") as archivo:
        archivo.seek(0, os.SEEK_END)
        restante = archivo.tell()
        datos = b""
        while restante > 0 and datos.count(b"\n") <= cantidad:
            salto = min(tamano_bloque, restante)
            restante -= salto
            archivo.seek(restante)
            datos = archivo.read(salto) + datos
    texto = datos.decode("utf-8", "replace")
    return texto.splitlines()[-cantidad:]


def main():
    cantidad = LINEAS_POR_DEFECTO
    if len(sys.argv) > 1:
        try:
            cantidad = int(sys.argv[1])
        except ValueError:
            print("El argumento debe ser un número de líneas. Recibido:", sys.argv[1])
            return 1
        if cantidad < 1:
            print("El número de líneas debe ser mayor que 0.")
            return 1
        cantidad = min(cantidad, LINEAS_MAXIMAS)

    encontrado = False
    for etiqueta, ruta in LOGS:
        if not os.path.isfile(ruta):
            continue
        encontrado = True
        print("")
        print(
            "===== {} — {} (últimas {} líneas) =====".format(etiqueta, ruta, cantidad)
        )
        try:
            for renglon in leer_cola(ruta, cantidad):
                print(renglon)
        except Exception as error:
            print("No se pudo leer el archivo: {}".format(error))

    if not encontrado:
        print("No se encontró ningún log del agente en las rutas conocidas:")
        for etiqueta, ruta in LOGS:
            print("  - {}: {}".format(etiqueta, ruta))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
