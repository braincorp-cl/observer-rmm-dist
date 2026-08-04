#!/usr/bin/env python3
"""Diagnostico del agente ObserverRMM y del agente Mesh.

Solo LEE: no instala, no reinicia y no modifica configuracion. Reporta plataforma,
rutas de instalacion, configuracion efectiva (con el token enmascarado), estado de
los servicios, alcanzabilidad TCP de la API y de NATS, y frescura de los logs.

Sale con 0 si todo lo critico esta sano y con 1 si algo falla, para que sirva
tambien como check de script.

Sin argumentos. Solo biblioteca estandar: corre con el Python embebido del agente
en Windows y con el interprete del sistema en Linux y macOS.
"""

import json
import os
import platform
import socket
import subprocess
import sys
import time

# El agente pasa el stdout por strings.ToValidUTF8(s, "") (agent/utils.go:401), que BORRA
# toda secuencia UTF-8 invalida. En Windows el Python embebido escribe stdout en cp1252
# (medido en un Windows 11 real: sys.stdout.encoding == "cp1252"), donde un acento es un
# solo byte que no es UTF-8 valido => los acentos desaparecian de la salida sin dejar
# rastro. En Linux y macOS stdout ya es UTF-8 y esto es un no-op.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# Rutas, servicios y claves de configuracion tomados del codigo del agente
# (agent/agent.go:85-102, agent/install_unix.go:25-42, main.go:186-188). Si el
# agente los cambia, este script queda desalineado: es la misma trampa que dejo
# a macos_fix_mesh_install.sh apuntando a una ruta que no existia.
SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_MACOS = SISTEMA == "Darwin"

CLAVE_REGISTRO = r"SOFTWARE\ObserverRMM"
CONFIG_UNIX = "/etc/observeragent"

TIEMPO_ESPERA_TCP = 5

fallas = []


def titulo(texto):
    print("")
    print("== {} ==".format(texto))


def linea(etiqueta, valor):
    print("  {:<28} {}".format(etiqueta + ":", valor))


def falla(mensaje):
    fallas.append(mensaje)
    return "FALLA"


def correr(argumentos):
    """Ejecuta un comando y devuelve (rc, salida). Nunca lanza excepcion."""
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        return proceso.returncode, proceso.stdout.decode("utf-8", "replace").strip()
    except Exception as error:
        return 1, "no se pudo ejecutar ({})".format(error)


def enmascarar(valor):
    if not valor:
        return "(vacio)"
    if len(valor) <= 8:
        return "***"
    return valor[:4] + "..." + valor[-4:]


def leer_config():
    """Devuelve la configuracion del agente como dict de claves en minusculas."""
    if ES_WINDOWS:
        import winreg

        config = {}
        try:
            clave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLAVE_REGISTRO)
        except OSError:
            return config
        for nombre in (
            "BaseURL",
            "ApiURL",
            "AgentID",
            "Token",
            "AgentPK",
            "Proxy",
            "MeshDir",
            "WinTmpDir",
            "NatsStandardPort",
            "NatsProxyPort",
        ):
            try:
                config[nombre.lower()] = winreg.QueryValueEx(clave, nombre)[0]
            except OSError:
                pass
        clave.Close()
        return config

    if not os.path.isfile(CONFIG_UNIX):
        return {}
    try:
        with open(CONFIG_UNIX, "r") as archivo:
            crudo = json.load(archivo)
    except Exception:
        return {}
    return dict((str(k).lower(), v) for k, v in crudo.items())


def rutas_agente():
    if ES_WINDOWS:
        archivos_programa = os.environ.get("ProgramFiles", r"C:\Program Files")
        datos_programa = os.environ.get("ProgramData", r"C:\ProgramData")
        return {
            "directorio del agente": os.path.join(archivos_programa, "ObserverAgent"),
            "binario del agente": os.path.join(
                archivos_programa, "ObserverAgent", "observeragent.exe"
            ),
            "directorio del Mesh": os.path.join(archivos_programa, "Mesh Agent"),
            "temporal del agente": os.path.join(datos_programa, "ObserverRMM"),
            "log del agente": os.path.join(
                archivos_programa, "ObserverAgent", "agent.log"
            ),
        }
    return {
        "directorio del agente": "/opt/observeragent",
        "binario del agente": binario_agente_unix(),
        "directorio del Mesh": "/opt/observermesh",
        "configuracion": CONFIG_UNIX,
        "log del agente": "/var/log/observeragent.log",
    }


def binario_agente_unix():
    """Ruta real del binario del agente, resuelta y no asumida.

    No esta en el mismo lugar en todos los paquetes: medido en un host Fedora 44
    (RPM) el binario vive en /usr/local/bin/observeragent, mientras que las
    constantes del agente apuntan a /opt/observeragent/observeragent. Asumir una
    sola ruta hacia que este diagnostico reportara una FALLA falsa en toda la
    flota RPM, que es justo lo que vuelve inservible a un script de diagnostico.

    La fuente autoritativa es el ExecStart del servicio: es el binario que el
    sistema arranca de verdad. Las rutas conocidas quedan como respaldo.
    """
    for unidad in (
        "/etc/systemd/system/observeragent.service",
        "/lib/systemd/system/observeragent.service",
        "/usr/lib/systemd/system/observeragent.service",
    ):
        if not os.path.isfile(unidad):
            continue
        try:
            with open(unidad, "r") as archivo:
                for renglon in archivo:
                    if not renglon.strip().startswith("ExecStart="):
                        continue
                    orden = renglon.split("=", 1)[1].strip()
                    candidato = orden.split()[0] if orden else ""
                    if candidato and os.path.exists(candidato):
                        return candidato
        except OSError:
            continue

    # macOS: el plist lleva el binario como primer argumento.
    if ES_MACOS and os.path.isfile("/Library/LaunchDaemons/observeragent.plist"):
        try:
            import plistlib

            with open("/Library/LaunchDaemons/observeragent.plist", "rb") as archivo:
                argumentos = plistlib.load(archivo).get("ProgramArguments") or []
            if argumentos and os.path.exists(str(argumentos[0])):
                return str(argumentos[0])
        except Exception:
            pass

    for conocida in (
        "/opt/observeragent/observeragent",
        "/usr/local/bin/observeragent",
        "/usr/bin/observeragent",
    ):
        if os.path.exists(conocida):
            return conocida

    # Ninguna existe: se devuelve la ruta canonica para que el reporte diga cual
    # se busco, en vez de mentir con una que tampoco esta.
    return "/opt/observeragent/observeragent"


def estado_servicios_windows():
    """Estado de los servicios del agente y del Mesh, en ingles y de una sola pasada.

    NO se parsea `sc query`: su salida esta localizada (en un Windows en espanol la
    etiqueta es ESTADO, no STATE), asi que buscar "STATE" devolvia "estado no
    reconocido" y el diagnostico inventaba un problema. Medido en dos Windows 11 en
    espanol. La propiedad State de Win32_Service es una enumeracion fija en ingles,
    independiente del idioma del sistema.
    """
    consulta = (
        "Get-CimInstance Win32_Service "
        "-Filter \"Name='observeragent' OR Name='mesh agent'\" | "
        "Select-Object Name, State | ConvertTo-Json -Compress"
    )
    # correr() devuelve la tupla (rc, salida): desempaquetarla, no usarla entera.
    rc, salida = correr(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", consulta]
    )
    if rc != 0 or not salida:
        return {}

    try:
        crudo = json.loads(salida)
    except ValueError:
        return {}

    if isinstance(crudo, dict):
        crudo = [crudo]

    estados = {}
    for item in crudo:
        nombre = str(item.get("Name") or "").lower()
        estado = item.get("State")
        if nombre and estado:
            estados[nombre] = str(estado)
    return estados


def estado_servicio(nombre_windows, unidad_systemd, etiqueta_launchd, cache=None):
    """Estado del servicio en la plataforma actual, o None si no se pudo leer."""
    if ES_WINDOWS:
        if cache is None:
            cache = estado_servicios_windows()
        return cache.get(nombre_windows.lower())

    if ES_MACOS:
        rc, _ = correr(["launchctl", "list", etiqueta_launchd])
        return "cargado" if rc == 0 else "no cargado"

    rc, salida = correr(["systemctl", "is-active", unidad_systemd])
    return salida if salida else None


def alcanzable(anfitrion, puerto):
    inicio = time.time()
    try:
        conexion = socket.create_connection((anfitrion, int(puerto)), TIEMPO_ESPERA_TCP)
        conexion.close()
        return True, int((time.time() - inicio) * 1000)
    except Exception as error:
        return False, str(error)


def idioma_del_sistema():
    """Idioma en que este equipo responde, y pagina de codigos de su consola.

    En una flota mixta importa saberlo: es lo que decide si un servicio se reporta
    como "Detenido" o como "Stopped", y si la salida de una herramienta nativa llega
    traducida. Los scripts de esta biblioteca estan escritos para no depender de eso
    (comparan contra SID, GUID, enums y codigos numericos, nunca contra el texto
    traducido), pero cuando algo falla en un solo equipo de la flota este dato suele
    ser la primera pista.
    """
    if SISTEMA != "Windows":
        idioma = os.environ.get("LANG") or os.environ.get("LC_ALL") or "(sin LANG)"
        return idioma, None

    idioma = "(desconocido)"
    try:
        import ctypes

        # GetUserDefaultUILanguage devuelve el LCID de la interfaz, no el del formato
        # regional: es el que determina en que idioma responden las herramientas.
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        buf = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.LCIDToLocaleName(lcid, buf, 85, 0):
            idioma = buf.value
        else:
            idioma = "LCID {}".format(lcid)
    except Exception:
        pass

    pagina = None
    try:
        import ctypes

        pagina = ctypes.windll.kernel32.GetOEMCP()
    except Exception:
        pass

    return idioma, pagina


def informar_plataforma():
    titulo("Plataforma")
    linea("sistema", "{} {}".format(SISTEMA, platform.release()))
    linea("equipo", platform.node())
    linea("arquitectura", platform.machine())
    linea("python del script", platform.python_version())

    idioma, pagina = idioma_del_sistema()
    linea("idioma del sistema", idioma)
    if pagina:
        linea("pagina de codigos", "OEM {}".format(pagina))


def informar_rutas():
    titulo("Rutas de instalacion")
    for etiqueta, ruta in rutas_agente().items():
        if os.path.exists(ruta):
            linea(etiqueta, "OK  {}".format(ruta))
        else:
            estado = falla("no existe {} ({})".format(etiqueta, ruta))
            linea(etiqueta, "{} {}".format(estado, ruta))


def informar_config(config):
    titulo("Configuracion del agente")
    if not config:
        origen = CLAVE_REGISTRO if ES_WINDOWS else CONFIG_UNIX
        linea(
            "configuracion",
            "{} no se pudo leer ({})".format(
                falla("configuracion del agente ilegible"), origen
            ),
        )
        return
    linea("URL de la consola", config.get("baseurl", "(ausente)"))
    linea("host de la API", config.get("apiurl", "(ausente)"))
    linea("ID del agente", config.get("agentid", "(ausente)"))
    linea("PK del agente", config.get("agentpk", "(ausente)"))
    linea("token", enmascarar(str(config.get("token", ""))))
    linea("proxy", config.get("proxy") or "(sin proxy)")
    puerto_nats = config.get("natsstandardport")
    linea("NATS", "TCP {}".format(puerto_nats) if puerto_nats else "websockets (443)")


def informar_servicios():
    titulo("Servicios")

    # En Windows los dos servicios se consultan de una sola pasada: cada llamada a
    # PowerShell cuesta un arranque de proceso.
    cache = estado_servicios_windows() if ES_WINDOWS else None

    estado_agente = estado_servicio(
        "observeragent", "observeragent.service", "observeragent", cache
    )
    if estado_agente is None:
        linea("agente ObserverRMM", falla("servicio del agente no encontrado"))
    else:
        sano = any(
            marca in estado_agente.lower() for marca in ("running", "active", "cargado")
        )
        if not sano:
            falla("servicio del agente no esta corriendo ({})".format(estado_agente))
        linea("agente ObserverRMM", estado_agente)

    estado_mesh = estado_servicio("mesh agent", "meshagent.service", "meshagent", cache)
    if estado_mesh is None:
        # El Mesh puede faltar legitimamente (instalacion con -nomesh): se avisa,
        # pero no se cuenta como falla del agente.
        linea("agente Mesh", "AVISO no encontrado (instalado con -nomesh?)")
    else:
        linea("agente Mesh", estado_mesh)


def informar_conectividad(config):
    titulo("Conectividad")
    anfitrion = config.get("apiurl")
    if not anfitrion:
        linea("API", falla("sin host de API en la configuracion"))
        return
    ok, detalle = alcanzable(anfitrion, 443)
    if ok:
        linea("API (TCP 443)", "OK  {} en {} ms".format(anfitrion, detalle))
    else:
        linea(
            "API (TCP 443)",
            "{} {} ({})".format(falla("API inalcanzable en 443"), anfitrion, detalle),
        )

    puerto_nats = config.get("natsstandardport")
    if puerto_nats:
        ok, detalle = alcanzable(anfitrion, puerto_nats)
        if ok:
            linea("NATS (TCP {})".format(puerto_nats), "OK  en {} ms".format(detalle))
        else:
            linea(
                "NATS (TCP {})".format(puerto_nats),
                "{} ({})".format(
                    falla("NATS inalcanzable en {}".format(puerto_nats)), detalle
                ),
            )
    else:
        # Sin puerto TCP configurado el agente habla NATS por websockets sobre el
        # mismo 443 que ya se probo arriba, asi que no hay un segundo socket que medir.
        linea("NATS (websockets)", "va por el 443 ya verificado")


def informar_logs():
    titulo("Logs")
    for etiqueta, ruta in rutas_agente().items():
        if "log" not in etiqueta:
            continue
        if not os.path.isfile(ruta):
            linea(etiqueta, "no existe todavia  {}".format(ruta))
            continue
        edad_minutos = int((time.time() - os.path.getmtime(ruta)) / 60)
        linea(
            etiqueta,
            "{} KiB, ultima escritura hace {} min".format(
                os.path.getsize(ruta) // 1024, edad_minutos
            ),
        )


def main():
    print("Diagnostico del agente ObserverRMM")
    informar_plataforma()
    informar_rutas()
    config = leer_config()
    informar_config(config)
    informar_servicios()
    informar_conectividad(config)
    informar_logs()

    titulo("Resultado")
    if fallas:
        print("  {} problema(s) detectado(s):".format(len(fallas)))
        for problema in fallas:
            print("   - {}".format(problema))
        return 1
    print("  Sin problemas detectados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
