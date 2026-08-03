#!/usr/bin/env python3
"""Número de serie y datos del BIOS/firmware del equipo.

Solo LEE. Pensado para alimentar un campo personalizado (por ejemplo el serial,
para cruzarlo con inventario o garantías) desde las tres plataformas con un solo
script, en vez de uno por sistema operativo.

Imprime pares `clave: valor` y, al final, una línea `SERIAL=<valor>` fácil de
capturar. Sale con 1 si no logró determinar el número de serie.

Sin argumentos. Solo biblioteca estándar.
"""

import json
import os
import platform
import re
import subprocess
import sys

SISTEMA = platform.system()

VALORES_BASURA = {
    "",
    "0",
    "none",
    "n/a",
    "na",
    "default string",
    "to be filled by o.e.m.",
    "system serial number",
    "not specified",
    "not available",
    "unknown",
}


def correr(argumentos):
    try:
        proceso = subprocess.run(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        if proceso.returncode != 0:
            return None
        return proceso.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return None


def util(valor):
    """Descarta los rellenos que los fabricantes dejan en el DMI."""
    if valor is None:
        return None
    limpio = str(valor).strip()
    if limpio.lower() in VALORES_BASURA:
        return None
    return limpio


def datos_windows():
    datos = {}

    # El serial vive en Win32_BIOS y no en el registro, así que hay que pasar por
    # CIM. Se piden todos los campos de una sola vez para no pagar varios arranques
    # de PowerShell.
    consulta = (
        "$b = Get-CimInstance Win32_BIOS; "
        "$s = Get-CimInstance Win32_ComputerSystem; "
        "[pscustomobject]@{"
        "serial=$b.SerialNumber; bios_version=$b.SMBIOSBIOSVersion; "
        "bios_fabricante=$b.Manufacturer; bios_fecha=$b.ReleaseDate; "
        "fabricante=$s.Manufacturer; modelo=$s.Model; "
        "familia=$s.SystemFamily} | ConvertTo-Json -Compress"
    )
    salida = correr(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", consulta]
    )
    if salida:
        try:
            crudo = json.loads(salida)
            for clave, valor in crudo.items():
                if util(valor):
                    datos[clave] = str(valor).strip()
        except ValueError:
            pass

    # Respaldo por registro para los campos que no necesitan CIM: sirve si
    # PowerShell está restringido por política.
    if "bios_version" not in datos:
        try:
            import winreg

            clave = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS"
            )
            for nombre, destino in (
                ("BIOSVersion", "bios_version"),
                ("BIOSVendor", "bios_fabricante"),
                ("BIOSReleaseDate", "bios_fecha"),
                ("SystemManufacturer", "fabricante"),
                ("SystemProductName", "modelo"),
            ):
                try:
                    valor = util(winreg.QueryValueEx(clave, nombre)[0])
                    if valor and destino not in datos:
                        datos[destino] = valor
                except OSError:
                    pass
            clave.Close()
        except Exception:
            pass

    return datos


def datos_linux():
    # /sys/class/dmi/id lo expone el kernel; product_serial requiere root, que es
    # como corre el agente.
    campos = {
        "serial": "product_serial",
        "fabricante": "sys_vendor",
        "modelo": "product_name",
        "familia": "product_family",
        "bios_version": "bios_version",
        "bios_fabricante": "bios_vendor",
        "bios_fecha": "bios_date",
        "placa_fabricante": "board_vendor",
        "placa_modelo": "board_name",
    }
    datos = {}
    for clave, archivo in campos.items():
        ruta = os.path.join("/sys/class/dmi/id", archivo)
        try:
            with open(ruta, "r") as manejador:
                valor = util(manejador.read())
                if valor:
                    datos[clave] = valor
        except Exception:
            continue

    if "serial" not in datos:
        salida = correr(["dmidecode", "-s", "system-serial-number"])
        if util(salida):
            datos["serial"] = salida.strip()
    return datos


def datos_macos():
    datos = {}
    salida = correr(["system_profiler", "-json", "SPHardwareDataType"])
    if salida:
        try:
            bloque = json.loads(salida)["SPHardwareDataType"][0]
            mapa = {
                "serial": "serial_number",
                "modelo": "machine_model",
                "familia": "machine_name",
                "bios_version": "boot_rom_version",
                "chip": "chip_type",
            }
            for clave, origen in mapa.items():
                if util(bloque.get(origen)):
                    datos[clave] = str(bloque[origen]).strip()
            datos.setdefault("fabricante", "Apple")
        except Exception:
            pass

    if "serial" not in datos:
        # ioreg no depende de system_profiler y es más rápido.
        salida = correr(["ioreg", "-l"])
        if salida:
            encontrado = re.search(r'"IOPlatformSerialNumber"\s*=\s*"([^"]+)"', salida)
            if encontrado and util(encontrado.group(1)):
                datos["serial"] = encontrado.group(1)
    return datos


def main():
    if SISTEMA == "Windows":
        datos = datos_windows()
    elif SISTEMA == "Darwin":
        datos = datos_macos()
    else:
        datos = datos_linux()

    print("Inventario de hardware — {} {}".format(SISTEMA, platform.release()))
    print("  equipo:                      {}".format(platform.node()))
    print("  arquitectura:                {}".format(platform.machine()))
    for clave in sorted(datos):
        print("  {:<28} {}".format(clave + ":", datos[clave]))

    serial = datos.get("serial")
    print("")
    if serial:
        print("SERIAL={}".format(serial))
        return 0

    print("SERIAL=")
    print("No se pudo determinar el número de serie en este equipo.")
    if SISTEMA == "Linux":
        print("En Linux suele requerir root o un DMI incompleto (frecuente en VM).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
