#!/usr/bin/env python3
"""Publica docs-site/ en docs.observer.cl por WebDAV (PUT + MKCOL autenticados).

Lo corre el job publish-docs.yml en cada release. Sustituye al `sudo rsync` manual
desde el control-plane, que ataba la publicacion a un equipo concreto.

Solo biblioteca estandar: el runner no instala nada para esto.

Tres reglas que vienen de como quedo el vhost y de errores ya pagados:

1. El vhost permite PUT y MKCOL, pero NO DELETE (autorizacion metodo por metodo,
   ver scripts/appserver/docs.observer.cl.conf). Un archivo que deja de existir en
   el repo NO desaparece del sitio: hay que borrarlo a mano en el appserver. El
   script lo avisa en el resumen en vez de fingir que sincroniza.

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
import urllib.error
import urllib.request

LIMITE_SHA = 1024 * 1024  # 1 MiB
EXCLUIDOS = {"README.md"}  # el vhost lo niega: publicaria topologia interna
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origen", default="docs-site")
    ap.add_argument("--base", default="https://docs.observer.cl")
    ap.add_argument("--usuario", default=os.environ.get("DOCS_UPLOAD_USER", ""))
    ap.add_argument("--clave", default=os.environ.get("DOCS_UPLOAD_PASSWORD", ""))
    ap.add_argument("--simular", action="store_true", help="dice que haria, sin escribir")
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

    print(f"{len(archivos)} archivos · {iguales} sin cambio · {len(pendientes)} por subir")
    if args.simular:
        for rel, _ in pendientes:
            print(f"  subiria {rel}")
        return 0
    if not pendientes:
        print("nada que publicar")
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

    if fallos:
        print(f"::error::{fallos} archivo(s) no quedaron publicados correctamente")
        return 1
    print(f"OK: {len(pendientes)} archivo(s) publicados y verificados por efecto")
    print("::notice::el vhost no permite DELETE: lo retirado del repo sigue servido "
          "hasta borrarlo a mano en el appserver")
    return 0


if __name__ == "__main__":
    sys.exit(main())
