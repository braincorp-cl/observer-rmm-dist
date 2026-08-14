#!/usr/bin/env python3
"""Endurece el servicio del Mesh en Linux: le quita CAP_SYS_MODULE.

QUE PROBLEMA RESUELVE

El MeshAgent ejecuta 'lshw -class disk' como parte de su inventario. lshw hace un
ioctl de red con el nombre de interfaz "/dev/vmnet1"; dev_load() del kernel intenta
autocargar el modulo dos veces y el SEGUNDO intento --request_module("%s", name)--
solo ocurre si el llamador tiene CAP_SYS_MODULE. Ese intento lanza
'modprobe -q -- /dev/vmnet1', que abre esa ruta como si fuera un .ko y se bloquea
para siempre dentro del driver vmnet de VMware Workstation. lshw queda en estado D,
el agente se queda esperando a ese hijo y DEJA DE LEER los mensajes del servidor: el
equipo aparece EN LINEA Y SORDO, sin "Tomar control" y sin ningun sintoma que lo
delate. Medido el 2026-08-14; el testigo es el Recv-Q del socket agente->servidor.

POR QUE EN TODOS LOS EQUIPOS Y NO SOLO DONDE HAY VMWARE

El disparador viaja en el core de ARRANQUE del propio MeshAgent, dentro del binario
oficial: corre a los ~0,7 s de cada inicio con la forma vieja del comando, y recien
~3 s despues toma el relevo el core bueno, que ya usa '-disable network' y no cuelga.
Ni actualizar el agente ni refrescar el core evitan el disparador, porque ocurre
antes. Y la exposicion no es "tener VMware hoy" sino adquirir cualquier driver que se
bloquee en request_module.

Es seguro: el MeshAgent no carga modulos del kernel.

QUE HACE

Escribe /etc/systemd/system/meshagent.service.d/10-meshagent-hardening.conf, recarga
systemd y reinicia el servicio. Es idempotente: si el archivo ya esta con el
contenido correcto y la capability ya no esta, no toca nada.

El reinicio corta las sesiones de control remoto abiertas contra ESTE equipo (unos
segundos). Con --solo-verificar no se escribe ni se reinicia nada.

VERIFICACION

No basta con que el archivo exista: se lee CapBnd del proceso vivo y se comprueba que
el bit 16 (CAP_SYS_MODULE) quedo en 0. Sale 1 si no se pudo confirmar.

Uso:
    agente-mesh-endurecer.py
    agente-mesh-endurecer.py --solo-verificar
"""

import os
import platform
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVICIO = "meshagent.service"
DIRECTORIO = "/etc/systemd/system/{}.d".format(SERVICIO)
ARCHIVO = os.path.join(DIRECTORIO, "10-meshagent-hardening.conf")
BIT_CAP_SYS_MODULE = 16

CONTENIDO = """# Escrito por el script 'Agente - Endurecer el servicio Mesh' de Observer RMM.
# Sin esta linea, un `lshw` del agente puede quedar en estado D dentro de un driver
# que se porte mal y dejar al equipo en linea pero sordo al servidor.
# Reportado aguas arriba al proyecto del agente.
[Service]
CapabilityBoundingSet=~CAP_SYS_MODULE
TimeoutStopSec=20
"""


def correr(argumentos, plazo=60):
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=plazo,
        )
        return proceso.returncode, proceso.stdout.decode("utf-8", "replace").strip()
    except Exception as error:
        return 1, str(error)


def pid_del_mesh():
    """PID del meshagent. Se busca por la ruta del binario y no por nombre: en
    algunos equipos el proceso aparece con argumentos y en otros no."""
    codigo, salida = correr(
        ["systemctl", "show", "-p", "MainPID", "--value", SERVICIO], 20
    )
    if codigo == 0 and salida.isdigit() and salida != "0":
        return int(salida)
    codigo, salida = correr(["pgrep", "-x", "meshagent"], 20)
    if codigo == 0 and salida.split():
        return int(salida.split()[0])
    return 0


def capability_presente(pid):
    """Devuelve True/False si se pudo leer, None si no.

    CapBnd es una mascara hexadecimal; se mira el bit, no el texto, porque el
    nombre de la capability no aparece en /proc."""
    try:
        with open("/proc/{}/status".format(pid), "r") as archivo:
            for linea in archivo:
                if linea.startswith("CapBnd:"):
                    mascara = int(linea.split()[1], 16)
                    return bool(mascara & (1 << BIT_CAP_SYS_MODULE))
    except Exception:
        return None
    return None


def directiva_puesta():
    """La directiva puede haberla dejado este script, el rol de Ansible o el
    instalador, y cada uno escribe su propia cabecera. Lo que importa es la
    directiva, no el texto del archivo: comparar contenidos completos haria que
    los tres vehiculos se pisaran el archivo en cada corrida."""
    for nombre in sorted(os.listdir(DIRECTORIO)) if os.path.isdir(DIRECTORIO) else []:
        if not nombre.endswith(".conf"):
            continue
        try:
            with open(os.path.join(DIRECTORIO, nombre), "r") as archivo:
                if "CapabilityBoundingSet=~CAP_SYS_MODULE" in archivo.read():
                    return True
        except Exception:
            continue
    return False


def capability_segun_systemd():
    """Lo que systemd tiene CONFIGURADO para la unidad. Es el segundo testigo:
    si el proceso vivo no se puede leer, esto al menos dice si el drop-in llego
    a la unidad o lo esta pisando otro override."""
    codigo, salida = correr(
        ["systemctl", "show", "-p", "CapabilityBoundingSet", "--value", SERVICIO], 20
    )
    if codigo != 0:
        return None
    return "cap_sys_module" in salida.lower()


def esperar_capability_ausente(intentos=8, espera=1.5):
    """Vuelve a leer el proceso vivo hasta que la capability se haya ido.

    Hay una ventana despues del restart en la que /proc todavia muestra el
    conjunto ANTERIOR: systemd hace fork, despues suelta la capability del
    bounding set y recien ahi exec. Leer una sola vez ahi dentro confunde esa
    ventana con un fallo real. Medido el 2026-08-14 en un equipo de la flota:
    el MISMO pid daba 'presente' al instante de aplicar y 'ausente' un minuto
    despues, con el drop-in bien puesto y systemd ya sin la capability."""
    pid = 0
    presente = None
    for intento in range(intentos):
        pid = pid_del_mesh()
        presente = capability_presente(pid) if pid else None
        if presente is False:
            return pid, presente
        if intento < intentos - 1:
            time.sleep(espera)
    return pid, presente


def procesos_colgados():
    """Procesos en estado D (ininterrumpible) que sean el sintoma conocido."""
    codigo, salida = correr(["ps", "-eo", "stat,pid,comm"], 20)
    if codigo != 0:
        return []
    colgados = []
    for linea in salida.splitlines()[1:]:
        partes = linea.split(None, 2)
        if len(partes) == 3 and partes[0].startswith("D"):
            if partes[2].strip() in ("lshw", "modprobe"):
                colgados.append("{} (pid {})".format(partes[2].strip(), partes[1]))
    return colgados


def main():
    solo_verificar = "--solo-verificar" in sys.argv

    if platform.system() != "Linux":
        print("Este script es especifico de Linux (systemd).")
        print("Sistema detectado: {}".format(platform.system()))
        return 1

    if not os.path.exists("/opt/observermesh/meshagent"):
        print(
            "Este equipo no tiene el agente Mesh instalado: no hay nada que endurecer."
        )
        return 0

    if os.geteuid() != 0:
        print("Hay que correrlo como root (el archivo va en /etc/systemd/system).")
        return 1

    print("== Estado inicial ==")
    pid = pid_del_mesh()
    presente = capability_presente(pid) if pid else None
    print("  PID del servicio      : {}".format(pid if pid else "no esta corriendo"))
    print(
        "  CAP_SYS_MODULE        : {}".format(
            {True: "presente", False: "ausente", None: "no se pudo leer"}[presente]
        )
    )
    ya_estaba = directiva_puesta()
    print("  Drop-in al dia        : {}".format("si" if ya_estaba else "no"))

    for colgado in procesos_colgados():
        print("  Proceso colgado en D  : {}".format(colgado))

    if solo_verificar:
        print("")
        print("== Resultado (solo verificacion, no se toco nada) ==")
        if ya_estaba and presente is False:
            print("  El equipo ya esta endurecido.")
            return 0
        print(
            "  Falta aplicar el endurecimiento: correr el script sin --solo-verificar."
        )
        return 1

    if ya_estaba and presente is False:
        print("")
        print("== Resultado ==")
        print("  Ya estaba endurecido: no se escribio nada ni se reinicio el servicio.")
        return 0

    print("")
    print("== Aplicando ==")
    if ya_estaba:
        # La directiva ya esta puesta por otra via --el rol de Ansible o el
        # instalador-- y solo falta que el servicio la tome. Reescribir el archivo
        # dejaria a los dos vehiculos pisandose el contenido en cada corrida.
        print("  La directiva ya estaba escrita: solo falta que el servicio la tome.")
    else:
        try:
            if not os.path.isdir(DIRECTORIO):
                os.makedirs(DIRECTORIO, mode=0o755)
            with open(ARCHIVO, "w") as archivo:
                archivo.write(CONTENIDO)
            os.chmod(ARCHIVO, 0o644)
            print("  Escrito {}".format(ARCHIVO))
        except Exception as error:
            print("  ERROR al escribir el drop-in: {}".format(error))
            return 1

    codigo, salida = correr(["systemctl", "daemon-reload"], 60)
    print("  daemon-reload         : {}".format("ok" if codigo == 0 else salida))
    codigo, salida = correr(["systemctl", "restart", SERVICIO], 120)
    print("  restart del servicio  : {}".format("ok" if codigo == 0 else salida))

    print("")
    print("== Verificacion sobre el proceso vivo ==")
    # El servicio recien arranco: el PID cambio y hay que volver a leerlo, y con
    # reintentos, porque el conjunto viejo sigue visible unos instantes. Un
    # `exit 0` del restart no prueba que la capability se haya ido.
    pid, presente = esperar_capability_ausente()
    en_systemd = capability_segun_systemd()
    print("  PID del servicio      : {}".format(pid if pid else "no esta corriendo"))
    print(
        "  CAP_SYS_MODULE        : {}".format(
            {True: "presente", False: "ausente", None: "no se pudo leer"}[presente]
        )
    )
    print(
        "  Segun la unidad       : {}".format(
            {True: "presente", False: "ausente", None: "no se pudo consultar"}[
                en_systemd
            ]
        )
    )

    print("")
    print("== Resultado ==")
    if presente is False:
        print("  Endurecido y confirmado sobre el proceso vivo.")
        return 0
    if presente is None:
        print("  El drop-in quedo escrito, pero no se pudo confirmar sobre el proceso.")
        print(
            "  Revisar que el servicio este corriendo y volver a correr con --solo-verificar."
        )
        return 1
    print("  El drop-in quedo escrito y la capability SIGUE presente en el proceso.")
    if en_systemd is False:
        print("  Pero la unidad ya NO la declara: el proceso es anterior al cambio.")
        print(
            "  Reiniciar el servicio otra vez, o volver a correr con --solo-verificar."
        )
    else:
        print(
            "  Y la unidad tambien la declara: hay otro override en el equipo,"
            " revisar 'systemctl cat {}'.".format(SERVICIO)
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
