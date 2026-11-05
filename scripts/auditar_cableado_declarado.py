#!/usr/bin/env python3
"""Detecta funcionalidad DECLARADA Y NO CONSTRUIDA: configuración que nadie lee
y tareas Celery que nadie invoca.

    python3 scripts/auditar_cableado_declarado.py            # informe completo
    python3 scripts/auditar_cableado_declarado.py --resumen  # sólo lo huérfano

Por qué existe
--------------
El 2026-10-29 se descubrió que `CoreSettings.erase_attachment_retention_days`
existía, se podía configurar por la API, devolvía 200 y NINGUNA línea del código
lo leía. En paralelo, la tarea que debía usarlo —`prune_erase_attachments`— no
estaba agendada en ninguna parte: el único `grep` del nombre en todo el repo era
su propio `def`. Durante dos incrementos ningún adjunto del módulo de borrado
caducó, mientras la política de uso aceptable publicada afirmaba que sí.

Nada de eso puso rojo el gate. La tarea pasaba sus tests, tenía buen docstring y
citaba la norma correcta; el campo viajaba por la API porque
`CoreSettingsSerializer` declara `fields = "__all__"`, así que aparecía en el
contrato sin que nadie hubiera escrito una sola línea que lo leyera.

De ahí las dos reglas que se comprueban acá:

1. CAMPO SIN LECTURA DE BACKEND  =>  configuración que miente.
   Se exige al menos una lectura en Python de producción. Aparecer en la API NO
   cuenta, y es justo lo que enmascaró el defecto: con `fields = "__all__"` el
   serializer expone cualquier campo nuevo sin mencionarlo, así que el round-trip
   PUT/GET devuelve 200 tanto si el valor gobierna algo como si no gobierna nada.
   Aparecer sólo en el formulario de la consola tampoco cuenta: una perilla que
   se guarda y se vuelve a mostrar, y que ningún servidor lee, es exactamente el
   defecto que se busca.

2. TAREA SIN LLAMADOR  =>  tarea que no corre.
   Se exige un llamador en producción: una entrada del `beat_schedule`, un
   `.delay()`/`.apply_async()`/`.s()`, o otra tarea. Un llamador que sólo existe
   en los tests NO cuenta: es precisamente la forma en que esto pasa los tests
   sin ocurrir nunca en una instancia viva.

Límites conocidos (se declaran para que nadie confíe de más)
------------------------------------------------------------
El análisis es estático y por nombre, así que falla en una dirección concreta:
cuando un campo de `CoreSettings` se llama igual que un campo de OTRO modelo
(hoy `date_format` en `accounts.User`, `erase_attachment_retention_days`,
`alert_template`, `workstation_policy` y `server_policy` en `clients`/`agents`),
las lecturas del homónimo cuentan como lecturas del campo global. Lo mismo entre
una tarea y una función normal del mismo nombre (hoy
`expire_stale_retrieval_orders` y `run_win_task`), y por eso la resolución de
tareas mira de qué módulo viene el símbolo en cada archivo.

El error, entonces, es dejar pasar algo huérfano, nunca acusar de huérfano algo
que se usa. Esa asimetría es deliberada: un gate que grita en falso se termina
desactivando, y el día que se desactiva deja de encontrar el defecto real.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import warnings
from typing import Iterable, NamedTuple

# Tareas sin llamador que se aceptan a sabiendas, cada una con su motivo. Se
# compara por IGUALDAD (ver `main` y el gate): si alguien cablea o borra una, hay
# que sacarla de acá. Una lista que sólo crece se convierte en el lugar donde el
# defecto se esconde con permiso.
HUERFANAS_CONOCIDAS = frozenset(
    {
        # Código muerto, sin consecuencia observable. Editar una tarea
        # automatizada sí llega al agente: `AutomatedTask.save()` marca los
        # `TaskResult` como NOT_SYNCED y `core.tasks.sync_scheduled_tasks` —que
        # el beat corre cada 2 min— arma la acción "modify" por NATS. Esta tarea,
        # y el `AutomatedTask.modify_task_on_agent` del que es único llamador,
        # son una vía paralela que nadie usa. Propuesta: borrar las dos.
        "autotasks.tasks.modify_win_task",
        # Plantilla de Celery ("Request: {!r}"), herramienta de diagnóstico. No
        # pretende correr sola, así que no promete nada que no cumpla.
        "observerrmm.celery.debug_task",
    }
)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
API = RAIZ / "api" / "observerrmm"
MODELO_CORE = API / "core" / "models.py"
CELERY = API / "observerrmm" / "celery.py"

# Dónde se buscan lecturas que NO son de backend. No deciden el veredicto; se
# informan para poder distinguir "se lee y tiene efecto" de "sólo se muestra en
# la consola", que es la diferencia entre un campo sano y uno decorativo.
DIRS_FRONTEND = ("web/app/src",)


def _parse(fuente: str) -> ast.AST:
    """`ast.parse` sin arrastrar los avisos del archivo compilado.

    Compilar todo el repo despierta los `SyntaxWarning` de cualquier archivo con
    un `"\\W"` sin `r`, y salen atribuidos a este gate (`<unknown>:300`) en vez
    de a su archivo. Ya los reporta `flake8` donde corresponde; repetirlos acá
    sólo ensucia la salida de la CI y le pone cara de culpable al gate.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(fuente)


def _es_test(p: pathlib.Path) -> bool:
    return (
        p.name.startswith("test_") or p.name == "tests.py" or "/tests/" in p.as_posix()
    )


def _es_migracion(p: pathlib.Path) -> bool:
    return "/migrations/" in p.as_posix()


def _fuentes_backend() -> list[pathlib.Path]:
    """Python de producción: sin migraciones (son historia, no lectores) y sin
    tests (un test que lee el campo no hace que el producto lo lea)."""
    return [
        p for p in sorted(API.rglob("*.py")) if not _es_migracion(p) and not _es_test(p)
    ]


# ---------------------------------------------------------------------------
# Campos de CoreSettings
# ---------------------------------------------------------------------------


class Campo(NamedTuple):
    nombre: str
    lecturas_backend: list[str]
    lecturas_frontend: list[str]

    @property
    def huerfano(self) -> bool:
        return not self.lecturas_backend


def campos_coresettings() -> dict[str, set[int]]:
    """nombre -> líneas que ocupa su propia declaración (no son lecturas)."""
    arbol = _parse(MODELO_CORE.read_text(encoding="utf-8"))
    campos: dict[str, set[int]] = {}
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.ClassDef) and nodo.name == "CoreSettings"):
            continue
        for st in nodo.body:
            if not (isinstance(st, ast.Assign) and isinstance(st.value, ast.Call)):
                continue
            func = ast.unparse(st.value.func)
            if "models." in func or "ArrayField" in func:
                destino = st.targets[0]
                if isinstance(destino, ast.Name):
                    fin = st.end_lineno or st.lineno
                    campos[destino.id] = set(range(st.lineno, fin + 1))
    return campos


class _Sondas(NamedTuple):
    """Regexes de un campo, compiladas UNA vez.

    Compilarlas por campo y no por línea no es microoptimización: el gate recorre
    ~74 campos sobre todo el Python de producción, y bajo la instrumentación de
    `coverage` (que la CI siempre activa) el costo por línea se multiplica hasta
    volver el test lento de un modo que invita a desactivarlo.
    """

    nombre: str
    citado: str
    calificado: str
    presencia: re.Pattern
    atributo: re.Pattern
    asignacion: re.Pattern
    literal: re.Pattern


def _sondas(nombre: str) -> _Sondas:
    esc = re.escape(nombre)
    return _Sondas(
        nombre=nombre,
        citado=f"`{nombre}`",
        calificado=f"CoreSettings.{nombre}",
        presencia=re.compile(rf"\b{esc}\b"),
        atributo=re.compile(rf"[.\[]\s*{esc}\b"),
        asignacion=re.compile(rf"\b{esc}\s*="),
        literal=re.compile(rf"""["']{esc}["']"""),
    )


def _es_prosa(s: _Sondas, linea: str) -> bool:
    """Una mención en comentario o docstring no es una lectura.

    El repo documenta mucho y bien, así que el nombre de un campo aparece a
    menudo en prosa que explica otra cosa. Contar eso como lectura volvería el
    gate inútil: el defecto original tenía comentarios impecables.
    """
    if linea.lstrip().startswith("#"):
        return True
    if s.citado in linea:  # convención del repo para citar un campo
        return True
    # `CoreSettings.campo` siempre es prosa: el código real llega al valor por una
    # INSTANCIA (`core.`, `self.`, `cs.`), nunca por la clase. Sin esta regla, una
    # línea de docstring como "De `CoreSettings.keep_awake_baseline_enabled`."
    # pasaría por lectura, que es exactamente el tipo de comentario impecable
    # detrás del cual se escondió el defecto original.
    if s.calificado in linea:
        return True
    # Acceso real: `.campo`, `campo=`, o el nombre como clave/string.
    return not (
        s.atributo.search(linea)
        or s.asignacion.search(linea)
        or s.literal.search(linea)
    )


def auditar_campos() -> list[Campo]:
    declarados = campos_coresettings()
    # Las líneas se parten UNA vez por archivo, no una vez por campo: son ~74
    # campos contra ~450 archivos y re-partirlos en cada vuelta multiplicaba por
    # 74 el trabajo, lo bastante lento como para que el gate dé ganas de saltarlo.
    textos = [
        (p, txt, txt.splitlines())
        for p, txt in (
            (p, p.read_text(encoding="utf-8", errors="replace"))
            for p in _fuentes_backend()
        )
    ]

    frontend: list[tuple[pathlib.Path, str, list[str]]] = []
    for d in DIRS_FRONTEND:
        base = RAIZ / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in (".ts", ".js", ".vue"):
                txt = p.read_text(encoding="utf-8", errors="replace")
                frontend.append((p, txt, txt.splitlines()))

    resultado: list[Campo] = []
    for nombre, lineas_def in declarados.items():
        sondas = _sondas(nombre)
        back: list[str] = []
        for p, txt, lineas in textos:
            if nombre not in txt:
                continue
            propio = p == MODELO_CORE
            for i, linea in enumerate(lineas, 1):
                if nombre not in linea:
                    continue
                if propio and i in lineas_def:
                    continue  # su propia declaración
                if not sondas.presencia.search(linea) or _es_prosa(sondas, linea):
                    continue
                back.append(f"{p.relative_to(RAIZ)}:{i}")
        front: list[str] = []
        for p, txt, lineas in frontend:
            if nombre not in txt:
                continue
            for i, linea in enumerate(lineas, 1):
                if nombre in linea and sondas.presencia.search(linea):
                    front.append(f"{p.relative_to(RAIZ)}:{i}")
        resultado.append(Campo(nombre, back, front))
    return resultado


# ---------------------------------------------------------------------------
# Tareas Celery
# ---------------------------------------------------------------------------


class Tarea(NamedTuple):
    modulo: str
    nombre: str
    definicion: str
    llamadores: list[str]

    @property
    def ruta(self) -> str:
        return f"{self.modulo}.{self.nombre}"

    @property
    def huerfana(self) -> bool:
        return not self.llamadores


def _modulo(p: pathlib.Path) -> str:
    return ".".join(p.relative_to(API).with_suffix("").parts)


def _decorada_como_tarea(nodo: ast.AST) -> bool:
    return any(
        re.search(r"\b(app\.task|shared_task)", ast.unparse(d))
        for d in getattr(nodo, "decorator_list", [])
    )


def _importa(arbol: ast.AST, paquete: str) -> dict[str, str]:
    """nombre local -> módulo del que viene. Resuelve también los `from .x import`
    y los imports dentro de funciones, que es como importa casi todo este repo
    para evitar ciclos."""
    origen: dict[str, str] = {}
    partes = paquete.split(".")
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = ".".join(partes[: max(len(partes) - nodo.level, 0)])
                mod = f"{base}.{nodo.module}" if nodo.module else base
            else:
                mod = nodo.module or ""
            for a in nodo.names:
                origen[a.asname or a.name] = mod
    return origen


def tareas_celery() -> list[tuple[str, str, pathlib.Path, int]]:
    encontradas = []
    for p in sorted(API.rglob("*.py")):
        if _es_migracion(p):
            continue
        try:
            arbol = _parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(
                nodo, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and _decorada_como_tarea(nodo):
                encontradas.append((_modulo(p), nodo.name, p, nodo.lineno))
    return encontradas


_DESPACHO = r"\.\s*(delay|apply_async|si|s)\s*\("


def auditar_tareas() -> list[Tarea]:
    definidas = tareas_celery()
    fuentes = [
        (p, txt, _modulo(p), txt.splitlines())
        for p, txt in (
            (p, p.read_text(encoding="utf-8", errors="replace"))
            for p in sorted(API.rglob("*.py"))
            if not _es_migracion(p)
        )
    ]
    arboles: dict[pathlib.Path, dict[str, str]] = {}
    for p, txt, mod, _ in fuentes:
        try:
            arboles[p] = _importa(_parse(txt), mod)
        except SyntaxError:
            arboles[p] = {}

    resultado: list[Tarea] = []
    for mod, nombre, defp, defline in definidas:
        llamadores: list[str] = []
        for p, txt, mod_p, lineas in fuentes:
            if nombre not in txt or _es_test(p):
                continue  # un llamador que sólo vive en los tests no cuenta
            rel = p.relative_to(RAIZ)
            # ¿En ESTE archivo, `nombre` se refiere a ESTA tarea? Sin esto, una
            # función homónima de otro módulo (hoy `expire_stale_retrieval_orders`
            # en erase/services.py) se contaría como llamada a la tarea, que es
            # el agujero por el que una tarea huérfana pasa inadvertida.
            resuelve = mod_p == mod or arboles[p].get(nombre) == mod
            alias: set[str] = set()
            for i, linea in enumerate(lineas, 1):
                if nombre not in linea:
                    continue
                if p == defp and defline - 6 <= i <= defline:
                    continue  # su propio def y decoradores
                # Nombre de tarea como string: beat_schedule, send_task.
                if re.search(
                    rf"""["']{re.escape(mod)}\.{re.escape(nombre)}["']""", linea
                ):
                    llamadores.append(f"{rel}:{i} (beat/string)")
                    continue
                # Llamada totalmente calificada: ee.reporting.tasks.email_report.delay(
                if re.search(
                    rf"{re.escape(mod)}\.{re.escape(nombre)}{_DESPACHO}", linea
                ):
                    llamadores.append(f"{rel}:{i} (calificada)")
                    continue
                if not resuelve:
                    continue
                if re.search(rf"\b{re.escape(nombre)}{_DESPACHO}", linea):
                    llamadores.append(f"{rel}:{i} (delay)")
                    continue
                # Alias: `email_task = agent_outage_email_task` y más abajo
                # `email_task.delay(...)`. Así despacha todo alerts/models.py.
                m = re.match(rf"\s*(\w+)\s*=\s*{re.escape(nombre)}\s*$", linea)
                if m:
                    alias.add(m.group(1))
                    continue
                # Llamada directa, pero NO un acceso por atributo: dentro de
                # `autotasks/tasks.py`, `task.run_win_task()` es el MÉTODO del
                # modelo homónimo, no la tarea. Contarlo dejaría que una tarea se
                # acreditara a sí misma como llamador desde su propio cuerpo.
                if re.search(
                    rf"(?<![.\w]){re.escape(nombre)}\s*\(", linea
                ) and not linea.strip().startswith(("def ", "async def ")):
                    llamadores.append(f"{rel}:{i} (directa)")
            for a in alias:
                for i, linea in enumerate(lineas, 1):
                    if re.search(rf"\b{re.escape(a)}{_DESPACHO}", linea):
                        llamadores.append(f"{rel}:{i} (alias {a})")
                        break
        # Los llamadores se ordenan por cuán bien explican que la tarea corra: el
        # beat antes que el `run_all_tasks`, que es un comando para forzarlas a
        # mano y no prueba que nada las dispare solas.
        orden = {"(beat/string)": 0, "(delay)": 1, "(calificada)": 1}
        llamadores.sort(key=lambda c: next((v for k, v in orden.items() if k in c), 2))
        resultado.append(
            Tarea(mod, nombre, f"{defp.relative_to(RAIZ)}:{defline}", llamadores)
        )
    return resultado


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _imprimir(items: Iterable[str]) -> None:
    for i in items:
        print(f"        {i}")


def main(argv: list[str]) -> int:
    resumen = "--resumen" in argv

    campos = auditar_campos()
    tareas = auditar_tareas()
    campos_huerfanos = [c for c in campos if c.huerfano]
    tareas_huerfanas = [t for t in tareas if t.huerfana]
    nuevas = {t.ruta for t in tareas_huerfanas} - HUERFANAS_CONOCIDAS
    ya_cableadas = HUERFANAS_CONOCIDAS - {t.ruta for t in tareas if t.huerfana}

    print("=" * 78)
    print(f"CoreSettings: {len(campos)} campos declarados")
    print("=" * 78)
    for c in sorted(campos, key=lambda c: c.nombre):
        if resumen and not c.huerfano:
            continue
        if c.huerfano:
            clase = "(c) CERO LECTURAS -- configuracion que miente"
        else:
            # (a) "se lee y tiene efecto" vs (b) "solo se muestra en la consola"
            # no se decide aca: hay que mirar QUE hace el codigo con el valor, y
            # fingir que un conteo lo resuelve seria peor que no decir nada.
            clase = (
                f"(a/b) {len(c.lecturas_backend)} lecturas backend, "
                f"{len(c.lecturas_frontend)} frontend"
            )
        print(f"  {'[!]' if c.huerfano else '   '} {c.nombre:40s} {clase}")
        if c.huerfano:
            _imprimir(c.lecturas_frontend[:6] or ["(ni frontend)"])

    print()
    print("=" * 78)
    print(f"Celery: {len(tareas)} tareas definidas")
    print("=" * 78)
    for t in sorted(tareas, key=lambda t: t.ruta):
        if resumen and not t.huerfana:
            continue
        print(
            f"  {'[!]' if t.huerfana else '   '} {t.ruta:55s} "
            f"{'HUERFANA' if t.huerfana else t.llamadores[0]}"
        )
        if t.huerfana:
            _imprimir([f"def en {t.definicion}"])

    print()
    print(
        f"RESULTADO: {len(campos_huerfanos)} campo(s) sin lectura; "
        f"{len(tareas_huerfanas)} tarea(s) sin llamador, de las cuales "
        f"{len(nuevas)} nueva(s) y {len(tareas_huerfanas) - len(nuevas)} aceptada(s) "
        "en HUERFANAS_CONOCIDAS."
    )
    for r in sorted(ya_cableadas):
        print(
            f"  OJO: {r} ya tiene llamador (o dejó de existir) y sigue en "
            "HUERFANAS_CONOCIDAS; hay que sacarla."
        )
    return 1 if (campos_huerfanos or nuevas or ya_cableadas) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
