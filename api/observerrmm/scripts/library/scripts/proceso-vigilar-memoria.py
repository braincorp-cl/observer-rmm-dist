#!/usr/bin/env python3
"""Vigila el consumo de memoria de un proceso y alerta si pasa un umbral.

Reemplaza el script de Windows del catálogo original por uno que corre en las tres
plataformas, porque una fuga de memoria no es un problema exclusivo de Windows.

Para qué sirve de verdad: como check programado sobre un proceso que se sabe con
tendencia a fugar (un servicio propio, un motor de base de datos, un navegador en un
kiosco). Sale con código 1 cuando el proceso supera el umbral, así la consola genera
la alerta sola en vez de que alguien tenga que ir a mirar.

Suma la memoria de TODOS los procesos con ese nombre, no solo del primero. Es
deliberado: los navegadores y muchos servicios se reparten en decenas de procesos hijos
y mirar solo uno da una cifra tranquilizadora y falsa.

No usa psutil: en Windows lee la memoria por CIM y en Linux/macOS por `ps`, así que
funciona con el Python embebido del agente sin instalar nada.

Uso:
    proceso-vigilar-memoria.py <nombre_proceso> [umbral_MiB]

Ejemplos:
    proceso-vigilar-memoria.py chrome 4096
    proceso-vigilar-memoria.py postgres
    proceso-vigilar-memoria.py                (lista los 15 que más consumen)
"""

import json
import platform
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

UMBRAL_POR_DEFECTO_MIB = 2048
MIB = 1024 * 1024
CANTIDAD_TOP = 15


def correr(argumentos):
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        if proceso.returncode != 0:
            return None
        return proceso.stdout.decode("utf-8", "replace")
    except Exception:
        return None


def procesos_windows():
    """Devuelve [(nombre, pid, bytes_memoria)] leyendo por CIM.

    WorkingSetSize es la memoria física que el proceso tiene asignada, que es la que
    importa para "este proceso se está comiendo la RAM". VirtualSize incluiría espacio
    reservado y nunca tocado, que infla la cifra sin significar nada.
    """
    consulta = (
        "Get-CimInstance Win32_Process | "
        "Select-Object Name, ProcessId, WorkingSetSize | "
        "ConvertTo-Json -Compress"
    )
    salida = correr(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", consulta]
    )
    if not salida:
        return None

    try:
        crudo = json.loads(salida)
    except ValueError:
        return None

    if isinstance(crudo, dict):
        crudo = [crudo]

    resultado = []
    for item in crudo:
        nombre = item.get("Name") or ""
        # Se saca la extensión para que el usuario pueda pasar "chrome" y no
        # "chrome.exe", que es lo natural.
        if nombre.lower().endswith(".exe"):
            nombre = nombre[:-4]
        try:
            resultado.append(
                (
                    nombre,
                    int(item.get("ProcessId") or 0),
                    int(item.get("WorkingSetSize") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return resultado


def procesos_unix():
    """Devuelve [(nombre, pid, bytes_memoria)] leyendo por ps.

    rss viene en kibibytes en Linux y en macOS, así que se multiplica por 1024.
    """
    salida = correr(["ps", "-eo", "pid=,rss=,comm="])
    if not salida:
        return None

    resultado = []
    for renglon in salida.splitlines():
        partes = renglon.split(None, 2)
        if len(partes) < 3:
            continue
        try:
            pid = int(partes[0])
            rss_kib = int(partes[1])
        except ValueError:
            continue
        # comm puede venir con la ruta completa en macOS: interesa el nombre final.
        nombre = partes[2].strip().split("/")[-1]
        resultado.append((nombre, pid, rss_kib * 1024))
    return resultado


def memoria_total():
    if ES_WINDOWS:
        salida = correr(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
            ]
        )
        if salida:
            try:
                return int(salida.strip())
            except ValueError:
                return 0
        return 0

    if SISTEMA == "Darwin":
        salida = correr(["sysctl", "-n", "hw.memsize"])
        if salida:
            try:
                return int(salida.strip())
            except ValueError:
                return 0
        return 0

    try:
        with open("/proc/meminfo", "r") as archivo:
            for renglon in archivo:
                if renglon.startswith("MemTotal:"):
                    return int(renglon.split()[1]) * 1024
    except Exception:
        pass
    return 0


def main():
    nombre_buscado = sys.argv[1] if len(sys.argv) > 1 else None

    umbral_mib = UMBRAL_POR_DEFECTO_MIB
    if len(sys.argv) > 2:
        try:
            umbral_mib = int(sys.argv[2])
        except ValueError:
            print("El umbral debe ser un número de MiB. Recibido:", sys.argv[2])
            return 1
        if umbral_mib < 1:
            print("El umbral debe ser mayor que 0.")
            return 1

    procesos = procesos_windows() if ES_WINDOWS else procesos_unix()
    if procesos is None:
        print("No se pudo enumerar los procesos en este equipo.")
        return 1

    total_ram = memoria_total()

    print("Consumo de memoria — {} {}".format(SISTEMA, platform.release()))
    print("  equipo: {}".format(platform.node()))
    if total_ram:
        print("  RAM total: {:.1f} GiB".format(total_ram / float(1024**3)))

    if not nombre_buscado:
        # Sin argumento: se agrupa por nombre y se muestran los mayores. Sirve para
        # descubrir quién se está comiendo la memoria antes de saber a quién vigilar.
        agrupados = {}
        for nombre, _, bytes_memoria in procesos:
            agrupados[nombre] = agrupados.get(nombre, 0) + bytes_memoria

        print("")
        print("== Los {} procesos que más memoria consumen ==".format(CANTIDAD_TOP))
        ordenados = sorted(agrupados.items(), key=lambda par: par[1], reverse=True)
        for nombre, bytes_memoria in ordenados[:CANTIDAD_TOP]:
            porcentaje = ""
            if total_ram:
                porcentaje = "  ({:.1f}% de la RAM)".format(
                    100.0 * bytes_memoria / total_ram
                )
            print(
                "  {:<32} {:>9.1f} MiB{}".format(
                    nombre, bytes_memoria / float(MIB), porcentaje
                )
            )
        print("")
        print("Pasá un nombre de proceso como argumento para vigilarlo con umbral.")
        return 0

    objetivo = nombre_buscado.lower()
    if objetivo.endswith(".exe"):
        objetivo = objetivo[:-4]

    coincidencias = [p for p in procesos if p[0].lower() == objetivo]

    print("")
    print("== Proceso '{}' ==".format(nombre_buscado))

    if not coincidencias:
        # Un proceso ausente no es un exceso de memoria: se informa y se sale con 0.
        # Alertar acá confundiría "se cayó" con "consume mucho", que son incidentes
        # distintos y el check que corresponde es otro.
        print("  No hay ningún proceso con ese nombre corriendo ahora.")
        print("")
        print("  Ojo: esto NO es una alerta de memoria. Si te interesa saber que el")
        print("  proceso está caído, usá un check de servicio, no este script.")
        print("")
        print("PROCESOS=0")
        print("MEMORIA_MIB=0")
        return 0

    total_bytes = sum(p[2] for p in coincidencias)

    print("  instancias: {}".format(len(coincidencias)))
    print("  memoria total: {:.1f} MiB".format(total_bytes / float(MIB)))
    if total_ram:
        print("  porcentaje de la RAM: {:.1f}%".format(100.0 * total_bytes / total_ram))
    print("  umbral: {} MiB".format(umbral_mib))

    # Las instancias mayores, para ver si el consumo está concentrado en una que fuga
    # o repartido entre muchas que es lo normal.
    print("")
    print("  Instancias que más consumen:")
    for nombre, pid, bytes_memoria in sorted(
        coincidencias, key=lambda p: p[2], reverse=True
    )[:5]:
        print("    pid {:<8} {:>9.1f} MiB".format(pid, bytes_memoria / float(MIB)))

    print("")
    print("PROCESOS={}".format(len(coincidencias)))
    print("MEMORIA_MIB={:.1f}".format(total_bytes / float(MIB)))

    print("")
    print("== Resultado ==")
    if total_bytes > umbral_mib * MIB:
        print(
            "  SUPERA el umbral: {:.1f} MiB > {} MiB".format(
                total_bytes / float(MIB), umbral_mib
            )
        )
        return 1

    print(
        "  Dentro del umbral: {:.1f} MiB de {} MiB".format(
            total_bytes / float(MIB), umbral_mib
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
