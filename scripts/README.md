# scripts/

Herramientas de desarrollo y de CI. No se despliegan: no son parte del producto
ni del agente.

## `auditar_cableado_declarado.py`

Busca **funcionalidad declarada y no construida**: campos de `CoreSettings` que
ningún código lee y tareas Celery que nadie invoca.

```bash
python3 scripts/auditar_cableado_declarado.py            # informe completo
python3 scripts/auditar_cableado_declarado.py --resumen  # solo lo huerfano
```

Devuelve 0 si no encontró nada y 1 si encontró algo, así que sirve igual desde un
Makefile o un hook.

### Por qué existe

El 2026-10-29 se descubrió que `CoreSettings.erase_attachment_retention_days`
existía, se podía configurar por la API, devolvía 200 y **ninguna línea del
código lo leía**. En paralelo, la tarea que debía usarlo,
`prune_erase_attachments`, no estaba agendada en ninguna parte: el único `grep`
del nombre en todo el repo era su propio `def`.

Durante dos incrementos no caducó un solo adjunto del módulo de borrado, mientras
la política de uso aceptable publicada afirmaba por escrito que caducaban.

Lo que hay que explicar no es que el defecto existiera, sino por qué **nada lo
puso rojo**:

- El **campo** pasaba porque `CoreSettingsSerializer` declara
  `fields = "__all__"`. El serializer expone cualquier campo nuevo sin
  mencionarlo, así que el round-trip `PUT`/`GET` devuelve 200 tanto si el valor
  gobierna algo como si no gobierna nada. Aparecer en la API no es evidencia de
  nada, y es precisamente lo que enmascaró el defecto.
- La **tarea** pasaba porque sus tests la llamaban directamente. Un test que
  invoca la tarea prueba que la tarea funciona, no que alguien la invoque. Lo
  único que en producción nunca ocurría era justo lo que ningún test miraba.

Las dos mitades tenían buenos docstrings y citaban la norma correcta. Un campo
sin ninguna lectura, o una tarea sin ningún llamador, es funcionalidad declarada
y no construida: pasa los tests y no hace nada.

### Las dos reglas

1. **Todo campo de `CoreSettings` necesita al menos una lectura en Python de
   producción.** No cuentan las migraciones (son historia, no lectores), ni los
   tests, ni la mención en un comentario, ni aparecer en la API, ni estar en el
   formulario de la consola. Un campo que el backend lee sólo para devolverlo a
   la consola (por ejemplo `date_format`, que viaja como `default_date_format` en
   `dashinfo`) sí pasa: hay código que lo lee y algo cambia al cambiarlo.
2. **Toda `@app.task` necesita un llamador de producción**: una entrada del
   `beat_schedule`, un `.delay()`/`.apply_async()`/`.s()`, o otra tarea. Un
   llamador que sólo vive en los tests no cuenta.

Para una poda o un mantenimiento periódico nuevo, el molde del producto es
colgarlo de `core.tasks.core_maintenance_tasks`, que el beat corre cada hora, en
vez de agregar una entrada propia al `beat_schedule`.

### El gate

`api/observerrmm/core/test_cableado_declarado.py` importa este script y corre con
el resto de `pytest`, así que las dos reglas son obligatorias en CI. El gate
importa la lógica en vez de duplicarla para que el informe y la CI no puedan
discrepar.

Ese archivo incluye además dos tests que le dan al detector un repo de juguete
con un campo huérfano y una tarea huérfana puestos a mano, y exigen que los
encuentre. Sin eso, los dos tests principales pasarían igual si el detector
estuviera roto — que es el mismo defecto que se está corrigiendo: algo que pasa
los tests sin hacer su trabajo.

Las tareas huérfanas que se aceptan a sabiendas viven en `HUERFANAS_CONOCIDAS`,
**en este script**, cada una con el motivo escrito al lado; el gate la importa de
acá en vez de tener su propia copia, para que el informe y la CI no puedan
discrepar sobre qué deuda se está tolerando. La lista se compara por
**igualdad**: si alguien cablea o borra una de ellas, el gate obliga a sacarla.
Una lista que sólo crece se convierte en el lugar donde el defecto se esconde con
permiso.

Por eso el script sale 0 hoy, con dos huérfanas en pie: lo que lo pone en 1 es
una huérfana **nueva**, un campo sin lectura, o una entrada de
`HUERFANAS_CONOCIDAS` que ya dejó de hacer falta.

### Límite conocido

El análisis es estático y por nombre, así que falla **en una sola dirección**:
cuando un campo de `CoreSettings` se llama igual que un campo de otro modelo —hoy
`date_format` (`accounts.User`), `erase_attachment_retention_days`,
`alert_template`, `workstation_policy` y `server_policy` (`clients`/`agents`)—,
las lecturas del homónimo se cuentan como lecturas del campo global. Lo mismo
entre una tarea y una función normal del mismo nombre, hoy
`expire_stale_retrieval_orders` y `run_win_task`; por eso la resolución de tareas
mira de qué módulo viene el símbolo en cada archivo, que es lo que evitaba este
error.

El error posible, entonces, es dejar pasar algo huérfano, nunca acusar de huérfano
algo que se usa. La asimetría es deliberada: un gate que grita en falso se
termina desactivando, y el día que se desactiva deja de encontrar el defecto real.

## `verificar_biblioteca_scripts.py`

Gate de portabilidad de la biblioteca de scripts del producto (solo ASCII en el
contenido, nada de comparar contra texto que Windows traduce). Lo corre
`.github/workflows/scripts-library-portable.yml`.

## `build_changelog.py`

Genera el changelog publico (HTML autocontenido) desde `CHANGELOG.md`, que
`publish-changelog.yml` sube por WebDAV.
