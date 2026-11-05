"""Gate contra funcionalidad DECLARADA Y NO CONSTRUIDA.

Nace del defecto del 2026-10-29: `CoreSettings.erase_attachment_retention_days`
existía, se configuraba por la API, devolvía 200 y ninguna línea del código lo
leía; la tarea que debía usarlo, `prune_erase_attachments`, no estaba agendada en
ninguna parte. Dos incrementos sin que caducara un solo adjunto del módulo de
borrado, con la política de uso aceptable afirmando por escrito que caducaban.

Lo que hace falta explicar no es que el defecto existió, sino por qué NINGÚN test
lo vio. Las dos mitades pasaban sus pruebas: el campo, porque
`CoreSettingsSerializer` declara `fields = "__all__"` y el round-trip PUT/GET
devuelve 200 aunque el valor no gobierne nada; la tarea, porque sus tests la
invocan directamente, que es justo lo único que en producción no ocurría nunca.
Un test que llama a la tarea prueba que la tarea funciona, no que alguien la
llame.

De ahí que este gate no pruebe comportamiento sino CABLEADO, y que lo haga
mirando el repo como un todo en vez de ejercitar una función: es la única forma
de que una omisión —no una línea mala, una línea ausente— ponga algo rojo.

La lógica vive en `scripts/auditar_cableado_declarado.py`, que también se corre a
mano para el informe completo. Se importa en vez de duplicarse para que el gate y
el informe no puedan discrepar.
"""

import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[3]
AUDITOR = RAIZ / "scripts" / "auditar_cableado_declarado.py"


def _cargar_auditor():
    spec = importlib.util.spec_from_file_location("auditar_cableado_declarado", AUDITOR)
    assert spec and spec.loader, f"no se pudo cargar {AUDITOR}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def auditor():
    assert AUDITOR.is_file(), (
        f"falta {AUDITOR.relative_to(RAIZ)}. Si se movió, hay que mover este gate "
        "con él: borrarlo deja el repo sin la única comprobación de que la "
        "configuración y las tareas estén cableadas."
    )
    return _cargar_auditor()


# ---------------------------------------------------------------------------
# Tarea A: campos de CoreSettings
# ---------------------------------------------------------------------------


def test_todo_campo_de_coresettings_se_lee_en_el_backend(auditor):
    """Un campo que ningún Python de producción lee es configuración que miente.

    Se exige lectura de BACKEND a propósito, y no basta con que el campo aparezca
    en la API ni en el formulario de la consola:

    - La API lo expone solo, sin que nadie lo pida, por el `fields = "__all__"`
      del serializer. Es exactamente lo que enmascaró el defecto original.
    - Una perilla que la consola guarda y vuelve a mostrar, y que ningún servidor
      lee, es la definición del problema, no una excusa para aceptarla.

    Un campo que el backend sólo lee para devolverlo a la consola (p.ej.
    `date_format`, que viaja como `default_date_format` en dashinfo) SÍ pasa: hay
    código que lo lee y algo cambia cuando se cambia. La distinción entre "tiene
    efecto" y "sólo se muestra" se informa con el script, no se bloquea acá.
    """
    huerfanos = [c.nombre for c in auditor.auditar_campos() if c.huerfano]
    assert not huerfanos, (
        "Campos de CoreSettings que NADIE lee en el backend: "
        f"{sorted(huerfanos)}.\n"
        "Un campo así se puede configurar por la API, devuelve 200 y no hace "
        "nada. Hay que cablearlo donde su propio comentario dice que debería "
        "leerse, o no declararlo todavía."
    )


# ---------------------------------------------------------------------------
# Tarea B: tareas Celery
# ---------------------------------------------------------------------------

# Las tareas sin llamador que se aceptan a sabiendas, con el motivo de cada una,
# viven en `HUERFANAS_CONOCIDAS` del script. Están allá y no acá para que el
# informe que se corre a mano y este gate no puedan discrepar sobre qué deuda se
# está tolerando.


def test_toda_tarea_celery_tiene_llamador(auditor):
    """Una `@app.task` que nadie invoca es una tarea que no corre.

    Se exige un llamador de PRODUCCIÓN: una entrada del `beat_schedule`, un
    `.delay()`/`.apply_async()`/`.s()`, o otra tarea. Un llamador que sólo vive
    en los tests no cuenta: es la forma concreta en que `prune_erase_attachments`
    pasó dos olas en verde sin ejecutarse jamás.
    """
    huerfanas = {t.ruta for t in auditor.auditar_tareas() if t.huerfana}

    nuevas = huerfanas - auditor.HUERFANAS_CONOCIDAS
    assert not nuevas, (
        f"Tareas Celery que NADIE invoca: {sorted(nuevas)}.\n"
        "Si es una poda o mantenimiento periódico, cuélgala de "
        "`core.tasks.core_maintenance_tasks` (el beat la corre cada hora), que "
        "es el molde del producto, en vez de agregarle una entrada propia al "
        "beat_schedule."
    )

    ya_cableadas = auditor.HUERFANAS_CONOCIDAS - huerfanas
    assert not ya_cableadas, (
        f"{sorted(ya_cableadas)} ya tiene llamador (o dejó de existir), pero "
        "sigue en HUERFANAS_CONOCIDAS. Hay que sacarla de la lista: una excepción "
        "que nadie revisa es donde la próxima tarea huérfana se va a esconder."
    )


# ---------------------------------------------------------------------------
# El gate mirándose al espejo
# ---------------------------------------------------------------------------
#
# Los dos tests de arriba pasan hoy porque el repo está cableado. Pasarían
# igualito si el detector estuviera roto y no encontrara nada nunca — y entonces
# no servirían para nada, que es precisamente el defecto que se está corrigiendo:
# algo que pasa los tests sin hacer su trabajo.
#
# Así que se le da de comer un repo de juguete con un campo huérfano y una tarea
# huérfana puestos a mano, y se exige que los encuentre.


def _repo_de_juguete(tmp_path: pathlib.Path) -> pathlib.Path:
    api = tmp_path / "api" / "observerrmm"
    (api / "core").mkdir(parents=True)
    (api / "observerrmm").mkdir()
    (api / "modulo").mkdir()

    (api / "core" / "models.py").write_text(
        "class CoreSettings(models.Model):\n"
        "    campo_leido = models.PositiveIntegerField(default=1)\n"
        "    campo_huerfano = models.PositiveIntegerField(default=2)\n",
        encoding="utf-8",
    )
    # Lee campo_leido y nunca campo_huerfano. La mención en prosa del huérfano es
    # deliberada: el defecto original tenía comentarios impecables, y un detector
    # que acepte un comentario como lectura no habría encontrado nada.
    (api / "modulo" / "lector.py").write_text(
        "# campo_huerfano deberia leerse aca, pero nadie lo lee\n"
        "def f(core):\n"
        "    return core.campo_leido\n",
        encoding="utf-8",
    )
    (api / "modulo" / "tasks.py").write_text(
        "@app.task\n"
        "def tarea_agendada():\n"
        "    return 'ok'\n"
        "\n"
        "@app.task\n"
        "def tarea_llamada():\n"
        "    return 'ok'\n"
        "\n"
        "@app.task\n"
        "def tarea_huerfana():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    (api / "modulo" / "vista.py").write_text(
        "from modulo.tasks import tarea_llamada\n"
        "\n"
        "def v():\n"
        "    tarea_llamada.delay()\n",
        encoding="utf-8",
    )
    (api / "observerrmm" / "celery.py").write_text(
        'app.conf.beat_schedule = {"x": {"task": "modulo.tasks.tarea_agendada"}}\n',
        encoding="utf-8",
    )
    # Sólo invoca a la huérfana: tiene que seguir contándose como huérfana.
    (api / "modulo" / "test_tasks.py").write_text(
        "from modulo.tasks import tarea_huerfana\n"
        "\n"
        "def test_x():\n"
        "    tarea_huerfana.delay()\n",
        encoding="utf-8",
    )
    return api


def test_el_detector_encuentra_un_campo_huerfano(auditor, monkeypatch, tmp_path):
    api = _repo_de_juguete(tmp_path)
    monkeypatch.setattr(auditor, "RAIZ", tmp_path)
    monkeypatch.setattr(auditor, "API", api)
    monkeypatch.setattr(auditor, "MODELO_CORE", api / "core" / "models.py")

    huerfanos = {c.nombre for c in auditor.auditar_campos() if c.huerfano}
    assert huerfanos == {"campo_huerfano"}, (
        "El detector de campos no está detectando. Mientras siga así, "
        "test_todo_campo_de_coresettings_se_lee_en_el_backend pasa por "
        f"construcción y no vale nada. Encontró: {sorted(huerfanos)}"
    )


def test_el_detector_encuentra_una_tarea_huerfana(auditor, monkeypatch, tmp_path):
    api = _repo_de_juguete(tmp_path)
    monkeypatch.setattr(auditor, "RAIZ", tmp_path)
    monkeypatch.setattr(auditor, "API", api)
    monkeypatch.setattr(auditor, "CELERY", api / "observerrmm" / "celery.py")

    huerfanas = {t.ruta for t in auditor.auditar_tareas() if t.huerfana}
    assert huerfanas == {"modulo.tasks.tarea_huerfana"}, (
        "El detector de tareas no está detectando. Encontró: "
        f"{sorted(huerfanas)}. Si trae 'modulo.tasks.tarea_agendada' no está "
        "leyendo el beat_schedule; si NO trae 'modulo.tasks.tarea_huerfana' está "
        "aceptando un llamador de los tests, que es el agujero por donde pasó "
        "`prune_erase_attachments`."
    )
