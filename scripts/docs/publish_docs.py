#!/usr/bin/env python3
"""Publica docs-site/ en docs.observer.cl por WebDAV (PUT + MKCOL autenticados).

Lo corre el job publish-docs.yml en cada release. Sustituye al `sudo rsync` manual
desde el control-plane, que ataba la publicacion a un equipo concreto.

Solo biblioteca estandar: el runner no instala nada para esto.

Tres reglas que vienen de como quedo el vhost y de errores ya pagados:

1. El sitio se SINCRONIZA: lo que deja de existir en el repo se borra del docroot
   (DELETE autenticado en el vhost desde el 2026-10-26). Que hay publicado se sabe
   por el manifiesto que deja cada corrida, no por PROPFIND. Para que un checkout
   vacio o parcial no arrase el sitio, la purga se aborta si supera UMBRAL_PURGA de
   lo publicado; --purgar-igual lo fuerza cuando la baja es real.

2. Se sube solo lo que cambio. Para archivos de hasta LIMITE_SHA se compara el
   sha256 del cuerpo servido; mas arriba (videos) se compara el tamaño, porque
   descargar 30 MB en cada release para enterarse de que nada cambio es absurdo.

3. Despues de cada PUT se VERIFICA POR EFECTO: se pide el archivo al sitio publico
   y se compara su sha256 con el local. Un 201 no prueba que el contenido quedo
   servido; esa confusion ya dejo el changelog rezagado con los runs en verde.
"""

import argparse
import base64
import hashlib
import os
import sys
import re
import urllib.error
import urllib.parse
import urllib.request

LIMITE_SHA = 1024 * 1024  # 1 MiB
EXCLUIDOS = {"README.md", ".publish-manifest"}  # README: el vhost lo niega (topologia interna)
UMBRAL_PURGA = 0.25  # fraccion de lo publicado que la purga puede borrar sin forzar
TIMEOUT = 120


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def pedir(url, metodo, auth=None, cuerpo=None):
    req = urllib.request.Request(url, data=cuerpo, method=metodo)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


MANIFIESTO = ".publish-manifest"


def leer_manifiesto(base, auth):
    """Lo que la corrida anterior dejo publicado. None si todavia no hay manifiesto.

    No se usa PROPFIND: sobre una coleccion con index.html lo resuelve mod_dir y Apache
    responde 405, y forzar DirectoryIndex disabled para los demas metodos tumba la
    lectura publica (probado el 26-oct: el sitio entero quedo en 403).
    """
    code, cuerpo, _ = pedir(f"{base}/{MANIFIESTO}", "GET", auth)
    if code == 404:
        return None
    if code != 200:
        print(f"::error::GET del manifiesto devolvio {code}")
        return False
    return sorted(l.strip() for l in cuerpo.decode().splitlines() if l.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origen", default="docs-site")
    ap.add_argument("--base", default="https://docs.observer.cl")
    ap.add_argument("--usuario", default=os.environ.get("DOCS_UPLOAD_USER", ""))
    ap.add_argument("--clave", default=os.environ.get("DOCS_UPLOAD_PASSWORD", ""))
    ap.add_argument("--simular", action="store_true", help="dice que haria, sin escribir")
    ap.add_argument("--purgar-igual", action="store_true",
                    help="ejecuta la purga aunque supere el umbral (baja real de paginas)")
    args = ap.parse_args()

    if not args.simular and not (args.usuario and args.clave):
        print("::error::faltan DOCS_UPLOAD_USER / DOCS_UPLOAD_PASSWORD")
        return 1
    auth = f"{args.usuario}:{args.clave}"
    base = args.base.rstrip("/")

    archivos = []
    for raiz, _, nombres in os.walk(args.origen):
        for n in sorted(nombres):
            ruta = os.path.join(raiz, n)
            rel = os.path.relpath(ruta, args.origen).replace(os.sep, "/")
            if os.path.basename(rel) in EXCLUIDOS:
                continue
            archivos.append(rel)
    archivos.sort()
    if not archivos:
        print(f"::error::no hay archivos bajo {args.origen}")
        return 1

    # Colecciones primero y de menos a mas profundas: un PUT cuyo directorio padre
    # no existe devuelve 409.
    dirs = sorted({os.path.dirname(a) for a in archivos if os.path.dirname(a)},
                  key=lambda d: d.count("/"))

    pendientes, iguales = [], 0
    for rel in archivos:
        local = open(os.path.join(args.origen, rel), "rb").read()
        if len(local) <= LIMITE_SHA:
            code, cuerpo, _ = pedir(f"{base}/{rel}", "GET")
            igual = code == 200 and sha256(cuerpo) == sha256(local)
        else:
            code, _, hdrs = pedir(f"{base}/{rel}", "HEAD")
            igual = code == 200 and hdrs.get("Content-Length") == str(len(local))
        if igual:
            iguales += 1
        else:
            pendientes.append((rel, local))

    # Que sobra en el servidor. Los EXCLUIDOS no se tocan: su presencia o ausencia en el
    # docroot la gobierna el vhost (los niega), no este script.
    sobrantes, remoto = [], None
    if args.usuario and args.clave:
        remoto = leer_manifiesto(base, auth)
        if remoto is False:
            return 1
        if remoto is None:
            print("::notice::sin manifiesto todavia: esta corrida no purga nada y deja "
                  "uno sembrado para la proxima")
        else:
            locales = set(archivos)
            sobrantes = [r for r in remoto
                         if r not in locales and os.path.basename(r) not in EXCLUIDOS]

    print(f"{len(archivos)} archivos · {iguales} sin cambio · {len(pendientes)} por subir"
          f" · {len(sobrantes)} por borrar")

    # Un checkout vacio o parcial no debe arrasar el sitio.
    if sobrantes and remoto and not args.purgar_igual:
        fraccion = len(sobrantes) / len(remoto)
        if fraccion > UMBRAL_PURGA:
            print(f"::error::la purga borraria {len(sobrantes)} de {len(remoto)} archivos "
                  f"({fraccion:.0%} > {UMBRAL_PURGA:.0%}): parece un checkout incompleto. "
                  f"Si la baja es real, correr con --purgar-igual")
            return 1

    if args.simular:
        for rel, _ in pendientes:
            print(f"  subiria {rel}")
        for rel in sobrantes:
            print(f"  borraria {rel}")
        return 0
    if not pendientes and not sobrantes:
        print("nada que publicar ni que borrar")
        return 0

    for d in dirs:
        code, _, _ = pedir(f"{base}/{d}/", "MKCOL", auth)
        if code not in (201, 405):  # 405 = la coleccion ya existe
            print(f"::error::MKCOL /{d}/ devolvio {code}")
            return 1

    fallos = 0
    for rel, local in pendientes:
        code, _, _ = pedir(f"{base}/{rel}", "PUT", auth, local)
        if code not in (200, 201, 204):
            print(f"::error::PUT /{rel} devolvio {code}")
            fallos += 1
            continue
        code, cuerpo, _ = pedir(f"{base}/{rel}", "GET")
        if code != 200 or sha256(cuerpo) != sha256(local):
            print(f"::error::/{rel} se subio ({code}) pero lo servido NO coincide con el local")
            fallos += 1
            continue
        print(f"  publicado y verificado /{rel}")

    # Purga: tambien verificada por efecto (un 204 no prueba que dejo de servirse).
    for rel in sobrantes:
        code, _, _ = pedir(f"{base}/{rel}", "DELETE", auth)
        if code not in (200, 204, 404):
            print(f"::error::DELETE /{rel} devolvio {code}")
            fallos += 1
            continue
        code, _, _ = pedir(f"{base}/{rel}", "HEAD")
        if code != 404:
            print(f"::error::/{rel} se borro pero sigue respondiendo {code}")
            fallos += 1
            continue
        print(f"  borrado y verificado /{rel}")

    # El manifiesto se escribe AL FINAL: si algo fallo arriba, la proxima corrida
    # compara contra el estado anterior y vuelve a intentar, en vez de dar por
    # publicado lo que no quedo.
    if fallos:
        print(f"::error::{fallos} archivo(s) no quedaron como corresponde "
              f"(manifiesto sin actualizar a proposito)")
        return 1

    cuerpo = ("\n".join(archivos) + "\n").encode()
    code, _, _ = pedir(f"{base}/{MANIFIESTO}", "PUT", auth, cuerpo)
    if code not in (200, 201, 204):
        print(f"::error::PUT del manifiesto devolvio {code}")
        return 1
    print(f"OK: {len(pendientes)} publicado(s) y {len(sobrantes)} borrado(s), "
          f"todo verificado por efecto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
