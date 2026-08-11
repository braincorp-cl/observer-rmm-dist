#!/usr/bin/env python3
"""Actualizaciones de paquetes pendientes en Linux (apt/dnf) y macOS (brew).

Cierra parte del vacio de O-LIB-07: el catalogo tiene 'windows-update-restablecer.ps1'
para Windows y nada equivalente en las otras dos plataformas, aunque quedarse atras en
parches de seguridad es el mismo riesgo en cualquier sistema operativo.

Por defecto lee el estado SIN tocar red: apt sobre la cache ya existente
('apt list --upgradable'), dnf con '-C' (cache local) y brew sobre lo que ya sabe.
Pasando 'refrescar' se actualiza el indice de paquetes antes de listar (toca red;
en dnf y brew es ademas mas lento).

En Linux tambien informa si el equipo quedo pidiendo reinicio (Debian/Ubuntu marcan
esto en un archivo; RHEL/Fedora lo calculan con 'needs-restarting').

Uso:
    software-paquetes-pendientes.py [listar|refrescar]
"""

import platform
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


SISTEMA = platform.system()
ES_MACOS = SISTEMA == "Darwin"

REBOOT_REQUIRED_DEBIAN = "/var/run/reboot-required"


def correr(argumentos, tiempo_espera=120):
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=tiempo_espera,
        )
        return proceso.returncode, proceso.stdout.decode("utf-8", "replace").strip()
    except Exception as error:
        return 1, str(error)


def pendientes_apt(refrescar):
    if refrescar:
        print("  refrescando indice de apt (apt-get update)...")
        rc, salida = correr(["apt-get", "update", "-qq"], tiempo_espera=180)
        if rc != 0:
            print("  no se pudo refrescar: {}".format(salida))

    rc, salida = correr(["apt", "list", "--upgradable"])
    lineas = [
        linea
        for linea in salida.splitlines()
        if linea.strip() and not linea.startswith("Listing...")
        # "apt" avisa por stderr que su CLI no es estable para scripts; el aviso
        # no es un paquete y no debe contarse ni mostrarse como si lo fuera.
        and not linea.startswith("WARNING:")
    ]
    return lineas


def pendientes_dnf(refrescar):
    binario = "dnf" if shutil.which("dnf") else "yum"
    argumentos = [binario, "check-update"]
    if not refrescar:
        argumentos.append("-C")

    # dnf/yum devuelven 100 cuando SI hay actualizaciones, 0 cuando no hay, y
    # cualquier otro valor es un error real. No es un codigo de exit habitual.
    rc, salida = correr(argumentos, tiempo_espera=180)
    if rc not in (0, 100):
        print("  {} check-update fallo (rc={}): {}".format(binario, rc, salida))
        return []
    if rc == 0:
        return []

    lineas = [
        linea
        for linea in salida.splitlines()
        if linea.strip() and not linea.lower().startswith(("last metadata",))
    ]
    return lineas


def reinicio_pendiente_linux():
    import os

    if os.path.isfile(REBOOT_REQUIRED_DEBIAN):
        return True

    if shutil.which("needs-restarting"):
        # needs-restarting -r: exit 0 = no hace falta reiniciar, 1 = si hace falta.
        rc, _ = correr(["needs-restarting", "-r"])
        return rc == 1

    return None


def pendientes_brew(refrescar):
    if not shutil.which("brew"):
        return None

    if refrescar:
        print("  refrescando indice de brew (brew update)...")
        correr(["brew", "update"], tiempo_espera=180)

    _, salida = correr(["brew", "outdated"], tiempo_espera=60)
    return [linea for linea in salida.splitlines() if linea.strip()]


def pendientes_macos_sistema():
    """Actualizaciones del sistema operativo en si (no de brew)."""
    _, salida = correr(["softwareupdate", "-l"], tiempo_espera=180)
    lineas = salida.splitlines()
    if any("no new software" in linea.lower() for linea in lineas):
        return []
    # softwareupdate -l lista cada item con una linea "* Label: ..." o similar.
    return [linea for linea in lineas if linea.strip().startswith("*")]


def main():
    accion = sys.argv[1].lower() if len(sys.argv) > 1 else "listar"
    if accion not in ("listar", "refrescar"):
        print("Accion no reconocida: {}. Usa 'listar' o 'refrescar'.".format(accion))
        return 1
    refrescar = accion == "refrescar"

    print("Paquetes pendientes - {} {}".format(SISTEMA, platform.release()))
    print("  equipo: {}".format(platform.node()))
    print(
        "  modo:   {}".format(
            "REFRESCAR indice primero" if refrescar else "LISTAR (cache actual)"
        )
    )
    print("")

    if SISTEMA == "Linux":
        if shutil.which("apt"):
            pendientes = pendientes_apt(refrescar)
            gestor = "apt"
        elif shutil.which("dnf") or shutil.which("yum"):
            pendientes = pendientes_dnf(refrescar)
            gestor = "dnf/yum"
        else:
            print("No se encontro apt ni dnf/yum en este equipo.")
            return 1

        print("Gestor: {}".format(gestor))
        print("  paquetes pendientes: {}".format(len(pendientes)))
        for linea in pendientes[:30]:
            print("    {}".format(linea))
        if len(pendientes) > 30:
            print("    ... y {} mas".format(len(pendientes) - 30))

        reinicio = reinicio_pendiente_linux()
        print("")
        if reinicio is True:
            print(
                "  El equipo necesita reiniciar para aplicar actualizaciones ya instaladas."
            )
        elif reinicio is False:
            print("  No hace falta reiniciar.")
        else:
            print(
                "  No se pudo determinar si hace falta reiniciar (sin needs-restarting)."
            )

        print("")
        print("PAQUETES_PENDIENTES={}".format(len(pendientes)))
        return 1 if pendientes or reinicio is True else 0

    if ES_MACOS:
        del_sistema = pendientes_macos_sistema()
        print("macOS - Software Update")
        print("  actualizaciones del sistema: {}".format(len(del_sistema)))
        for linea in del_sistema:
            print("    {}".format(linea.strip()))

        pendientes_hb = pendientes_brew(refrescar)
        print("")
        if pendientes_hb is None:
            print("Homebrew: no instalado en este equipo.")
        else:
            print("Homebrew - paquetes desactualizados: {}".format(len(pendientes_hb)))
            for linea in pendientes_hb[:30]:
                print("    {}".format(linea))

        total = len(del_sistema) + (len(pendientes_hb) if pendientes_hb else 0)
        print("")
        print("PAQUETES_PENDIENTES={}".format(total))
        return 1 if total else 0

    print("Plataforma no soportada por este script: {}".format(SISTEMA))
    return 1


if __name__ == "__main__":
    sys.exit(main())
