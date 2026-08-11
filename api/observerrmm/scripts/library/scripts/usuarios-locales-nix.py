#!/usr/bin/env python3
"""Usuarios locales en Linux y macOS: listar, habilitar, deshabilitar.

Cierra parte del vacio de O-LIB-07: el catalogo tiene 'usuarios-locales.ps1' para
Windows (listar/crear/habilitar/deshabilitar) y nada equivalente en Linux/macOS.

Listar funciona igual en las dos plataformas. Habilitar y deshabilitar solo estan
implementados en Linux por ahora ('usermod -L/-U', metodo estandar y sin ambiguedad).
En macOS el mecanismo equivalente (marcar AuthenticationAuthority con
';DisabledUser;' via dscl) no se pudo verificar en un Mac real todavia, asi que el
script se niega a aplicarlo en vez de entregar un comando sin probar: por ahora solo
lista.

En Linux se excluyen las cuentas de sistema usando el rango de /etc/login.defs
(UID_MIN/UID_MAX), no un numero fijo, porque ese rango cambia entre distribuciones.
En macOS se excluyen las cuentas con guion bajo al inicio (_appstore, _www, etc.) y
las de UID menor a 500, que es el corte que usa el propio Directory Service.

Uso:
    usuarios-locales-nix.py listar
    usuarios-locales-nix.py deshabilitar <usuario>   (solo Linux)
    usuarios-locales-nix.py habilitar <usuario>       (solo Linux)
"""

import platform
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


SISTEMA = platform.system()
ES_MACOS = SISTEMA == "Darwin"


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


def rango_uid_linux():
    """Lee UID_MIN/UID_MAX de /etc/login.defs. Si falta, usa el valor por defecto
    de Debian y RHEL, que coincide: 1000-60000."""
    minimo, maximo = 1000, 60000
    try:
        with open("/etc/login.defs", "r") as archivo:
            for linea in archivo:
                partes = linea.split()
                if len(partes) != 2:
                    continue
                if partes[0] == "UID_MIN":
                    minimo = int(partes[1])
                elif partes[0] == "UID_MAX":
                    maximo = int(partes[1])
    except (OSError, ValueError):
        pass
    return minimo, maximo


def estado_linux(usuario):
    """L = bloqueado, P = con password usable, NP = sin password. Ver passwd(1)."""
    rc, salida = correr(["passwd", "-S", usuario])
    if rc != 0:
        return "desconocido"
    campos = salida.split()
    if len(campos) < 2:
        return "desconocido"
    codigo = campos[1]
    if codigo == "L":
        return "deshabilitado"
    if codigo in ("P", "NP"):
        return "habilitado"
    return "desconocido"


def listar_linux():
    minimo, maximo = rango_uid_linux()
    _, salida = correr(["getent", "passwd"])

    usuarios = []
    for linea in salida.splitlines():
        campos = linea.split(":")
        if len(campos) < 7:
            continue
        nombre, _, uid_texto, _, comentario, home, shell = campos[:7]
        try:
            uid = int(uid_texto)
        except ValueError:
            continue
        if not (minimo <= uid <= maximo):
            continue
        if shell.endswith(("/nologin", "/false")):
            # Cuenta de servicio con shell inhabilitado por diseno (ej. el usuario
            # de un daemon creado con adduser --system): no es una cuenta de login.
            continue
        usuarios.append((nombre, uid, comentario, home, estado_linux(nombre)))
    return usuarios


def listar_macos():
    _, salida = correr(["dscl", ".", "-list", "/Users", "UniqueID"])
    usuarios = []
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) != 2:
            continue
        nombre, uid_texto = partes
        if nombre.startswith("_"):
            continue
        try:
            uid = int(uid_texto)
        except ValueError:
            continue
        if uid < 500:
            continue

        _, autoridad = correr(
            [
                "dscl",
                ".",
                "-read",
                "/Users/{}".format(nombre),
                "AuthenticationAuthority",
            ]
        )
        estado = "deshabilitado" if "DisabledUser" in autoridad else "habilitado"
        usuarios.append((nombre, uid, "", "/Users/{}".format(nombre), estado))
    return usuarios


def imprimir_usuarios(usuarios):
    if not usuarios:
        print("  No hay cuentas de usuario locales (fuera de las de sistema).")
        return
    for nombre, uid, comentario, home, estado in sorted(usuarios, key=lambda u: u[1]):
        etiqueta = " - {}".format(comentario) if comentario else ""
        print(
            "  {:<20} uid={:<6} {:<14} {}{}".format(nombre, uid, estado, home, etiqueta)
        )


def cambiar_estado_linux(usuario, deshabilitar):
    bandera = "-L" if deshabilitar else "-U"
    rc, salida = correr(["usermod", bandera, usuario])
    if rc != 0:
        print("  no se pudo cambiar el estado de '{}': {}".format(usuario, salida))
        return False
    return True


def main():
    argumentos = sys.argv[1:]
    accion = argumentos[0].lower() if argumentos else "listar"

    print("Usuarios locales - {} {}".format(SISTEMA, platform.release()))
    print("  equipo: {}".format(platform.node()))
    print("")

    if accion == "listar":
        usuarios = listar_macos() if ES_MACOS else listar_linux()
        print("Cuentas encontradas: {}".format(len(usuarios)))
        imprimir_usuarios(usuarios)
        print("")
        print("USUARIOS={}".format(len(usuarios)))
        return 0

    if accion in ("deshabilitar", "habilitar"):
        if len(argumentos) < 2:
            print("Falta el nombre de usuario. Uso: {} <usuario>".format(accion))
            return 1
        usuario = argumentos[1]

        if ES_MACOS:
            print("En macOS este script solo lista cuentas por ahora.")
            print("Deshabilitar/habilitar via dscl no esta implementado: el metodo")
            print("(AuthenticationAuthority=';DisabledUser;') no se pudo verificar")
            print("todavia en un Mac real, y este catalogo no entrega comandos de")
            print("mutacion sin probar en hardware.")
            return 1

        deshabilitar = accion == "deshabilitar"
        if cambiar_estado_linux(usuario, deshabilitar):
            print(
                "  cuenta '{}' {}.".format(
                    usuario, "deshabilitada" if deshabilitar else "habilitada"
                )
            )
            print("  estado verificado: {}".format(estado_linux(usuario)))
            return 0
        return 1

    print(
        "Accion no reconocida: {}. Usa 'listar', 'deshabilitar' o 'habilitar'.".format(
            accion
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
