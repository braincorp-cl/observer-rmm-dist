#!/usr/bin/env python3
"""Salud de systemd: estado general y unidades caidas.

Cierra parte del vacio de O-LIB-07: el catalogo tiene 'servicios-automaticos-
detenidos.ps1' para Windows (servicios en Auto que no estan corriendo) y nada
equivalente para Linux, donde el concepto correcto no es "Auto" sino unidades que
systemd intento levantar y fallaron.

'systemctl is-system-running' devuelve un estado agregado (running, degraded,
maintenance, starting...) y 'systemctl --failed' enumera las unidades responsables
cuando el estado no es 'running'. Los dos se leen juntos porque el primero solo sin el
segundo no dice QUE fallo.

Solo lee estado, no reinicia ni reparara nada.

Uso:
    sistema-salud-systemd.py
"""

import platform
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def correr(argumentos):
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        return proceso.returncode, proceso.stdout.decode("utf-8", "replace").strip()
    except Exception as error:
        return 1, str(error)


def main():
    if platform.system() != "Linux":
        print("Este script es especifico de Linux (systemd).")
        print("Sistema detectado: {}".format(platform.system()))
        return 1

    if not shutil.which("systemctl"):
        print("No se encontro systemctl en este equipo: no usa systemd como init.")
        return 1

    print("Salud de systemd - {} {}".format(platform.node(), platform.release()))
    print("")

    # is-system-running devuelve rc != 0 cuando el estado no es "running", asi que
    # el codigo de salida no sirve como control de errores aca: el estado importa
    # sea cual sea el rc.
    _, estado = correr(["systemctl", "is-system-running"])
    estado = estado.strip()

    print("  estado general: {}".format(estado))

    _, salida_fallidas = correr(["systemctl", "--failed", "--no-legend", "--no-pager"])
    unidades_fallidas = [
        linea for linea in salida_fallidas.splitlines() if linea.strip()
    ]

    print("  unidades fallidas: {}".format(len(unidades_fallidas)))
    if unidades_fallidas:
        print("")
        print("  Detalle:")
        for linea in unidades_fallidas:
            campos = linea.split()
            nombre = campos[0] if campos else linea.strip()
            print("    {}".format(nombre))
            _, motivo = correr(
                [
                    "systemctl",
                    "status",
                    nombre,
                    "--no-pager",
                    "--lines=3",
                ]
            )
            for renglon in motivo.splitlines()[:5]:
                print("      {}".format(renglon.strip()))

    # Unidades socket/timer/path que fallaron y quedaron reintentando en bucle no
    # siempre aparecen como "failed" agregado; se informan aparte para no perderlas
    # detras de un estado "running" que oculta el detalle.
    _, listado_completo = correr(
        [
            "systemctl",
            "list-units",
            "--state=failed",
            "--no-legend",
            "--no-pager",
            "--all",
        ]
    )
    extra = [
        linea
        for linea in listado_completo.splitlines()
        if linea.strip()
        and linea.split()[0] not in {u.split()[0] for u in unidades_fallidas}
    ]
    if extra:
        print("")
        print("  Unidades adicionales en estado failed (--all):")
        for linea in extra:
            print("    {}".format(linea.strip()))
        unidades_fallidas = unidades_fallidas + extra

    print("")
    print("UNIDADES_FALLIDAS={}".format(len(unidades_fallidas)))
    print("ESTADO_GENERAL={}".format(estado))

    print("")
    print("== Resultado ==")
    if estado == "running" and not unidades_fallidas:
        print("  systemd esta sano: estado 'running' y sin unidades fallidas.")
        return 0

    print("  systemd reporta problemas: revisar el detalle de arriba.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
