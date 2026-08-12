"""El URLconf tiene que sobrevivir a que alguien encienda DEBUG en caliente.

`urls.py` decidía si publicar `/silk/` mirando `settings.DEBUG`, mientras que
`settings.py` decide si silk entra a INSTALLED_APPS al importarse. Los dos
momentos son distintos, así que bastaba encender DEBUG en caliente —una prueba,
un shell— para que este módulo intentara importar un paquete que sólo está en
`requirements-dev.txt` y se cayera el URLconf ENTERO: todas las rutas del
producto, no sólo la de silk.

La CI lo destapó el 2026-08-12, cuando el sorteo de `pytest-randomly` dejó
primera a la única prueba que enciende DEBUG en caliente. Hasta ahí había sido
suerte, no corrección.
"""

import importlib

from django.urls import clear_url_caches


def test_el_urlconf_sobrevive_a_debug_encendido_en_caliente(settings):
    settings.DEBUG = True
    clear_url_caches()

    # El re-import es el camino exacto que se caía: Django reimporta el urlconf
    # cuando sus cachés se limpian, y ahí leía el DEBUG de ESTE instante.
    modulo = importlib.reload(importlib.import_module("observerrmm.urls"))

    rutas = [str(getattr(p, "pattern", "")) for p in modulo.urlpatterns]
    assert not any(r.startswith("silk/") for r in rutas), (
        "el URLconf publicó /silk/ con silk fuera de INSTALLED_APPS: "
        "vuelve a depender de DEBUG en vez del hecho real"
    )
