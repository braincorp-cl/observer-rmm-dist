#!/usr/bin/env python3
"""
console_screenshots.py — Captura pantallazos de la consola Observer RMM para
documentar features en docs.observer.cl.

Herramienta de operador (NO se despliega: vive en scripts/docs/, fuera del
docroot del sitio). Requiere una sesión gráfica X11 con Firefox ESR +
geckodriver + selenium (ya presentes en la estación del operador).

ENFOQUE DE AUTENTICACIÓN (clave):
  La consola es una SPA (Quasar/Vue): guarda el token DRF en localStorage, no en
  cookies. En vez de pedir usuario/clave/2FA, esta herramienta LEE el token de
  una sesión ya iniciada en el perfil de Firefox del operador y lo INYECTA en un
  perfil Selenium limpio. Así:
    - no se manejan credenciales ni 2FA,
    - el perfil Selenium queda aislado (no arrastra otras sesiones del operador:
      correo, Claude, GitHub, etc.) → privacidad.
  Requisito: haber iniciado sesión en la consola (p.ej. rmm.observer.cl) en el
  Firefox normal al menos una vez (deja access_token/user_name/rmmver en
  storage/default/https+++<dominio>/ls/data.sqlite).

USO:
  DISPLAY=:0 python3 console_screenshots.py --base https://rmm.observer.cl \
      --steps steps.json --out ./shots
  # steps.json: lista de pasos; ver STEPS_EXAMPLE al final.

Después de capturar, para publicar en docs ver README.md (optimizar → embeber
<figure class="doc-shot"> → deploy al appserver → verificar en vivo).
"""
import argparse, glob, json, os, shutil, sqlite3, sys, tempfile, time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

FIREFOX_BIN = "/usr/bin/firefox-esr"
GECKODRIVER = "/usr/bin/geckodriver"


def read_session_from_profile(domain, profiles_dir=None):
    """Lee las claves de localStorage (access_token, user_name, rmmver...) de la
    sesión ya iniciada en el perfil de Firefox del operador para `domain`."""
    profiles_dir = profiles_dir or os.path.expanduser("~/.mozilla/firefox")
    origin = "https+++" + domain  # esquema de storage/default de Firefox
    candidates = glob.glob(os.path.join(profiles_dir, "*", "storage", "default", origin, "ls", "data.sqlite"))
    if not candidates:
        raise SystemExit(f"No hay sesión de {domain} en ningún perfil Firefox. "
                         f"Inicia sesión en la consola primero. (busqué {origin})")
    src = max(candidates, key=os.path.getmtime)  # el más reciente
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy(src, tmp)  # copia para no chocar con el Firefox vivo (WAL/lock)
    con = sqlite3.connect(tmp)
    # Firefox guarda value como BLOB: conversion_type (0=UTF-16, 1=UTF-8) y
    # compression_type (0=sin comprimir, 1=snappy). Hay que decodificar a str,
    # porque webdriver serializa a JSON (bytes no es serializable).
    rows = con.execute(
        "SELECT key, value, conversion_type, compression_type FROM data;"
    ).fetchall()
    con.close(); os.unlink(tmp)

    def _decode(val, conv, comp):
        if isinstance(val, str):
            return val
        b = val
        if comp == 1:  # snappy
            try:
                import snappy
                b = snappy.decompress(b)
            except Exception:
                raise SystemExit(
                    "El valor de localStorage está comprimido (snappy) y falta "
                    "python3-snappy. Instálalo o vuelve a iniciar sesión."
                )
        try:
            return b.decode("utf-16-le") if conv == 0 else b.decode("utf-8")
        except Exception:
            return b.decode("utf-8", "replace")

    sess = {
        (k.decode() if isinstance(k, bytes) else k): _decode(v, ct, cp)
        for k, v, ct, cp in rows
    }
    if "access_token" not in sess:
        raise SystemExit(f"El perfil tiene storage de {domain} pero sin access_token "
                         f"(sesión expirada). Vuelve a iniciar sesión.")
    return sess


class Capturer:
    def __init__(self, base, out, width=1680, height=1050):
        self.base = base.rstrip("/")
        self.out = out; os.makedirs(out, exist_ok=True)
        o = Options(); o.binary_location = FIREFOX_BIN
        o.set_preference("dom.webnotifications.enabled", False)
        o.set_preference("intl.accept_languages", "es-CL,es")
        s = Service(executable_path=GECKODRIVER, log_output=os.path.join(out, "geckodriver.log"))
        self.d = webdriver.Firefox(options=o, service=s)
        self.d.set_window_size(width, height)
        self.d.set_page_load_timeout(60)

    def authenticate(self, session):
        self.d.get(self.base + "/"); time.sleep(3)          # carga el origen
        for k, v in session.items():
            self.d.execute_script("window.localStorage.setItem(arguments[0],arguments[1]);", k, v)
        self.d.get(self.base + "/"); time.sleep(6)           # recarga autenticado
        ok = self.d.execute_script("return !!window.localStorage.getItem('access_token');")
        print(f"  auth: {'OK' if ok else 'FALLÓ'} | url={self.d.current_url}")
        return ok

    def click_text(self, text, tags=("div", "span", "button", "a", "td"), nth=0):
        xp = " | ".join(f"//{t}[normalize-space(text())={json.dumps(text, ensure_ascii=False)}]" for t in tags)
        els = [e for e in self.d.find_elements(By.XPATH, xp) if e.is_displayed()]
        if len(els) > nth:
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'});", els[nth])
            time.sleep(0.3); els[nth].click(); return True
        print(f"  ⚠ no encontré texto {text!r}")
        return False

    def click_contains(self, text, tags=("div", "span", "button", "a"), nth=0):
        """Como click_text pero por subcadena (contains), útil para etiquetas
        largas que Quasar parte en varios nodos o trunca visualmente."""
        xp = " | ".join(f"//{t}[contains(normalize-space(.), {json.dumps(text, ensure_ascii=False)})]" for t in tags)
        els = [e for e in self.d.find_elements(By.XPATH, xp) if e.is_displayed()]
        # el más específico = el que tiene menos elementos descendientes
        els.sort(key=lambda e: len(e.find_elements(By.XPATH, ".//*")))
        if len(els) > nth:
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'});", els[nth])
            time.sleep(0.3); els[nth].click(); return True
        print(f"  ⚠ no encontré (contains) {text!r}")
        return False

    def dblclick_text(self, text, tags=("td", "div", "span"), nth=0):
        """Doble-click sobre un texto (p.ej. una fila de tabla Quasar para abrir
        su editor). Útil cuando la acción está en @dblclick del componente."""
        xp = " | ".join(f"//{t}[normalize-space(text())={json.dumps(text, ensure_ascii=False)}]" for t in tags)
        els = [e for e in self.d.find_elements(By.XPATH, xp) if e.is_displayed()]
        if len(els) > nth:
            self.d.execute_script("arguments[0].scrollIntoView({block:'center'});", els[nth])
            time.sleep(0.3); ActionChains(self.d).double_click(els[nth]).perform(); return True
        print(f"  ⚠ no encontré texto {text!r} (dblclick)")
        return False

    def esc(self):
        ActionChains(self.d).send_keys(Keys.ESCAPE).perform(); time.sleep(0.5)

    def shot(self, name):
        p = os.path.join(self.out, name + ".png"); self.d.save_screenshot(p)
        print(f"  📸 {name}.png ({os.path.getsize(p)//1024}KB)")

    def run_step(self, step):
        """step = {name, actions:[...]}; actions: get/click/dblclick/tab/esc/sleep/shot."""
        for a in step.get("actions", []):
            typ = a[0]
            if typ == "get":      self.d.get(self.base + a[1]); time.sleep(a[2] if len(a) > 2 else 3)
            elif typ == "click":  self.click_text(a[1], tuple(a[2]) if len(a) > 2 else ("div","span","button","a","td"))
            elif typ == "clickc":   self.click_contains(a[1], tuple(a[2]) if len(a) > 2 else ("div","span","button","a"))
            elif typ == "dblclick": self.dblclick_text(a[1], tuple(a[2]) if len(a) > 2 else ("td","div","span")); time.sleep(3)
            elif typ == "tab":    self.click_text(a[1], ("div", "span")); time.sleep(2)
            elif typ == "esc":    self.esc()
            elif typ == "sleep":  time.sleep(a[1])
            elif typ == "shot":   self.shot(a[1])
        if "shot" not in [a[0] for a in step.get("actions", [])]:
            self.shot(step["name"])

    def quit(self):
        self.d.quit()


# Datos ÚTILES descubiertos (consola en español, ORMS ~v1.4.0 / rmmver 0.0.202):
#  - Barra de menús: Archivo · Ver · Agentes · Configuración · Herramientas · Reportes · Ayuda
#  - Reportes → "Gestor de reportes" (abre el Administrador de reportes)
#  - Pestañas de detalle de agente: Resumen · Chequeos · Tareas · Parches · Software ·
#    Historial · Notas · Activos · Depuración · Auditoría (Auditoría/Depuración a veces
#    requieren scroll de la barra de tabs)
#  - En STAGING suelen estar VACÍAS: Chequeos, Tareas, Historial (sin datos) → malas
#    para docs; usar un entorno con datos o descartarlas.
STEPS_EXAMPLE = [
    {"name": "01-dashboard", "actions": [["get", "/", 6], ["shot", "01-dashboard"]]},
    {"name": "02-agente-panel", "actions": [["click", "DESKTOP-8I6R7NF", ["td","div","span"]], ["sleep", 3], ["shot", "02-agente-panel"]]},
    {"name": "05-parches", "actions": [["tab", "Parches"], ["shot", "05-parches"]]},
    {"name": "06-software", "actions": [["tab", "Software"], ["shot", "06-software"]]},
    {"name": "09-activos", "actions": [["tab", "Activos"], ["shot", "09-activos"]]},
    {"name": "15-reportes", "actions": [["click", "Reportes", ["div","span","button"]], ["sleep", 1],
                                        ["click", "Gestor de reportes", ["div","span"]], ["sleep", 4],
                                        ["shot", "15-reportes-gestor"]]},
]


def main():
    ap = argparse.ArgumentParser(description="Capturas de la consola Observer RMM para docs.")
    ap.add_argument("--base", default="https://rmm.observer.cl", help="URL base de la consola")
    ap.add_argument("--domain", help="dominio para leer la sesión (por defecto: host de --base)")
    ap.add_argument("--steps", help="JSON con lista de pasos (por defecto: set de ejemplo)")
    ap.add_argument("--out", default="./shots", help="directorio de salida")
    args = ap.parse_args()

    domain = args.domain or args.base.split("://", 1)[-1].split("/", 1)[0]
    session = read_session_from_profile(domain)
    print(f"  sesión leída del perfil: user={session.get('user_name')} rmmver={session.get('rmmver')} "
          f"(access_token {len(session.get('access_token',''))} chars, no se muestra)")

    steps = json.load(open(args.steps)) if args.steps else STEPS_EXAMPLE
    cap = Capturer(args.base, args.out)
    try:
        if not cap.authenticate(session):
            sys.exit("auth falló")
        for st in steps:
            try:
                cap.run_step(st)
            except Exception as e:
                print(f"  ⚠ paso {st.get('name')!r} falló: {e}")
    finally:
        cap.quit(); print("  driver cerrado")


if __name__ == "__main__":
    main()
