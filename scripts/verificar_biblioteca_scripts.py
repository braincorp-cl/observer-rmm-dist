#!/usr/bin/env python3
"""Gate de portabilidad de la biblioteca de scripts del producto.

Corre en CI y tambien a mano:

    python3 scripts/verificar_biblioteca_scripts.py

Comprueba dos invariantes de los scripts de api/observerrmm/scripts/library/scripts/.

1. SOLO ASCII EN EL CONTENIDO
   El agente entrega el stdout del script al backend, y en Windows PowerShell 5.1
   escribe en la pagina de codigos OEM de la consola, no en UTF-8. El agente ya
   decodifica esa salida (ver DecodeCmdOutput en el repo del agente), pero la flota
   no se actualiza toda el mismo dia: mientras haya agentes viejos corriendo, un
   acento en la salida se pierde sin dejar rastro. Escribir la biblioteca en ASCII
   quita el problema de raiz en vez de depender de la version del agente.

   El BOM UTF-8 al inicio de un .ps1 SI se permite, y de hecho conviene: es la unica
   marca que hace que PowerShell 5.1 lea el archivo como UTF-8 en vez de como ANSI.

   Ojo: esto vale para los ARCHIVOS de script. El manifiesto observer_scripts.json
   conserva sus acentos a proposito — su texto va del JSON a la base y de ahi a la
   consola web, todo UTF-8 limpio, sin pasar nunca por el agente.

2. NADA DE COMPARAR CONTRA TEXTO QUE WINDOWS TRADUCE
   Una flota chilena mezcla equipos en espanol y en ingles. Un servicio detenido dice
   "Stopped" en uno y "Detenido" en el otro, y el grupo de administradores locales se
   llama "Administrators" o "Administradores" segun el equipo. Un script que compara
   contra ese texto funciona en la mitad de la flota y falla en silencio en la otra:
   no da error, simplemente no encuentra nada y reporta que todo esta bien.

   La regla es usar el identificador que ningun idioma cambia — SID, GUID, enum de
   .NET, codigo numerico del registro o de la RFC — y dejar el texto traducido solo
   para lo que se le muestra al operador. Ahi es al reves: que salga en su idioma.
"""

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BIBLIOTECA = RAIZ / "api" / "observerrmm" / "scripts" / "library" / "scripts"

BOM = "﻿"

# Cada patron trae el reemplazo invariante que corresponde, porque un gate que solo
# dice "no" obliga a redescubrir la solucion cada vez que salta.
PATRONES_LOCALIZADOS = [
    (
        r'-(eq|ne)\s+"(Running|Stopped|Paused|Detenido|En ejecucion|Pausado)"',
        "estado de servicio como texto; usar el enum [System.ServiceProcess.ServiceControllerStatus]",
    ),
    (
        r"\.StartMode\s+-(eq|ne)",
        "Win32_Service.StartMode viene traducido; leer Start (DWORD) de "
        "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\<servicio>",
    ),
    (
        r'\.State\s+-(eq|ne)\s+"(Running|Stopped|Detenido)"',
        "Win32_Service.State viene traducido; usar la propiedad booleana Started",
    ),
    (
        r'\.Status\s+-(eq|ne)\s+"(Up|Down|Activo|Desconectado)"',
        "Get-NetAdapter.Status viene traducido; usar ifOperStatus (1 = operativo, RFC 2863)",
    ),
    (
        r'-(Group|Name)\s+"(Administrators|Administradores|Users|Usuarios|Guests|Invitados)"',
        "el nombre del grupo local cambia con el idioma; resolverlo por SID "
        "(Get-LocalGroup -SID S-1-5-32-544)",
    ),
    (
        r"net\s+localgroup\s+(administrators|administradores)",
        "idem: resolver el grupo por SID en vez de por nombre",
    ),
]

# El propio manifiesto y este archivo nombran los patrones que prohiben.
EXTENSIONES = {".ps1", ".py", ".sh", ".bat", ".nu", ".ts"}


def revisar_ascii(ruta, texto):
    fallas = []
    cuerpo = texto[1:] if texto.startswith(BOM) else texto

    for numero, linea in enumerate(cuerpo.splitlines(), start=1):
        malos = sorted({c for c in linea if ord(c) > 127})
        if malos:
            visibles = " ".join("{!r} (U+{:04X})".format(c, ord(c)) for c in malos)
            fallas.append(
                "{}:{}: caracter no ASCII {}".format(ruta.name, numero, visibles)
            )
    return fallas


def revisar_localizacion(ruta, texto):
    fallas = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        # Un comentario que EXPLICA la trampa no es la trampa.
        despojada = linea.strip()
        if despojada.startswith("#"):
            continue
        for patron, remedio in PATRONES_LOCALIZADOS:
            if re.search(patron, linea):
                fallas.append(
                    "{}:{}: comparacion contra texto que Windows traduce -> {}\n"
                    "        {}".format(ruta.name, numero, remedio, despojada)
                )
    return fallas


def main():
    if not BIBLIOTECA.is_dir():
        print("No existe {}".format(BIBLIOTECA), file=sys.stderr)
        return 2

    archivos = sorted(
        p for p in BIBLIOTECA.iterdir() if p.is_file() and p.suffix in EXTENSIONES
    )
    if not archivos:
        print("No se encontro ningun script en {}".format(BIBLIOTECA), file=sys.stderr)
        return 2

    fallas = []
    for ruta in archivos:
        texto = ruta.read_text(encoding="utf-8")
        fallas.extend(revisar_ascii(ruta, texto))
        fallas.extend(revisar_localizacion(ruta, texto))

    if fallas:
        print("La biblioteca de scripts tiene {} problema(s):\n".format(len(fallas)))
        for falla in fallas:
            print("  " + falla)
        print(
            "\nEl porque de cada regla esta en la cabecera de "
            "scripts/verificar_biblioteca_scripts.py"
        )
        return 1

    print(
        "{} scripts revisados: ASCII limpio y sin comparaciones traducidas.".format(
            len(archivos)
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
