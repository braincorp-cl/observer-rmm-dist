# Triaje de alertas de Dependabot — rama `v2/auditoria-dependabot`

**Fecha:** 2026-11-05 · **Alcance:** `api/observerrmm/` (pip) y `web/app/` (npm) ·
**Objetivo:** separar lo que de verdad exige acción antes de publicar la 2.0.0 de lo
que es ruido de cadena de compilación.

> **Esto es un triaje, no una implementación.** No se tocó ningún manifiesto,
> lockfile ni archivo de código. No hay bumps en este commit. El único archivo
> nuevo es este informe.

---

## 0. Cómo se midió (y qué parte es inferencia)

### No hubo acceso a la API de alertas

```
GET repos/braincorp-cl/observer-rmm-dist/dependabot/alerts
→ 403 {"message":"Resource not accessible by integration"}
```

El token de esta sesión no tiene el permiso `security_events`, así que **no se
pudo leer la lista real de 172 alertas**: no hay números de alerta, ni fechas, ni
las severidades que GitHub le asignó a cada una, ni cuáles están ya descartadas.
Todo lo que sigue se reconstruyó desde los manifiestos y los lockfiles del repo.

### Lo que sí se midió con herramientas, no de memoria

Esto es importante: **el inventario de vulnerabilidades no es recuerdo del modelo,
es salida de herramienta contra los avisos publicados**, consultados hoy.

| Fuente | Comando | Qué da |
|---|---|---|
| Registro npm | `npm audit --package-lock-only` en `web/app/` | 132 pares (paquete, aviso) con severidad, rango y versión que corrige |
| Registro npm | `npm audit --package-lock-only --omit=dev` | **el corte runtime/build autoritativo**: 49 pares en el árbol de producción |
| OSV / PyPI | `pip-audit -r <manifiesto> --no-deps` ×3 | 38 avisos únicos en los tres manifiestos de `api/observerrmm/` |
| OSV / PyPI | `pip-audit` en `mcp/` y en `requirements.txt` raíz | **0 vulnerabilidades** en ambos |
| Repo | `grep` dirigido por aviso | si la ruta vulnerable tiene call site en este producto |

> **Actualización 2026-11-05 (segunda pasada):** una de las inferencias de esta lista
> quedó cerrada con medición. La compatibilidad de DRF con Django 4.2 ya no se infiere:
> está verificada contra los metadatos de PyPI y contra el resolutor de pip en **§2bis**,
> y la respuesta es **no** — `3.18.x` exige `django>=5.2`. Eso parte el ítem 1 en dos y
> sube la prioridad de la migración de Django.

### Qué parte es inferencia, marcada como tal

1. **La correspondencia con las 172 alertas.** Mi conteo da **170**. El cuadre está
   abajo (§1.1) y es bueno, pero no es la lista de GitHub: es una reconstrucción.
2. **La severidad de los 38 avisos de Python.** `api.osv.dev` está bloqueado por el
   proxy de egreso de esta sesión (`CONNECT tunnel failed, 403`), así que no pude
   traer el campo de severidad de cada aviso. Las severidades npm sí son reales
   (vienen de `npm audit`). Donde digo "alta" o "crítica" de un paquete Python es
   **mi criterio leyendo la descripción del aviso**, no la etiqueta de GitHub.
3. **`cryptography` / OpenSSL (GHSA-537c-gmf6-5ccf).** El aviso remite a
   `openssl-library.org/news/secadv/20260609.txt`, que no pude abrir y que es
   posterior a mi corte de conocimiento. Sé que *existe* y que el wheel lo arrastra;
   **no sé qué es**. Lo listo como acción por precaución, no porque lo haya evaluado.
4. **El EOL de Django 4.2** (§2, ítem 0) sale de mi conocimiento más la evidencia
   indirecta de los avisos. Es verificable en un minuto y conviene verificarlo.

### Lo que la medición corrigió del enunciado

El enunciado dice "nadie las ha mirado". Es cierto para las alertas, pero no para
Dependabot: `.github/dependabot.yml` **existe, está configurado con cuidado** (dos
grupos por ecosistema, `ignore` razonados con fecha y motivo) y
`api/observerrmm/requirements-test.txt` documenta por qué cada pin de prueba está
clavado. El comentario de ese archivo dice "Dependabot está DESACTIVADO en este
repo (medido 2026-08-06 por API)" — eso ya no es cierto, el `dependabot.yml` es
posterior y lo reactivó. También está desactualizado el comentario del
`dependabot.yml` sobre `actions/checkout@v4`: los workflows ya corren
`checkout@v7`, `setup-python@v7`, `setup-node@v7` y `setup-go@v7`.

### Dos hallazgos de configuración que mueven casi todo el triaje

Estos dos hechos son los que vacían la mayoría de los cubos. Verificados, no supuestos:

**(A) El frontend es una SPA pura, sin SSR.**
- `quasar.config.js` → `vueRouterMode: "history"`; el bloque `ssr:` es el andamiaje
  por defecto de la plantilla Quasar, todo comentado.
- **No existe `web/app/src-ssr/`**, que es requisito de `quasar build -m ssr`.
- `.github/workflows/ci.yml:277` → `npm run build` → `quasar build`, sin `-m ssr`.
- `deploy-frontend.yml` es explícito: *"Deploy solo-frontend (assets SPA + env-config.js)"*,
  `rsync` de `web/dist/` a `/var/www/observer/dist/` servido por nginx. Estático.

→ **Todo aviso que solo se dispara en el servidor SSR es inalcanzable acá**, incluida
una de las dos críticas de npm.

**(B) El backend no tiene instalado nada de lo que la mayoría de los CVE de Django necesitan.**
- `django.contrib.gis` no aparece en `INSTALLED_APPS` ni en ningún `.py` del árbol
  (`grep` de `contrib.gis|GEOSGeometry|GDALRaster|GeometryField|RasterField` → vacío).
- `MIDDLEWARE` no incluye `UpdateCacheMiddleware` ni `FetchFromCacheMiddleware`, y
  `cache_page` no se usa en ninguna parte. Hay Redis en `CACHES`, pero como caché
  programática, no como caché de vistas — y es la caché de vistas la que falla.
- `get_signed_cookie` y `DomainNameValidator`: cero call sites.
- `DEBUG = False`, `ADMIN_ENABLED = False` (así que `django.contrib.admin` no se
  carga), `AdminRenderer` no está configurado en `REST_FRAMEWORK`.

---

## 1. Resumen: en qué cubo cae cada alerta

Contado al nivel **(paquete, aviso)**, que es como cuenta Dependabot: un mismo aviso
genera una alerta por cada paquete afectado del árbol.

| Cubo | Alertas | % | Qué significa |
|---|---:|---:|---|
| **Runtime explotable** | **9** | 5 % | Llega al servidor o al bundle, y la ruta vulnerable tiene call site. **Esto es lo que hay que arreglar.** |
| **Runtime no alcanzable** | **61** | 36 % | El paquete viaja a producción, pero la función vulnerable no se usa o su precondición no se cumple. |
| **Solo desarrollo y build** | **88** | 52 % | Linters, Vite/Rollup, servidor de desarrollo, tipos, cadena de pruebas. No viaja a ningún lado. |
| **Falso positivo** | **12** | 7 % | El componente vulnerable no existe en este producto (dependencia muerta, o el aviso es sobre una pieza que no usamos). |
| **Total reconstruido** | **170** | | |

### Y dicho con las palabras que pide el enunciado

**De las 3 críticas de npm, ninguna es explotable en producción.** La crítica de
`proxy-addr` está en el servidor de desarrollo de Vite; la de `quasar` es XSS en el
renderizado SSR de meta tags, y acá no hay SSR; la de `dompurify` está en un paquete
que **nadie importa**. Las 11 críticas que reporta GitHub no son 11 problemas
críticos de este producto. Un paquete de build con CVE crítico casi nunca es
explotable en producción, y conviene decirlo así en vez de contarlo entre las críticas.

El 52 % de las alertas es cadena de compilación. Más de la mitad del tablero no
describe riesgo del producto desplegado.

### Desglose por ecosistema

| | Runtime explotable | Runtime no alcanzable | Solo build | Falso positivo | Total |
|---|---:|---:|---:|---:|---:|
| npm (`web/app/`) | 1 | 35 | 88 | 8 | **132** |
| pip (`api/observerrmm/`) | 8 | 26 | 0 | 4 | **38** |
| pip (`mcp/`) | 0 | 0 | 0 | 0 | **0** |
| pip (`requirements.txt` raíz) | 0 | 0 | 0 | 0 | **0** |
| **Total** | **9** | **61** | **88** | **12** | **170** |

### 1.1 Cuadre contra las 172 que reporta GitHub

| | Críticas | Altas | Moderadas | Bajas | Total |
|---|---:|---:|---:|---:|---:|
| Reportado por GitHub | 11 | 74 | 67 | 20 | **172** |
| npm medido (severidad real de `npm audit`) | 3 | 60 | 51 | 18 | **132** |
| pip medido (severidad **no** disponible) | — | — | — | — | **38** |
| **Medido total** | | | | | **170** |

170 contra 172: **falta un 1,2 %**. Los dos que sobran son probablemente `go.mod`
(que `dependabot.yml` cubre y yo no audité, §5) o una diferencia de conteo de
GitHub por ruta de manifiesto. El cuadre es lo bastante bueno para confiar en la
forma del tablero; no lo es para afirmar que esta lista es exactamente la de GitHub.

---

## 2. Las que SÍ exigen acción (9 alertas, 6 paquetes)

Ordenadas por lo que yo arreglaría primero.

### Ítem 0 — Lo que no es una alerta pero es el riesgo real: Django 4.2.30 está en EOL

**No va en la lista de acciones porque ninguno de sus 8 avisos es alcanzable
(§3), pero es el riesgo de seguridad más grande del backend** y conviene que quede
escrito antes de publicar una 2.0.0.

Las ocho descripciones dicen, literalmente, *"An issue was discovered in Django 5.2
before 5.2.x and 6.0 before 6.0.x"* y cierran con *"Earlier, unsupported Django
series (such as 5.0.x, 4.1.x, and 3.2.x) were not evaluated and may also be
affected."* **Ninguna versión que corrige está en la rama 4.2** — todas son 5.2.x,
6.0.x o 6.1.x. Eso no es casualidad: el soporte extendido de Django 4.2 LTS terminó
en abril de 2026 *(inferencia, ver §0)*, hace unos siete meses. La 4.2 no va a
recibir parches nunca más.

Hoy la configuración salva al producto: sin GeoDjango, sin middleware de caché, sin
`get_signed_cookie`, los ocho avisos no tienen por dónde entrar. Pero esa protección
es contingente —la primera vista que use caché de vistas vuelve a abrir tres— y el
próximo CVE de Django tampoco va a tener parche.

El repo ya lo sabe. `requirements-test.txt` y `dependabot.yml` documentan el techo
duro de `pytest-django <4.13` *"mientras los servidores corran Django 4.2 LTS"*, y
lo llaman *"parte de la migración de Django, no un bump suelto"*. Correcto. **La
migración de Django es un proyecto, y es el que de verdad mueve la aguja.**

Y hay un enganche que importa para el ítem 1: **la corrección completa de DRF exige
la migración de Django primero.** Esto ya no es inferencia — está verificado contra
los metadatos de PyPI y contra el resolutor de pip (§2bis): **DRF 3.18.x declara
`Requires-Dist: django>=5.2`**, y `pip` se niega a instalarlo junto a Django 4.2.30
con `ResolutionImpossible`. El detalle, y cómo parte la acción en dos, está en §2bis.

---

### Ítem 1 — `djangorestframework` · 3 alertas · **la prioridad real, y parte en dos**

| | |
|---|---|
| **Versión actual** | `3.15.2` (`api/observerrmm/requirements.txt`) |
| **Versión que corrige** | `3.17.2` corrige **una** de las tres · `3.18.2` corrige las tres |
| **Hasta dónde se puede llegar hoy** | **`3.17.2`, y no más.** Es la última versión que soporta Django 4.2 (§2bis). |
| **Riesgo de subir a `3.17.2`** | **Bajo-medio.** Dos menores, `django>=4.2` sin cambios, resolución limpia verificada con `pip --dry-run`. Los menores de DRF rompen cosas de vez en cuando (negociación de contenido, serializers), así que la CI es el testigo. |
| **Riesgo de subir a `3.18.2`** | **Bloqueado, no riesgoso.** `pip` lo rechaza con `ResolutionImpossible` mientras el pin sea Django 4.2.30. No es un bump: es la migración de Django. |

**Por qué importa acá.** DRF es toda la superficie de la API: `apiv3`/`apiv4` son por
donde entran los agentes, y es la única capa HTTP del producto. Las tres son
pre-autenticación y **no las tapa el throttling**: `REST_FRAMEWORK` solo define
`DEFAULT_THROTTLE_RATES` para `login` y `check_creds`, no un límite global. Un
servidor RMM expuesto a internet con agentes en endpoints es exactamente el perfil
que estos tres avisos describen.

| Aviso | Qué es | Por qué es alcanzable | Corrige |
|---|---|---|---|
| `CVE-2026-114136` (GHSA-3547-9m27-7rxg) | Nombrar un códec de compresión en el `charset` del `Content-Type` evade `DATA_UPLOAD_MAX_MEMORY_SIZE`: 108 bytes de cuerpo → 50 M de caracteres, ×466.033, +97 MiB de RSS por petición | El aviso dice *"No application configuration is required"* y *"unauthenticated attacker"*. Nada que desactivar. | **3.18.2** 🔒 |
| `CVE-2026-114138` (GHSA-33wh-fxxf-88vv) | Parseo cuadrático del header `Accept`: un GET con 780 KB de `Accept` tuvo un worker ocupado 18,87 s | La negociación de contenido corre en cada request antes de los permisos. Sin límite de tokens ni de tamaño. | **3.18.2** 🔒 |
| `PYSEC-2026-3827` (CVE-2026-73228) | `request.data` evade `DATA_UPLOAD_MAX_MEMORY_SIZE` en `application/json` y `x-www-form-urlencoded` | Todas las vistas usan `request.data`. El límite de Django está puesto y no sirve en esa ruta. | **3.17.2** ✅ |

🔒 = bloqueado tras la migración de Django · ✅ = alcanzable hoy sin tocar Django.

**Las dos peores son las bloqueadas.** Los dos DoS no autenticados —los que el aviso
describe sin necesidad de configuración y sin credenciales— se corrigen recién en
`3.18.2`, que exige Django ≥5.2. La que sí se puede cerrar hoy con `3.17.2` es la
evasión del límite de carga, que es real pero menos grave. Eso significa que
**mientras el backend siga en Django 4.2, los dos DoS pre-autenticación se quedan
abiertos, y la única mitigación disponible es de configuración, no de versión**:
límites de tamaño de cabecera y de cuerpo en nginx (`large_client_header_buffers`,
`client_max_body_size`) y throttling global en DRF, que hoy no existe (solo hay
`DEFAULT_THROTTLE_RATES` para `login` y `check_creds`). Eso es trabajo de
configuración, no un bump, y queda fuera de este triaje.

**Las otras dos de DRF no son alcanzables** y van en §3 — pero una de ellas,
`CVE-2026-114137`, es una trampa latente que conviene leer (§3, nota).

---

### §2bis — Verificación: ¿DRF 3.18.2 soporta Django 4.2? **No.**

Esta era la pregunta que el informe dejaba abierta como inferencia. Queda cerrada, y
medida dos veces: metadatos publicados y resolutor real.

**Metadatos de PyPI** (`https://pypi.org/pypi/djangorestframework/<v>/json`, consultado
2026-11-05):

| Versión | Requisito de Django | Clasificadores `Framework :: Django ::` | Publicada |
|---|---|---|---|
| `3.15.2` ← **actual** | `django>=4.2` | 4.2, 5.0 | 2024-06-19 |
| `3.16.0` | `django>=4.2` | 4.2, 5.0, 5.1, 5.2 | 2025-03-28 |
| `3.17.0` | `django>=4.2` | 4.2, 5.0, 5.1, 5.2, 6.0 | 2026-03-18 |
| `3.17.1` | `django>=4.2` | 4.2, 5.0, 5.1, 5.2, 6.0 | 2026-03-24 |
| **`3.17.2`** | **`django>=4.2`** | **4.2**, 5.0, 5.1, 5.2, 6.0 | 2026-08-05 |
| `3.18.0` | **`django>=5.2`** | 5.2, 6.0, 6.1 | 2026-08-07 |
| `3.18.1` | **`django>=5.2`** | 5.2, 6.0, 6.1 | 2026-09-07 |
| `3.18.2` | **`django>=5.2`** | 5.2, 6.0, 6.1 | 2026-10-06 |
| `3.18.3` | **`django>=5.2`** | 5.2, 6.0, 6.1 | 2026-10-06 |

**El soporte de Django 4.2 se cayó en `3.18.0`, dos días después de `3.17.2`.** Y no
hay backport: **no existe ninguna `3.17.3`**. La rama 3.17 se cerró en `3.17.2`, así
que las correcciones de `3.18.x` no van a llegar nunca a una versión compatible con
Django 4.2.

**Confirmación con el resolutor de pip** (no es lectura de metadatos, es el
comportamiento real de la instalación):

```
$ pip install --dry-run "djangorestframework==3.18.2" "django==4.2.30"
ERROR: Cannot install django==4.2.30 and djangorestframework==3.18.2
       because these package versions have conflicting dependencies.
ERROR: ResolutionImpossible

$ pip install --dry-run "djangorestframework==3.17.2" "django==4.2.30"
Would install Django-4.2.30 asgiref-3.13.0 djangorestframework-3.17.2 sqlparse-0.6.1
```

No es una incompatibilidad blanda que se pueda forzar con `--no-deps` y cruzar los
dedos: es un piso declarado en los metadatos, y `pip` se niega.

**Qué se sigue de esto, en concreto:**

1. **`3.17.2` se puede poner hoy**, sin tocar Django. Cierra `PYSEC-2026-3827` (de las
   explotables) y `PYSEC-2026-3828` (de las inalcanzables). Riesgo bajo-medio: dos
   menores, resolución limpia verificada.
2. **Los dos DoS no autenticados quedan bloqueados** tras la migración de Django, que
   es el ítem 0. Mitigación mientras tanto: límites en nginx y throttling global.
3. **La migración de Django sube de prioridad.** Antes era "deuda estructural por el
   EOL"; ahora también es la condición para cerrar las dos alertas más graves del
   backend. Y el mismo salto resuelve el techo de `pytest-django <4.13` que el repo
   ya documenta.
4. **Dato suelto útil:** el resolutor trae `sqlparse-0.6.1` por su cuenta, que es la
   versión que corrige las 6 alertas de `sqlparse` (§3.1). El pin explícito
   `sqlparse==0.5.3` lo bloquea; soltarlo, o subirlo, cierra esas 6 gratis.

---

### Ítem 2 — `urllib3` · 2 alertas · **el mejor costo/beneficio del informe**

| | |
|---|---|
| **Versión actual** | `2.7.0` |
| **Versión que corrige** | `2.8.0` |
| **Riesgo de subirla** | **Mínimo.** Un menor, drop-in. Ya está resuelta a `2.8.0` en el `requirements.txt` raíz, o sea que la combinación ya corre en la CI de esta misma sesión. |

**Por qué importa acá.** Los dos avisos son de la **API de streaming**, y el backend
la usa en dos lugares reales:

- `observerrmm/utils.py:95` — `requests.post(settings.EXE_GEN_URL, stream=True, …)`
  + `iter_content(chunk_size=1024)`: generación del instalador del agente.
- `core/utils.py:159` — `requests.get(dl_url, stream=True, timeout=15, verify=False)`
  + `iter_content(chunk_size=64*1024)`: descarga del instalador de MeshCentral.

`PYSEC-2026-4177` (CVE-2026-97689) y `PYSEC-2026-4176` (GHSA-gh4c-6fx4-qh6g) son
fallas al decodificar respuestas *chunked* y *chunked+comprimidas*. El extremo
remoto es el constructor de ejecutables y el host de MeshCentral — y en
`core/utils.py:159` va con **`verify=False`**, así que cualquiera en la ruta puede
*ser* el extremo remoto y controlar el framing de los chunks.

> **Aparte, no es alerta de Dependabot y no lo arreglé:** ese `verify=False` es un
> agujero de TLS por sí mismo, y además deja sin efecto el bundle de CA de certifi
> (ítem 4) en esa ruta. Es preexistente y está fuera del encargo. Queda nombrado.

La tercera de `urllib3` (`PYSEC-2026-4175`, separación de TLS de proxy) no es
alcanzable: no se usa `proxy_ssl_context` ni `proxy_assert_*` en ninguna parte.

---

### Ítem 3 — `msgpack` · 1 alerta

| | |
|---|---|
| **Versión actual** | `1.1.2` |
| **Versión que corrige** | `1.2.3` |
| **Riesgo de subirla** | **Bajo.** Un menor. Vale correr los tests de `agents/` y `autotasks/` porque es el códec del canal NATS. |

**Por qué importa acá.** `CVE-2026-114613` (GHSA-j586-36cw-2gc2): la extensión C
`msgpack._cmsgpack` **filtra un valor de mapa ya decodificado** cuando rechaza una
clave bajo `strict_map_key=True` (el default). Entradas malformadas repetidas →
crecimiento de memoria sin techo. Afecta a `unpackb()` y a `Unpacker`.

Call sites, todos sobre payloads que vienen de los agentes por NATS:

- `agents/models.py:987` y `:1036` — `msgpack.loads(msg.data)`
- `autotasks/tasks.py:115` — `msgpack.loads(msg.data)`

Un agente comprometido o falsificado en un endpoint puede empujar al proceso de API
o al worker a consumir memoria sin límite. En un RMM el agente **es** la superficie
de ataque que importa: corre en máquinas de clientes que uno no controla.

La otra de `msgpack` no es alcanzable: `PYSEC-2026-3625` (SEGV) necesita **reusar**
un `Unpacker` tras un error, y el workaround oficial es *"create a new Unpacker"*.
Acá solo se llama `msgpack.loads()`, que crea uno nuevo en cada invocación — no hay
ningún `Unpacker(` en el árbol. Ya estamos en el workaround sin saberlo.

---

### Ítem 4 — `certifi` · 1 alerta · **el más barato de todos**

| | |
|---|---|
| **Versión actual** | `2026.4.22` |
| **Versión que corrige** | `2026.10.19` o posterior (**no la `.18`**, ver abajo) |
| **Riesgo de subirla** | **Casi nulo.** Es un bundle de certificados: datos, no código. El `requirements.txt` raíz ya resuelve a `2026.10.23`. |

**Por qué importa acá.** `PYSEC-2026-4320` (GHSA-6q48-6c7w-9gw2): el bundle incluye
`emSign ECC Root CA - G3`, y **ocho intermedias de eMudhra que encadenan a esa raíz
tienen la clave privada comprometida**. Quien tenga una de esas claves emite
certificados válidos para cualquier hostname; si además está en la ruta, intercepta
o modifica el tráfico TLS.

El backend hace HTTPS de salida con `requests` —que usa certifi por defecto— hacia
Twilio, MeshCentral y el constructor de ejecutables. Esto no es teórico: son claves
revocadas y en circulación.

**Detalle que importa al elegir la versión:** la `2026.10.18` sacó *todas* las raíces
emSign y la `2026.10.19` **restauró las que no están afectadas**. Saltar a `.18`
puede romper verificaciones legítimas. Ir a `2026.10.19+`.

---

### Ítem 5 — `cryptography` · 1 alerta · **marcada como inferencia**

| | |
|---|---|
| **Versión actual** | `46.0.7` |
| **Versión que corrige** | `48.0.1` para esta; `50.0.0` si se quisieran cubrir las otras tres (inalcanzables) |
| **Riesgo de subirla** | **Medio.** 46 → 48 son dos mayores. Los mayores de `cryptography` suelen ser mecánicos, pero retiran APIs deprecadas y mueven el piso de Python/OpenSSL. Toca `agents/lostmode_crypto.py`, `erase/signing.py`, `observerrmm/helpers.py`, `core/views.py`. El `requirements.txt` raíz ya resuelve a `50.0.2`, lo que sugiere que el árbol tolera la rama 50. |

**Por qué importa acá.** `GHSA-537c-gmf6-5ccf` es el único de los cuatro que **no
depende de qué API llames**: los wheels de `cryptography` traen **OpenSSL enlazado
estáticamente**, y los anteriores a 48.0.1 traen una versión vulnerable. El
despliegue instala desde wheel. Si el wheel es vulnerable, el proceso es vulnerable,
y no hay `grep` que lo descarte.

**Lo que no sé:** el aviso remite a `openssl-library.org/news/secadv/20260609.txt`,
que no pude abrir (proxy) y que es posterior a mi corte. **No sé qué es la falla de
OpenSSL ni si su ruta se alcanza acá.** Lo pongo en la lista de acción porque es la
única de las cuatro que no pude descartar, no porque la haya evaluado. Antes de
gastar dos mayores en esto, **leer ese aviso**: puede subir a prioridad 1 o bajar a §3.

Las otras tres sí se descartan con confianza y van en §3.

---

### Ítem 6 — `quasar` · 1 alerta de 4 · bump recomendado por conveniencia, no por urgencia

| | |
|---|---|
| **Versión actual** | `2.18.5` |
| **Versión que corrige** | `2.35.2` — **`isSemVerMajor: false`**, lo confirma `npm audit` |
| **Riesgo de subirla** | **Medio, y no por semver.** Son 17 menores de un framework de UI. No rompe la API, pero mueve estilos y comportamiento de componentes, y este árbol está en plena ola de rediseño (`ui-v2`, ADR-027). **El riesgo es de regresión visual, no de API.** `dependabot.yml` solo ignora el **mayor** de `quasar`, así que este bump ya está permitido por la configuración. |

**Por qué importa acá — y por qué es solo una de las cuatro.** La única con call site
es la moderada: `GHSA-3r53-75j5-3g7j`, contaminación de prototipo en la utilidad
`extend()`, rango `<=2.21.4`, y `2.18.5` cae dentro. Uso real en
`src/components/modals/coresettings/URLActionsForm.vue:159`:

```ts
const localAction: URLAction = props.action ? reactive(extend({}, props.action)) : …
```

`props.action` es una URL Action que viene del backend. La llamada es **superficial**
(sin `true` como primer argumento), lo que limita bastante el daño, y el objeto lo
crean administradores. Es un caso flojo: lo listo porque existe, no porque me
preocupe. **Si el bump de 17 menores asusta más que esta moderada —y es defendible
que sí—, posponerlo es una decisión razonable.** Lo que no se puede es contar la
crítica de `quasar` como motivo para apurarlo:

**La crítica de `quasar` NO es alcanzable.** `GHSA-pq96-jpmf-w254` es XSS almacenado
o reflejado *"via unescaped SSR meta tag rendering in `getHead()`"*. Requiere el
servidor SSR. Acá no hay SSR (§0.A). Lo mismo la alta `GHSA-68jq-fhch-4xq4`, ReDoS
de `User-Agent` que *"lets one request stall a Quasar SSR server"* — no hay servidor
Quasar que estancar, hay nginx sirviendo archivos. La baja `GHSA-89vp-x45c-52cq`
(DOM clobbering en `openURL()` con SafariViewController) necesita DOM controlado por
el atacante, lo que ya sería XSS; `openURL()` se usa bastante, pero siempre con URLs
de core settings y preferencias.

---

## 3. Las que se pueden ignorar

### 3.1 Runtime no alcanzable — 61 alertas

El paquete sí viaja a producción. La función vulnerable no se usa, o su precondición
no se cumple.

#### Backend — 26 alertas

| Paquete | Alertas | Por qué se ignora |
|---|---:|---|
| `django` 4.2.30 | **8** | Tres son de GeoDjango (`GEOSGeometry` WKT, `GDALRaster`, lookups espaciales) y `django.contrib.gis` no está en `INSTALLED_APPS` ni se importa en ningún `.py`. Tres son del middleware de caché de vistas (`has_vary_header`, `UpdateCacheMiddleware`, `cache_page`) y ese middleware no está en `MIDDLEWARE` ni se usa el decorador. Una es `get_signed_cookie`, cero call sites. Una es `DomainNameValidator`, cero call sites, y el propio aviso dice *"Django itself is unaffected because HttpResponse prohibits newlines in HTTP headers"*. **Inalcanzables hoy — pero leer el ítem 0: la rama 4.2 está en EOL y ninguna corrección va a llegar.** |
| `sqlparse` 0.5.3 | **6** | Las seis son DoS o generación de código sobre **SQL que provee quien llama** (ReDoS en literales con `$$`, statements de solo comentario, `ReindentFilter`, modos de salida Python/PHP). `sqlparse` no se importa en ningún archivo del proyecto: solo llega como dependencia de Django, que lo usa para `sqlmigrate` y para formatear SQL en depuración. No existe ruta donde un atacante entregue texto SQL a un formateador, y `DEBUG = False`. `django-silk` —que sí formatea SQL— solo se carga con `DEBUG and not DEMO`. El bump a 0.6.0 es barato y conviene arrastrarlo cuando se toque el archivo, pero no justifica un PR propio. |
| `cryptography` 46.0.7 | **3** | Las tres necesitan APIs que el repo no usa. `PYSEC-2026-3554` (SAN comodín escapa de un name constraint) y `PYSEC-2026-3553` (blowup exponencial resolviendo cadenas) son de la **API de validación de rutas X.509** (`PolicyBuilder`, `verify_directly_issued_by`); acá solo hay `x509.load_pem_x509_certificate()` en `observerrmm/helpers.py:137` y `core/views.py:706,770`, que parsea, no valida cadenas. `PYSEC-2026-3552` (Bleichenbacher en `pkcs7_decrypt_*`) no tiene call site: el uso es Fernet, firma y verificación RSA, carga de claves PEM. La cuarta sí es acción (ítem 5). |
| `django-allauth` 65.2.0 | **3** | `INSTALLED_APPS` trae **solo** `allauth.socialaccount.providers.openid_connect`. `PYSEC-2025-111` es específico de los proveedores **Okta y NetIQ** (usaban `preferred_username` como identificador): no instalados. `PYSEC-2025-110` es del **IdP** de allauth (tokens que sobreviven a `is_active=False`): `allauth.idp` no está instalado — sí está `allauth.headless`, que es otra cosa. `PYSEC-2026-56` (redirección abierta) exige **SSO SAML iniciado por el IdP**, que el propio aviso dice que viene desactivado por defecto, y el proveedor SAML no está instalado. OIDC genérico sí corre en producción vía `ee.sso`, así que allauth es código runtime: simplemente no las partes vulnerables. El salto a 65.14.1 es un parche dentro de 65.x — gratis, arrastrarlo cuando se toque el archivo. |
| `djangorestframework` 3.15.2 | **2** | `PYSEC-2026-3828` es de `AdminRenderer`, que no está en `REST_FRAMEWORK` (no hay `DEFAULT_RENDERER_CLASSES`, y `AdminRenderer` no es un default de DRF). `CVE-2026-114137` — ver la nota abajo. Las otras tres son el ítem 1. |
| `weasyprint` 66.0 | **2** | `PYSEC-2026-3412` (inyección de CSS, **sin versión que corrija**) exige `presentational_hints=True`; la llamada en `ee/reporting/utils.py:109` es `HTML(string=html).write_pdf(stylesheets=[…], font_config=…)` y no lo pasa, así que queda en `False`. Suerte, porque no hay parche. `PYSEC-2026-4311` (EPS → Pillow → Ghostscript → RCE) exige **Ghostscript instalado en el host**, y ningún rol de Ansible lo instala (`grep ghostscript|libgs|gs-` sobre `roles/`, `install.yml`, `deploy-api.yml` → vacío). **Verificar en el inventario real**: si alguna otra cosa trajo `gs`, esta sube a acción. Las otras dos son falso positivo (§3.3). |
| `urllib3` 2.7.0 | **1** | `PYSEC-2026-4175` separa la configuración TLS del proxy de la del destino. No se usa `proxy_ssl_context`, `proxy_assert_hostname` ni `proxy_assert_fingerprint`. Las otras dos son el ítem 2. |
| `msgpack` 1.1.2 | **1** | `PYSEC-2026-3625` (SEGV) exige reusar un `Unpacker` tras un error; solo se usa `msgpack.loads()`, que crea uno nuevo por llamada. No hay `Unpacker(` en el árbol. La otra es el ítem 3. |

> **Nota sobre `CVE-2026-114137` (DRF `TokenProxy`) — inalcanzable hoy, trampa mañana.**
> El aviso: borrar un token con `.delete()` sobre un `TokenProxy` **no borra nada**,
> no lanza excepción, reporta éxito, y el token sigue autenticando.
>
> Acá no es alcanzable, por dos razones verificadas: **no existe ningún call site que
> borre un Token** (`grep` de `.delete()` sobre tokens → vacío), y `django.contrib.admin`
> —que es donde DRF registra `TokenProxy`— no se carga, porque `ADMIN_ENABLED = False`.
>
> Pero vale saberlo, porque la premisa está armada: `apiv3/views.py` autentica a los
> agentes con `rest_framework.authentication.TokenAuthentication` sobre
> `rest_framework.authtoken.models.Token` (creados en `apiv3/views.py:664`), no con
> knox — knox es la autenticación de los operadores. O sea que **los tokens de agente
> son tokens de DRF y hoy no se revocan nunca**. El día que alguien escriba la
> revocación usando el modelo proxy, va a fallar en silencio y a dejar vivos tokens
> de agente que cree revocados. En un RMM eso es grave. No es una alerta que haya
> que atender: es una línea para el backlog.

#### Frontend — 35 alertas

| Paquete | Alertas | Por qué se ignora |
|---|---:|---|
| `axios` 1.17.0 | **22** | Es el único cliente HTTP de la UI y corre **en el navegador**. La mayoría de los 22 son del **adaptador Node**: `proxy` heredado tras clonar interceptores, HTTP/2 (`ClientHttp2Session`, bypass de DNS y proxy), `createConnection` heredado, ReDoS en `fromDataURI` que *"freezes the Node event loop"*, `NO_PROXY` y CIDR. En un bundle de navegador ese adaptador no existe. De los que sí podrían tocar al navegador, varios son **"gadgets" de contaminación de prototipo**: necesitan que algo *más* aporte la primitiva de contaminación, y no la aporta nadie. Los de `formDataToJSON` / `toFormData` no tienen call site (`grep` de `formToJSON|toFormData|maxRedirects|maxBodyLength|proxy:` sobre `src/` → vacío). **Juicio, no prueba:** no demostré ruta alcanzable para ninguno de los 22, y por eso van acá; pero la corrección es `1.21.0`, **`isSemVerMajor: false`**, un bump de parche sobre el cliente HTTP de toda la app. Si se abre un PR de frontend por cualquier motivo, este es el que yo metería primero — barato, central, sin excusa para no hacerlo. |
| `vue-i18n` 9.14.5 + `@intlify/core-base` + `@intlify/shared` | **5** | Un mismo par de avisos contado en tres paquetes. `GHSA-83rm-6c8r-g728` (alta) y `GHSA-8rc2-428q-7ww3` (baja) son ambos sobre **`escapeParameter`**: que no escapa vía `srcdoc`, y que no escapa valores nombrados cuando la llamada también pasa una lista. **`escapeParameter` no está activado**: `src/boot/i18n.ts:36` configura `createI18n({ legacy: false, globalInjection: true, … })` y nada más. Nunca se dependió de esa mitigación. Y la ruta no se cierra sola: los 9 `v-html` del árbol reciben `opt.label` de arreglos de opciones estáticos construidos con `t("clave")` sin parámetros interpolados (`ScheduleForm.vue:314-327`, `AutomatedTaskForm.vue`, `ObserverDropdown.vue:38`); los `srcdoc` están en las vistas de reporting (`ReportView.vue:12`, `ReportHistoryView.vue:12`, `ReportTemplatePreview.vue:15`) y reciben HTML de reporte que viene de la API, **no mensajes de traducción**. No hay confluencia entre el sink y la fuente. **Y acá la corrección sí es cara:** `npm audit` da `11.4.18` con **`isSemVerMajor: true`** — un salto de 9 a 11, que es migración, no bump. Postergarlo es lo correcto. |
| `quasar` 2.18.5 | **3** | La crítica (`getHead()` SSR) y la alta (ReDoS SSR de `User-Agent`) exigen el servidor SSR, que no existe (§0.A). La baja es DOM clobbering en `openURL()`. Detalle en el ítem 6. |
| `follow-redirects` 1.16.0 | **3** | Las tres son fugas de credenciales siguiendo redirecciones entre orígenes. Solo entra por `axios` (adaptador **Node**) y por `http-proxy` (servidor de desarrollo). El bundle del navegador no la incluye: redirecciones y cabeceras las maneja el navegador. |
| `@vue/server-renderer` 3.5.22 | **1** | `GHSA-g2v6-rqmx-r4w6`, XSS por falta de CR en la lista negra de nombres de atributo, es **solo del renderizador de servidor**. Llega al árbol de producción porque `vue` lo declara como dependencia, no porque se use. Sin SSR, no se importa ni se empaqueta. La corrección (`vue` `3.5.44`) es **`isSemVerMajor: false`**, un parche: gratis, arrastrarlo. |
| `form-data` 4.0.5 | **1** | Inyección de CRLF en nombres de campo y de archivo multipart. Solo entra por el adaptador Node de `axios`. En el navegador, los multipart los arma `FormData` nativo. |

### 3.2 Solo desarrollo y build — 88 alertas

Ninguna viaja al servidor ni al bundle. **Es el 52 % del tablero.**

**83 alertas: dependencias de desarrollo del frontend** (`"dev": true` en el
lockfile, confirmado por `npm audit --omit=dev`). 601 de los 731 paquetes del
lockfile son dev-only. Incluye **1 crítica, 38 altas, 33 moderadas y 11 bajas**:

- **La crítica es `proxy-addr`** (suplantación de IP por subred de confianza IPv4
  mapeada en IPv6), que llega por la cadena Express del servidor de desarrollo de
  Quasar. **Ese servidor no existe en producción** — producción es nginx sirviendo
  `/var/www/observer/dist`. Esta es exactamente la alerta que el enunciado describe:
  CVE crítico en paquete de build, no explotable en producción.
- `vite`, `rollup`, `esbuild`, `serialize-javascript`, `browserslist`,
  `baseline-browser-mapping`: cadena de compilación. Varias son literalmente del
  servidor de desarrollo (*"any website to send any requests to the development
  server"*, `server.fs.deny` evadible con `?import&raw`).
- `@quasar/app-vite`, `@quasar/cli`, `@quasar/render-ssr-error`,
  `@quasar/ssl-certificate`: las altas son claves TLS **de desarrollo** con permisos
  laxos y la página de error **de desarrollo** SSR/SSG filtrando el entorno. Ni
  desarrollo ni SSR son producción acá.
- `eslint`/`@typescript-eslint/*`/`@intlify/eslint-plugin-vue-i18n`: linters.
- `body-parser`, `compression`, `qs`, `http-proxy-middleware`, `node-forge`,
  `js-yaml`, `immutable`, `brace-expansion`, `minimatch`, `glob`, `fast-uri`,
  `postcss-selector-parser`, `@vitejs/plugin-vue`: transitivas de las anteriores.

> `dependabot.yml` ignora el mayor de `eslint` y del stack de lint con el argumento
> de que *"el salto de eslint 8 → 9 es la migración a flat config"* y *"un PR
> permanentemente rojo no es una señal, es ruido"*. Visto el triaje, **ese ignore
> está bien puesto**: es ruido de build, no riesgo de producto.

**5 alertas: `postcss`, `nanoid`, `source-map-js` — build disfrazado de runtime.**
Estas tres **aparecen en el árbol de producción** de `npm audit --omit=dev`, y es
justo el caso que hay que mirar dos veces en vez de contarlo como runtime. Están ahí
porque `vue` declara `@vue/compiler-sfc` como dependencia (el compilador de
plantillas en runtime), y de ahí bajan `postcss` → `nanoid`, y `source-map-js`.
**En un build de Vite las plantillas se precompilan**, y `@vue/compiler-sfc` no entra
al bundle del navegador. Y los avisos son de máquina de build: travesía de rutas por
`sourceMappingURL` que lee archivos `.map` arbitrarios, bucle infinito de `nanoid`
con tamaño negativo, DoS de `source-map-js` por offsets de secciones indexadas. Nada
de eso ocurre en el navegador del operador. **Clasificación: solo build**, pese a la
etiqueta `prod` del lockfile.

### 3.3 Falso positivo — 12 alertas

El componente vulnerable **no existe** en este producto.

| Paquete | Alertas | Por qué |
|---|---:|---|
| `dompurify` 3.4.8 | **8** (1 crítica, 1 alta, 2 moderadas, 4 bajas) | **Está declarado en `dependencies` de `package.json` y no se importa en ninguna parte.** `grep -rni dompurify` sobre todo `web/app/` excluyendo `node_modules` y el lockfile devuelve **una sola línea: la del propio `package.json`**. Cero `import`, cero uso, y en el lockfile lo requiere únicamente `<root>` — ningún otro paquete depende de él. Vite lo elimina por tree-shaking: **no viaja al bundle**. La crítica `GHSA-cg2g-xh64-v4q7` (evasión de `SAFE_FOR_TEMPLATES` en shadow roots) es una de las dos críticas de npm del tablero, y describe una función que este producto nunca llama. Además ninguna de las ocho tiene precondición activada: no se usa `setConfig`, `addHook`, `IN_PLACE`, `RETURN_TRUSTED_TYPE` ni `CUSTOM_ELEMENT_HANDLING`. **La corrección más limpia no es subir a 3.4.17: es borrar la línea 25 del `package.json`.** Eso cierra 8 alertas, incluida una crítica, sin tocar una sola línea de código de la aplicación. Es el cambio de mejor relación beneficio/riesgo del informe entero — y por eso lo dejo recomendado y no hecho (§4). |
| `weasyprint` 66.0 | **2** | `PYSEC-2026-2034` (SSRF) y `PYSEC-2026-3940` son ambos **evasiones de un `url_fetcher` personalizado restrictivo**. En `ee/reporting/utils.py:109` **no se pasa ningún `url_fetcher`**, así que no hay restricción que evadir: la precondición del aviso no se cumple. `PYSEC-2026-3940` encima exige `xmp_metadata=[url]` o adjuntos, y la llamada solo pasa `stylesheets` y `font_config`. **Aparte, y esto sí es real pero no es este CVE:** al no haber `url_fetcher`, WeasyPrint usa el fetcher por defecto, que descarga cualquier URL del HTML del reporte — incluidos `localhost` y endpoints de metadatos de nube. **Eso es exposición a SSRF por diseño, presente en toda versión, y ningún bump la arregla.** Se arregla pasando un `url_fetcher` restrictivo. Queda nombrado como deuda de diseño, fuera del encargo. |
| `black` 26.5.1 | **2** (una por manifiesto: `requirements-dev.txt` y `requirements-test.txt`) | `CVE-2026-114134` es sobre **la GitHub Action que Black trae incluida**, y solo cuando se la invoca con `use_pyproject: true`: entonces lee `tool.black.required-version` sin validar y ejecuta código no confiable. Acá **no se usa esa Action**. `ci.yml:235` corre el binario instalado por pip: `black --exclude migrations/ --check --diff observerrmm`. Los `uses:` de todos los workflows son `actions/checkout@v7`, `actions/setup-{go,node,python}@v7` y `softprops/action-gh-release@v3` — ninguno es `psf/black`. Y no existe ninguna clave `required-version` en ningún `.toml` del repo. El componente vulnerable no se ejecuta nunca. (Aun si se usara: `black` es formateador, solo build.) |

---

## 4. Qué elegí NO hacer, y por qué

1. **No subí ninguna dependencia, ni toqué `package.json`, `package-lock.json`,
   `requirements*.txt` ni código.** Es la restricción explícita del encargo. Incluye
   los casos donde la corrección es trivial y me costaba no hacerla: borrar la línea
   `"dompurify": "3.4.8"` cierra 8 alertas y una crítica sin riesgo, y `certifi` es
   un cambio de datos. **Siguen sin hacer.** Van recomendados, no aplicados.

2. **No abrí PR.** No se pidió. El commit queda en `v2/auditoria-dependabot`.

3. **No cerré ni descarté alertas en GitHub.** Sin permiso de `security_events` no
   podría, y tampoco correspondería: descartar una alerta es una decisión del equipo,
   y este documento es el insumo para tomarla, no la decisión.

4. **No audité `go.mod` ni `github-actions`,** aunque `dependabot.yml` los cubre. El
   encargo delimita `api/` y `web/app/`. Para registro: `go.mod` declara 9 módulos
   (`nats.go` 1.52.0, `sqlx` 1.4.0, `lib/pq` 1.12.3, `ugorji/go/codec` 1.3.1,
   `logrus` 1.9.4, `golang.org/x/crypto` 0.49.0, …) y es el binario `nats-api`, que
   el propio `dependabot.yml` marca como seguro de subir porque **no comparte el
   toolchain clavado del agente** (ADR-023 / Win7). Los workflows ya están en `@v7`.
   **Ahí pueden estar las 2 alertas que me faltan para llegar a 172** (§1.1).
   `govulncheck` no está instalado y no lo instalé por no ensanchar el encargo.

5. **No corrí los tests ni el linter, y por lo tanto no reporto fallas preexistentes.**
   Un triaje sin cambios de código no puede romper nada, así que correrlos no
   aportaba evidencia. **No afirmo que la CI esté verde ni roja: no la medí.** Lo que
   sí queda registrado del propio repo es que `pytest-django` tiene un techo duro en
   `4.12.x` mientras los servidores corran Django 4.2 LTS —`4.13.0` rompe 232 tests
   con marca `django_db`—, y que `dependabot.yml` lo ignora a propósito. Eso es
   preexistente, está bien documentado y **no lo toqué**.

6. **No instalé `govulncheck` ni fui a buscar los avisos que el proxy bloquea.**
   `api.osv.dev` está bloqueado por la política de egreso de esta sesión, y de ahí
   salen los dos huecos que dejo marcados como inferencia: las severidades de los 38
   avisos de Python, y el contenido del aviso de OpenSSL del ítem 5. Preferí dejarlos
   señalados como huecos antes que rellenarlos de memoria.

7. **No toqué nada fuera de `TRIAJE-DEPENDABOT.md`,** por las sesiones hermanas que
   trabajan en paralelo. `git status` antes de empezar estaba limpio sobre
   `fb59a20`.

8. **No reescribí `dependabot.yml`.** Está mejor pensado que la mayoría de los que
   he visto y sus `ignore` resisten este triaje. Lo único que detecté es cosmético y
   lo dejo dicho sin arreglarlo: el comentario de cabecera dice que Dependabot está
   desactivado (ya no lo está) y que `checkout` va en `@v4` (ya va en `@v7`). Ajustar
   comentarios no es triaje.

---

## 5. Si solo se van a hacer tres cosas antes de la 2.0.0

1. **`djangorestframework` → `3.17.2`, y abrir la migración de Django como proyecto**
   (ítem 1 + §2bis + ítem 0). La pregunta que este informe dejaba abierta ya está
   contestada: **DRF 3.18.2 no soporta Django 4.2** (`django>=5.2`, y `pip` lo
   rechaza). Así que `3.17.2` es el techo de hoy y cierra una de las tres; **los dos
   DoS no autenticados quedan bloqueados tras la migración de Django**, y mientras
   tanto se mitigan en nginx y con throttling global, no con un bump. Eso hay que
   saberlo **antes** de poner fecha a la 2.0.0, no después: si la 2.0.0 sale sobre
   Django 4.2, sale con esas dos abiertas y conviene que sea una decisión escrita y
   no un descubrimiento.
2. **`certifi` → `2026.10.19+` y `urllib3` → `2.8.0`** (ítems 4 y 2). Claves de CA
   comprometidas y dos fallas de streaming con call sites reales, a cambio de un
   bump de datos y un menor drop-in que la CI de esta sesión ya resolvió por su
   cuenta. No hay argumento para no hacerlo.
3. **Borrar `dompurify` del `package.json`** (§3.3). Ocho alertas, una de ellas
   crítica, cerradas borrando una línea de una dependencia que nadie importa.

Y una cuarta que no es un bump: **`msgpack` → `1.2.3`** (ítem 3). Es la única de las
nueve donde el vector es el agente, y en un RMM el agente es la superficie que
importa.
