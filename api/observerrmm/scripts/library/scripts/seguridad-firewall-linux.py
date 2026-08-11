#!/usr/bin/env python3
"""Estado del firewall en Linux: ufw o firewalld, el que este presente.

Cierra el vacio de O-LIB-07: el catalogo ya tiene 'firewall-uac-estado.ps1' para
Windows y nada para Linux, aunque un firewall apagado es el mismo riesgo en las dos
plataformas.

No asume una distribucion: prueba ufw primero (Debian/Ubuntu) y si no esta instalado
prueba firewalld (RHEL/Fedora/SUSE). Si ninguno de los dos existe se informa tal cual,
sin fallar, porque puede haber un firewall de otro tipo (nftables/iptables a mano) que
este script no intenta interpretar.

Solo lee estado, nunca cambia reglas.

Uso:
    seguridad-firewall-linux.py
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


def reportar_ufw(binario):
    _, salida = correr([binario, "status", "verbose"])
    lineas = salida.splitlines()

    activo = bool(lineas) and lineas[0].strip().lower() == "status: active"

    entrantes = [
        linea
        for linea in lineas
        if "allow in" in linea.lower() or "deny in" in linea.lower()
    ]

    print("Firewall detectado: ufw")
    print("  estado: {}".format("ACTIVO" if activo else "INACTIVO"))
    for linea in lineas[1:4]:
        if linea.strip():
            print("  {}".format(linea.strip()))
    print("  reglas de entrada: {}".format(len(entrantes)))
    if entrantes:
        print("")
        print("  Reglas:")
        for regla in entrantes:
            print("    {}".format(regla.strip()))

    return activo


def reportar_firewalld(binario):
    rc_estado, estado = correr([binario, "--state"])
    activo = rc_estado == 0 and estado.strip().lower() == "running"

    print("Firewall detectado: firewalld")
    print("  estado: {}".format("ACTIVO" if activo else "INACTIVO"))

    if activo:
        _, zona_default = correr([binario, "--get-default-zone"])
        print("  zona por defecto: {}".format(zona_default.strip()))

        _, servicios = correr(
            [binario, "--zone", zona_default.strip(), "--list-services"]
        )
        _, puertos = correr([binario, "--zone", zona_default.strip(), "--list-ports"])
        print("  servicios permitidos: {}".format(servicios.strip() or "(ninguno)"))
        print("  puertos abiertos: {}".format(puertos.strip() or "(ninguno)"))

    return activo


def main():
    if platform.system() != "Linux":
        print("Este script es especifico de Linux (ufw/firewalld).")
        print("Sistema detectado: {}".format(platform.system()))
        return 1

    print(
        "Verificacion de firewall - {} {}".format(platform.node(), platform.release())
    )
    print("")

    ufw_bin = shutil.which("ufw")
    firewalld_bin = shutil.which("firewall-cmd")

    if ufw_bin:
        activo = reportar_ufw(ufw_bin)
    elif firewalld_bin:
        activo = reportar_firewalld(firewalld_bin)
    else:
        print("No se encontro ufw ni firewalld instalados en este equipo.")
        print("Puede haber un firewall gestionado a mano con nftables/iptables:")
        print("este script no lo interpreta.")
        return 1

    print("")
    print("== Resultado ==")
    if activo:
        print("  El firewall esta activo.")
        return 0

    print("  El firewall esta INACTIVO. El equipo queda expuesto en la red en la")
    print("  que este conectado.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
