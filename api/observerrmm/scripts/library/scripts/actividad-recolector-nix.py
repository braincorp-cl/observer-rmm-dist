#!/usr/bin/env python3
"""Observer Actividad - recolector para macOS y Linux (feature 048).

Equivalente de actividad-recolector.ps1: lee los TSV que deja el muestreador en el
home de cada usuario y emite por stdout UNA linea JSON con el resumen por usuario y
por dia. Se usa como TAREA PROGRAMADA con el nombre exacto
"Observer Actividad - Recolector" (cada corrida queda en el historial del agente y
de ahi la leen las plantillas de reporte).

Emite los dias cerrados que aun no informo (hasta --max-dias) y guarda la marca en
el directorio de instalacion, asi un equipo apagado entrega al encender sin
duplicar. El formato de salida y la regla de huecos son los mismos que en Windows;
ver la cabecera de actividad-recolector.ps1.

Uso:
    actividad-recolector-nix.py [--hoy] [--max-dias 7] [--reiniciar]
"""

import argparse
import datetime as dt
import glob
import json
import os
import platform
import socket
import sys
import time

TOP_HORA = 5
TOP_PROCS = 25
TOP_TITULOS = 10
MAX_SALIDA = 60000

if platform.system() == "Darwin":
    SO = "macos"
    BASE = "/Library/Application Support/ObserverActividad"
    REL_DATOS = "Library/Application Support/ObserverActividad"
    HOMES = "/Users/*"
else:
    SO = "linux"
    BASE = "/opt/observer-actividad"
    REL_DATOS = ".local/share/observer-actividad"
    HOMES = "/home/*"

MARCA = os.path.join(BASE, "recolector.json")


def raices():
    for home in sorted(glob.glob(HOMES)):
        raiz = os.path.join(home, REL_DATOS)
        if os.path.isdir(raiz):
            yield raiz


def top(tabla, n):
    orden = sorted(tabla.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    return {k: int(round(v)) for k, v in orden}


def epoch(ts):
    return int(time.mktime(ts.timetuple()))


def resumir(archivo, dir_capturas):
    por_usuario = {}
    previo = {}
    with open(archivo, encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            c = linea.rstrip("\n").split("\t")
            if len(c) < 5:
                continue
            try:
                ts = dt.datetime.strptime(c[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
            u = c[1]
            r = por_usuario.setdefault(
                u,
                {
                    "primero": ts,
                    "ultimo": ts,
                    "activo": 0.0,
                    "inactivo": 0.0,
                    "huecos": 0.0,
                    "horas": {},
                    "procs": {},
                    "titulos": {},
                    "nota": "",
                },
            )
            titulo = c[5] if len(c) > 5 else ""
            if c[2] == "#nota":
                r["nota"] = titulo
                continue
            if c[2] == "#inicio":
                ant = previo.get(u)
                if ant:
                    hueco = (ts - ant[0]).total_seconds() - ant[1]
                    if hueco > 2 * ant[1]:
                        datos = dict(
                            p.split("=", 1) for p in titulo.split(";") if "=" in p
                        )
                        try:
                            boot = int(datos.get("boot", 0))
                            sesion = int(datos.get("sesion", 0))
                        except ValueError:
                            boot = sesion = 0
                        ant_epoch = epoch(ant[0])
                        if boot <= ant_epoch and sesion <= ant_epoch:
                            r["huecos"] += min(hueco / 60, 240)
                continue
            try:
                i = int(c[4])
            except ValueError:
                continue
            if i <= 0:
                continue
            minutos = i / 60.0
            hh = ts.strftime("%H")
            celda = r["horas"].setdefault(hh, {"a": 0.0, "i": 0.0, "p": {}})
            if c[3] == "1":
                r["activo"] += minutos
                celda["a"] += minutos
                celda["p"][c[2]] = celda["p"].get(c[2], 0) + minutos
                r["procs"][c[2]] = r["procs"].get(c[2], 0) + minutos
                if titulo:
                    r["titulos"][titulo] = r["titulos"].get(titulo, 0) + minutos
            else:
                r["inactivo"] += minutos
                celda["i"] += minutos
            r["primero"] = min(r["primero"], ts)
            r["ultimo"] = max(r["ultimo"], ts)
            previo[u] = (ts, i)

    capturas = len(glob.glob(os.path.join(dir_capturas, "*.jpg")))
    salida = []
    for u, r in por_usuario.items():
        if r["activo"] + r["inactivo"] <= 0 and not r["nota"]:
            continue
        item = {
            "usuario": u,
            "primero": r["primero"].strftime("%H:%M"),
            "ultimo": r["ultimo"].strftime("%H:%M"),
            "activo_min": int(round(r["activo"])),
            "inactivo_min": int(round(r["inactivo"])),
            "huecos_min": int(round(r["huecos"])),
            "capturas": capturas,
            "horas": {
                hh: {
                    "a": int(round(cel["a"])),
                    "i": int(round(cel["i"])),
                    "p": top(cel["p"], TOP_HORA),
                }
                for hh, cel in sorted(r["horas"].items())
            },
            "procs": top(r["procs"], TOP_PROCS),
            "titulos_top": [
                [t[:80], int(round(m))]
                for t, m in sorted(r["titulos"].items(), key=lambda kv: -kv[1])[
                    :TOP_TITULOS
                ]
            ],
        }
        if r["nota"]:
            item["nota"] = r["nota"]
        salida.append(item)
    return salida


def leer_marca(reiniciar):
    if reiniciar:
        return None
    try:
        with open(MARCA, encoding="utf-8") as fh:
            return dt.date.fromisoformat(json.load(fh)["ultimo"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hoy", action="store_true")
    ap.add_argument("--max-dias", type=int, default=7)
    ap.add_argument("--reiniciar", action="store_true")
    args = ap.parse_args()
    max_dias = min(max(args.max_dias, 1), 14)

    hoy = dt.date.today()
    ultimo = leer_marca(args.reiniciar)
    dias = [
        hoy - dt.timedelta(days=k)
        for k in range(max_dias, 0, -1)
        if ultimo is None or hoy - dt.timedelta(days=k) > ultimo
    ]
    if args.hoy:
        dias.append(hoy)

    zona = time.strftime("%z")
    tz = zona[:3] + ":" + zona[3:] if len(zona) == 5 else zona
    lista_raices = list(raices())

    salida_dias = []
    for d in dias:
        fecha = d.isoformat()
        usuarios = []
        for raiz in lista_raices:
            archivo = os.path.join(raiz, "datos", fecha + ".tsv")
            if not os.path.isfile(archivo):
                continue
            try:
                usuarios.extend(resumir(archivo, os.path.join(raiz, "capturas", fecha)))
            except OSError as exc:
                print("No se pudo leer {}: {}".format(archivo, exc), file=sys.stderr)
        if not usuarios:
            continue
        dia = {"fecha": fecha, "tz": tz, "usuarios": usuarios}
        if d == hoy:
            dia["parcial"] = True
        salida_dias.append(dia)

    doc = {"v": 1, "so": SO, "equipo": socket.gethostname(), "dias": salida_dias}
    texto = json.dumps(doc, ensure_ascii=True, separators=(",", ":"))
    if len(texto) > MAX_SALIDA:
        for dia in salida_dias:
            for u in dia["usuarios"]:
                u["titulos_top"] = []
                for cel in u["horas"].values():
                    cel["p"] = {}
        texto = json.dumps(doc, ensure_ascii=True, separators=(",", ":"))
    print(texto)

    if any(d < hoy for d in dias) and os.path.isdir(BASE):
        try:
            with open(MARCA, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "ultimo": (hoy - dt.timedelta(days=1)).isoformat(),
                        "corrida": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    },
                    fh,
                )
        except OSError as exc:
            print("No se pudo guardar la marca: {}".format(exc), file=sys.stderr)


if __name__ == "__main__":
    main()
