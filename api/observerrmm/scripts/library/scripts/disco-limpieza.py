#!/usr/bin/env python3
"""Libera espacio borrando temporales y cachés seguros de borrar.

Reemplaza los dos scripts de Windows del catálogo original (limpiar C: y vaciar la
papelera) por uno que además funciona en Linux y macOS, donde el disco lleno es tan
frecuente como en Windows y no había nada.

Qué borra, por plataforma:
  Windows — %TEMP% del sistema, temporales de cada perfil de usuario, la caché de
            descargas de Windows Update (SoftwareDistribution\\Download), los logs
            de IIS si existen, los volcados de error y la papelera de reciclaje.
  Linux   — /tmp y /var/tmp con más de un día, journal de systemd por encima de un
            límite, cachés de apt/dnf y las papeleras de cada usuario.
  macOS   — cachés de usuario y de sistema, logs viejos y las papeleras.

Qué NO borra nunca, a propósito: nada dentro de un perfil que no sea caché o
temporal, ni descargas, ni la carpeta de instaladores de Windows (Installer), que
parece basura y es lo que necesitan las desinstalaciones y actualizaciones.

Por defecto SIMULA: informa cuánto liberaría sin borrar nada. Hay que pedir 'aplicar'.

Uso:
    disco-limpieza.py [simular|aplicar]
"""

import os
import platform
import shutil
import subprocess
import sys
import time

SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_MACOS = SISTEMA == "Darwin"

EDAD_MINIMA_DIAS = 1
MIB = 1024 * 1024


def correr(argumentos):
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=600,
        )
        return proceso.returncode, proceso.stdout.decode("utf-8", "replace").strip()
    except Exception as error:
        return 1, str(error)


def es_viejo(ruta, dias):
    """True si el archivo no se modificó en los últimos `dias`."""
    if dias <= 0:
        return True
    try:
        return (time.time() - os.path.getmtime(ruta)) > (dias * 86400)
    except OSError:
        return False


def medir_y_borrar(directorio, aplicar, dias=0):
    """Recorre `directorio` y borra (o mide) su contenido. Devuelve (bytes, archivos).

    Nunca borra el directorio raíz en sí: solo su contenido. Borrar el propio %TEMP%
    o /tmp rompe cosas que esperan que exista.
    """
    if not directorio or not os.path.isdir(directorio):
        return 0, 0

    liberados = 0
    contados = 0

    for nombre in os.listdir(directorio):
        ruta = os.path.join(directorio, nombre)
        try:
            if os.path.islink(ruta):
                # Un enlace se borra solo si es viejo, y nunca se sigue: seguirlo
                # podría llevar el borrado fuera del directorio que queremos limpiar.
                if es_viejo(ruta, dias):
                    tamano = 0
                    if aplicar:
                        os.unlink(ruta)
                    liberados += tamano
                    contados += 1
                continue

            if os.path.isfile(ruta):
                if not es_viejo(ruta, dias):
                    continue
                tamano = os.path.getsize(ruta)
                if aplicar:
                    os.remove(ruta)
                liberados += tamano
                contados += 1
                continue

            if os.path.isdir(ruta):
                if not es_viejo(ruta, dias):
                    continue
                tamano = 0
                archivos = 0
                for raiz, _, nombres in os.walk(ruta):
                    for archivo in nombres:
                        completo = os.path.join(raiz, archivo)
                        try:
                            tamano += os.path.getsize(completo)
                            archivos += 1
                        except OSError:
                            continue
                if aplicar:
                    shutil.rmtree(ruta, ignore_errors=True)
                liberados += tamano
                contados += archivos
        except (OSError, PermissionError):
            # Un archivo en uso no se puede borrar: es lo normal en %TEMP% y no es
            # un error del script.
            continue

    return liberados, contados


def objetivos_windows():
    sistema = os.environ.get("SystemRoot", r"C:\Windows")
    unidad = os.environ.get("SystemDrive", "C:")

    objetivos = [
        ("temporales de Windows", os.path.join(sistema, "Temp"), 0),
        (
            "caché de Windows Update",
            os.path.join(sistema, "SoftwareDistribution", "Download"),
            EDAD_MINIMA_DIAS,
        ),
        ("volcados de error", os.path.join(sistema, "Minidump"), EDAD_MINIMA_DIAS),
        ("logs de IIS", os.path.join(unidad + "\\", "inetpub", "logs", "LogFiles"), 30),
    ]

    # Temporales por perfil: se recorre Users en vez de usar %TEMP%, que apunta solo
    # al del usuario que corre el script (SYSTEM, no el que llenó el disco).
    perfiles = os.path.join(unidad + "\\", "Users")
    if os.path.isdir(perfiles):
        for perfil in os.listdir(perfiles):
            temporal = os.path.join(perfiles, perfil, "AppData", "Local", "Temp")
            if os.path.isdir(temporal):
                objetivos.append(
                    ("temporales de {}".format(perfil), temporal, EDAD_MINIMA_DIAS)
                )
    return objetivos


def objetivos_linux():
    objetivos = [
        ("/tmp", "/tmp", EDAD_MINIMA_DIAS),
        ("/var/tmp", "/var/tmp", EDAD_MINIMA_DIAS),
        ("caché de apt", "/var/cache/apt/archives", 0),
        ("caché de dnf", "/var/cache/dnf", 0),
        ("crash reports", "/var/crash", EDAD_MINIMA_DIAS),
    ]
    for base in ("/home", "/root"):
        if not os.path.isdir(base):
            continue
        candidatos = (
            [base]
            if base == "/root"
            else [os.path.join(base, d) for d in os.listdir(base)]
        )
        for hogar in candidatos:
            papelera = os.path.join(hogar, ".local", "share", "Trash", "files")
            if os.path.isdir(papelera):
                objetivos.append(
                    ("papelera de {}".format(os.path.basename(hogar)), papelera, 0)
                )
    return objetivos


def objetivos_macos():
    objetivos = [
        ("/tmp", "/tmp", EDAD_MINIMA_DIAS),
        ("/var/tmp", "/var/tmp", EDAD_MINIMA_DIAS),
        ("logs del sistema", "/private/var/log/asl", 30),
    ]
    usuarios = "/Users"
    if os.path.isdir(usuarios):
        for usuario in os.listdir(usuarios):
            if usuario.startswith("."):
                continue
            cache = os.path.join(usuarios, usuario, "Library", "Caches")
            if os.path.isdir(cache):
                objetivos.append(
                    ("caché de {}".format(usuario), cache, EDAD_MINIMA_DIAS)
                )
            papelera = os.path.join(usuarios, usuario, ".Trash")
            if os.path.isdir(papelera):
                objetivos.append(("papelera de {}".format(usuario), papelera, 0))
    return objetivos


def espacio_libre(ruta):
    try:
        return shutil.disk_usage(ruta).free
    except Exception:
        return None


def vaciar_papelera_windows(aplicar):
    """La papelera de Windows vive en $Recycle.Bin de cada volumen."""
    liberados = 0
    contados = 0
    for letra in "CDEFGH":
        raiz = "{}:\\$Recycle.Bin".format(letra)
        if not os.path.isdir(raiz):
            continue
        try:
            for sid in os.listdir(raiz):
                bytes_sid, archivos_sid = medir_y_borrar(
                    os.path.join(raiz, sid), aplicar, 0
                )
                liberados += bytes_sid
                contados += archivos_sid
        except (OSError, PermissionError):
            continue
    return liberados, contados


def recortar_journal(aplicar):
    """El journal de systemd puede ocupar varios GB y no lo alcanza un rm."""
    if not os.path.isdir("/var/log/journal"):
        return 0
    antes = 0
    for raiz, _, nombres in os.walk("/var/log/journal"):
        for nombre in nombres:
            try:
                antes += os.path.getsize(os.path.join(raiz, nombre))
            except OSError:
                continue
    if not aplicar:
        return antes // 2 if antes > 200 * MIB else 0

    rc, salida = correr(["journalctl", "--vacuum-size=200M"])
    if rc != 0:
        print("  no se pudo recortar el journal: {}".format(salida))
        return 0

    despues = 0
    for raiz, _, nombres in os.walk("/var/log/journal"):
        for nombre in nombres:
            try:
                despues += os.path.getsize(os.path.join(raiz, nombre))
            except OSError:
                continue
    return max(0, antes - despues)


def main():
    accion = sys.argv[1].lower() if len(sys.argv) > 1 else "simular"
    if accion not in ("simular", "aplicar"):
        print("Acción no reconocida: {}. Usá 'simular' o 'aplicar'.".format(accion))
        return 1

    aplicar = accion == "aplicar"
    raiz_sistema = os.environ.get("SystemDrive", "C:") + "\\" if ES_WINDOWS else "/"

    libre_antes = espacio_libre(raiz_sistema)

    print("Limpieza de temporales — {} {}".format(SISTEMA, platform.release()))
    print("  equipo: {}".format(platform.node()))
    print("  modo:   {}".format("APLICAR (borra de verdad)" if aplicar else "SIMULAR"))
    if libre_antes is not None:
        print("  libre antes: {:.2f} GB".format(libre_antes / float(1024**3)))

    if ES_WINDOWS:
        objetivos = objetivos_windows()
    elif ES_MACOS:
        objetivos = objetivos_macos()
    else:
        objetivos = objetivos_linux()

    print("")
    total_bytes = 0
    total_archivos = 0

    for etiqueta, ruta, dias in objetivos:
        if not os.path.isdir(ruta):
            continue
        liberados, contados = medir_y_borrar(ruta, aplicar, dias)
        total_bytes += liberados
        total_archivos += contados
        verbo = "liberado" if aplicar else "liberaría"
        print(
            "  {:<34} {} {:.1f} MiB en {} archivo(s)".format(
                etiqueta + ":", verbo, liberados / float(MIB), contados
            )
        )

    if ES_WINDOWS:
        liberados, contados = vaciar_papelera_windows(aplicar)
        total_bytes += liberados
        total_archivos += contados
        verbo = "liberado" if aplicar else "liberaría"
        print(
            "  {:<34} {} {:.1f} MiB en {} archivo(s)".format(
                "papelera de reciclaje:", verbo, liberados / float(MIB), contados
            )
        )
    elif not ES_MACOS:
        liberados = recortar_journal(aplicar)
        total_bytes += liberados
        verbo = "recortado" if aplicar else "recortaría"
        print(
            "  {:<34} {} {:.1f} MiB".format(
                "journal de systemd:", verbo, liberados / float(MIB)
            )
        )

    print("")
    print("== Resultado ==")
    print(
        "  total {}: {:.2f} GB en {} archivo(s)".format(
            "liberado" if aplicar else "que se liberaría",
            total_bytes / float(1024**3),
            total_archivos,
        )
    )

    if aplicar and libre_antes is not None:
        libre_despues = espacio_libre(raiz_sistema)
        if libre_despues is not None:
            print("  libre después: {:.2f} GB".format(libre_despues / float(1024**3)))
            # Verificación por efecto: el espacio libre real, no la suma de tamaños.
            # Difieren cuando hay archivos en uso que no se pudieron borrar.
            ganado = libre_despues - libre_antes
            print(
                "  ganancia medida en disco: {:.2f} GB".format(ganado / float(1024**3))
            )
            if ganado < total_bytes * 0.5:
                print("")
                print("  La ganancia real es bastante menor a lo contado: parte de los")
                print("  archivos estaban en uso y no se pudieron borrar.")
    elif not aplicar:
        print("")
        print("  No se borró nada. Volvé a correr con el argumento 'aplicar'.")

    print("")
    print("LIBERADO_MIB={:.1f}".format(total_bytes / float(MIB)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
