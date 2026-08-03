#!/usr/bin/env python3
"""Diagnóstico del agente ObserverRMM y del agente Mesh.

Solo LEE: no instala, no reinicia y no modifica configuración. Reporta plataforma,
rutas de instalación, configuración efectiva (con el token enmascarado), estado de
los servicios, alcanzabilidad TCP de la API y de NATS, y frescura de los logs.

Sale con 0 si todo lo crítico está sano y con 1 si algo falla, para que sirva
también como check de script.

Sin argumentos. Solo biblioteca estándar: corre con el Python embebido del agente
en Windows y con el intérprete del sistema en Linux y macOS.
"""

import json
import os
import platform
import socket
import subprocess
import sys
import time

# Rutas, servicios y claves de configuración tomados del código del agente
# (agent/agent.go:85-102, agent/install_unix.go:25-42, main.go:186-188). Si el
# agente los cambia, este script queda desalineado: es la misma trampa que dejó
# a macos_fix_mesh_install.sh apuntando a una ruta que no existía.
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
    """Ejecuta un comando y devuelve (rc, salida). Nunca lanza excepción."""
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
        return "(vacío)"
    if len(valor) <= 8:
        return "***"
    return valor[:4] + "..." + valor[-4:]


def leer_config():
    """Devuelve la configuración del agente como dict de claves en minúsculas."""
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
        "binario del agente": "/opt/observeragent/observeragent",
        "directorio del Mesh": "/opt/observermesh",
        "configuración": CONFIG_UNIX,
        "log del agente": "/var/log/observeragent.log",
    }


def estado_servicio(nombre_windows, unidad_systemd, etiqueta_launchd):
    """Estado del servicio en la plataforma actual, o None si no se pudo leer."""
    if ES_WINDOWS:
        rc, salida = correr(["sc", "query", nombre_windows])
        if rc != 0:
            return None
        for renglon in salida.splitlines():
            if "STATE" in renglon.upper():
                return renglon.split(":")[-1].strip()
        return "estado no reconocido"

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


def informar_plataforma():
    titulo("Plataforma")
    linea("sistema", "{} {}".format(SISTEMA, platform.release()))
    linea("equipo", platform.node())
    linea("arquitectura", platform.machine())
    linea("python del script", platform.python_version())


def informar_rutas():
    titulo("Rutas de instalación")
    for etiqueta, ruta in rutas_agente().items():
        if os.path.exists(ruta):
            linea(etiqueta, "OK  {}".format(ruta))
        else:
            estado = falla("no existe {} ({})".format(etiqueta, ruta))
            linea(etiqueta, "{} {}".format(estado, ruta))


def informar_config(config):
    titulo("Configuración del agente")
    if not config:
        origen = CLAVE_REGISTRO if ES_WINDOWS else CONFIG_UNIX
        linea(
            "configuración",
            "{} no se pudo leer ({})".format(
                falla("configuración del agente ilegible"), origen
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
    estado_agente = estado_servicio(
        "observeragent", "observeragent.service", "observeragent"
    )
    if estado_agente is None:
        linea("agente ObserverRMM", falla("servicio del agente no encontrado"))
    else:
        sano = any(
            marca in estado_agente.lower() for marca in ("running", "active", "cargado")
        )
        if not sano:
            falla("servicio del agente no está corriendo ({})".format(estado_agente))
        linea("agente ObserverRMM", estado_agente)

    estado_mesh = estado_servicio("mesh agent", "meshagent.service", "meshagent")
    if estado_mesh is None:
        # El Mesh puede faltar legítimamente (instalación con -nomesh): se avisa,
        # pero no se cuenta como falla del agente.
        linea("agente Mesh", "AVISO no encontrado (¿instalado con -nomesh?)")
    else:
        linea("agente Mesh", estado_mesh)


def informar_conectividad(config):
    titulo("Conectividad")
    anfitrion = config.get("apiurl")
    if not anfitrion:
        linea("API", falla("sin host de API en la configuración"))
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
        # mismo 443 que ya se probó arriba, así que no hay un segundo socket que medir.
        linea("NATS (websockets)", "va por el 443 ya verificado")


def informar_logs():
    titulo("Logs")
    for etiqueta, ruta in rutas_agente().items():
        if "log" not in etiqueta:
            continue
        if not os.path.isfile(ruta):
            linea(etiqueta, "no existe todavía  {}".format(ruta))
            continue
        edad_minutos = int((time.time() - os.path.getmtime(ruta)) / 60)
        linea(
            etiqueta,
            "{} KiB, última escritura hace {} min".format(
                os.path.getsize(ruta) // 1024, edad_minutos
            ),
        )


def main():
    print("Diagnóstico del agente ObserverRMM")
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
