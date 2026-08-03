#!/usr/bin/env python3
"""Activa o desactiva el modo depuración del agente ObserverRMM.

Añade o quita `-log debug` en la definición del servicio. **No reinicia el
servicio a propósito**: el agente ejecuta este script como proceso hijo, así que
reiniciarlo desde acá mataría al propio script antes de que informe el resultado
(y antes de poder revertir si algo salió mal). El cambio queda escrito y toma
efecto en el siguiente arranque del servicio — usá la acción de reinicio del
agente desde la consola, que la ejecuta el servidor y no este proceso.

Antes de escribir guarda el valor original y verifica que la definición resultante
siga conteniendo el ejecutable y `-m svc`; si no, no escribe nada.

Uso:
    agente-modo-depuracion.py [estado|activar|desactivar]

Sin argumentos equivale a `estado` (solo lee, no modifica).
"""

import os
import platform
import plistlib
import shutil
import subprocess
import sys

# El agente pasa el stdout por strings.ToValidUTF8(s, "") (agent/utils.go:401), que BORRA
# toda secuencia UTF-8 invalida. En Windows el Python embebido escribe stdout en cp1252
# (medido en un Windows 11 real: sys.stdout.encoding == "cp1252"), donde un acento es un
# solo byte que no es UTF-8 valido => los acentos desaparecian de la salida sin dejar
# rastro. En Linux y macOS stdout ya es UTF-8 y esto es un no-op.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_MACOS = SISTEMA == "Darwin"

# Definición del servicio según el código del agente: en las tres plataformas
# arranca como `<ejecutable> -m svc` (agent/agent.go:213-218 y agent/install.go:306
# para el plist de macOS). El flag de nivel de log es `-log` (main.go:26).
CLAVE_SERVICIO_WINDOWS = r"SYSTEM\CurrentControlSet\Services\observeragent"
UNIDADES_SYSTEMD = [
    "/etc/systemd/system/observeragent.service",
    "/lib/systemd/system/observeragent.service",
    "/usr/lib/systemd/system/observeragent.service",
]
PLIST_MACOS = "/Library/LaunchDaemons/observeragent.plist"

BANDERA = "-log"
NIVEL_DEPURACION = "debug"


def unidad_systemd():
    for ruta in UNIDADES_SYSTEMD:
        if os.path.isfile(ruta):
            return ruta
    return None


# --------------------------------------------------------------------- Windows


def _windows_leer():
    import winreg

    clave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLAVE_SERVICIO_WINDOWS)
    valor, tipo = winreg.QueryValueEx(clave, "ImagePath")
    clave.Close()
    return valor, tipo


def _windows_escribir(valor, tipo):
    import winreg

    clave = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, CLAVE_SERVICIO_WINDOWS, 0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(clave, "ImagePath", 0, tipo, valor)
    clave.Close()


def windows_estado():
    valor, _ = _windows_leer()
    return BANDERA in valor.lower(), valor


def windows_aplicar(activar):
    valor, tipo = _windows_leer()
    partes = valor.split()
    minusculas = [parte.lower() for parte in partes]

    if BANDERA in minusculas:
        indice = minusculas.index(BANDERA)
        # quita el flag y su valor
        del partes[indice : indice + 2]

    if activar:
        partes += [BANDERA, NIVEL_DEPURACION]

    nuevo = " ".join(partes)
    if "-m" not in nuevo or "svc" not in nuevo:
        print("ABORTADO: la definición resultante no conserva `-m svc`.")
        print("  original: {}".format(valor))
        print("  quedaría: {}".format(nuevo))
        return False, valor

    print("  respaldo del valor original: {}".format(valor))
    _windows_escribir(nuevo, tipo)
    return True, nuevo


# ----------------------------------------------------------------------- Linux


def linux_estado():
    ruta = unidad_systemd()
    if ruta is None:
        return None, None
    with open(ruta, "r") as archivo:
        contenido = archivo.read()
    for renglon in contenido.splitlines():
        if renglon.strip().startswith("ExecStart="):
            return BANDERA in renglon.lower(), renglon.strip()
    return None, None


def linux_aplicar(activar):
    ruta = unidad_systemd()
    if ruta is None:
        print("No se encontró la unidad systemd del agente en:")
        for candidata in UNIDADES_SYSTEMD:
            print("  - {}".format(candidata))
        return False, None

    with open(ruta, "r") as archivo:
        renglones = archivo.read().splitlines()

    nuevos = []
    original = None
    resultante = None
    for renglon in renglones:
        if not renglon.strip().startswith("ExecStart="):
            nuevos.append(renglon)
            continue
        original = renglon
        partes = renglon.split()
        minusculas = [parte.lower() for parte in partes]
        if BANDERA in minusculas:
            indice = minusculas.index(BANDERA)
            del partes[indice : indice + 2]
        if activar:
            partes += [BANDERA, NIVEL_DEPURACION]
        resultante = " ".join(partes)
        nuevos.append(resultante)

    if original is None:
        print("ABORTADO: la unidad {} no tiene línea ExecStart=.".format(ruta))
        return False, None

    if "-m" not in resultante or "svc" not in resultante:
        print("ABORTADO: el ExecStart resultante no conserva `-m svc`.")
        print("  original: {}".format(original))
        print("  quedaría: {}".format(resultante))
        return False, original

    shutil.copy2(ruta, ruta + ".observer.bak")
    print("  respaldo en {}".format(ruta + ".observer.bak"))
    with open(ruta, "w") as archivo:
        archivo.write("\n".join(nuevos) + "\n")

    # daemon-reload solo relee las unidades: no reinicia el servicio ni mata a
    # este proceso. Sin esto systemd seguiría usando la definición vieja.
    subprocess.run(["systemctl", "daemon-reload"], timeout=30)
    return True, resultante


# ----------------------------------------------------------------------- macOS


def macos_argumentos():
    with open(PLIST_MACOS, "rb") as archivo:
        datos = plistlib.load(archivo)
    return datos, datos.get("ProgramArguments", [])


def macos_estado():
    if not os.path.isfile(PLIST_MACOS):
        return None, None
    _, argumentos = macos_argumentos()
    minusculas = [str(a).lower() for a in argumentos]
    return BANDERA in minusculas, " ".join(str(a) for a in argumentos)


def macos_aplicar(activar):
    if not os.path.isfile(PLIST_MACOS):
        print("No se encontró {}.".format(PLIST_MACOS))
        return False, None

    datos, argumentos = macos_argumentos()
    original = list(argumentos)
    minusculas = [str(a).lower() for a in argumentos]
    if BANDERA in minusculas:
        indice = minusculas.index(BANDERA)
        del argumentos[indice : indice + 2]
    if activar:
        argumentos += [BANDERA, NIVEL_DEPURACION]

    if "-m" not in argumentos or "svc" not in argumentos:
        print("ABORTADO: los argumentos resultantes no conservan `-m svc`.")
        print("  original: {}".format(" ".join(str(a) for a in original)))
        print("  quedarían: {}".format(" ".join(str(a) for a in argumentos)))
        return False, " ".join(str(a) for a in original)

    shutil.copy2(PLIST_MACOS, PLIST_MACOS + ".observer.bak")
    print("  respaldo en {}".format(PLIST_MACOS + ".observer.bak"))
    datos["ProgramArguments"] = argumentos
    with open(PLIST_MACOS, "wb") as archivo:
        plistlib.dump(datos, archivo)
    return True, " ".join(str(a) for a in argumentos)


# ------------------------------------------------------------------------ main


def estado_actual():
    if ES_WINDOWS:
        return windows_estado()
    if ES_MACOS:
        return macos_estado()
    return linux_estado()


def aplicar(activar):
    if ES_WINDOWS:
        return windows_aplicar(activar)
    if ES_MACOS:
        return macos_aplicar(activar)
    return linux_aplicar(activar)


def main():
    accion = sys.argv[1].lower() if len(sys.argv) > 1 else "estado"
    if accion not in ("estado", "activar", "desactivar"):
        print("Acción no reconocida: {}".format(accion))
        print("Usá: estado | activar | desactivar")
        return 1

    activo, definicion = estado_actual()
    if activo is None:
        print(
            "No se pudo leer la definición del servicio del agente en {}.".format(
                SISTEMA
            )
        )
        return 1

    print("Modo depuración actualmente: {}".format("ACTIVO" if activo else "inactivo"))
    print("  definición: {}".format(definicion))

    if accion == "estado":
        return 0

    quiere_activo = accion == "activar"
    if quiere_activo == activo:
        print("")
        print(
            "Nada que hacer: ya estaba {}.".format("activo" if activo else "inactivo")
        )
        return 0

    print("")
    print("Aplicando: {}".format(accion))
    ok, resultante = aplicar(quiere_activo)
    if not ok:
        return 1

    print("  definición nueva: {}".format(resultante))
    print("")
    print("Escrito. NO se reinició el servicio (mataría a este script).")
    print("Reiniciá el agente desde la consola para que tome efecto.")
    if quiere_activo:
        print("Acordate de desactivarlo: en depuración el log crece rápido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
