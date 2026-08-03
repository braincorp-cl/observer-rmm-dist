# Notas de release del producto

**Regla: todo release nuevo del producto DEBE traer el detalle de los cambios de la versión.**
Sin `release-notes/<tag>.md` el workflow de release **falla y no crea la release**, así que no es un
recordatorio: es un requisito.

## Cómo cortar una versión

1. Subir `ORMM_VERSION` en `api/observerrmm/observerrmm/settings.py`.
2. Agregar la entrada `## vX.Y.Z — YYYY-MM-DD` en [`CHANGELOG.md`](../CHANGELOG.md) — **el CI lo exige
   en cada push**: si `ORMM_VERSION` no tiene su entrada, falla. Ese archivo alimenta el changelog
   público (`agents.observer.cl/changelog/`) y el ancla `#vX.Y.Z` que enlaza la consola.
3. Escribir `release-notes/vX.Y.Z.md` con el cuerpo **completo** de la release (ver estructura abajo).
4. Commitear, taggear ese commit (`git tag -a vX.Y.Z`) y pushear el tag a `origin`.
5. El workflow valida las notas y crea la release de GitHub con este archivo como cuerpo.

## CHANGELOG.md vs release-notes/

No son lo mismo y por eso conviven:

| | `CHANGELOG.md` | `release-notes/<tag>.md` |
|---|---|---|
| Dónde se ve | changelog público del CDN, enlazado desde la consola | página de releases de GitHub |
| Formato | viñetas breves, una línea por cambio | cuerpo completo con secciones, contexto y enlaces |
| Alcance | todas las versiones, en un archivo | una versión por archivo |

La regla de oro: el CHANGELOG responde *"¿qué cambió?"* de un vistazo; las notas de release responden
*"¿me conviene actualizar y qué implica?"*.

## Estructura del archivo

Cuerpo completo de la release, en **español**, escrito para el **operador** (no para quien escribió el
código). La referencia de estilo es
[`v1.4.1`](https://github.com/braincorp-cl/observer-rmm-dist/releases/tag/v1.4.1):

1. Párrafo de presentación: qué tipo de versión es y qué trae en una línea.
2. `## Cambios en esta versión` — agrupado por área. Qué cambia **para quien usa el producto**. Los
   arreglos empiezan con **"Corregido"** y explican qué se veía mal antes.
3. `## Agente` — con qué versión del agente se acompaña, y enlace a sus notas.
4. `## Actualización` — qué hay que hacer para actualizar, y si hay migraciones de base de datos.
5. Pie con el enlace al README y la licencia (uso interno BrainCorp).

## Por qué existe esta carpeta

Los releases del producto se creaban **a mano**, y eso falló de las dos formas posibles: `v1.4.1`
existía como release pero **no tenía entrada en el CHANGELOG** (así que el ancla `#v1.4.1` que enlaza
la consola no resolvía), y `v1.4.2` tenía entrada en el CHANGELOG pero **no existía como release**.
Los dos huecos son ahora gates de CI en vez de pasos que hay que recordar.

Mismo criterio que en el repo del agente (`observer-agent-dist/release-notes/`).
