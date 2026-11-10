#!/usr/bin/env python3
"""
capturar_docs_v2.py — captura las figuras de docs.observer.cl sobre la UI v2.

Herramienta de operador (vive en scripts/docs/, FUERA del docroot). Es el ejecutor
de `GUION-RECAPTURA-UI-V2.md`: ese documento manda, esto sólo lo corre.

🔴 NO CORRER antes de que cierren (a) el bump a 2.0.0 y (b) la tanda del sistema de
diseño de `app.sass`. Cualquier captura anterior se repite: el anillo de foco cambia
el aspecto de todo control enfocado y el radio de los campos es global.

Qué hace distinto a `console_screenshots.py`:

  - Usa el arnés del gauntlet 046 (Chromium headless + token del canario + CERROJO DE
    ESCRITURA: toda petición no-GET se registra y no se envía). Encuadrar no puede
    reiniciar, apagar ni borrar nada por accidente.
  - Flota SINTÉTICA por decisión del usuario (5-nov): «Universal Retail» es ficticia,
    así que no hay nada que difuminar. Y además tiene MÁS datos que la real:
    LIM-CAJA-06 trae 326 parches y 378 programas contra 32 y 14 del equipo de
    laboratorio. Se esconde el cliente de andamiaje «Canario 050 - Cliente W».
  - Antes de cada disparo deja el foco limpio y lo PRUEBA. Con `outline: 0` el foco
    era invisible y el arnés lo dejaba puesto sin que se notara; con el anillo nuevo
    saldría un halo de 2 px que se leería como defecto del producto. La sonda queda
    guardada junto a la captura: ausencia probada, no supuesta.
  - Deja `sonda.json` con, por captura: url, foco, errores severos de consola y
    escrituras bloqueadas. Un PNG sin su sonda no se publica.

USO:
    GAUNTLET_TOKEN=$(.../canarios.sh token | cut -d= -f2) \
      python3 -I capturar_docs_v2.py --salida ./shots [--solo dashboard,parches]

Después: revisar a ojo una por una, convertir a WebP q82 y reponer los <figure>
desde docs-site-fuera-de-linea/capturas-v1-bloques.html subiendo el ?v=N.
"""
import argparse, json, os, subprocess, sys, time

ARNES_POR_OMISION = ("/home/jptamayo/projects/braincorp-cl/observer-rmm/"
                     "_reversa_forward/046-ui-v2-piloto-agente-1c/instrumento")

# DOS equipos sintéticos, porque NINGUNO tiene las dos cosas. Medido sobre la flota
# entera el 5-nov (171 agentes), no sobre una muestra:
#
#   · los 39 sintéticos CON chequeos tienen exactamente 1 chequeo, 26 parches y 12 programas
#   · LIM-CAJA-06 tiene 326 parches y 378 programas, y CERO chequeos
#
# Así que las tablas dedicadas (parches, software) van sobre el rico, y el panel de
# agente —que muestra la tarjeta «Estado de chequeos»— sobre uno que tenga chequeos, o
# sale diciendo «Sin chequeos». Los dos son de «Universal Retail»: el cambio de equipo
# entre una figura y otra no se nota.
#
# 🪤 Y la elección NO es libre: 50 de los 160 sintéticos llevan una IP pública en espacio
# REAL y enrutable. El seeder se pasó del /24 de RFC 5737 (192.0.3.x, 198.51.101.x y
# 203.0.114.x en vez de 192.0.2.0/24, 198.51.100.0/24 y 203.0.113.0/24), así que publicar
# el panel de uno de esos publica la IP de un tercero. Los dos de acá están verificados
# en rango reservado; si se cambian, hay que volver a comprobarlo.
AGENTE = "wbYuJLkUMqiMlMJounyxkxgXvaROtfWOkEXEWxkH"   # LIM-CAJA-06 · 326 parches, 378 programas · 100.64.10.247 ✅
AGENTE_CHEQUEOS = "eKGIrXeJbngTXEDZjMabVjxfINiXWydaBhWbFXtG"  # MIA-CAJA-06 · 1 chequeo · 198.51.100.115 ✅

# Prefijos de IP pública que SÍ se pueden publicar. Todo lo demás se recorta.
IP_PUBLICABLE = (r"^(192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|100\.64\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)")

# Lo que nunca debe salir en una captura publicada.
#
# 🪤 NO vale buscar el texto en `textContent` de cualquier elemento: textContent incluye
# TODOS los descendientes, así que «Canario 050» casa también el `q-layout` entero y
# esconderlo deja la página EN BLANCO. Pasó en el ensayo del 5-nov y la captura salió
# vacía con la sonda en verde, porque la sonda sólo miraba el foco. Se busca en las HOJAS
# (sin hijos) y se esconde el ancestro de fila, que es lo que de verdad hay que tapar.
OCULTAR = [
    # (selector de hoja, regex sobre SU propio texto, selector del ancestro a esconder)
    (".q-banner", r"mantenimiento|maintenance", ".q-banner"),      # servidor en mantenimiento
    # 🔑 El cliente de andamiaje no es sólo ruido visual: carga DESKTOP-4G49P7G, una
    # máquina REAL con su IP de salida (207.248.205.50, fluitek). Esconderlo es también
    # medida de privacidad, no sólo limpieza de la foto.
    #
    # Ese equipo es WIN_REBOOT y está ahí de prestado: `canarios.sh flota050-on` lo mueve
    # al cliente canario y el teardown lo devuelve a su sitio. Así que esta regla puede
    # quedarse SIN CASAR NADA el día que el canario se desmonte y el cliente desaparezca.
    # 🪤 Eso NO la vuelve código muerto: mientras el canario esté activo protege a una
    # máquina real, y volverá a hacerlo en el siguiente `flota050-on`. No borrarla por
    # verla sin efecto en una corrida.
    ("span", r"^Canario 050", ".q-tree__node"),                    # cliente de andamiaje en el árbol
    ("td, .q-td", r"^Canario 050", "tr"),                          # y si asomara en una tabla
]

# name: (ruta, [acciones], recorte)
#   acciones: ("clic", texto) | ("clic_i", icono) | ("espera", seg)
#   recorte: "vista" = viewport completo · "dialogo" = al diálogo de encima
PASOS = [
    ("dashboard",             "/",                              [], "vista"),
    ("agente-panel",          f"/agents/{AGENTE_CHEQUEOS}/summary", [], "vista"),
    ("parches",               f"/agents/{AGENTE}/patches",      [], "vista"),
    ("software",              f"/agents/{AGENTE}/software",     [], "vista"),
    ("plantillas-biblioteca", "/scripts",                       [], "vista"),
    ("modo-perdido-lista",    "/lost-equipment",                [], "vista"),
    ("modo-perdido-dialogo",  "/lost-equipment",                [("clic", "Marcar como perdido")], "dialogo"),
    ("ubicacion-mapa",        f"/agents/{AGENTE}/summary",      [("clic_i", "place"), ("espera", 3)], "dialogo"),
    ("respuesta-menu",        f"/agents/{AGENTE}/summary",      [("clic", "Más acciones"), ("clic", "Respuesta rápida")], "dialogo"),
    ("respuesta-mensaje",     f"/agents/{AGENTE}/summary",      [("clic", "Más acciones"), ("clic", "Respuesta rápida"),
                                                                 ("clic", "Mensaje en pantalla")], "dialogo"),
    ("script-ia-prompt",      "/scripts",                       [("clic", "Nuevo script"), ("clic_i", "auto_awesome")], "dialogo"),
    ("reportes-gestor",       "/",                              [("clic_i", "summarize"), ("clic", "Gestor de reportes")], "dialogo"),
    ("reportes-programacion", "/",                              [("clic_i", "summarize"), ("clic", "Gestor de reportes"),
                                                                 ("clic", "Programaciones de reportes")], "dialogo"),
    ("reportes-historial",    "/",                              [("clic_i", "summarize"), ("clic", "Gestor de reportes"),
                                                                 ("clic", "Historial de ejecución de reportes")], "dialogo"),
]

# Las que exigen una ESCRITURA real y por eso no están arriba. Ver el guion, §decisiones.
A_MANO = {
    "script-ia-borrador":       "pulsar «Generar borrador» (llamada real a la IA: el cerrojo la bloquea)",
    "script-ejecucion-windows": "ejecutar un script de SÓLO LECTURA en un equipo y esperar la salida",
    "modo-perdido-lista (con filas)": "SEMBRAR la fila en la BD; nunca marcar un equipo vivo",
    "ubicacion-historico":      "un equipo con trayectoria: la VM de laboratorio hereda un solo punto",
    "reportes-preview-html/pdf": "abrir un reporte del historial y alternar HTML/PDF",
}

SONDA_FOCO = """
var a = document.activeElement;
if (a && a !== document.body) a.blur();
return {es_body: document.activeElement === document.body,
        focus_visible: document.querySelectorAll(':focus-visible').length};
"""

# 🔑 Sin esto, una captura EN BLANCO pasa en verde: la sonda de foco no mira el contenido.
SONDA_CONTENIDO = "return (document.body.innerText || '').trim().length;"

# 🔴 Ninguna captura debe publicar la IP de un tercero. Hay DOS controles, y son de
# naturaleza distinta a propósito:
#
#  (a) COMPUERTA, precisa y bloqueante: antes de capturar se le pregunta a la API la
#      `public_ip` de cada equipo que va a salir y se exige que esté en rango reservado.
#      Es un hecho comprobable, no una heurística.
#
#  (b) AVISO, heurístico y NO bloqueante: se listan las cadenas con pinta de IPv4 que se
#      vean en la captura, para que una persona las mire.
#
# 🪤 El aviso NO puede ser la compuerta, y esto costó dos ensayos: el inventario de
# software está lleno de versiones indistinguibles de una IP (2.1.0.7, 8.0.2.5,
# 109.1.47.186 — todas IPv4 válidas). El primer intento fue filtrar por octetos ≤255:
# sólo mató 32.0.0.363. El segundo fue exigir que el elemento fuera el campo, su texto y
# nada más: tampoco sirve, porque la versión TAMBIÉN ocupa su propia celda. Un patrón no
# distingue «2.1.0.7 versión» de «2.1.0.7 dirección»; el contexto está en el dato, no en
# el texto. De ahí que lo preciso venga de la API y el regex se quede en aviso.
SONDA_IP = """
var ok = new RegExp(arguments[0]);
var re = /\\b(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\b/;
var vistas = [];
var it = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
var n;
while ((n = it.nextNode())) {
  var e = n.parentElement;
  if (!e || !e.offsetParent) continue;
  var txt = (n.textContent || ''), g = new RegExp(re.source, 'g'), m;
  while ((m = g.exec(txt)) !== null) {
    if ([m[1],m[2],m[3],m[4]].some(function(o){return parseInt(o,10) > 255;})) continue;
    if (ok.test(m[0])) continue;
    vistas.push({ip: m[0], contexto: txt.trim().slice(0, 50)});
  }
}
return vistas;
"""
TEXTO_MINIMO = 400          # una vista de la consola nunca baja de aquí
COLORES_MINIMOS = 32        # un PNG de un solo tono es una captura perdida


def colores(png):
    """Cuántos colores distintos tiene el PNG. 1 = imagen plana = captura vacía."""
    try:
        from PIL import Image
    except ImportError:
        return None
    c = Image.open(png).convert("RGB").getcolors(maxcolors=100000)
    return len(c) if c else 100000


def ocultar(s):
    """Esconde el andamiaje. Devuelve cuántos elementos tapó, para poder auditarlo."""
    return s.js("""
      var reglas = arguments[0], n = 0;
      reglas.forEach(function(r){
        var re = new RegExp(r[1], 'i');
        document.querySelectorAll(r[0]).forEach(function(e){
          // sólo HOJAS, y sobre su propio texto: textContent de un contenedor arrastra
          // toda la app y esconderlo deja la página en blanco.
          if (e.children.length) return;
          if (!re.test((e.textContent || '').trim())) return;
          var obj = e.closest(r[2]) || e;
          // cortafuegos: nunca esconder algo que ocupe media pantalla
          var b = obj.getBoundingClientRect();
          if (b.height > window.innerHeight * 0.5 || b.width > window.innerWidth * 0.9) return;
          obj.style.display = 'none'; n++;
        });
      });
      return n;
    """, OCULTAR)


def recortar(png, caja):
    """Recorta el PNG a `caja` = {x,y,w,h} con 12 px de aire. Sin PIL no recorta."""
    try:
        from PIL import Image
    except ImportError:
        print("  ⚠ sin Pillow: no se recorta"); return False
    im = Image.open(png); aire = 12
    x0 = max(0, int(caja["x"]) - aire); y0 = max(0, int(caja["y"]) - aire)
    x1 = min(im.width, int(caja["x"] + caja["w"]) + aire)
    y1 = min(im.height, int(caja["y"] + caja["h"]) + aire)
    if x1 - x0 < 50 or y1 - y0 < 50:
        print("  ⚠ caja degenerada: no se recorta"); return False
    im.crop((x0, y0, x1, y1)).save(png)
    return True


def ip_del_agente(agent_id, token):
    """La `public_ip` que la API dice que tiene ese equipo. None si no se pudo leer."""
    o = subprocess.run(["curl", "-s", "--max-time", "25", "-H", f"Authorization: Token {token}",
                        f"https://api.observer.cl/agents/{agent_id}/"], capture_output=True, text=True).stdout
    try:
        return json.loads(o).get("public_ip")
    except Exception:
        return None


def compuerta_ip(token):
    """BLOQUEANTE: ningún equipo capturado puede tener una IP pública enrutable.

    50 de los 160 agentes sintéticos la tienen: el seeder se pasó del /24 de RFC 5737
    (192.0.3.x, 198.51.101.x, 203.0.114.x). Elegir «uno sintético» no basta.
    """
    import re as _re
    ok = _re.compile(IP_PUBLICABLE)
    malos = []
    for etiqueta, aid in (("AGENTE", AGENTE), ("AGENTE_CHEQUEOS", AGENTE_CHEQUEOS)):
        ip = ip_del_agente(aid, token)
        estado = "?" if ip is None else ("reservada" if ok.match(ip) else "🔴 ENRUTABLE")
        print(f"  compuerta · {etiqueta}: {ip} — {estado}")
        if ip is None or not ok.match(ip):
            malos.append((etiqueta, aid, ip))
    return malos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="./shots")
    ap.add_argument("--arnes", default=ARNES_POR_OMISION)
    ap.add_argument("--solo", help="lista de nombres separados por coma")
    ap.add_argument("--ancho", type=int, default=1400)
    ap.add_argument("--alto", type=int, default=758)
    a = ap.parse_args()

    sys.path.insert(0, a.arnes)
    from sesion import Sesion                                   # noqa: E402
    from selenium.webdriver.common.by import By                 # noqa: E402

    os.makedirs(a.salida, exist_ok=True)

    token = os.environ.get("GAUNTLET_TOKEN")
    if token:
        malos = compuerta_ip(token)
        if malos:
            sys.exit("🔴 compuerta de IP: " + "; ".join(f"{e} ({i}) tiene IP enrutable {ip}"
                                                        for e, i, ip in malos) +
                     ". Elige otro equipo: publicar eso publica la IP de un tercero.")
    else:
        print("  ⚠ sin GAUNTLET_TOKEN: no se pudo correr la compuerta de IP por API")
    pasos = PASOS if not a.solo else [p for p in PASOS if p[0] in a.solo.split(",")]
    if not pasos:
        sys.exit(f"--solo no casó con ningún paso. Hay: {', '.join(p[0] for p in PASOS)}")

    def clic(s, texto, tags):
        xp = " | ".join(f"//{t}[normalize-space(text())={json.dumps(texto, ensure_ascii=False)}]" for t in tags)
        els = [e for e in s.d.find_elements(By.XPATH, xp) if e.is_displayed()]
        if not els:
            return False
        s.d.execute_script("arguments[0].scrollIntoView({block:'center'});", els[0]); time.sleep(.4)
        try:
            els[0].click()
        except Exception:
            s.d.execute_script("arguments[0].click()", els[0])
        time.sleep(2.5); return True

    sondas, fallos = {}, []
    with Sesion(ancho=a.ancho, alto=a.alto) as s:
        for nombre, ruta, acciones, modo in pasos:
            print(f"· {nombre}")
            try:
                s.ir(ruta, espera=7)
                texto_antes = s.js(SONDA_CONTENIDO)
                tapados = ocultar(s)
                for acc in acciones:
                    if acc[0] == "espera":
                        time.sleep(acc[1]); continue
                    tags = ("i",) if acc[0] == "clic_i" else ("div", "span", "button", "a", "td")
                    if not clic(s, acc[1], tags):
                        raise RuntimeError(f"no encontré {acc[1]!r}")
                    tapados += ocultar(s)
                foco = s.js(SONDA_FOCO)                 # deja el foco limpio Y lo prueba
                time.sleep(.4)
                png = os.path.join(a.salida, nombre + ".png")
                s.captura(png)
                caja = None
                if modo == "dialogo":
                    caja = s.js("""
                      var ds = Array.from(document.querySelectorAll('.q-dialog,.q-menu'))
                        .filter(function(d){return d.getBoundingClientRect().height > 40;});
                      if (!ds.length) return null;
                      var r = ds[ds.length-1].getBoundingClientRect();
                      return {x:r.x, y:r.y, w:r.width, h:r.height};
                    """)
                    if caja:
                        recortar(png, caja)
                texto = s.js(SONDA_CONTENIDO)
                ips = s.js(SONDA_IP, IP_PUBLICABLE)
                cols = colores(png)
                reparos = []

                if not (foco["es_body"] and foco["focus_visible"] == 0):
                    reparos.append("FOCO SUCIO (puede salir el anillo)")
                if texto < TEXTO_MINIMO:
                    reparos.append(f"PÁGINA VACÍA ({texto} car. de texto)")
                if texto_antes and texto < texto_antes * 0.5:
                    reparos.append(f"ocultar() se comió la página ({texto_antes}→{texto} car.)")
                if cols is not None and cols < COLORES_MINIMOS:
                    reparos.append(f"IMAGEN PLANA ({cols} colores)")
                sondas[nombre] = {"url": s.d.current_url, "foco": foco, "recorte": caja,
                                  "ips_a_revisar": ips,
                                  "texto_antes": texto_antes, "texto": texto,
                                  "tapados": tapados, "colores": cols,
                                  "limpia": not reparos, "reparos": reparos}
                marca = "✓" if not reparos else "⚠ " + " · ".join(reparos)
                print(f"  {marca}  {os.path.getsize(png)//1024} KB")
            except Exception as e:
                fallos.append((nombre, str(e)[:160])); print(f"  ✗ {e}")
        ev = s.evidencia()

    salida = {"sondas": sondas, "fallos": fallos,
              "sonda_consola": ev["sonda_consola"],
              "errores_consola": ev["consola_errores"],
              "escrituras_bloqueadas": ev["escrituras_bloqueadas"],
              "a_mano": A_MANO}
    with open(os.path.join(a.salida, "sonda.json"), "w") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    sucias = [n for n, v in sondas.items() if not v["limpia"]]
    print(f"\n{len(sondas)} capturas · {len(fallos)} fallos · sonda de consola: "
          f"{'OK' if ev['sonda_consola'] else '🔴 MUDA (la lista de errores no prueba nada)'} · "
          f"{len(ev['consola_errores'])} errores severos")
    dudosas = {n: v["ips_a_revisar"] for n, v in sondas.items() if v.get("ips_a_revisar")}
    if dudosas:
        print("\n🟡 cadenas con pinta de IPv4 a la vista — AVISO, no compuerta. En el inventario")
        print("   de software casi siempre son versiones. Mirar una por una antes de publicar:")
        for n, xs in dudosas.items():
            print(f"   {n}: " + ", ".join(f"{x['ip']} en «{x['contexto'][:34]}»" for x in xs[:3]))
    if sucias:
        print(f"🔴 CON REPAROS: {', '.join(sucias)} — ninguna de estas se publica sin revisar")
    print(f"\nA mano, aparte ({len(A_MANO)}):")
    for k, v in A_MANO.items():
        print(f"  · {k}: {v}")
    return 1 if (fallos or sucias) else 0


if __name__ == "__main__":
    sys.exit(main())
